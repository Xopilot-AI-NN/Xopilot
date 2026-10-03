"""Strict, one-time conversion of the pinned Miku RVC checkpoint to ONNX.

PyTorch is an installer dependency only. The live voice uses ONNX Runtime.
"""

import hashlib
import json
from pathlib import Path


def export_miku(checkpoint, destination):
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from .models import SynthesizerTrnMs768NSFsid
    from .attention_export import patch_attention_for_onnx

    torch.set_num_threads(2)
    checkpoint, destination = Path(checkpoint), Path(destination)
    # Never execute a downloaded pickle. Only tensors and primitive containers.
    data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if data.get("version") != "v2" or data.get("f0") != 1:
        raise ValueError("Miku requires an RVC v2 model with F0.")
    config = list(data["config"])
    config[-3] = data["weight"]["emb_g.weight"].shape[0]
    model = SynthesizerTrnMs768NSFsid(*config, is_half=False)
    del model.enc_q  # Training-only posterior encoder, absent from inference weights.
    model.load_state_dict(data["weight"], strict=True)
    model.eval()
    model.remove_weight_norm()
    patch_attention_for_onnx()

    class Wrapper(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.model = model

        def forward(self, phone, lengths, pitch, nsff0, sid, noise, source_noise):
            self.model.dec.m_source.l_sin_gen.external_noise = source_noise
            g = self.model.emb_g(sid).unsqueeze(-1)
            m, logs, mask = self.model.enc_p(phone, pitch, lengths)
            z = (m + torch.exp(logs) * noise * 0.66666) * mask
            z = self.model.flow(z, mask, g=g, reverse=True)
            return self.model.dec(z * mask, nsff0, g=g)

    wrapper = Wrapper().eval()
    hop = model.dec.upp
    names = ["phone", "lengths", "pitch", "nsff0", "sid", "noise", "source_noise"]
    rng = np.random.default_rng(3939)

    def inputs(frames):
        return {
            "phone": rng.standard_normal((1, frames, 768)).astype(np.float32) * 0.1,
            "lengths": np.array([frames], dtype=np.int64),
            "pitch": np.full((1, frames), 125, dtype=np.int64),
            "nsff0": np.linspace(190, 270, frames, dtype=np.float32)[None],
            "sid": np.array([0], dtype=np.int64),
            "noise": rng.standard_normal((1, config[2], frames)).astype(np.float32),
            "source_noise": rng.standard_normal((1, frames * hop, 1)).astype(np.float32),
        }

    sample = inputs(50)
    with torch.no_grad():
        torch.onnx.export(
            wrapper, tuple(torch.from_numpy(sample[key]) for key in names), str(destination),
            input_names=names, output_names=["audio"], opset_version=17,
            dynamo=False, do_constant_folding=True,
            dynamic_axes={"phone": {1: "frames"}, "pitch": {1: "frames"},
                          "nsff0": {1: "frames"}, "noise": {2: "frames"},
                          "source_noise": {1: "samples"}, "audio": {2: "samples"}},
        )
    onnx.checker.check_model(str(destination))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(destination), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    parity = []
    for frames in (37, 83, 140):
        feed = inputs(frames)
        with torch.no_grad():
            expected = wrapper(*(torch.from_numpy(feed[key]) for key in names)).numpy()
        actual = session.run(None, feed)[0]
        error = np.abs(actual - expected)
        if actual.shape != (1, 1, frames * hop) or not np.isfinite(actual).all():
            raise RuntimeError("Invalid exported Miku waveform.")
        # The input tensors and random excitation are identical in both runtimes.
        if float(error.mean()) > 0.0005 or float(error.max()) > 0.025:
            raise RuntimeError(f"Miku ONNX parity failed: {error.mean()}, {error.max()}")
        parity.append({"frames": frames, "mean_absolute_error": float(error.mean()),
                       "max_absolute_error": float(error.max())})
    metadata = {"format": 1, "version": "v2", "sample_rate": config[-1],
                "hop": hop, "inter_channels": config[2], "speaker_id": 0,
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "onnx_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "parity": parity}
    destination.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata), flush=True)


if __name__ == "__main__":
    import sys
    export_miku(sys.argv[1], sys.argv[2])
