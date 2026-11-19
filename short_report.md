# Defining and Measuring Directed Task Transfer in Multi-Task Visual Question Answering

## 1. Research Problem and Questions

Multi-task learning (MTL) can exploit shared knowledge across related visual question answering (VQA) tasks, but jointly training arbitrary tasks does not guarantee positive transfer. Before designing a task grouping or curriculum, two questions must be addressed: **what constitutes a distinct reasoning task**, and **which tasks actually benefit from knowledge learned on other tasks**?

The project's **primary research question** is:

> **When the number of target-task training examples is held fixed, does adding labeled data from a source task reliably improve target-task performance relative to target-only learning?**

This question is grounded in a broader task-definition problem. A VQA question has a **task-level label** (e.g., attribute verification) but may require several **operation-level reasoning steps** (e.g., identifying an object, following a relation, and verifying an attribute). Consequently, different task groups may share underlying operations without being identical tasks. The study is organized around three related questions:

- **RQ1 — Task definition:** How can annotated reasoning types and programs be used to define consistent VQA task groups while distinguishing the evaluated task from its component reasoning operations?
- **RQ2 — Directed transfer:** Which source-to-target task combinations yield reliable improvements or degradation under a fixed target-data budget, and how do sequential and joint training differ?
- **RQ3 — Operation-level explanation (future investigation):** To what extent can overlapping reasoning operations explain or predict measured transfer between tasks?

**Scope:** The completed experiments operationalize RQ1 and measure RQ2. They **do not directly establish** the explanatory relationship proposed in RQ3 or test an automatically selected MTL curriculum.

## 2. Proposed Method

### 2.1. Task definition and reasoning-operation separation

The study uses binary (`yes`/`no`) questions from **GQA balanced**, avoiding differences in answer vocabularies across task groups. GQA detailed types define five research tasks:

| Task | GQA type | Capability assessed |
|---|---|---|
| Existence | `exist` | Determine whether a specified object exists |
| Attribute verification | `verifyAttr` | Verify an object's attribute |
| Relation verification | `verifyRel` | Verify a relation between objects |
| Comparison | `compare` | Compare attributes of objects |
| Logical reasoning | `logic` | Combine multiple conditions |

The `program_strict` protocol requires reasoning programs, removes `relate`-containing questions from existence, attribute verification, and comparison, and excludes selected strongly label-imbalanced families. **Reasoning programs and task identifiers are used for grouping, filtering, and analysis only**, never as model inputs. This is a controlled taxonomy based on existing GQA annotations, **not yet a newly learned, cross-dataset-validated operation-based taxonomy**. Shared operations motivate transfer hypotheses but are not assumed to prove task compatibility.

### 2.2. Shared VQA probe and transfer measurement

The final transfer experiment uses **frozen CLIP ViT-L/14 visual and text encoders**. Image tokens (257 × 1,024) and text representations (768 dimensions) are projected to width 512, combined with a `[FUS]` token and modality embeddings, and processed by a four-layer, eight-head Transformer fusion module. One shared binary head predicts `yes` or `no`, with approximately **13.53M trainable probe parameters**. An earlier ViT-B/16 probe and **Qwen2.5-VL-3B-Instruct** are used for learnability and image-dependence checks; Qwen is **not** used to construct the final transfer matrix.

For source task $S$, target task $T$, regime $A$, and seed $r$, the directed transfer effect is:

$$
\Delta_A(S\!\rightarrow\!T,r) = M_T\!\left(f_{A(S\rightarrow T,r)}\right) - M_T\!\left(f_{\mathrm{Base}(T,r)}\right),\qquad A\in\{\mathrm{Seq},\mathrm{Joint}\}.
$$

Here $M_T$ is the target-task evaluation metric and $\Delta$ is measured in **percentage points (pp)**. Every intervention is compared with a target-only baseline using the **same target sample and seed**:

- **Target-only:** Train on target examples alone.
- **Sequential (Seq):** Train on source examples, then fine-tune on target examples with a reset optimizer and schedule.
- **Joint:** Train from scratch on pooled source and target examples using one shared model.

The five tasks produce **20 directed source-target pairs**, each tested under Seq and Joint. Additional **same-group**, **out-of-group**, and **shuffled-label** controls help distinguish potentially meaningful transfer from generic effects of additional training data. These comparisons measure *training-regime effects*: without compute-matched controls, they cannot isolate semantic knowledge transfer from extra optimizer updates.

## 3. Experimental Setup

The strict-filtered GQA data are divided by **image ID**, preventing the same image from appearing in both `train_core` and the internal `dev` set. A fixed seed (0) allocates 10% of original training images to `dev`. The original validation split is used for separate reference analyses; **the final transfer map is evaluated on `dev`**, while `testdev` is not used for model evaluation.

| Group | Train core | Dev | Validation |
|---|---:|---:|---:|
| Existence | 18,921 | 2,083 | 2,879 |
| Attribute verification | 23,462 | 2,721 | 3,633 |
| Relation verification | 50,947 | 5,576 | 7,933 |
| Comparison | 15,994 | 1,705 | 2,504 |
| Logical reasoning | 101,611 | 11,117 | 15,926 |
| **Total** | **210,935** | **23,202** | **32,875** |

The final L/14 matrix uses **10,000 source** and **1,000 target** questions per directed pair, with seeds **1000, 1001, 1002**. Target-only models train for **10 epochs**; Seq performs **10 source + 10 target epochs**; Joint performs **10 epochs on pooled data**. The shared recipe uses AdamW ($10^{-4}$ learning rate), batch size 64, cosine decay, 5% warmup, dropout 0.1, gradient clipping at 1, and BCE-with-logits loss.

**Primary metric:** accuracy for four groups; **balanced accuracy** for relation verification on the predefined `verifyRel_relation` subset, which is locally label-imbalanced. Log-loss and AUROC are secondary diagnostics. Paired 95% confidence intervals use a **hierarchical bootstrap (2,000 replicates)** over seeds and image clusters. To qualify as *supportive*, an effect must exceed **+1 pp throughout its CI**, have a positive sign in all three seeds, pass Benjamini–Hochberg-adjusted significance ($p\leq0.05$), and satisfy the predefined control and hard-question checks. *Harmful* effects face analogous criteria below **−1 pp**. The final analysis remains **exploratory**, not independently confirmed on held-out seeds and validation data.

## 4. Results and Discussion

### 4.1. Measurement-model validity and learnability

The original **CLIP B/16** probe exhibits limited visual grounding: when trained on full target data, real images improve over blank-image training for existence (**+5.38 pp**) and logic (**+6.24 pp**), but not for attribute verification (**−0.88 pp**), relation verification (**−1.38 pp**), or comparison (**−2.79 pp**). Upgrading to **CLIP L/14** does not consistently resolve the weakness; its 1,000-example target-only scores on `dev` remain **51.39%** for attribute verification and **49.64%** for comparison. The full L/14 quality-validation suite was not rerun.

In contrast, **Qwen2.5-VL-3B-Instruct** achieves **71.73%** zero-shot comparison accuracy *with images* versus **50.60%** *without images* on validation. In a **single-task**, two-seed comparison LoRA pilot, mean `dev` accuracy reaches **75.37%** with 1,000 examples and **76.83%** with 4,000, compared with **72.14%** zero-shot accuracy on that same `dev` split. Thus, comparison is learnable by a stronger VLM; near-chance CLIP probe performance cannot establish that comparison lacks useful cross-task relationships. These Qwen experiments **do not test MTL transfer**.

### 4.2. Directed transfer map (CLIP L/14)

Each off-diagonal cell below shows **Seq / Joint mean transfer effects (pp)** on `dev`, measured against paired target-only baselines. Rows are **source tasks**; columns are **target tasks**.

| Source ↓ / Target → | Exist | Attribute | Relation | Compare | Logic |
|---|---:|---:|---:|---:|---:|
| **Exist** | — | −0.87 / −0.61 | −1.85 / −0.44 | +1.29 / +1.13 | +0.40 / −0.85 |
| **Attribute** | −1.14 / −2.19 | — | +0.24 / +0.05 | +1.72 / +0.49 | −1.35 / −1.73 |
| **Relation** | −0.22 / −2.45 | −1.24 / −0.10 | — | +1.04 / +1.52 | −0.69 / −1.94 |
| **Compare** | −1.44 / −1.55 | −0.83 / −1.30 | −0.24 / −0.62 | — | −1.73 / −1.51 |
| **Logic** | +0.78 / −1.04 | −1.38 / −1.41 | −0.47 / −2.17 | +0.18 / +0.16 | — |

Across **40 cross-task effects**, **12 means are positive and 28 negative**, but **all 40 are classified as *insufficient evidence*** under the prespecified criteria. For example, Attribute → Comparison under Seq has a mean effect of **+1.72 pp** (95% CI **[−0.66, +4.18]**), so its CI does not establish an improvement above +1 pp. Relation → Existence under Joint is **−2.45 pp** (95% CI **[−5.03, −0.05]**), which does not establish harm beyond −1 pp. Transfer can appear **direction-dependent** and **regime-dependent**, but these observed differences are not yet statistically confirmed task relationships.

### 4.3. Controls, interpretation, and research status

Adding **same-group** data gives clearer mean gains for existence (**+4.26 / +4.93 pp**, Seq/Joint), relation verification (**+4.24 / +5.68 pp**), and logic (**+7.75 / +8.81 pp**). Such gains show that the probe can benefit from additional relevant data, even when evidence for *cross-group* transfer is inconclusive.

The completed study supports the following interpretation:

- **RQ1:** A reproducible five-task taxonomy and operation-aware filtering protocol have been established, but the proposed broader framework has **not been validated across datasets**.
- **RQ2:** All directed pairs have been measured under two regimes, but **no supportive or harmful cross-task edge has been confirmed**.
- **RQ3:** Whether shared reasoning operations explain or predict transfer **remains untested** by the reported transfer matrix.

Major limitations include weak CLIP probe quality on some tasks; only **one target budget and three seeds**; additional computation in Seq and Joint relative to target-only; missing L/14 blank-image and image-disjoint-source transfer controls; and no independent confirmation of candidate edges. The pairwise matrix also does **not** evaluate three-task interactions, joint training across all five tasks, or any **transfer-guided curriculum**.

**Conclusion.** The contribution established so far is a controlled, auditable **task-definition and directed-transfer measurement framework** for binary VQA, **not a demonstrated transfer-guided curriculum algorithm**. Future work should first validate model learnability and image grounding, then confirm selected transfer directions using computation-matched controls, stronger models, and held-out evaluation. Only after reliable edges are established can operation-level analysis and transfer-informed MTL grouping or curricula be tested meaningfully.

---

*Detailed sources: [Original project report](https://github.com/Datyth/Transfer-MTL/blob/main/PROJECT_OVERVIEW_EXPERIMENT_REPORT.md), [CLIP L/14 transfer results](https://github.com/Datyth/Transfer-MTL/blob/main/gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/edges.csv), and [Frozen experimental design](https://github.com/Datyth/Transfer-MTL/blob/main/gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/design.FROZEN.json).*
