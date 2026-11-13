# Frozen GQA Stage 2 audit

Source commit: 8755c70f92fbca447f08b6ea10a366796ba77c0b

Registry SHA-256: c122aac0bbb9ed8ad6eaa93843d95df664ba75c767946003e90ff2469c27b451

Config bundle SHA-256: 209ae83ecde8b0ad7d8b3ff757a893db9d0b1eb5ddd9f28ac53edfca5bc51b10

## Frozen hashes

- task_rules: 2f2ce20ebd8ee804f5180cd52280dfbf739ec392a70738552ce0cc6abe05285a
- op_family_map: d49d3f0b71c8c9dbe3c147f066e0c8bd76a15eccdbd2c0363acfbc304eec7942
- answer_families: c5458dcda98ebb63f1c2fb23e37c07baa50d460fe61991bde8857a7ff33bfb6c
- audit_runtime: 0202974f53822911c0a501cef053afbdbc2d5023be123e0cece9c290cb49298a
- frozen_manifest: 88c6701f9e251306c52ec00e3f494769852ed53715f9d8a5e526a4d14284a254

## Applied decisions

- A: Relation-free exist (types.semantic==obj, equal to program R_strict==0) is the primary exist task. The <=50% exclusion cap is explicitly WAIVED for exist (observed 71.9% on train). Analyses are stratified bare vs attribute_conditioned. The unfiltered variant is run side by side.
- B: program_broad and semantic_sensitivity variants are dropped (identical membership to program_strict in Stage 1). program_strict is the rule. types.semantic==obj is kept only as an exact-membership cross-check for exist.
- C: verifyRel keeps all negative types. Co and Cr are reported as separate metric subsets. relVerifyCop (35 train) appears only in pooled metrics.
- D: Logic primary target excludes the single-class types verifyAttrAnd and verifyMaterialAnd (1,301 train). Logic is reported in two strata: exist_composition and attribute_composition. No rebalancing.
- E: position/material/location/weather/place/animal/gender/type/company verify and compare types stay secondary (not in the pilot). Sizes are reported only.
- F: twoSameMaterial and twoSameMaterialC are excluded from compare (family yes ratio 0.379 is outside [0.40,0.60]).
- G: Dev split = 10% of train images (seed 0), chosen so every pilot task has >=1,000 dev questions.

## Integrity and split policy

Input and frozen file hashes are verified. Locked task/stratum regression counts and the exact exist semantic/program membership cross-check must pass before baselines. No rules are adjusted to audit outcomes.

Dev contains 7,214 of 72,140 train images: ceil(10% × image count), sorted image IDs, numpy.default_rng(seed=0), without replacement. No retry or family balancing is applied. The exact list and hash are in dev_images.json.

| split_a | split_b | overlap_images | images_a | images_b |
|---|---|---|---|---|
| train | val | 0 | 72140 | 10234 |
| train | testdev | 0 | 72140 | 398 |
| val | testdev | 0 | 10234 | 398 |

cross_split_references.csv counts self references, original split crossings, the train_core/dev boundary and targets outside the balanced files. An absent balanced target is not counted as a split crossing.

Parquet preserves question IDs as strings. Program depth is the longest number of dependency edges (a dependency-free select has depth 0); missing, cyclic or out-of-range dependencies yield NaN.

Testdev is count-only: no text/program feature cache, model predictions, operand decomposition, answer-ratio analysis or operation/lexical analysis. Only frozen assignments, locked regression counts, registry IDs, and requested image/reference boundary checks use its records.

## Task counts

| variant | split | task | questions | images |
|---|---|---|---|---|
| unfiltered | train_core | exist | 67298 | 32880 |
| unfiltered | train_core | verifyAttr | 31396 | 23501 |
| unfiltered | train_core | verifyRel | 50947 | 27670 |
| unfiltered | train_core | compare | 15994 | 12508 |
| unfiltered | train_core | logic | 101611 | 47130 |
| unfiltered | dev | exist | 7528 | 3693 |
| unfiltered | dev | verifyAttr | 3583 | 2633 |
| unfiltered | dev | verifyRel | 5576 | 3046 |
| unfiltered | dev | compare | 1705 | 1343 |
| unfiltered | dev | logic | 11117 | 5141 |
| unfiltered | val | exist | 10548 | 5175 |
| unfiltered | val | verifyAttr | 4914 | 3659 |
| unfiltered | val | verifyRel | 7933 | 4345 |
| unfiltered | val | compare | 2504 | 1951 |
| unfiltered | val | logic | 15926 | 7389 |
| unfiltered | testdev | exist | 556 | 257 |
| unfiltered | testdev | verifyAttr | 712 | 324 |
| unfiltered | testdev | verifyRel | 769 | 305 |
| unfiltered | testdev | compare | 291 | 198 |
| unfiltered | testdev | logic | 1755 | 385 |
| program_strict | train_core | exist | 18921 | 15779 |
| program_strict | train_core | verifyAttr | 23462 | 18854 |
| program_strict | train_core | verifyRel | 50947 | 27670 |
| program_strict | train_core | compare | 15994 | 12508 |
| program_strict | train_core | logic | 101611 | 47130 |
| program_strict | dev | exist | 2083 | 1762 |
| program_strict | dev | verifyAttr | 2721 | 2129 |
| program_strict | dev | verifyRel | 5576 | 3046 |
| program_strict | dev | compare | 1705 | 1343 |
| program_strict | dev | logic | 11117 | 5141 |
| program_strict | val | exist | 2879 | 2433 |
| program_strict | val | verifyAttr | 3633 | 2927 |
| program_strict | val | verifyRel | 7933 | 4345 |
| program_strict | val | compare | 2504 | 1951 |
| program_strict | val | logic | 15926 | 7389 |
| program_strict | testdev | exist | 162 | 126 |
| program_strict | testdev | verifyAttr | 573 | 294 |
| program_strict | testdev | verifyRel | 769 | 305 |
| program_strict | testdev | compare | 291 | 198 |
| program_strict | testdev | logic | 1755 | 385 |

## Answer balance and strata

| variant | split | task | yes | no | yes_ratio | filter_exclusion_rate |
|---|---|---|---|---|---|---|
| unfiltered | train_core | exist | 33397.0000 | 33901.0000 | 0.4963 | 0.0000 |
| unfiltered | train_core | verifyAttr | 15527.0000 | 15869.0000 | 0.4946 | 0.0000 |
| unfiltered | train_core | verifyRel | 24964.0000 | 25983.0000 | 0.4900 | 0.0000 |
| unfiltered | train_core | compare | 8025.0000 | 7969.0000 | 0.5018 | 0.0000 |
| unfiltered | train_core | logic | 50857.0000 | 50754.0000 | 0.5005 | 0.0000 |
| unfiltered | dev | exist | 3800.0000 | 3728.0000 | 0.5048 | 0.0000 |
| unfiltered | dev | verifyAttr | 1769.0000 | 1814.0000 | 0.4937 | 0.0000 |
| unfiltered | dev | verifyRel | 2813.0000 | 2763.0000 | 0.5045 | 0.0000 |
| unfiltered | dev | compare | 849.0000 | 856.0000 | 0.4979 | 0.0000 |
| unfiltered | dev | logic | 5605.0000 | 5512.0000 | 0.5042 | 0.0000 |
| unfiltered | val | exist | 5272.0000 | 5276.0000 | 0.4998 | 0.0000 |
| unfiltered | val | verifyAttr | 2429.0000 | 2485.0000 | 0.4943 | 0.0000 |
| unfiltered | val | verifyRel | 3885.0000 | 4048.0000 | 0.4897 | 0.0000 |
| unfiltered | val | compare | 1206.0000 | 1298.0000 | 0.4816 | 0.0000 |
| unfiltered | val | logic | 8181.0000 | 7745.0000 | 0.5137 | 0.0000 |
| program_strict | train_core | exist | 9419.0000 | 9502.0000 | 0.4978 | 0.7188 |
| program_strict | train_core | verifyAttr | 11595.0000 | 11867.0000 | 0.4942 | 0.2527 |
| program_strict | train_core | verifyRel | 24964.0000 | 25983.0000 | 0.4900 | 0.0000 |
| program_strict | train_core | compare | 8025.0000 | 7969.0000 | 0.5018 | 0.0000 |
| program_strict | train_core | logic | 50857.0000 | 50754.0000 | 0.5005 | 0.0000 |
| program_strict | dev | exist | 1067.0000 | 1016.0000 | 0.5122 | 0.7233 |
| program_strict | dev | verifyAttr | 1341.0000 | 1380.0000 | 0.4928 | 0.2406 |
| program_strict | dev | verifyRel | 2813.0000 | 2763.0000 | 0.5045 | 0.0000 |
| program_strict | dev | compare | 849.0000 | 856.0000 | 0.4979 | 0.0000 |
| program_strict | dev | logic | 5605.0000 | 5512.0000 | 0.5042 | 0.0000 |
| program_strict | val | exist | 1463.0000 | 1416.0000 | 0.5082 | 0.7271 |
| program_strict | val | verifyAttr | 1791.0000 | 1842.0000 | 0.4930 | 0.2607 |
| program_strict | val | verifyRel | 3885.0000 | 4048.0000 | 0.4897 | 0.0000 |
| program_strict | val | compare | 1206.0000 | 1298.0000 | 0.4816 | 0.0000 |
| program_strict | val | logic | 8181.0000 | 7745.0000 | 0.5137 | 0.0000 |

| variant | split | task | stratum | questions | yes_ratio |
|---|---|---|---|---|---|
| unfiltered | train_core | exist | bare | 10148 | 0.4914 |
| unfiltered | train_core | exist | attribute_conditioned | 8773 | 0.5052 |
| unfiltered | train_core | exist | relational_unfiltered_only | 48377 | 0.4956 |
| unfiltered | train_core | logic | exist_composition | 80111 | 0.5022 |
| unfiltered | train_core | logic | attribute_composition | 21500 | 0.4943 |
| unfiltered | dev | exist | bare | 1137 | 0.5075 |
| unfiltered | dev | exist | attribute_conditioned | 946 | 0.5180 |
| unfiltered | dev | exist | relational_unfiltered_only | 5445 | 0.5019 |
| unfiltered | dev | logic | exist_composition | 8876 | 0.5059 |
| unfiltered | dev | logic | attribute_composition | 2241 | 0.4975 |
| unfiltered | val | exist | bare | 1582 | 0.5000 |
| unfiltered | val | exist | attribute_conditioned | 1297 | 0.5181 |
| unfiltered | val | exist | relational_unfiltered_only | 7669 | 0.4967 |
| unfiltered | val | logic | exist_composition | 12515 | 0.5146 |
| unfiltered | val | logic | attribute_composition | 3411 | 0.5104 |
| program_strict | train_core | exist | bare | 10148 | 0.4914 |
| program_strict | train_core | exist | attribute_conditioned | 8773 | 0.5052 |
| program_strict | train_core | exist | relational_unfiltered_only | 0 |  |
| program_strict | train_core | logic | exist_composition | 80111 | 0.5022 |
| program_strict | train_core | logic | attribute_composition | 21500 | 0.4943 |
| program_strict | dev | exist | bare | 1137 | 0.5075 |
| program_strict | dev | exist | attribute_conditioned | 946 | 0.5180 |
| program_strict | dev | exist | relational_unfiltered_only | 0 |  |
| program_strict | dev | logic | exist_composition | 8876 | 0.5059 |
| program_strict | dev | logic | attribute_composition | 2241 | 0.4975 |
| program_strict | val | exist | bare | 1582 | 0.5000 |
| program_strict | val | exist | attribute_conditioned | 1297 | 0.5181 |
| program_strict | val | exist | relational_unfiltered_only | 0 |  |
| program_strict | val | logic | exist_composition | 12515 | 0.5146 |
| program_strict | val | logic | attribute_composition | 3411 | 0.5104 |

Family statistics are in family_stats.csv. Empty relational exist families under program_strict are recorded as empty, not as nonempty single-class families.

## Question-only baseline

Each task/variant fits TF-IDF word 1–2 grams (min_df=2) and logistic regression (C=1, max_iter=2000) on train_core question strings only. Detailed types, programs, task and family labels never enter the feature matrix. Unit accuracies use the pooled task model. Majority labels come from the corresponding train_core task/family/stratum/subset, not from evaluation answers.

| variant | task | questions | accuracy | majority_accuracy | gain_over_majority |
|---|---|---|---|---|---|
| unfiltered | exist | 10548 | 0.5642 | 0.5002 | 0.0640 |
| unfiltered | verifyAttr | 4914 | 0.5541 | 0.5057 | 0.0484 |
| unfiltered | verifyRel | 7933 | 0.7136 | 0.5103 | 0.2033 |
| unfiltered | compare | 2504 | 0.4984 | 0.4816 | 0.0168 |
| unfiltered | logic | 15926 | 0.6736 | 0.5137 | 0.1599 |
| program_strict | exist | 2879 | 0.5651 | 0.4918 | 0.0733 |
| program_strict | verifyAttr | 3633 | 0.5522 | 0.5070 | 0.0451 |
| program_strict | verifyRel | 7933 | 0.7136 | 0.5103 | 0.2033 |
| program_strict | compare | 2504 | 0.4984 | 0.4816 | 0.0168 |
| program_strict | logic | 15926 | 0.6736 | 0.5137 | 0.1599 |

## verifyRel Co/Cr diagnostics

relVerifyCop appears only in pooled metrics. Co/Cr subset class priors differ: raw accuracy and gain over the subset's training-majority baseline are both reported. A dash pointer is a program annotation observation and by itself does not prove visual object absence.

| variant | split | unit | questions | accuracy | majority_accuracy | gain_over_majority |
|---|---|---|---|---|---|---|
| unfiltered | dev | verifyRel_Cr | 3556 | 0.6251 | 0.7911 | -0.1659 |
| unfiltered | dev | verifyRel_Co | 4829 | 0.7571 | 0.5825 | 0.1746 |
| unfiltered | val | verifyRel_Cr | 4881 | 0.6183 | 0.7959 | -0.1776 |
| unfiltered | val | verifyRel_Co | 6931 | 0.7523 | 0.5605 | 0.1917 |
| program_strict | dev | verifyRel_Cr | 3556 | 0.6251 | 0.7911 | -0.1659 |
| program_strict | dev | verifyRel_Co | 4829 | 0.7571 | 0.5825 | 0.1746 |
| program_strict | val | verifyRel_Cr | 4881 | 0.6183 | 0.7959 | -0.1776 |
| program_strict | val | verifyRel_Co | 6931 | 0.7523 | 0.5605 | 0.1917 |

| split | detailed_type | questions | verify_rel_dash_rate | any_program_dash_rate |
|---|---|---|---|---|
| dev | relVerify | 2813 | 0.0014 | 0.0014 |
| dev | relVerifyCo | 2016 | 1.0000 | 1.0000 |
| dev | relVerifyCop | 4 | 0.0000 | 0.0000 |
| dev | relVerifyCr | 743 | 0.0000 | 0.0000 |
| train_core | relVerify | 24964 | 0.0016 | 0.0016 |
| train_core | relVerifyCo | 19710 | 1.0000 | 1.0000 |
| train_core | relVerifyCop | 31 | 0.0000 | 0.0000 |
| train_core | relVerifyCr | 6242 | 0.0000 | 0.0000 |
| val | relVerify | 3885 | 0.0036 | 0.0036 |
| val | relVerifyCo | 3046 | 1.0000 | 1.0000 |
| val | relVerifyCop | 6 | 0.0000 | 0.0000 |
| val | relVerifyCr | 996 | 0.0000 | 0.0000 |

## Logic decomposition

| variant | split | questions | both_exist_count | both_exist_share | unparseable_logic_count |
|---|---|---|---|---|---|
| unfiltered | train_core | 101611 | 80111.0000 | 0.7884 | 0.0000 |
| unfiltered | dev | 11117 | 8876.0000 | 0.7984 | 0.0000 |
| unfiltered | val | 15926 | 12515.0000 | 0.7858 | 0.0000 |
| program_strict | train_core | 101611 | 80111.0000 | 0.7884 | 0.0000 |
| program_strict | dev | 11117 | 8876.0000 | 0.7984 | 0.0000 |
| program_strict | val | 15926 | 12515.0000 | 0.7858 | 0.0000 |

Terminal operand families describe reasoning, not task labels. Shared and nested subprograms keep their complete dependency indices. See logic_decomposition.csv and logic_operand_pairs.csv.

## Pre-registered checks

| check | status | waived | rows |
|---|---|---|---|
| blind_accuracy_gain | FLAG | False | 4 |
| blind_accuracy_gain | PASS | False | 6 |
| depth_nan_rate | PASS | False | 30 |
| family_has_both_answers | INFO | False | 3 |
| family_has_both_answers | PASS | False | 111 |
| filter_exclusion_rate | FLAG | True | 3 |
| filter_exclusion_rate | PASS | False | 24 |
| filter_exclusion_rate | PASS | True | 3 |
| original_split_image_disjointness | PASS | False | 3 |
| task_size | PASS | False | 30 |
| task_yes_ratio | PASS | False | 30 |
| testdev_size_info_only | INFO | False | 10 |
| unparseable_logic_rate | PASS | False | 6 |

The observed exist exclusion rate remains FLAG with the explicit Decision A waiver. Testdev's 300-question value is informational under the frozen rules. Complete results are in preregistered_checks.csv.

### Unwaived flags

| check | variant | split | task | unit | observed | threshold |
|---|---|---|---|---|---|---|
| blind_accuracy_gain | unfiltered | val | verifyRel |  | 0.2033 | <= 0.15 |
| blind_accuracy_gain | unfiltered | val | logic |  | 0.1599 | <= 0.15 |
| blind_accuracy_gain | program_strict | val | verifyRel |  | 0.2033 | <= 0.15 |
| blind_accuracy_gain | program_strict | val | logic |  | 0.1599 | <= 0.15 |

## Manual review and secondary sizes

manual_review_sample.csv has up to 25 retained train questions per task/variant and up to 25 removed questions per filtered task, without replacement. Review allocation cycles equally across families up to capacity. This does not rebalance training. human_ok is empty. Zero available removed questions are reported in manual_sample_availability.csv. Secondary types have sizes only in secondary_sizes.csv.

## Figures

### task_sizes

![task_sizes](figures/task_sizes.png)

[PDF](figures/task_sizes.pdf)

### answer_balance

![answer_balance](figures/answer_balance.png)

[PDF](figures/answer_balance.pdf)

### program_length_depth

![program_length_depth](figures/program_length_depth.png)

[PDF](figures/program_length_depth.pdf)

### operation_profile

![operation_profile](figures/operation_profile.png)

[PDF](figures/operation_profile.pdf)

### unfiltered_image_coverage

![unfiltered_image_coverage](figures/unfiltered_image_coverage.png)

[PDF](figures/unfiltered_image_coverage.pdf)

### unfiltered_image_jaccard

![unfiltered_image_jaccard](figures/unfiltered_image_jaccard.png)

[PDF](figures/unfiltered_image_jaccard.pdf)

### unfiltered_lexical_cosine

![unfiltered_lexical_cosine](figures/unfiltered_lexical_cosine.png)

[PDF](figures/unfiltered_lexical_cosine.pdf)

### unfiltered_vocabulary_jaccard

![unfiltered_vocabulary_jaccard](figures/unfiltered_vocabulary_jaccard.png)

[PDF](figures/unfiltered_vocabulary_jaccard.pdf)

### unfiltered_operation_cosine

![unfiltered_operation_cosine](figures/unfiltered_operation_cosine.png)

[PDF](figures/unfiltered_operation_cosine.pdf)

### program_strict_image_coverage

![program_strict_image_coverage](figures/program_strict_image_coverage.png)

[PDF](figures/program_strict_image_coverage.pdf)

### program_strict_image_jaccard

![program_strict_image_jaccard](figures/program_strict_image_jaccard.png)

[PDF](figures/program_strict_image_jaccard.pdf)

### program_strict_lexical_cosine

![program_strict_lexical_cosine](figures/program_strict_lexical_cosine.png)

[PDF](figures/program_strict_lexical_cosine.pdf)

### program_strict_vocabulary_jaccard

![program_strict_vocabulary_jaccard](figures/program_strict_vocabulary_jaccard.png)

[PDF](figures/program_strict_vocabulary_jaccard.pdf)

### program_strict_operation_cosine

![program_strict_operation_cosine](figures/program_strict_operation_cosine.png)

[PDF](figures/program_strict_operation_cosine.pdf)

### blind_baselines

![blind_baselines](figures/blind_baselines.png)

[PDF](figures/blind_baselines.pdf)

### logic_operand_pairs

![logic_operand_pairs](figures/logic_operand_pairs.png)

[PDF](figures/logic_operand_pairs.pdf)

### filter_exclusion_rates

![filter_exclusion_rates](figures/filter_exclusion_rates.png)

[PDF](figures/filter_exclusion_rates.pdf)

### verifyrel_Co_Cr_baselines

![verifyrel_Co_Cr_baselines](figures/verifyrel_Co_Cr_baselines.png)

[PDF](figures/verifyrel_Co_Cr_baselines.pdf)

## Open decisions for the human

- Review manual examples and record human_ok.
- Record how the unwaived audit flags will be handled in subsequent transfer experiments; this audit does not change the frozen registry.
- Review Co/Cr observations and baseline gains before assigning causal shortcut interpretations.

## Reproduce

```bash
conda activate datpt_mtl
python -m pytest -q
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m gqa_audit stage2 --questions data/gqa/questions
python -m gqa_audit.verify_stage2 --questions data/gqa/questions
```
