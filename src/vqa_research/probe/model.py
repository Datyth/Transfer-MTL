"""One-head CLIP-token fusion probe defined by the frozen pilot protocol."""

from __future__ import annotations

import torch
from torch import nn
from transformers import CLIPModel


ALLOWED_BATCH_KEYS = frozenset({"image_tokens", "input_ids", "attention_mask", "labels"})


class ProbeModel(nn.Module):
    def __init__(self, clip_path, *, train_text: bool, max_text_tokens: int = 32):
        super().__init__()
        if max_text_tokens > 77 or max_text_tokens % 8:
            raise ValueError("CLIP text length must be a multiple of 8 and at most 77")
        clip = CLIPModel.from_pretrained(clip_path, local_files_only=True, use_safetensors=False)
        vision_config = clip.config.vision_config
        self.image_shape = ((vision_config.image_size // vision_config.patch_size) ** 2 + 1,
                            vision_config.hidden_size)
        text_width = clip.config.text_config.hidden_size
        self.text_encoder = clip.text_model
        del clip
        self.train_text = train_text
        self.max_text_tokens = max_text_tokens
        self.text_encoder.requires_grad_(train_text)
        self.image_projection = nn.Linear(self.image_shape[1], 512)
        self.image_norm = nn.LayerNorm(512)
        self.text_projection = nn.Linear(text_width, 512)
        self.text_norm = nn.LayerNorm(512)
        self.type_embeddings = nn.Parameter(torch.zeros(2, 512))
        self.fusion_token = nn.Parameter(torch.zeros(1, 1, 512))
        layer = nn.TransformerEncoderLayer(d_model=512, nhead=8, dim_feedforward=2048,
                                           dropout=0.1, activation="gelu", batch_first=True,
                                           norm_first=True)
        self.fusion = nn.TransformerEncoder(layer, num_layers=4, enable_nested_tensor=False)
        self.head_norm = nn.LayerNorm(512)
        self.head = nn.Linear(512, 1)
        nn.init.normal_(self.fusion_token, std=0.02)
        nn.init.normal_(self.type_embeddings, std=0.02)

    def train(self, mode: bool = True):
        super().train(mode)
        if not self.train_text:
            self.text_encoder.eval()
        return self

    def forward(self, **batch):
        if not set(batch) <= ALLOWED_BATCH_KEYS:
            raise ValueError(f"Audit or unknown columns reached probe: {set(batch) - ALLOWED_BATCH_KEYS}")
        if not {"image_tokens", "input_ids", "attention_mask"} <= set(batch):
            raise ValueError("Probe batch is missing model inputs")
        image = batch["image_tokens"]
        input_ids, attention_mask = batch["input_ids"], batch["attention_mask"]
        if image.shape[1:] != self.image_shape or input_ids.shape[1] != self.max_text_tokens:
            raise ValueError("Unexpected probe input dimensions")
        if self.train_text:
            text = self.text_encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        else:
            with torch.no_grad():
                text = self.text_encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        text = self.text_norm(self.text_projection(text)) + self.type_embeddings[0]
        image = self.image_norm(self.image_projection(image)) + self.type_embeddings[1]
        fused = torch.cat((self.fusion_token.expand(len(image), -1, -1), text, image), dim=1)
        padding = torch.cat((torch.zeros((len(image), 1), dtype=torch.bool, device=image.device),
                             ~attention_mask.bool(),
                             torch.zeros((len(image), self.image_shape[0]), dtype=torch.bool, device=image.device)), dim=1)
        fused = self.fusion(fused, src_key_padding_mask=padding)
        return self.head(self.head_norm(fused[:, 0])).squeeze(-1)


def parameter_counts(model: nn.Module) -> dict:
    return {"total": sum(p.numel() for p in model.parameters()),
            "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad)}
