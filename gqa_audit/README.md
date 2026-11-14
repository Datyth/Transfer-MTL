# GQA task audit

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

## Frozen Stage 2

The four files supplied in `data/gqa/next_requires/` approve decisions A–G.
Their exact bytes are preserved in the final YAML files and frozen manifest in
`gqa_audit/config/`. Stage 2 checks hashes and locked task/stratum counts before
fitting its fixed question-only baselines. Testdev is count-only.

```bash
conda activate datpt_mtl
python -m pytest -q
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m gqa_audit stage2 --questions data/gqa/questions
python -m gqa_audit.verify_stage2 --questions data/gqa/questions
```

Outputs are in `gqa_audit/outputs/stage2/`, with a cached notebook in
`notebooks/gqa_stage2_audit.ipynb`. Large reproducible Parquet caches are excluded
from Git. Plot exports have PNG at 200 dpi and PDF versions. Every derived table
references a config-bundle hash, resolved to the complete hashes in the manifest.
The independent verifier recounts raw registry membership, uses a separate Kahn
traversal for DAG depths, rescores predictions and replays notebook cells.

Registry provenance uses the latest commit affecting package Python files or
configuration. A later commit containing only audit outputs does not alter this
source commit or the registry hash. The repository HEAD is recorded separately.

## Frozen Stage 2b (decisions H–L)

The supplied `analysis_plan.FROZEN.yaml` is copied byte-for-byte to `config/`.
This addendum uses the existing validated caches. It creates fixed evaluation
subsets, operation-subtype descriptors, question-level overlap controls, missing
diagnostic baselines, and the shared `gqa_audit.evaluation` library. Operational
details explicitly stated in the prompt are recorded in `stage2b_runtime.yaml`;
they do not rewrite the frozen H–L plan. Stage 1/2 outputs are hashed before and
after the run and never regenerated.

```bash
conda activate datpt_mtl
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m gqa_audit stage2b --questions data/gqa/questions
python -m gqa_audit.verify_stage2b --questions data/gqa/questions
```

Outputs are in `gqa_audit/outputs/stage2b/`, with the executed overview notebook
`notebooks/gqa_stage2b_analysis.ipynb`. The complete test output is saved as
`pytest_report.txt`. Every artifact's SHA-256 is recorded in `run_manifest.json`;
the manifest excludes itself and the subsequent independent verifier result.

`evaluate(predictions, variant, parts, final=False)` requires exactly one yes/no
prediction for every registered ID in the requested parts. It reports pooled
metrics and explicit primary scopes: verifyRel uses balanced accuracy on the
relation subset (also intersected with text-hard when applicable). Confidence
intervals sample whole images 1,000 times. Single-class balanced accuracy is
undefined rather than silently replaced by ordinary accuracy.

Testdev processing is refused unless final mode is explicitly requested. Stage
2b never requests it. At final evaluation only, the library reads testdev labels,
image IDs and question text, refits the frozen blind baseline and first checks
that it reproduces dev/val predictions exactly. Final testdev output contains
family/stratum units only. No VLM or transfer model is run in this addendum.

Text-hard is conditional on the frozen blind baseline; its baseline accuracy is
zero by construction. Descriptor tables contain task/family/answer audit columns,
but only approved operation tokens may be used as operation features. Raw source
document-frequency overlap counts are not normalized across differently sized
source tasks. Human review and the Stage 3 model/protocol decision remain open.
