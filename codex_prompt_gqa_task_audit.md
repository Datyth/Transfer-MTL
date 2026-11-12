# Task: GQA Task Audit for a Multi-Task VQA Transfer Study

## Context (read first)
You are helping with a research project on directional task transfer between reasoning-oriented VQA tasks in GQA.
Before any model is trained, we need a reproducible, auditable **task registry**: which GQA questions belong to which
learning task, and whether those tasks are large, balanced and free of obvious confounds.

The study defines a *task* as a subset of GQA questions chosen by an existing benchmark label (`types.detailed`) and a
fixed inclusion rule. A question's functional program (`semantic` field) is kept **separately** as a description of the
reasoning operations it involves. It is never used as the task label.

Planned pilot tasks (all yes/no answers):

| Pilot task | Intended GQA `types.detailed` family | Extra rule |
|---|---|---|
| exist | object existence (`exist*`) | exclude questions with relation steps |
| verifyAttr | attribute verification (`verifyAttr*`) | exclude relation steps |
| verifyRel | relation verification (`verifyRel*`) | keep relation steps |
| compare | pairwise comparison (`twoSame*`, `twoDiff*`) | exclude relation steps |
| logic | logical composition (`logicAnd*`, `logicOr*`) | composite target; no relation filter |

**Important:** the names above are *intended families*. The real `types.detailed` values may be more granular or named
differently. Do **not** assume. Discover them from the data and report them.

This is a **no-GPU** job. It only needs the question JSON files. Images and visual features are not needed.

---

## Ground rules
1. **Do not modify raw data.** Read-only access to the GQA files. Write all outputs under `gqa_audit/outputs/`.
2. **Memory-safe parsing.** The train balanced file is large. Use streaming JSON parsing (`ijson`), or parse once and
   cache a compact Parquet table (`questions_<split>.parquet`) with only the needed fields. Then work from Parquet.
3. **Every rule lives in one config file** (`gqa_audit/config/task_rules.yaml`, plus `op_family_map.yaml`). No rule may be
   hard-coded inside analysis code.
4. **Never adjust rules based on audit outcomes** (sizes, balance, baseline accuracy) without an explicit human
   decision. Report outcomes; do not optimize them.
5. **Determinism.** Fix all random seeds (default 0). Record package versions, the git commit, and SHA-256 hashes of the
   input files.
6. **Fail loudly.** If a field is missing, an operation is unmapped, or the format differs from these instructions,
   stop and report. Do not guess silently.
7. Python ≥3.10. Allowed packages: `ijson`, `pandas`, `pyarrow`, `numpy`, `scikit-learn`, `matplotlib`, `pyyaml`,
   `pytest`. Put the code in a small package `gqa_audit/` with a CLI (`python -m gqa_audit <stage>`).

## Data
- Expected files: `train_balanced_questions.json`, `val_balanced_questions.json`, `testdev_balanced_questions.json`.
- Path: `<GQA_QUESTIONS_DIR>`. **Ask me for the path.** If the files are absent, ask before downloading. The official
  archive is `questions1.2.zip` from the GQA website.
- Do **not** use `test`/`challenge` files (they have no public answers). Do not use `all_*` (unbalanced) files in this
  audit, except to report their existence.
- Each file is a dict `question_id -> record`. Expected record fields (verify!): `imageId`, `question`, `answer`,
  `fullAnswer`, `isBalanced`, `types{structural, semantic, detailed}`, `semantic` (list of steps
  `{operation, argument, dependencies}`), `groups{global, local}`, `entailed`, `equivalent`, `annotations`.

---

## STAGE 1: Inspection (then STOP for human review)

### 1.1 Schema report
- Print 3 example records per split, abbreviated.
- List all top-level keys and their frequencies. Flag any record missing an expected field.
- Save `outputs/stage1/schema_report.md`.

### 1.2 Question-type inventory
- Count questions per split for every `types.detailed` value. For each value also report: the `types.structural` and
  `types.semantic` values it co-occurs with, and the fraction of `yes`, `no` and other answers.
- Save `outputs/stage1/detailed_type_inventory.csv`.

### 1.3 Operation catalogue
- GQA operation strings may contain a subtype (e.g. `"verify color"`, `"choose rel"`, `"filter material"`). For every
  step, record the full operation string and a *head* (the first token).
- Count operation strings and heads per split. Show 3 example arguments for each.
- Save `outputs/stage1/operation_catalogue.csv`.

### 1.4 Proposed mappings (proposals only; nothing is frozen)
- Write `config/task_rules.PROPOSED.yaml`. Map each raw `types.detailed` value to one pilot task, using the intended
  families above, or to `secondary` if it does not fit. Add a `reason` comment for every non-obvious choice and an
  `AMBIGUOUS` flag where uncertain.
- Write `config/op_family_map.PROPOSED.yaml`. Map every operation string to one or more families from: `select`,
  `filter_attribute`, `query_attribute`, `verify_attribute`, `relation`, `exist`, `compare` (same/different/common),
  `choose`, `logic` (and/or). Flag anything that does not fit.
- Propose **two** definitions of "relation step" and count both:
  - `R_strict`: the operation head is `relate`.
  - `R_broad`: `R_strict`, OR any operation whose string refers to relations (e.g. `verify rel`, `choose rel`), OR any
    step whose argument encodes a relation.

  List the exact matching strings for each definition.

### 1.5 Stage 1 summary
In `outputs/stage1/STAGE1_SUMMARY.md` report:
- The detailed types that match each intended family, with counts.
- Unmatched or ambiguous types.
- The operation catalogue size.
- How many candidate questions each relation definition would remove from exist / verifyAttr / compare.

**Then STOP.** Do not run Stage 2 until I approve and rename the `.PROPOSED.yaml` files to final ones.

---

## STAGE 2: Frozen audit (run only after approval)

At start, compute and store the SHA-256 of both final config files. All later outputs must reference these hashes.

### 2.1 Eligibility and task assignment
A question is eligible if all of the following hold:
- the answer, after stripping and lowercasing, is in `{yes, no}`;
- `semantic` is non-empty;
- its `types.detailed` maps to a pilot task.

Apply the relation filter (configurable `R_strict`/`R_broad`) to the tasks marked "exclude relation steps".
Produce **two variants**:
- `filtered`: the rule as specified;
- `unfiltered`: same, but with no relation exclusion.

Assertions: each question gets ≤1 pilot task; the tasks are disjoint within each variant.

### 2.2 Split plan (proposal; record it, do not evaluate models)
- Check that `imageId` sets are disjoint across train / val / testdev. Report the size of any overlap.
- Propose a **dev split carved from train by image** (default 5% of train images, seed 0). This gives:
  `train_core`, `dev` (model selection), `val` (held-out analysis) and `testdev` (sealed final test).
- Check `entailed`/`equivalent` references. Count references that cross split boundaries, including the new
  train_core/dev boundary.

### 2.3 Per-task statistics (each variant × split)
- Number of questions and number of unique images.
- Yes/no ratio overall, and per `types.detailed` value inside each task.
- Exclusion counts for each rule: non-binary answer, empty program, relation filter.
- Program length L, number of relation steps, and dependency depth: the longest path in the step DAG built from
  `dependencies`. Mark depth as NaN when dependencies are missing or invalid, and count those cases.
- Operation-family profile: the fraction of questions containing each family.

Save `outputs/stage2/task_stats.csv` and `outputs/stage2/op_family_profile.csv`.

### 2.4 Confound checks
1. **Image overlap between tasks** (train, each variant): a matrix of |images_i ∩ images_j| / |images_j|, plus Jaccard.
2. **Question-only blind baseline per task:**
   - Report majority-class accuracy.
   - Train TF-IDF (word 1–2-grams, min_df=2) + logistic regression (C=1.0, max_iter=2000) on `train_core`. Report
     accuracy on `dev` and `val`.
   - Do not tune beyond this fixed setting.
   - Also report a per-`types.detailed` breakdown.
3. **Lexical overlap between tasks:** cosine similarity of the tasks' mean TF-IDF vectors, and Jaccard overlap of their
   question vocabularies.
4. **Operation overlap between tasks:** cosine similarity of the operation-family profile vectors from 2.3. This is the
   candidate predictor of transfer that later experiments will test.

### 2.5 Logic-target decomposition (for compositional-generalization splits)
For each logic question:
- Locate the `and`/`or` step and trace each operand's sub-program through `dependencies`.
- Label each operand by its terminal operation family, using the same categories as the pilot tasks (exist /
  verifyAttr / verifyRel / compare / other), and record whether that operand contains a relation step.
- Report a table of operand-type pairs (unordered) × {and, or} × split, plus a count of unparseable cases.
- Save `outputs/stage2/logic_decomposition.csv`.

### 2.6 Manual review sample
- For each pilot task × variant, sample 25 train questions, stratified by `types.detailed` (seed 0).
- Columns: question_id, imageId, question, answer, detailed type, pretty-printed program (one step per line with
  dependency indices), relation flags, assigned task, and an empty column `human_ok` for me to fill in.
- Also sample 25 questions **removed** by the relation filter from each filtered task.
- Save `outputs/stage2/manual_review_sample.csv`. Do not judge these automatically.

### 2.7 Frozen task registry
Write `outputs/stage2/task_registry.json` containing:
- For each variant, task and split: the list of question_ids.
- The config file hashes, input file hashes, git commit, package versions, seed and dev-split image list hash.
- A `registry_sha256` over the canonicalized (sorted-key) content.

Also write `task_registry_summary.csv` with counts only.

### 2.8 Pre-registered checks (report PASS/FLAG; do not change anything)
| Check | Threshold |
|---|---|
| train_core questions per task | ≥ 10,000 (FLAG if below) |
| dev, val questions per task | ≥ 1,000 each |
| testdev questions per task | report; FLAG if < 300 |
| yes ratio per task | within [0.40, 0.60] |
| blind TF-IDF accuracy on val | FLAG if > majority + 0.15 |
| relation-filter exclusion rate | report; FLAG if > 50% of a task |
| unparseable logic questions | FLAG if > 5% |
| depth NaN rate | FLAG if > 5% |

### 2.9 Figures (matplotlib; PNG at 200 dpi + PDF)
1. Bar chart: questions per task × variant (train_core/dev/val/testdev).
2. Stacked bar chart: yes/no ratio per task.
3. Histograms: program length and depth per task, filtered variant.
4. Heatmap: operation-family profile (tasks × families).
5. Heatmaps: image overlap, lexical overlap and operation overlap between tasks.
6. Bar chart: blind-baseline vs majority accuracy per task.
7. Heatmap: logic operand-pair counts.

### 2.10 Report
Write `outputs/stage2/AUDIT_REPORT.md` containing:
- the config hashes and registry hash;
- the key tables and the figures;
- the PASS/FLAG table;
- a plain list of open decisions for the human. For example: should twoSame/twoDiff be pooled, should logicAnd/logicOr
  be pooled, is R_strict or R_broad the primary rule, and does any task need to be dropped.

Keep the report factual: no recommendations that change the rules.

---

## Tests (required)
`pytest` tests on small hand-written records covering:
- head extraction from operation strings;
- `R_strict`/`R_broad` detection;
- DAG depth, including missing or invalid dependencies;
- logic operand tracing for `and`/`or` with nested sub-programs;
- task disjointness;
- registry hash stability (the same input gives the same hash).

## Deliverable checklist (final message to me)
- Which stage was run.
- Paths to all outputs.
- The PASS/FLAG table.
- Any ambiguities you hit and how they were (not) resolved.
- Exact commands to reproduce: `python -m gqa_audit stage1 --questions <dir>` and
  `python -m gqa_audit stage2 --questions <dir>`.
