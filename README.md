# GQA research experiments

The accepted audit package is in `gqa_audit/`. New model experiment code is in
`src/vqa_research/`; the entry script only parses and launches the experiment.
Frozen model protocols live in `configs/`, local model weights in `checkpoints/`.

```bash
conda activate datpt_mtl
python scripts/run_experiment.py --models 3b
```

This runs the fixed 3B zero-shot experiment, writes resumable prediction shards,
checks both prompt templates, tests greedy generation and batch invariance, then
creates metric tables, PNG/PDF figures and `STAGE3_REPORT.md` under
`gqa_audit/outputs/stage3/`. Repeating the command verifies completed shards and
continues unfinished ones. The batch size defaults to 16; keep the same value on
resume. A new batch size requires a separate prediction directory/run.

Useful options:

```bash
python scripts/run_experiment.py --prepare-only
python scripts/run_experiment.py --evaluate-only --models 3b
python -m pytest -q
```

`--prepare-only` checks images, model files, environment and tokenizer without
inference. `--evaluate-only` rebuilds tables and reports from existing predictions.
Explicit `--models 3b 7b` enables the optional phase B download and evaluation.
No testdev questions are scored; no training takes place.

Implementation: `data.py` reads accepted inputs; `model.py` builds prompts and
scores yes/no; `inference.py` manages shards; `analysis.py` calls the accepted
evaluation library; `report.py` writes checks, tables and figures;
`experiment.py` runs these steps in order. The accepted evaluator exposes its
existing bootstrap draws for paired image/no-image confidence intervals.
