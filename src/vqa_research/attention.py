"""Batch equal-length vision windows, preserving the official SDPA operations.

Transformers 4.57.1 loops over every vision window. Concatenating independent
windows along the batch axis reduces kernel launches without cross-window
attention, padding, changes to weights, or different attention mathematics.
"""

from collections import defaultdict
from types import MethodType

import torch
from transformers.integrations.sdpa_attention import sdpa_attention_forward
from transformers.models.qwen2_5_vl.modeling_qwen2_5_vl import apply_rotary_pos_emb_vision


def grouped_vision_attention(self, hidden_states, cu_seqlens, rotary_pos_emb=None,
                             position_embeddings=None, **kwargs):
    if self.training or self.config._attn_implementation != "sdpa":
        raise ValueError("Grouped vision attention supports SDPA inference only")
    length = hidden_states.shape[0]
    query, key, value = self.qkv(hidden_states).reshape(length, 3, self.num_heads, -1).permute(1, 0, 2, 3).unbind(0)
    query, key = apply_rotary_pos_emb_vision(query, key, *position_embeddings)
    lengths = (cu_seqlens[1:] - cu_seqlens[:-1]).tolist()
    splits = [torch.split(t.transpose(0, 1).unsqueeze(0), lengths, dim=2) for t in (query, key, value)]
    groups = defaultdict(list)
    for index, size in enumerate(lengths):
        groups[size].append(index)
    ordered = [None] * len(lengths)
    for indices in groups.values():
        q, k, v = [torch.cat([chunks[i] for i in indices], dim=0) for chunks in splits]
        result, _ = sdpa_attention_forward(self, q, k, v, attention_mask=None,
            scaling=self.scaling, dropout=0.0, is_causal=False, **kwargs)
        for index, chunk in zip(indices, result.unbind(0)):
            ordered[index] = chunk
    return self.proj(torch.cat(ordered, dim=0).reshape(length, -1).contiguous())


def enable_grouped_attention(model):
    originals = []
    for block in model.model.visual.blocks:
        attention = block.attn
        originals.append((attention, attention.forward))
        attention.forward = MethodType(grouped_vision_attention, attention)
    return originals


def restore_attention(originals):
    for attention, forward in originals:
        attention.forward = forward

