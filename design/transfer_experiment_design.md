# Transfer experiments for multi-task VQA: design proposal (v0.1, not frozen)

Status: PROPOSAL for your decision. Nothing below is frozen or has been run. "Measured" marks numbers I computed from our data; "assumption" marks numbers that depend on values we do not know yet (seed noise, training time).

## 0. What is fixed by earlier stages (do not re-open)
- Five tasks with frozen membership (registry c122aac0...): exist, verifyAttr, verifyRel, compare, logic; train_core / dev / val splits, testdev sealed.
- Decisions H-L: verifyRel primary metric = balanced accuracy on relVerify vs relVerifyCr; subsets `text_hard`, `logic_no_not_cue`; descriptors = operation strings without arguments, IDs or `(-)`; testdev only per stratum/family.
- Evaluation library `gqa_audit.evaluation`; text floors per task (compare 0.498, exist 0.565, logic 0.674, verifyAttr 0.552, verifyRel 0.646 on val).
- Stage 3 (Qwen2.5-VL-3B zero-shot, val): 0.717 / 0.879 / 0.865 / 0.834 / 0.847 (compare / exist / logic / verifyAttr / verifyRel). Scoring must use batch size 1: 7.9 q/s with image, so 2,500 questions take about 5 min and full val about 88 min per model.
- Pending small fixes by you: 4 rows of `paired_differences_3b.csv`; rerun `pytest -q`. A 5-minute re-check on my side is enough.

## 1. Core design: two instruments
| Tier | Model | Role | Why |
|---|---|---|---|
| Probe (main instrument) | Frozen CLIP-type image encoder with cached features + small trainable text/fusion transformer; no GQA pretraining | Full transfer matrices, many seeds, controls, family-level analysis, curricula | A run costs minutes, so seeds and controls are affordable; no GQA contamination |
| Confirmatory | Qwen2.5-VL-3B + LoRA (batch-1 scoring) | Does the probe's picture survive in a strong pretrained VLM? | Closest to the literature (Sachdeva et al. CVPR 2026 fine-tune Qwen-2.5-VL 3B/7B/32B independently per task with LoRA) |
| Optional bridge | SmolVLM-256M/500M or Florence-2-base (0.23B) + LoRA | Same model class as Qwen at lower cost (speed not measured) | Training data not verified for GQA exposure; treat with the same contamination caveat as Qwen |

The probe is only valid if it passes four gates (section 6). If it fails them, the fallback is the bridge model, then a reduced Qwen design.

## 2. Estimands (per target t, source s, target budget b, N_s source questions)
- **B(t,b)**: train on b target questions only.
- **Sequential S(s to t,b)**: train on N_s source questions, then on b target questions.
- **Joint J(s+t,b)**: train on N_s source plus b target questions mixed.
- **Zero-shot cross-task Z(s to t)**: train on s only, test on t.
Fixed by design: every source uses the same N_s (proposed 10,000; the smallest task, compare, has 15,994 train_core questions), drawn stratified by family with the run seed, so source size is not a confound. Target budgets b in {250, 1,000, 4,000} (to be set by the pilot where learning curves are not saturated). The recipe (learning rate, steps per budget) is tuned on dev for B only, then frozen and reused for all arms; this slightly disfavours transfer arms.

## 3. Controls (what makes a "transfer" claim credible)
1. **Placebo source**: N_s questions from a secondary yes/no type outside the pilot (position / location / weather verify). Separates reasoning transfer from learning the yes/no format and answer prior.
2. **Self source**: N_s extra questions from the target task itself. Gives the ceiling of benefit from more same-task data, and the denominator for normalized transfer.
3. **Blank-image replicate** (probe only; primary budget): every arm repeated with images zeroed. Transfer that survives is text/prior transfer.
4. **Shortcut subsets** (decision J): every effect also on `text_hard`, `logic_no_not_cue`, `verifyRel_relation`.
5. **Paired seeds**: same seed gives the same target subset in all arms of a comparison.
6. **Image-disjoint source variant** (robustness): source questions from images absent from the target budget (task-level image Jaccard is 0.16 to 0.42).

## 4. Metrics (ordered by statistical efficiency)
| # | Metric | Definition | Use |
|---|---|---|---|
| M1 | Log-loss gain | NLL(B) minus NLL(arm) on target val (continuous, proper scoring rule) | Most sensitive primary effect; to be confirmed by signal-to-noise in the pilot |
| M2 | AUROC gain | Threshold-free; separates ranking from yes/no bias shift | Guards against "transfer" that is only a prior shift |
| M3 | Primary-metric gain | Accuracy (verifyRel: balanced accuracy on relation subset), threshold fixed at 0 | Interpretable; also a dev-calibrated-threshold variant |
| M4 | Normalized transfer | (arm - B) / (Self - B); placebo-corrected version subtracts the placebo effect | Comparable across tasks and ceilings; analogous in spirit to the Perfection Gap Factor of Sachdeva et al. (I have not verified their exact formula; read the paper before freezing) |
| M5 | Equivalent target examples | Extra target questions that give the same gain, from the fitted learning curve | Interpretable cost unit; only where the curve slope is reliable |
| M6 | Asymmetry and interference | T(s to t) minus T(t to s); change on the source task after sequential training | RQ1 directionality, forgetting |
| M7 | Aggregates | Mean and worst-task normalized gain over the 5 tasks | RQ3 comparisons |
Accuracy has the lowest statistical efficiency because it discards confidence; it is reported, not relied on.

## 5. Statistics and power
- Measured: clustering by image barely matters (design effect 0.91 to 1.14 in Stage 3 CIs), so questions can be treated as nearly independent, but seeds and sampled target subsets must be resampled.
- Evaluation-set error does **not** shrink with more seeds. Detectable effect (80% power, assumption: two models disagree on 10% of questions):

| Evaluation questions | Seed SD (points) | 5 seeds, alpha 0.05 | 5 seeds, Holm over 20 edges |
|---|---|---|---|
| 2,500 | 0.5 | 2.0 | 2.7 |
| 2,500 | 1.0 | 2.5 | 3.5 |
| 2,500 | 2.0 | 4.0 | 5.5 |
| 5,000 | 1.0 | 2.2 | 3.0 |
(points of accuracy; table in `detectable_effect_table.csv`). Consequences: use the probe on full val (2,504 to 15,926 questions per task) and continuous metrics (M1, M2); Qwen can only confirm large effects.
- Pre-register a short list of primary hypotheses; everything else is exploratory with BH/Holm correction and CIs rather than p-values.
- Stability rule for an edge (proposal): same sign in at least 80% of seeds, CI excludes the smallest effect of interest (set from pilot noise), survives on `text_hard`, and exceeds the placebo effect.
- Intervals: hierarchical bootstrap over seeds and images, paired across arms.

## 6. The probe model and its validity gates
Specification (proposal): CLIP ViT-B/16 at 224 px, frozen, patch tokens cached in fp16 (about 0.30 MB per image, about 22 GB for 74,573 images); question encoder initialised from a small pretrained text transformer and trained; 2 to 4 cross-attention fusion layers; one yes/no logit; tens of millions of trainable parameters (estimate). Known limit: a 14x14 grid is coarse for small objects and spatial relations; fallback is a higher-resolution encoder pooled to about 12x12.
Gates, decided on dev in the pilot, before any matrix run:
- G1 uses the image: single-task full-train accuracy at least 0.10 above the text floor on every task.
- G2 no leak: blank-image run falls back to text-floor level.
- G3 not saturated: learning curve rises at least 1 point per doubling between 1k and 4k examples.
- G4 low noise: seed SD at b = 1,000 at most 1.5 points.
(thresholds are my proposals.)

## 7. Experiment sizes (counts from the design; time per run is unmeasured)
- Task-level probe matrix, 5 seeds: 30 source trainings + 525 sequential target phases + 450 joint trainings + 355 for the blank-image replicate = about 1,360 short trainings (about 816 with 3 seeds). Sequential target phases reuse the source checkpoints.
- Family-level probe matrix (RQ2; 14 families with at least 2,500 train_core questions, 182 directed pairs; N_s about 2,000, b about 500, 3 seeds): about 630 short trainings.
- Qwen confirmatory: 5 targets x (B, best and worst probe-predicted source, placebo, self) x 3 seeds = 75 target phases + 18 source trainings; evaluation on target-only subsets (about 5 to 10 min each, about 8 h total) plus training time to be measured.
Feasibility depends on probe run time; the pilot measures it.

## 8. Research questions
- **RQ1 (transfer is measurable, directional, stable):** matrices of M1 to M6 for sequential and joint transfer at three budgets, with placebo and self controls, task level.
- **RQ2 (does operation overlap explain transfer):** three granularities. (a) Task: descriptive only; 8 of 10 task pairs have operation overlap at most 0.026 (measured). (b) Family: 91 pairs, overlap SD 0.34, 35 pairs strictly between 0.05 and 0.95, 42 pairs at exactly 0 (measured, figure). Predictors compared: operation overlap at two token granularities (full operation string and operation head, pre-registered), lexical overlap, image overlap, gradient affinity, representation similarity; mixed model with random effects for source and target. Natural controls: near-identical program profiles with different wording (existThat vs existAttr 1.00; verifyAttr vs verifyAttrK 0.98). (c) Question level: within-question comparison across sources with question and source effects (Stage 2b finding: sharing is almost "has a filter step", so identification comes mainly from logic targets).
- **RQ3 (transfer-guided curricula):** only after RQ1/RQ2; baselines uniform joint, temperature sampling, random orders, difficulty curriculum, PCGrad or CAGrad; metrics M7, area under learning curve, cost including matrix estimation; curriculum derived on dev, scored on val; probe first, Qwen confirms the best one.
- **RQ4 (composition in logic):** hold out operand-pair types in logic training (from the Stage 2 decomposition), train on primitives plus the remaining logic pairs; metric = logic accuracy on held-out pairs and the share of the logic gain recovered without those pairs; exist_composition vs attribute_composition strata; `logic_no_not_cue`.

## 9. Roadmap with gates
| Stage | Content | Gate to pass |
|---|---|---|
| 3.5a | You fix the 4 paired-difference rows and rerun pytest; I re-check (about 5 min) | Corrected rows match my values |
| 3.5b | Feature cache + probe pilot: single-task learning curves, 5 seeds at b = 250 / 1,000 / 4,000, blank-image run, timing; Qwen-LoRA timing pilot (1 task, 1 budget, 2 seeds) | G1 to G4; choice of M1 vs M3 by signal-to-noise on dev |
| 4a | Freeze `transfer_design.FROZEN.yaml`: estimands, budgets, N_s, seeds, controls, primary hypotheses, stability rule, descriptor granularities | Your approval |
| 4b | Probe task-level matrix (RQ1) | Controls behave (self > 0, placebo near 0, shuffled-label source <= 0) |
| 5 | Family-level matrix and predictors (RQ2) | Predictors evaluated by cross-validated rank correlation |
| 6 | Qwen confirmatory (rank agreement with probe on the same edges) | Agreement reported; claims scoped to what agrees |
| 7 | Curricula (RQ3), then Qwen confirmation | Cost-adjusted comparison |
| 8 | Composition (RQ4) | |
| 9 | testdev once, per stratum/family | |

## 10. Main risks (honest assessment)
1. **Power.** Typical transfer effects in the low-data regime may be 1 to 3 points; at 2,500 evaluation questions and Holm correction over 20 edges, many edges will be inconclusive. Mitigation: continuous metrics, full-val probe evaluation, fewer pre-registered primary tests.
2. **External validity.** Probe transfer may not match Qwen's. Mitigation: explicit agreement analysis; scope claims.
3. **Contamination.** Qwen (and likely the small pretrained VLMs) may have seen GQA/Visual Genome; zero-shot Qwen is already 0.72 to 0.88. Transfer in Qwen may be small because the capability is already present; this is a finding, not a failure.
4. **Few tasks.** Five tasks give 20 directed edges; families are nested in tasks, so family-level results need mixed models and are not independent evidence.
5. **Transfer is definition-dependent.** Report sequential, joint and zero-shot, raw and normalized; do not pick one after seeing the matrix.
6. **Placebo is imperfect.** No source is content-free; use more than one placebo if the pilot shows a large placebo effect.

## 11. Decisions needed from you
1. Approve the two-tier design (probe main, Qwen confirmatory, bridge optional)?
2. Probe encoder: CLIP ViT-B/16 224 px (proposal) or a higher-resolution/other encoder?
3. N_s = 10,000; budgets 250/1,000/4,000; 3 seeds first pass, 5 where effects are near the threshold?
4. May I write the Stage 3.5b prompt (feature cache, probe, pilot, timing) and a draft `transfer_design.FROZEN.yaml` for your review (not frozen until the pilot)?
