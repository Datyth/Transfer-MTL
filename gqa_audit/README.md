# GQA Stage 1 audit

Run from the project root:

```bash
conda activate datpt_mtl
python -m pytest -q
python -m gqa_audit stage1 --questions data/gqa/questions
python -m gqa_audit.verify_stage1 --questions data/gqa/questions
```

Stage 1 uses streaming JSON and writes reports under `gqa_audit/outputs/stage1/`.
The notebook `notebooks/gqa_stage1_audit.ipynb` contains outputs from executing its
visible code. No Jupyter package is required to generate or verify it.

Eligibility requires string answers `'yes'`/`'no'` and a nonempty list program.
The configuration is validated before output files are changed. YAML booleans in
the answer list are rejected. Every pilot type is checked against independent raw
answer and empty-program counters. The separate verifier reads the raw data again
without calling the production eligibility, relation or rollup functions.

The corrected rerun preserves the existing proposed task assignments. Family
pairing, suffix samples and the four filter variants are diagnostics for human
review; they do not freeze a primary rule or rebalance data. Raw answers remain
separate from detailed-type labels. No model is trained in this stage.

Review the three `.PROPOSED.yaml` files, the summary, family flags, and independent
verification report before approving Stage 2. Source/input/config hashes are in
`run_manifest.json`; config snapshots are stored beside the reports.
