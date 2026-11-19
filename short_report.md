# Transfer-Guided Multi-Task Learning for Visual Question Answering

*Concise experimental report | Proposed method, setup, and results*

## 1. Proposed Method

This study investigates **directed knowledge transfer between reasoning tasks** in binary visual question answering (VQA). The central question is whether adding examples from a *source* task improves performance on a *target* task when the number of target training examples is held fixed. All tasks share the same `yes`/`no` label space, reducing the influence of differences in answer vocabularies.

Questions from **GQA balanced** are organized into five groups based on their annotated reasoning type: **existence** (`exist`), **attribute verification** (`verifyAttr`), **relation verification** (`verifyRel`), **comparison** (`compare`), and **logical reasoning** (`logic`). Reasoning programs are used only for task definition and analysis; the model receives the image and original English question, **not** task IDs or program annotations. The strict filtering protocol removes selected relation-containing questions and strongly label-imbalanced question families to reduce task overlap and shortcut effects.

### 1.1. Shared VQA probe

The main measurement model uses **frozen CLIP ViT-L/14 image and text encoders**. The image encoder provides 257 tokens of dimension 1,024, and the text encoder provides 768-dimensional question features. Both modalities are projected into a shared 512-dimensional space, combined with modality embeddings and a `[FUS]` token, and passed through a **four-layer pre-LN Transformer** (8 attention heads, feed-forward width 2,048). A single binary prediction head at `[FUS]` outputs a `yes` logit. No task-specific head is used. The resulting model has approximately **13.53 million trainable parameters** in the fusion/probe configuration. An earlier CLIP ViT-B/16 variant is used for preliminary validity checks.

### 1.2. Directed transfer measurement

For each distinct source–target pair $(S,T)$, transfer is measured against a target-only model trained with the **same target sample and random seed**:

$$
\Delta_A(S\rightarrow T)=M_T(f_{A(S\rightarrow T)})-M_T(f_{\mathrm{Base}(T)}),\qquad A\in\{\mathrm{Seq},\mathrm{Joint}\}.
$$

Here, $M_T$ denotes target-task performance, and $\Delta$ is reported in **percentage points (pp)**. The two regimes examine different ways of using source information:

- **Sequential transfer (Seq):** train on source examples first, then fine-tune the resulting model on target examples with a fresh optimizer and learning-rate schedule.
- **Joint training (Joint):** train a newly initialized model on the union of source and target examples with shared parameters and no task-specific loss weighting.

The design covers **20 directed pairs** (five sources × four other targets) in each regime. Three diagnostic controls use additional **same-group** examples, **out-of-group** questions, or **shuffled source labels**. These controls test whether observed gains are specific to source-task information rather than simply reflecting additional data or optimization. The directed map is intended to inform later task grouping or curriculum design; **a learned curriculum itself has not yet been tested**.

## 2. Experimental Setup

### 2.1. Dataset and evaluation

The project uses GQA balanced with strict binary-question filtering (`program_strict`). The original training images are split by image ID into **90% `train_core` and 10% internal `dev`**, using seed 0. All questions about one image stay in the same split to avoid image-level leakage. The original validation split is retained for separate reference/confirmation analyses, and `testdev` is **not used for model evaluation** in the reported transfer experiments.

| Task group | Train core | Dev | Validation |
|---|---:|---:|---:|
| Existence | 18,921 | 2,083 | 2,879 |
| Attribute verification | 23,462 | 2,721 | 3,633 |
| Relation verification | 50,947 | 5,576 | 7,933 |
| Comparison | 15,994 | 1,705 | 2,504 |
| Logical reasoning | 101,611 | 11,117 | 15,926 |
| **Total** | **210,935** | **23,202** | **32,875** |

The primary metric is **accuracy** for four groups and **balanced accuracy** for relation verification, evaluated specifically on the `verifyRel_relation` subset to avoid a misleading majority-label advantage. Log-loss and AUROC are supplementary diagnostics.

### 2.2. Training protocol and statistical criteria

The final CLIP L/14 experiment uses **1,000 target questions, 10,000 source questions**, and three seeds (1000, 1001, 1002). The target-only baseline trains for **10 epochs**. Seq uses **10 source epochs followed by 10 target epochs**; Joint uses **10 epochs on the pooled data**. The common recipe is AdamW (learning rate $10^{-4}$), batch size 64, cosine schedule with 5% warmup, dropout 0.1, gradient clipping at 1, binary cross-entropy with logits, and bf16 autocast. The encoders remain frozen.

Reported transfer estimates are paired by seed and target sample. **Hierarchical paired bootstrap** confidence intervals (2,000 replicates) resample seeds and image clusters. A *supportive* edge must have a 95% CI entirely above **+1 pp**, positive effects in all three seeds (the ≥80% rule), Benjamini–Hochberg-adjusted $p\leq 0.05$, and satisfy the prespecified controls and hard-question criteria. *Harmful* edges face analogous criteria below **−1 pp**. The final matrix is **exploratory on `dev`**, not a held-out confirmatory evaluation.

## 3. Results and Discussion

### 3.1. Model validity and task learnability

The earlier CLIP B/16 probe had limited image-grounding ability: at full training size, real images improved performance over blank-image training by **+5.38 pp** for existence and **+6.24 pp** for logic, but not for attribute verification (**−0.88 pp**), relation verification (**−1.38 pp**), or comparison (**−2.79 pp**). This makes weak or negative transfer difficult to interpret as evidence of incompatibility between reasoning tasks.

The CLIP L/14 variant did not consistently improve 1,000-example target-only baselines. Its mean `dev` scores were **53.14%** (existence), **51.39%** (attribute), **52.86%** (relation), **49.64%** (comparison), and **54.79%** (logic). In contrast, **Qwen2.5-VL-3B-Instruct** achieved substantially better zero-shot performance with images on validation, including **71.73%** for comparison versus **50.60%** without images. A separate **single-task** Qwen LoRA pilot on comparison achieved **75.37%** mean `dev` accuracy with 1,000 examples and **76.83%** with 4,000 (two seeds each). These results support task learnability with a stronger VLM, but **do not demonstrate inter-task transfer**.

### 3.2. Complete directed transfer map (CLIP L/14)

Each cell is the mean change in target `dev` score, in **pp**, relative to the paired target-only baseline (three seeds). Source and target directions are not interchangeable.

| Source → target | Seq Δ (pp) | Joint Δ (pp) |
|---|---:|---:|
| Existence → Attribute | −0.87 | −0.61 |
| Existence → Relation | −1.85 | −0.44 |
| Existence → Comparison | +1.29 | +1.13 |
| Existence → Logic | +0.40 | −0.85 |
| Attribute → Existence | −1.14 | −2.19 |
| Attribute → Relation | +0.24 | +0.05 |
| Attribute → Comparison | +1.72 | +0.49 |
| Attribute → Logic | −1.35 | −1.73 |
| Relation → Existence | −0.22 | −2.45 |
| Relation → Attribute | −1.24 | −0.10 |
| Relation → Comparison | +1.04 | +1.52 |
| Relation → Logic | −0.69 | −1.94 |
| Comparison → Existence | −1.44 | −1.55 |
| Comparison → Attribute | −0.83 | −1.30 |
| Comparison → Relation | −0.24 | −0.62 |
| Comparison → Logic | −1.73 | −1.51 |
| Logic → Existence | +0.78 | −1.04 |
| Logic → Attribute | −1.38 | −1.41 |
| Logic → Relation | −0.47 | −2.17 |
| Logic → Comparison | +0.18 | +0.16 |

Among **40 cross-task effects**, **12** mean differences are positive and **28** are negative. However, **all 40 are classified as having insufficient evidence** under the prespecified criteria. For example, Attribute → Comparison under Seq reaches **+1.72 pp**, but its 95% CI is **[−0.66, +4.18] pp**, which does not establish a gain above the +1 pp threshold. Relation → Existence under Joint reaches **−2.45 pp** with CI **[−5.03, −0.05] pp**, but does not establish harm of at least −1 pp. Positive cells therefore identify candidates for follow-up, **not confirmed transfer relationships**.

### 3.3. Controls, limitations, and conclusion

Adding **same-group** data provides clearer improvements than cross-group transfer for several targets: Seq/Joint effects are **+4.26/+4.93 pp** for existence, **+4.24/+5.68 pp** for relation verification, and **+7.75/+8.81 pp** for logic. This shows that the probe can benefit from additional relevant examples even when cross-group gains remain uncertain.

The current evidence is constrained by a weak CLIP measurement probe on some groups, **only one target budget and three seeds**, and the absence of complete L/14 image-grounding checks, image-disjoint-source controls, and independent validation of candidate transfer edges. Joint training also processes more examples and performs more optimizer updates than the target-only baseline, so measured effects cannot be attributed uniquely to semantic knowledge sharing.

**Conclusion.** The project establishes an auditable task taxonomy and a controlled method for measuring directed transfer in binary VQA. Its full 20-pair CLIP L/14 map is complete but **does not yet confirm any supportive or harmful cross-task relation**. The next step is to validate probe quality and test a small set of candidate directions with stronger visual models, matched computational budgets, stronger controls, and held-out confirmation before designing transfer-guided curricula.

---

*Source and detailed records: [full project report](https://github.com/Datyth/Transfer-MTL/blob/main/PROJECT_OVERVIEW_EXPERIMENT_REPORT.md), [CLIP L/14 edge results](https://github.com/Datyth/Transfer-MTL/blob/main/gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/edges.csv), and [frozen experimental design](https://github.com/Datyth/Transfer-MTL/blob/main/gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/design.FROZEN.json).*
