# Adapted from SUC-DriverOld/rvc.onnx; see LICENSE and PROVENANCE.md.
import math
import torch
from torch.nn import functional as F
from .attentions import MultiHeadAttention

# CompilationUnit embeds helper source in bytecode-only Flet packages.
_helpers = torch.jit.CompilationUnit("""
def _jit_get_relative_embeddings(
    relative_embeddings: torch.Tensor,
    length_ref: torch.Tensor,
    window_size: int,
) -> torch.Tensor:
    length = length_ref.size(2)
    pad_length = length - (window_size + 1)
    if pad_length < 0:
        pad_length = 0
    slice_start = (window_size + 1) - length
    if slice_start < 0:
        slice_start = 0
    slice_end = slice_start + 2 * length - 1
    if pad_length > 0:
        padded = F.pad(relative_embeddings, [0, 0, pad_length, pad_length, 0, 0])
    else:
        padded = relative_embeddings
    return padded[:, slice_start:slice_end]


def _jit_rel_pos_to_abs(x: torch.Tensor) -> torch.Tensor:
    b = x.size(0)
    h = x.size(1)
    l = x.size(2)
    x = F.pad(x, [0, 1, 0, 0, 0, 0, 0, 0])
    x_flat = x.reshape([b, h, -1])
    x_flat = F.pad(x_flat, [0, l - 1, 0, 0, 0, 0])
    x_final = x_flat.reshape([b, h, l + 1, 2 * l - 1])
    return x_final[:, :, :l, l - 1:]


def _jit_abs_pos_to_rel(x: torch.Tensor) -> torch.Tensor:
    b = x.size(0)
    h = x.size(1)
    l = x.size(2)
    x = F.pad(x, [0, l - 1, 0, 0, 0, 0, 0, 0])
    x_flat = x.reshape([b, h, -1])
    x_flat = F.pad(x_flat, [l, 0, 0, 0, 0, 0])
    x_final = x_flat.reshape([b, h, l, 2 * l])
    return x_final[:, :, :, 1:]


""")
_jit_get_relative_embeddings = _helpers._jit_get_relative_embeddings
_jit_rel_pos_to_abs = _helpers._jit_rel_pos_to_abs
_jit_abs_pos_to_rel = _helpers._jit_abs_pos_to_rel


def _patched_attention(self, query, key, value, mask=None):
    b = query.size(0)
    query = query.view(b, self.n_heads, self.k_channels, -1).transpose(2, 3)
    key = key.view(b, self.n_heads, self.k_channels, -1).transpose(2, 3)
    value = value.view(b, self.n_heads, self.k_channels, -1).transpose(2, 3)
    scores = torch.matmul(
        query / math.sqrt(self.k_channels), key.transpose(-2, -1)
    )
    if self.window_size is not None:
        key_relative_embeddings = _jit_get_relative_embeddings(
            self.emb_rel_k, key, self.window_size
        )
        rel_logits = self._matmul_with_relative_keys(
            query / math.sqrt(self.k_channels), key_relative_embeddings
        )
        scores = scores + _jit_rel_pos_to_abs(rel_logits)
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e4)
    p_attn = F.softmax(scores, dim=-1)
    p_attn = self.drop(p_attn)
    output = torch.matmul(p_attn, value)
    if self.window_size is not None:
        relative_weights = _jit_abs_pos_to_rel(p_attn)
        value_relative_embeddings = _jit_get_relative_embeddings(
            self.emb_rel_v, key, self.window_size
        )
        output = output + self._matmul_with_relative_values(
            relative_weights, value_relative_embeddings
        )
    output = (
        output.transpose(2, 3)
        .contiguous()
        .reshape(b, self.n_heads * self.k_channels, -1)
    )
    return output, p_attn


def patch_attention_for_onnx():
    MultiHeadAttention.attention = _patched_attention

