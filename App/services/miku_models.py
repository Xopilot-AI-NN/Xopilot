"""Pinned learned voice resources and lightweight installation detection."""

import json

from .voice_catalog import VOICE_DIR


CHECKPOINT_SHA256 = "ed8522a71c0985fd6825d7c91330dea5b8dc036ec4a2d5cad89fdebe4002a37c"
BASE_REPO = "TigreGotico/voiceclonnx-rvc"
BASE_REVISION = "cbfbabdabe6a1414292bade8f857fb6074abf130"
MIKU_REPO = "HidekoHaruna/RVC_V2_Hatsune_Miku"
MIKU_REVISION = "0a5ccf3ba0040aecc959a97bad2997e8a0482964"
RESOURCES = {
    "contentvec.onnx": (
        f"https://huggingface.co/{BASE_REPO}/resolve/{BASE_REVISION}/contentvec_768l12.onnx",
        "cbddd8fa9352b3128df6359e2e3da6be0f9072e768e51e3efc3004e5030ea97f",
    ),
    "rmvpe.onnx": (
        f"https://huggingface.co/{BASE_REPO}/resolve/{BASE_REVISION}/rmvpe.onnx",
        "5370e71ac80af8b4b7c793d27efd51fd8bf962de3a7ede0766dac0befa3660fd",
    ),
    "miku.pth": (
        f"https://huggingface.co/{MIKU_REPO}/resolve/{MIKU_REVISION}/weights/MikuAI_e210_s6300.pth",
        CHECKPOINT_SHA256,
    ),
}


def model_directory():
    return VOICE_DIR / "miku-rvc"


def miku_installed():
    root = model_directory()
    try:
        metadata = json.loads((root / "miku.json").read_text(encoding="utf-8"))
        if (not isinstance(metadata, dict) or metadata.get("format") != 1 or metadata.get("version") != "v2"
                or metadata.get("checkpoint_sha256") != CHECKPOINT_SHA256
                or not metadata.get("onnx_sha256") or len(metadata.get("parity", [])) != 3):
            return False
        return all((root / name).is_file() and (root / name).stat().st_size > 0
                   for name in ("contentvec.onnx", "rmvpe.onnx", "miku.onnx"))
    except (OSError, ValueError, TypeError):
        return False
