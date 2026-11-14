"""Qwen chat inputs and next-token yes/no scoring, without audit metadata."""

from functools import lru_cache
import re
import time

import numpy as np
from PIL import Image
import torch
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration


def build_messages(question, template, with_image):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A nonempty question string is required")
    content = [{"type": "image"}] if with_image else []
    content.append({"type": "text", "text": template.format(question=question)})
    return [{"role": "user", "content": content}]


def check_token_ids(processor, templates):
    tokenizer = processor.tokenizer
    result = {}
    for word in ("yes", "Yes", "no", "No"):
        ids = tokenizer.encode(word, add_special_tokens=False)
        if len(ids) != 1:
            raise ValueError(f"STOP: {word!r} is not one token: {ids}")
        for template in templates.values():
            for with_image in (True, False):
                prefix = processor.apply_chat_template(build_messages("Is this visible?", template, with_image),
                                                       tokenize=False, add_generation_prompt=True)
                before = tokenizer.encode(prefix, add_special_tokens=False)
                after = tokenizer.encode(prefix + word, add_special_tokens=False)
                if after != before + ids:
                    raise ValueError(f"STOP: {word!r} changes tokenization at the first assistant position")
        result[word] = ids[0]
    if len(set(result.values())) != 4:
        raise ValueError("STOP: yes/no spellings have duplicate token IDs")
    return result


def yes_no_scores(logits, token_ids):
    logits = logits.float()
    return (torch.logsumexp(logits[:, [token_ids["yes"], token_ids["Yes"]]], dim=-1)
            - torch.logsumexp(logits[:, [token_ids["no"], token_ids["No"]]], dim=-1))


@lru_cache(maxsize=128)
def read_image(path):
    with Image.open(path) as image:
        return image.convert("RGB")


class YesNoModel:
    def __init__(self, path, protocol):
        self.protocol = protocol
        settings = protocol["model_loading"]
        self.processor = AutoProcessor.from_pretrained(path, local_files_only=True, use_fast=False,
            min_pixels=settings["min_pixels"], max_pixels=settings["max_pixels"])
        self.processor.tokenizer.padding_side = "left"
        self.token_ids = check_token_ids(self.processor, protocol["templates"])
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(path,
            torch_dtype=torch.bfloat16, attn_implementation=settings["attn_implementation"],
            local_files_only=True, device_map={"": 0}).eval()
        self.image_token_id = self.model.config.image_token_id

    def inputs(self, questions, image_paths, template):
        with_image = image_paths is not None
        chats = [build_messages(question, template, with_image) for question in questions]
        text = [self.processor.apply_chat_template(chat, tokenize=False, add_generation_prompt=True) for chat in chats]
        images = [read_image(str(path)) for path in image_paths] if with_image else None
        batch = self.processor(text=text, images=images, padding=True, return_tensors="pt")
        if not batch.attention_mask[:, -1].eq(1).all():
            raise ValueError("Last position must be the first assistant token context, never padding")
        return batch.to(self.model.device)

    @torch.inference_mode()
    def score(self, questions, image_paths, template):
        torch.cuda.synchronize()
        start = time.perf_counter()
        inputs = self.inputs(questions, image_paths, template)
        output = self.model(**inputs, use_cache=False, logits_to_keep=1)
        scores = yes_no_scores(output.logits[:, -1, :], self.token_ids)
        if not torch.isfinite(scores).all():
            raise ValueError("Nonfinite yes/no scores")
        counts = inputs.input_ids.eq(self.image_token_id).sum(dim=1).cpu().numpy()
        probabilities = scores.sigmoid().cpu().numpy()
        scores = scores.cpu().numpy()
        torch.cuda.synchronize()
        seconds = (time.perf_counter() - start) / len(questions)
        return {"score": scores, "pred": np.where(scores > 0, "yes", "no"), "p_yes": probabilities,
                "n_image_tokens": counts, "seconds": np.full(len(questions), seconds)}

    @torch.inference_mode()
    def generate(self, questions, image_paths, template):
        inputs = self.inputs(questions, image_paths, template)
        generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=5,
                                        use_cache=True, temperature=None, top_p=None, top_k=None)
        text = self.processor.batch_decode(generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        result = []
        for value in text:
            match = re.match(r"^\s*(yes|no)\b", value, flags=re.I)
            result.append({"generation": value, "first_word": match.group(1).lower() if match else ""})
        return result
