# Stage 1 summary — proposal only

No task rules have been frozen. Review all three `.PROPOSED.yaml` files before Stage 2.

## Intended detailed-type families

| Task | Detailed type | Train | Val | Testdev | Total | Flag |
|---|---|---:|---:|---:|---:|---|
| exist | `exist` | 5,564 | 791 | 28 | 6,383 |  |
| logic | `existAnd` | 10,683 | 1,551 | 48 | 12,282 | AMBIGUOUS |
| logic | `existAndC` | 10,753 | 1,395 | 56 | 12,204 | AMBIGUOUS |
| exist | `existAttr` | 1,410 | 199 | 17 | 1,626 |  |
| exist | `existAttrC` | 1,418 | 183 | 12 | 1,613 |  |
| exist | `existAttrNot` | 1,513 | 210 | 15 | 1,738 |  |
| exist | `existAttrNotC` | 1,440 | 175 | 19 | 1,634 |  |
| logic | `existAttrOr` | 8,378 | 1,189 | 66 | 9,633 | AMBIGUOUS |
| logic | `existAttrOrC` | 7,958 | 1,125 | 97 | 9,180 | AMBIGUOUS |
| exist | `existC` | 5,721 | 791 | 29 | 6,541 |  |
| exist | `existMaterial` | 179 | 19 | 2 | 200 |  |
| exist | `existMaterialC` | 165 | 21 | 0 | 186 |  |
| exist | `existMaterialNot` | 210 | 28 | 2 | 240 |  |
| exist | `existMaterialNotC` | 189 | 31 | 1 | 221 |  |
| logic | `existOr` | 21,405 | 3,109 | 105 | 24,619 | AMBIGUOUS |
| logic | `existOrC` | 21,511 | 3,026 | 103 | 24,640 | AMBIGUOUS |
| exist | `existRelS` | 26,711 | 3,809 | 218 | 30,738 |  |
| exist | `existRelSC` | 19,663 | 2,742 | 148 | 22,553 |  |
| exist | `existRelSRC` | 7,448 | 1,118 | 28 | 8,594 |  |
| exist | `existThat` | 1,482 | 201 | 19 | 1,702 |  |
| exist | `existThatC` | 1,440 | 202 | 16 | 1,658 |  |
| exist | `existThatNot` | 128 | 15 | 0 | 143 |  |
| exist | `existThatNotC` | 145 | 13 | 2 | 160 |  |
| logic | `existThatOr` | 4,254 | 591 | 25 | 4,870 | AMBIGUOUS |
| logic | `existThatOrC` | 4,045 | 529 | 68 | 4,642 | AMBIGUOUS |
| verifyRel | `relVerify` | 27,777 | 3,885 | 441 | 32,103 |  |
| verifyRel | `relVerifyCo` | 21,726 | 3,046 | 273 | 25,045 |  |
| verifyRel | `relVerifyCop` | 35 | 6 | 0 | 41 |  |
| verifyRel | `relVerifyCr` | 6,985 | 996 | 55 | 8,036 |  |
| compare | `twoDifferent` | 4,476 | 622 | 59 | 5,157 | AMBIGUOUS |
| compare | `twoDifferentC` | 4,361 | 632 | 79 | 5,072 | AMBIGUOUS |
| compare | `twoSame` | 4,398 | 584 | 77 | 5,059 | AMBIGUOUS |
| compare | `twoSameC` | 4,464 | 666 | 76 | 5,206 | AMBIGUOUS |
| compare | `twoSameMaterial` | 701 | 107 | 46 | 854 | AMBIGUOUS |
| compare | `twoSameMaterialC` | 1,148 | 161 | 107 | 1,416 | AMBIGUOUS |
| verifyAttr | `verifyAttr` | 6,650 | 901 | 151 | 7,702 |  |
| logic | `verifyAttrAnd` | 1,219 | 152 | 38 | 1,409 | AMBIGUOUS |
| verifyAttr | `verifyAttrC` | 6,833 | 933 | 116 | 7,882 |  |
| verifyAttr | `verifyAttrCThis` | 641 | 92 | 11 | 744 |  |
| verifyAttr | `verifyAttrK` | 10,028 | 1,427 | 234 | 11,689 |  |
| verifyAttr | `verifyAttrKC` | 10,209 | 1,460 | 182 | 11,851 |  |
| verifyAttr | `verifyAttrThis` | 618 | 101 | 18 | 737 |  |
| logic | `verifyAttrs` | 11,742 | 1,741 | 589 | 14,072 | AMBIGUOUS |
| logic | `verifyAttrsC` | 11,999 | 1,670 | 598 | 14,267 | AMBIGUOUS |
| logic | `verifyMaterialAnd` | 82 | 18 | 10 | 110 | AMBIGUOUS |

## Unmatched or ambiguous detailed types

- `activity` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `activityChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `activityWho` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `category` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryAttr` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryRelO` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryRelOChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryRelS` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryThat` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryThatChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryThis` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `categoryThisChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `chooseAttr` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `company` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `companyChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `companyVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `companyVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `comparativeChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `diffAnimals` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `diffAnimalsC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `diffGender` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `dir` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `directOf` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `directWhich` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `existAnd` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existAndC` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existAttrOr` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existAttrOrC` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existOr` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existOrC` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existThatOr` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `existThatOrC` → `logic` (AMBIGUOUS): Observed and/or composition; overlaps the exist family and needs human review; also matches another family prefix
- `how` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `locationChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `locationVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `locationVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `material` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `materialChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `materialVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `materialVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `objThisChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `place` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `placeChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `placeVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `placeVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `positionChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `positionQuery` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `positionVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `positionVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `relChooser` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `relO` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `relS` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameAnimals` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameAnimalsC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameGender` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameGenderC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameMaterialRelate` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `sameRelate` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `state` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `stateChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `twoCommon` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `twoDifferent` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `twoDifferentC` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `twoSame` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `twoSameC` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `twoSameMaterial` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `twoSameMaterialC` → `compare` (AMBIGUOUS): Pooling twoSame and twoDifferent needs human review
- `typeChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `typeVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `typeVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `verifyAttrAnd` → `logic` (AMBIGUOUS): Observed and composition; overlaps attribute verification and needs human review; also matches another family prefix
- `verifyAttrs` → `logic` (AMBIGUOUS): Observed and composition; overlaps attribute verification and needs human review; also matches another family prefix
- `verifyAttrsC` → `logic` (AMBIGUOUS): Observed and composition; overlaps attribute verification and needs human review; also matches another family prefix
- `verifyMaterialAnd` → `logic` (AMBIGUOUS): Observed and composition; overlaps attribute verification and needs human review
- `weather` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `weatherChoose` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `weatherVerify` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing
- `weatherVerifyC` → `secondary` (UNMATCHED): Outside the intended pilot families; review before freezing

## Operation catalogue

- Unique full operation strings: **137**
- Unique heads: **12**

- Unmapped operation strings: **0**


## Relation filter impact on eligible yes/no questions with nonempty programs

| Task | Split | Eligible | R_strict removed | R_broad removed |
|---|---|---:|---:|---:|
| exist | train | 74,826 | 53,822 | 53,822 |
| exist | val | 10,548 | 7,669 | 7,669 |
| exist | testdev | 556 | 394 | 394 |
| verifyAttr | train | 34,979 | 8,796 | 8,796 |
| verifyAttr | val | 4,914 | 1,281 | 1,281 |
| verifyAttr | testdev | 712 | 139 | 139 |
| compare | train | 19,548 | 0 | 0 |
| compare | val | 2,772 | 0 | 0 |
| compare | testdev | 444 | 0 | 0 |

Exact matching operation and argument strings are in `relation_matches.csv`.


## Eligibility correction and validation

The previous run was invalid for eligibility and filter impact: unquoted YAML yes/no values were loaded as booleans, so string answers never matched. The config now uses quoted strings and is type-checked before scanning. Raw answer counts independently check every pilot type's eligible count. No task definitions were changed for this correction.

Integrity checks: 336 PASS, 0 FAIL. See validation_checks.csv.

## Task counts by proposed variant

All variants are diagnostics, not a frozen primary rule. semantic_sensitivity replaces the exist program filter with the benchmark semantic label. See variant_equivalence.csv for exact membership comparisons.

| Variant | Task | Split | Questions | Yes ratio | Filter exclusion rate |
|---|---|---|---:|---:|---:|
| unfiltered | exist | train | 74,826 | 0.4971 | 0.0000 |
| unfiltered | verifyAttr | train | 34,979 | 0.4945 | 0.0000 |
| unfiltered | verifyRel | train | 56,523 | 0.4914 | 0.0000 |
| unfiltered | compare | train | 19,548 | 0.4898 | 0.0000 |
| unfiltered | logic | train | 114,029 | 0.5066 | 0.0000 |
| unfiltered | exist | val | 10,548 | 0.4998 | 0.0000 |
| unfiltered | verifyAttr | val | 4,914 | 0.4943 | 0.0000 |
| unfiltered | verifyRel | val | 7,933 | 0.4897 | 0.0000 |
| unfiltered | compare | val | 2,772 | 0.4737 | 0.0000 |
| unfiltered | logic | val | 16,096 | 0.5188 | 0.0000 |
| unfiltered | exist | testdev | 556 | 0.5414 | 0.0000 |
| unfiltered | verifyAttr | testdev | 712 | 0.5660 | 0.0000 |
| unfiltered | verifyRel | testdev | 769 | 0.5735 | 0.0000 |
| unfiltered | compare | testdev | 444 | 0.4099 | 0.0000 |
| unfiltered | logic | testdev | 1,803 | 0.4886 | 0.0000 |
| program_strict | exist | train | 21,004 | 0.4992 | 0.7193 |
| program_strict | verifyAttr | train | 26,183 | 0.4941 | 0.2515 |
| program_strict | verifyRel | train | 56,523 | 0.4914 | 0.0000 |
| program_strict | compare | train | 19,548 | 0.4898 | 0.0000 |
| program_strict | logic | train | 114,029 | 0.5066 | 0.0000 |
| program_strict | exist | val | 2,879 | 0.5082 | 0.7271 |
| program_strict | verifyAttr | val | 3,633 | 0.4930 | 0.2607 |
| program_strict | verifyRel | val | 7,933 | 0.4897 | 0.0000 |
| program_strict | compare | val | 2,772 | 0.4737 | 0.0000 |
| program_strict | logic | val | 16,096 | 0.5188 | 0.0000 |
| program_strict | exist | testdev | 162 | 0.5123 | 0.7086 |
| program_strict | verifyAttr | testdev | 573 | 0.5707 | 0.1952 |
| program_strict | verifyRel | testdev | 769 | 0.5735 | 0.0000 |
| program_strict | compare | testdev | 444 | 0.4099 | 0.0000 |
| program_strict | logic | testdev | 1,803 | 0.4886 | 0.0000 |
| program_broad | exist | train | 21,004 | 0.4992 | 0.7193 |
| program_broad | verifyAttr | train | 26,183 | 0.4941 | 0.2515 |
| program_broad | verifyRel | train | 56,523 | 0.4914 | 0.0000 |
| program_broad | compare | train | 19,548 | 0.4898 | 0.0000 |
| program_broad | logic | train | 114,029 | 0.5066 | 0.0000 |
| program_broad | exist | val | 2,879 | 0.5082 | 0.7271 |
| program_broad | verifyAttr | val | 3,633 | 0.4930 | 0.2607 |
| program_broad | verifyRel | val | 7,933 | 0.4897 | 0.0000 |
| program_broad | compare | val | 2,772 | 0.4737 | 0.0000 |
| program_broad | logic | val | 16,096 | 0.5188 | 0.0000 |
| program_broad | exist | testdev | 162 | 0.5123 | 0.7086 |
| program_broad | verifyAttr | testdev | 573 | 0.5707 | 0.1952 |
| program_broad | verifyRel | testdev | 769 | 0.5735 | 0.0000 |
| program_broad | compare | testdev | 444 | 0.4099 | 0.0000 |
| program_broad | logic | testdev | 1,803 | 0.4886 | 0.0000 |
| semantic_sensitivity | exist | train | 21,004 | 0.4992 | 0.7193 |
| semantic_sensitivity | verifyAttr | train | 26,183 | 0.4941 | 0.2515 |
| semantic_sensitivity | verifyRel | train | 56,523 | 0.4914 | 0.0000 |
| semantic_sensitivity | compare | train | 19,548 | 0.4898 | 0.0000 |
| semantic_sensitivity | logic | train | 114,029 | 0.5066 | 0.0000 |
| semantic_sensitivity | exist | val | 2,879 | 0.5082 | 0.7271 |
| semantic_sensitivity | verifyAttr | val | 3,633 | 0.4930 | 0.2607 |
| semantic_sensitivity | verifyRel | val | 7,933 | 0.4897 | 0.0000 |
| semantic_sensitivity | compare | val | 2,772 | 0.4737 | 0.0000 |
| semantic_sensitivity | logic | val | 16,096 | 0.5188 | 0.0000 |
| semantic_sensitivity | exist | testdev | 162 | 0.5123 | 0.7086 |
| semantic_sensitivity | verifyAttr | testdev | 573 | 0.5707 | 0.1952 |
| semantic_sensitivity | verifyRel | testdev | 769 | 0.5735 | 0.0000 |
| semantic_sensitivity | compare | testdev | 444 | 0.4099 | 0.0000 |
| semantic_sensitivity | logic | testdev | 1,803 | 0.4886 | 0.0000 |

## Answer-family pairing and flags

| Task | Family | Detailed types | Train yes | Train no | Flag |
|---|---|---|---:|---:|---|
| exist | exist | exist, existC | 5564 | 5721 |  |
| logic | existAnd | existAnd, existAndC | 10683 | 10753 |  |
| exist | existAttr | existAttr, existAttrC | 1410 | 1418 |  |
| exist | existAttrNot | existAttrNot, existAttrNotC | 1513 | 1440 |  |
| logic | existAttrOr | existAttrOr, existAttrOrC | 8378 | 7958 |  |
| exist | existMaterial | existMaterial, existMaterialC | 179 | 165 |  |
| exist | existMaterialNot | existMaterialNot, existMaterialNotC | 210 | 189 |  |
| logic | existOr | existOr, existOrC | 21405 | 21511 |  |
| exist | existRelS | existRelS, existRelSC, existRelSRC | 26711 | 27111 |  |
| exist | existThat | existThat, existThatC | 1482 | 1440 |  |
| exist | existThatNot | existThatNot, existThatNotC | 128 | 145 |  |
| logic | existThatOr | existThatOr, existThatOrC | 4254 | 4045 |  |
| verifyRel | relVerify | relVerify, relVerifyCo, relVerifyCop, relVerifyCr | 27777 | 28746 |  |
| compare | twoDifferent | twoDifferent, twoDifferentC | 4476 | 4361 |  |
| compare | twoSame | twoSame, twoSameC | 4398 | 4464 |  |
| compare | twoSameMaterial | twoSameMaterial, twoSameMaterialC | 701 | 1148 |  |
| verifyAttr | verifyAttr | verifyAttr, verifyAttrC | 6650 | 6833 |  |
| logic | verifyAttrAnd | verifyAttrAnd | 1219 | 0 | SINGLE_CLASS |
| verifyAttr | verifyAttrThis | verifyAttrCThis, verifyAttrThis | 618 | 641 |  |
| verifyAttr | verifyAttrK | verifyAttrK, verifyAttrKC | 10028 | 10209 |  |
| logic | verifyAttrs | verifyAttrs, verifyAttrsC | 11742 | 11999 |  |
| logic | verifyMaterialAnd | verifyMaterialAnd | 82 | 0 | SINGLE_CLASS |

Single-class and empty families are reported without rebalancing or changing assignments. Family flags per split and variant are in variant_counts.csv.

## Suffix examples and open decisions

See suffix_examples.md for up to five seeded train examples and a factual observation per detailed type. The meanings of Co, Cr, Cop, K, That and other suffixes remain for human review.

Material/position verification and animal/gender comparison types remain secondary in this rerun. The previous task proposal is preserved so the bug correction is comparable. Their inclusion, family pooling, and a primary relation rule require human review.
