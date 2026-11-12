# Stage 1 summary — proposal only

No task rules have been frozen. Review both `.PROPOSED.yaml` files before Stage 2.

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
| exist | train | 0 | 0 | 0 |
| exist | val | 0 | 0 | 0 |
| exist | testdev | 0 | 0 | 0 |
| verifyAttr | train | 0 | 0 | 0 |
| verifyAttr | val | 0 | 0 | 0 |
| verifyAttr | testdev | 0 | 0 | 0 |
| compare | train | 0 | 0 | 0 |
| compare | val | 0 | 0 | 0 |
| compare | testdev | 0 | 0 | 0 |

Exact matching operation and argument strings are in `relation_matches.csv`.
