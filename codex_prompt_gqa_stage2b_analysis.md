# Task: GQA analysis addendum, Stage 2b (decisions H-L; no model training)

## 0. Read first
- Stage 1 and Stage 2 are **finished and accepted**. Do not rerun them and do not modify `outputs/stage1/` or
  `outputs/stage2/`. The task registry is final:
  `outputs/stage2/task_registry.json`, `registry_sha256 = c122aac0bbb9ed8ad6eaa93843d95df664ba75c767946003e90ff2469c27b451`.
- The human has taken decisions H-L. They are encoded in **one new frozen file** that you copy unchanged to
  `gqa_audit/config/analysis_plan.FROZEN.yaml` (sha256 `0d23283638bbfa254994156fe30650ef5db6254f50c943f27c7233452b99520b`). Never regenerate or reformat it.
- This stage adds analysis subsets, question-level descriptors, an evaluation library and the Stage 2 items that were
  missing. **No GPU, no images, no VLM.** Write everything to `gqa_audit/outputs/stage2b/`.
- **Extend the existing package** (`gqa_audit`); keep the CLI, cache and tests. New entry point:
  `python -m gqa_audit stage2b --questions data/gqa/questions`.

| ID | Decision (human, final) |
|---|---|
| H | Primary verifyRel metric = **balanced accuracy on `verifyRel_relation`** = {relVerify, relVerifyCr}. Pooled verifyRel accuracy and `verifyRel_Co` = {relVerify, relVerifyCo} are secondary. Other tasks: accuracy primary. Balanced accuracy, yes-prediction rate and n are always reported too. |
| I | Logic keeps its frozen target. Two analysis subsets are fixed now, before any model is trained: `logic_no_not_cue` and `text_hard` (all tasks). Main results are also reported on both. |
| J | Every future transfer edge is reported next to the target's blind-baseline gain and on the target's `text_hard` subset. |
| K | RQ2 is tested at **question level** with operation-subtype descriptors (operation strings, no arguments). Task-level overlap is descriptive only. |
| L | testdev is reported only per stratum and per family, never pooled against val. |

Why (context for you, not to re-open): the question-only baseline showed a deterministic cue in `existThatOr`
("not" implies "no" in 100% of train and val), an object-name prior in `existOr`/`existAttrOr`, and that verifyRel's
text gain comes only from the wrong-object (Co) negatives. Task-level operation overlap is nearly constant across
task pairs, so it cannot test RQ2.

## 1. Ground rules
1. `question_id` is always a string. Read the Stage 2 cache with the existing loader.
2. All rules come from `analysis_plan.FROZEN.yaml` and the Stage 2 frozen configs. Nothing is hard-coded.
3. Never change a rule because of an outcome. Report PASS / FLAG / INFO.
4. Descriptors and features never contain `types.detailed`, family, task labels, arguments, object IDs or the `(-)`
   marker. (Analysis tables may *group by* family or detailed type, as an audit.)
5. **testdev stays sealed.** No text, program or prediction processing of testdev in this stage. The evaluation
   library must refuse testdev unless called with an explicit `final=True` flag, and no code in this stage sets it.
6. Seed 0. Record package versions, git commit, and SHA-256 of every input and output.

## 2. Steps

### 2b.0 Preflight (STOP on any mismatch)
1. SHA-256 of `analysis_plan.FROZEN.yaml` = `0d23283638bbfa254994156fe30650ef5db6254f50c943f27c7233452b99520b`; `status: FROZEN`.
2. `task_registry.json` loads, and its recomputed hash equals `c122aac0bbb9ed8ad6eaa93843d95df664ba75c767946003e90ff2469c27b451` (convention in the registry file).
3. SHA-256 of `outputs/stage2/blind_predictions.csv` = `9cbd7f95fed1aa49301cdd6c86b4ff5cc35af26ccc3bf732554098dd66413c00`.
4. The Stage 2 frozen configs keep their hashes (task_rules `2f2ce20e...`, op_family_map `d49d3f0b...`,
   answer_families `c5458dcd...`).

### 2b.1 Missing Stage 2 deliverables (compute now, from the cache)
1. `pytest_report.txt`: full `python -m pytest -q` output, including the Stage 2 tests.
2. `dash_rate_by_type.csv`: every pilot detailed type x part (train_core, dev, val) x answer: `n`, `n_dash`,
   `dash_rate` (`(-)` substring in any step argument). Expected: 1.0 for existC, existRelSC, existAndC, existOrC,
   existAttrOrC, existThatOrC, relVerifyCo; 0.0 for existRelSRC, relVerifyCr, relVerifyCop and every attribute
   C-type. FLAG any deviation; do not reinterpret.
3. `program_structure_by_type.csv`: pilot types, train_core: mean / median / p10 / p90 of program length, depth and
   `relate`-step share, by detailed type and answer.
4. `program_structure_baseline.csv`: per task (program_strict), logistic regression (C=1.0, max_iter=2000, inputs
   standardized) on train_core with program length, depth, relate-step count and operation-family presence flags;
   then a second fit adding the dash flag. Report dev and val accuracy and majority accuracy. Reference values I
   obtained on val: structure only exist 0.508, verifyAttr 0.508, verifyRel 0.583, compare 0.482, logic 0.494;
   with dash exist 0.783, verifyRel 0.872, logic 0.620. Report your values; small differences are fine, explain
   any difference > 0.01.
5. `verifyrel_within_subset_baselines.csv`: question-only TF-IDF baselines (same frozen settings) **trained and
   evaluated within** `verifyRel_relation` and within `verifyRel_Co`; report accuracy, balanced accuracy and
   majority accuracy on dev and val. Also per-class recall of the existing pooled model on relVerify, relVerifyCo,
   relVerifyCr (my values on val: 0.662, 0.868, 0.449).
6. Family-level blind-baseline FLAGs: add family rows (gain > 0.15, families with n >= 100) to a new
   `preregistered_checks_family.csv`. Expected FLAGs on val: existThatOr, existAttrOr, existOr.
7. `manual_review_verifyrel.csv`: 25 train_core questions each of relVerify, relVerifyCo, relVerifyCr (seed 0),
   same columns as `manual_review_sample.csv`, empty `human_ok`.
8. `registry_questions.parquet`: one row per assigned question (question_id string, imageId, part, task, family,
   stratum, in_program_strict, in_unfiltered, answer, program_length, depth, n_relate). testdev rows carry
   only IDs, part, task, family, stratum and the two membership flags.
9. Figure `dash_rate_by_type.png/.pdf`.

### 2b.2 Analysis subsets (decisions H and I)
Build `analysis_subsets.json`: for each subset x variant x task x part, the sorted question-ID list, plus all input
hashes and an `analysis_subsets_sha256` (same canonical-JSON convention as the registry).
- `verifyRel_relation`, `verifyRel_Co`: parts train_core, dev, val.
- `logic_no_not_cue`: logic minus questions with family `existThatOr` whose question text matches the frozen regex
  `(?i)\bnot\b|n't\b`. Parts train_core, dev, val (testdev only at final evaluation).
- `text_hard`: rows of `blind_predictions.csv` with `prediction != answer`, per variant x task x part (dev, val).
  Add `text_hard_by_family.csv` with family-level counts and yes ratios.

Regression targets (must match **exactly**, else STOP):

`text_hard` (variant x part x task):

| variant | part | task | n | text_hard | text_hard_yes |
|---|---|---|---|---|---|
| program_strict | dev | compare | 1,705 | 815 | 415 |
| program_strict | dev | exist | 2,083 | 901 | 492 |
| program_strict | dev | logic | 11,117 | 3,709 | 1,504 |
| program_strict | dev | verifyAttr | 2,721 | 1,245 | 650 |
| program_strict | dev | verifyRel | 5,576 | 1,579 | 931 |
| program_strict | val | compare | 2,504 | 1,256 | 575 |
| program_strict | val | exist | 2,879 | 1,252 | 672 |
| program_strict | val | logic | 15,926 | 5,198 | 2,212 |
| program_strict | val | verifyAttr | 3,633 | 1,627 | 858 |
| program_strict | val | verifyRel | 7,933 | 2,272 | 1,314 |
| unfiltered | dev | compare | 1,705 | 815 | 415 |
| unfiltered | dev | exist | 7,528 | 3,252 | 1,814 |
| unfiltered | dev | logic | 11,117 | 3,709 | 1,504 |
| unfiltered | dev | verifyAttr | 3,583 | 1,616 | 839 |
| unfiltered | dev | verifyRel | 5,576 | 1,579 | 931 |
| unfiltered | val | compare | 2,504 | 1,256 | 575 |
| unfiltered | val | exist | 10,548 | 4,597 | 2,545 |
| unfiltered | val | logic | 15,926 | 5,198 | 2,212 |
| unfiltered | val | verifyAttr | 4,914 | 2,191 | 1,150 |
| unfiltered | val | verifyRel | 7,933 | 2,272 | 1,314 |

`logic_no_not_cue`:

| part | logic | not_cue | logic_no_not_cue |
|---|---|---|---|
| dev | 11,117 | 278 | 10,839 |
| train_core | 101,611 | 2,594 | 99,017 |
| val | 15,926 | 383 | 15,543 |

verifyRel subsets (`verifyRel_Co_subset` = relVerify + relVerifyCo):

| part | relVerify | relVerifyCr | verifyRel_Co_subset |
|---|---|---|---|
| train_core | 24,964 | 6,242 | 44,674 |
| dev | 2,813 | 743 | 4,829 |
| val | 3,885 | 996 | 6,931 |

Also report: how many `logic_no_not_cue` exclusions fall inside val `text_hard` (expected 0 of 383, because the
baseline answers them correctly).

### 2b.3 Question-level descriptors (decision K)
1. Tokens per program step: the stripped `operation` string (e.g. `verify color`, `filter material`, `relate`,
   `exist`, `and`); if the step argument starts with `not(`, also emit `<operation> [neg]`. No arguments, IDs or
   `(-)`.
2. Freeze the vocabulary from **program_strict train_core** (expected size **104** tokens including `select` and
   `[neg]` tokens). Tokens unseen there map to `UNSEEN`; report UNSEEN counts per part.
3. `question_descriptors.parquet` (train_core, dev, val; program_strict and unfiltered): question_id, part,
   variant flags, task, family, stratum, answer, token multiset (`select` excluded), `with_select` token multiset,
   program_length, depth, n_relate. Save `descriptor_vocabulary.json` with its hash.

### 2b.4 Question-level overlap and its confounds (decision K)
For every directed pair source -> target (source != target) and part (dev, val):
1. `shared_binary`: the target question has >= 1 non-`select` token that occurs in the source task's program_strict
   train_core questions. `shared_continuous`: sum over the question's distinct non-`select` tokens of the source
   task's train_core document frequency.
2. `question_overlap_counts.csv`: n_target, n_sharing, share. Regression targets for val (exact; compare pairs are
   all 0 and are listed in the frozen file):

| source | target | n_target | n_sharing |
|---|---|---|---|
| verifyAttr | exist | 2,879 | 1,296 |
| verifyRel | exist | 2,879 | 1,297 |
| logic | exist | 2,879 | 2,879 |
| exist | verifyAttr | 3,633 | 478 |
| verifyRel | verifyAttr | 3,633 | 489 |
| logic | verifyAttr | 3,633 | 3,502 |
| exist | verifyRel | 7,933 | 1,279 |
| verifyAttr | verifyRel | 7,933 | 1,295 |
| logic | verifyRel | 7,933 | 2,970 |
| exist | logic | 15,926 | 12,838 |
| verifyAttr | logic | 15,926 | 6,843 |
| verifyRel | logic | 15,926 | 4,930 |

3. `overlap_contrast_viability.csv`: per directed pair, flag `NO_CONTRAST` when share < 0.05 or > 0.95 on val
   (expected: every pair involving compare; logic -> exist; logic -> verifyAttr), else `OK`.
4. `overlap_confounds.csv`: for every `OK` pair, compare sharing vs non-sharing target questions on: mean program
   length, mean depth, yes ratio, family mix (counts), stratum mix, and blind-baseline accuracy (dev, val). This shows
   what a future question-level transfer analysis must control for. **Do not fit any transfer model.**
5. Figures: question-level share heatmap (source x target, val); confound plot (program length and blind accuracy,
   sharing vs non-sharing, per OK pair).

### 2b.5 Evaluation library (used by every later stage)
Write `gqa_audit/evaluation.py`:
- `load_registry()`, `load_subsets()`; both verify hashes.
- `evaluate(predictions, variant, parts, final=False)`: `predictions` has `question_id` (string) and `pred` in
  {yes, no}, optionally `p_yes`. Returns a tidy table over task, family, stratum and every analysis subset, with:
  accuracy, balanced accuracy, yes-prediction rate, n, and a 95% **cluster-bootstrap CI over imageId** (1,000
  resamples, seed 0). The primary metric per task follows decision H. testdev raises unless `final=True`; with
  `final=True` it reports testdev per stratum and per family only, never a pooled testdev task number (decision L).
- `shortcut_control_table(edges)`: takes rows (source, target, condition, metric, value, ci) and appends
  `value_on_text_hard`, `target_blind_gain_val` and an empty `target_no_image_gain` (filled in Stage 3). Decision J.
- Fail loudly on missing, duplicate or extra question IDs.
Demonstrate the library on two existing "models" for dev and val: the Stage 2 blind predictions and a constant
train_core-majority predictor. Save `demo_eval_blind.csv` and `demo_eval_majority.csv`. Note in the report that the
blind model scores 0 on `text_hard` by construction; this is a correctness check, not a result.

### 2b.6 Report
`STAGE2B_REPORT.md`: preflight, the regression-target table (expected vs actual), the missing-deliverables results,
subset sizes and yes ratios, descriptor vocabulary, the question-level share matrix, the contrast-viability and
confound tables, the demo evaluation, the PASS/FLAG/INFO list, and "Open decisions for the human". Factual only.

## 3. Tests (keep all existing ones)
- `analysis_plan.FROZEN.yaml`: status, hash, regex loaded as a string, no YAML booleans in unexpected places.
- `logic_no_not_cue` regex on toy questions ("not blue" excluded; "knot", "nothing" kept; "isn't" excluded).
- descriptor tokenizer: arguments, IDs and `(-)` never appear; `[neg]` emitted only for `not(` arguments;
  unseen tokens map to `UNSEEN`.
- `evaluate`: balanced accuracy on a toy fixture; cluster bootstrap deterministic with seed 0; testdev refused
  without `final=True`; no pooled testdev number with `final=True`; missing/duplicate IDs raise.
- subset hash stability.
Save the full output to `outputs/stage2b/pytest_report.txt`.

## 4. Final message to me
Preflight result; regression targets (expected vs actual); output paths; the share matrix and viability flags; the
confound summary; the verifyRel within-subset baselines; the structure baseline; anything ambiguous.
