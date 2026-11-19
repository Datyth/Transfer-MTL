"""Frozen dev gates and metric-selection rule."""
import numpy as np
import pandas as pd


def gate_table(curves, blank, root):
    blind = pd.read_csv(root / "gqa_audit/outputs/stage2b/demo_eval_blind.csv")
    floor = blind[(blind.variant == "program_strict") & (blind.part == "dev") & (blind.level == "task")]
    floors = dict(zip(floor.task, floor.primary_value))
    floors["verifyRel"] = .6411
    rows = []
    for task, data in curves.groupby("task"):
        def primary(budget):
            return data[data.budget.astype(str) == str(budget)].primary
        full = primary("full").mean()
        blank_full = blank[(blank.task == task) & (blank.budget.astype(str) == "full")].primary.mean()
        growth = (primary(4000).mean() - primary(1000).mean()) / 2
        noise = primary(1000).std(ddof=1)
        rows.append({"task": task, "text_floor": floors[task], "full": full, "blank_full": blank_full,
                     "image_gain": full - blank_full, "gain_per_doubling": growth, "seed_sd_1000": noise,
                     "G1": "PASS" if full >= floors[task] + .10 else "FLAG",
                     "G2": "PASS" if full - blank_full >= .10 else "FLAG",
                     "G3": "PASS" if growth >= .01 else "FLAG",
                     "G4": "PASS" if noise <= .015 else "FLAG"})
    return pd.DataFrame(rows)


def select_metric(contrasts):
    primary = float(np.median(np.abs([c["primary_gain"]["z"] for c in contrasts])))
    loss = float(np.median(np.abs([c["log_loss_gain"]["z"] for c in contrasts])))
    return {"median_abs_z_primary": primary, "median_abs_z_log_loss": loss,
            "selected": "log_loss_gain" if loss >= 1.25 * primary else "primary_gain"}
