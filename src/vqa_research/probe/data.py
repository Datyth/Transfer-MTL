"""Frozen-registry sampling and model-only batches for the probe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from torch.utils.data import Dataset
from transformers import CLIPTokenizerFast

from gqa_audit.evaluation import load_registry
from gqa_audit.stage1 import iter_records
from .features import ROOT, EXPECTED


PILOT_SEEDS = frozenset(range(1000, 1005))
TASKS = ("exist", "verifyAttr", "verifyRel", "compare", "logic")
PLACEBO_TYPES = frozenset(("locationVerify", "locationVerifyC", "placeVerify", "placeVerifyC",
                           "weatherVerify", "weatherVerifyC"))


def rng(seed: int, component: int) -> np.random.Generator:
    if seed not in PILOT_SEEDS:
        raise ValueError(f"Pilot seed {seed} is not registered")
    return np.random.default_rng(np.random.SeedSequence([seed, component]))


class PilotData:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.registry = load_registry(self.root / "gqa_audit/outputs/stage2/task_registry.json")
        self.membership = self.registry["variants"]["program_strict"]
        stage2 = self.root / "gqa_audit/outputs/stage2/cache"
        columns = ["question_id", "image_id", "question", "answer", "detailed"]
        train = pq.read_table(stage2 / "questions_train.parquet", columns=columns).to_pandas()
        dev_images = set(json.loads((self.root / "gqa_audit/outputs/stage2/dev_images.json").read_text())["image_ids"])
        train["part"] = np.where(train.image_id.isin(dev_images), "dev", "train_core")
        metadata = pq.read_table(self.root / "gqa_audit/outputs/stage2b/registry_questions.parquet",
                                 columns=["question_id", "family", "part"]).to_pandas()
        self.frame = train.merge(metadata, on=["question_id", "part"], how="left", validate="one_to_one")
        missing = self.frame.question.isna() & self.frame.detailed.isin(PLACEBO_TYPES) & self.frame.part.eq("train_core")
        if missing.any():
            wanted = set(self.frame.loc[missing, "question_id"])
            texts = {qid: record["question"] for qid, record in
                     iter_records(self.root / "data/gqa/questions/train_balanced_questions.json") if qid in wanted}
            if set(texts) != wanted:
                raise ValueError("Placebo question text missing from frozen raw input")
            self.frame.loc[missing, "question"] = self.frame.loc[missing, "question_id"].map(texts)
        self.by_id = self.frame.set_index("question_id", drop=False)
        self.tokenizer = CLIPTokenizerFast.from_pretrained(self.root / "checkpoints/clip-vit-base-patch16",
                                                            local_files_only=True)
        index = pq.read_table(self.root / "data/features/clip_vitb16_224/index.parquet").to_pandas()
        if len(index) != EXPECTED or index.imageId.duplicated().any():
            raise ValueError("Feature index is incomplete")
        self.image_rows = dict(zip(index.imageId, index.row))
        self.tokens_path = self.root / "data/features/clip_vitb16_224/tokens.float16.memmap"
        self.blank_path = self.root / "data/features/clip_vitb16_224/blank_tokens.npy"

    def target_ids(self, task: str, budget: int | str, seed: int) -> list[str]:
        rng(seed, 1)  # Reject main-study seeds even for the full budget.
        pool = self.membership[task]["train_core"]
        if budget == "full":
            return list(pool)
        if budget not in (250, 1000, 4000):
            raise ValueError("Invalid target budget")
        return [pool[i] for i in rng(seed, 1).permutation(len(pool))[:budget]]

    def source_ids(self, task: str, source: str, seed: int) -> list[str]:
        if source == "self":
            pool = self.membership[task]["train_core"]
            return [pool[i] for i in rng(seed, 1).permutation(len(pool))[4000:14000]]
        if source == "placebo_global":
            pool = self.frame.loc[(self.frame.part == "train_core") &
                                  self.frame.detailed.isin(PLACEBO_TYPES), "question_id"].tolist()
            if len(pool) != 5371:
                raise ValueError("Placebo pool is not 5,371")
            return [pool[i] for i in rng(seed, 2).permutation(len(pool))]
        if source not in TASKS:
            raise ValueError("Unknown real source task")
        pool = self.membership[source]["train_core"]
        return [pool[i] for i in rng(seed, 2).permutation(len(pool))[:10000]]

    def shuffled_labels(self, source_ids: list[str], seed: int) -> dict[str, str]:
        originals = self.by_id.loc[source_ids, "answer"].to_numpy(copy=True)
        shuffled = originals[rng(seed, 5).permutation(len(originals))]
        return dict(zip(source_ids, shuffled))

    def composition(self, ids: list[str]) -> dict:
        frame = self.by_id.loc[ids]
        return {"n": len(ids), "family": frame.family.fillna("").value_counts().to_dict(),
                "answer": frame.answer.value_counts().to_dict()}

    def dataset(self, ids: list[str], *, blank: bool = False, labels: dict[str, str] | None = None):
        return ProbeDataset(self, ids, blank=blank, labels=labels)


class ProbeDataset(Dataset):
    def __init__(self, source: PilotData, ids: list[str], *, blank: bool, labels: dict[str, str] | None):
        self.source = source
        frame = source.by_id.loc[ids]
        if frame.question.isna().any() or not frame.answer.isin(("yes", "no")).all():
            raise ValueError("Missing question text or binary label")
        self.rows = [source.image_rows[x] for x in frame.image_id]
        enc = source.tokenizer(frame.question.tolist(), add_special_tokens=True, padding="max_length",
                               max_length=32, truncation=False, return_tensors="pt")
        if enc.input_ids.shape[1] != 32:
            raise ValueError("Question exceeds 32 CLIP tokens")
        self.input_ids, self.attention_mask = enc.input_ids, enc.attention_mask
        answers = [labels.get(qid, answer) if labels else answer for qid, answer in zip(ids, frame.answer)]
        self.labels = torch.tensor([float(x == "yes") for x in answers], dtype=torch.float32)
        self.blank = blank
        self._tokens = None

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        if self._tokens is None:
            self._tokens = (np.load(self.source.blank_path, mmap_mode="r") if self.blank else
                            np.memmap(self.source.tokens_path, dtype=np.float16, mode="r",
                                      shape=(EXPECTED, 197, 768)))
        row = self._tokens if self.blank else self._tokens[self.rows[index]]
        return {"image_tokens": torch.from_numpy(np.asarray(row, dtype=np.float32)),
                "input_ids": self.input_ids[index], "attention_mask": self.attention_mask[index],
                "labels": self.labels[index]}
