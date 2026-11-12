# Stage 1 schema report

| Split | Questions |
|---|---:|
| train | 943,000 |
| val | 132,062 |
| testdev | 12,578 |

## Top-level field frequencies

| Split | Field | Records |
|---|---|---:|
| testdev | `annotations` | 12,578 |
| testdev | `answer` | 12,578 |
| testdev | `entailed` | 12,578 |
| testdev | `equivalent` | 12,578 |
| testdev | `fullAnswer` | 12,578 |
| testdev | `groups` | 12,578 |
| testdev | `imageId` | 12,578 |
| testdev | `isBalanced` | 12,578 |
| testdev | `question` | 12,578 |
| testdev | `semantic` | 12,578 |
| testdev | `semanticStr` | 12,578 |
| testdev | `types` | 12,578 |
| train | `annotations` | 943,000 |
| train | `answer` | 943,000 |
| train | `entailed` | 943,000 |
| train | `equivalent` | 943,000 |
| train | `fullAnswer` | 943,000 |
| train | `groups` | 943,000 |
| train | `imageId` | 943,000 |
| train | `isBalanced` | 943,000 |
| train | `question` | 943,000 |
| train | `semantic` | 943,000 |
| train | `semanticStr` | 943,000 |
| train | `types` | 943,000 |
| val | `annotations` | 132,062 |
| val | `answer` | 132,062 |
| val | `entailed` | 132,062 |
| val | `equivalent` | 132,062 |
| val | `fullAnswer` | 132,062 |
| val | `groups` | 132,062 |
| val | `imageId` | 132,062 |
| val | `isBalanced` | 132,062 |
| val | `question` | 132,062 |
| val | `semantic` | 132,062 |
| val | `semanticStr` | 132,062 |
| val | `types` | 132,062 |

## Missing expected fields

| Split | Field | Missing |
|---|---|---:|
| train | `imageId` | 0 |
| train | `question` | 0 |
| train | `answer` | 0 |
| train | `fullAnswer` | 0 |
| train | `isBalanced` | 0 |
| train | `types` | 0 |
| train | `semantic` | 0 |
| train | `groups` | 0 |
| train | `entailed` | 0 |
| train | `equivalent` | 0 |
| train | `annotations` | 0 |
| val | `imageId` | 0 |
| val | `question` | 0 |
| val | `answer` | 0 |
| val | `fullAnswer` | 0 |
| val | `isBalanced` | 0 |
| val | `types` | 0 |
| val | `semantic` | 0 |
| val | `groups` | 0 |
| val | `entailed` | 0 |
| val | `equivalent` | 0 |
| val | `annotations` | 0 |
| testdev | `imageId` | 0 |
| testdev | `question` | 0 |
| testdev | `answer` | 0 |
| testdev | `fullAnswer` | 0 |
| testdev | `isBalanced` | 0 |
| testdev | `types` | 0 |
| testdev | `semantic` | 0 |
| testdev | `groups` | 0 |
| testdev | `entailed` | 0 |
| testdev | `equivalent` | 0 |
| testdev | `annotations` | 0 |

## Other schema issues

| Issue | Count |
|---|---:|

### Example issues


## Available unbalanced files (existence only; not parsed)

| File | Size (bytes) |
|---|---:|
| challenge_all_questions.json | 83,476,451 |
| challenge_balanced_questions.json | 5,800,302 |
| submission_all_questions.json | 492,981,231 |
| test_all_questions.json | 156,968,340 |
| testdev_all_questions.json | 153,446,657 |
| train_all_questions/train_all_questions_0.json | 1,236,128,669 |
| train_all_questions/train_all_questions_1.json | 1,235,712,327 |
| train_all_questions/train_all_questions_2.json | 1,235,890,885 |
| train_all_questions/train_all_questions_3.json | 1,235,521,715 |
| train_all_questions/train_all_questions_4.json | 1,235,772,941 |
| train_all_questions/train_all_questions_5.json | 1,235,477,906 |
| train_all_questions/train_all_questions_6.json | 1,235,068,698 |
| train_all_questions/train_all_questions_7.json | 1,235,539,281 |
| train_all_questions/train_all_questions_8.json | 1,236,032,518 |
| train_all_questions/train_all_questions_9.json | 1,235,981,804 |
| val_all_questions.json | 1,735,745,976 |

## Three abbreviated examples: train

```json
{
  "question_id": "02930152",
  "imageId": "2354786",
  "question": "Is the sky dark?",
  "answer": "yes",
  "types": {
    "detailed": "verifyAttr",
    "semantic": "attr",
    "structural": "verify"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "sky (2486325)"
    },
    {
      "operation": "verify color",
      "argument": "dark"
    }
  ],
  "semantic_length": 2
}
```

```json
{
  "question_id": "07333408",
  "imageId": "2375429",
  "question": "What is on the white wall?",
  "answer": "pipe",
  "types": {
    "detailed": "relS",
    "semantic": "rel",
    "structural": "query"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "wall (722332)"
    },
    {
      "operation": "filter color",
      "argument": "white"
    },
    {
      "operation": "relate",
      "argument": "_,on,s (722335)"
    }
  ],
  "semantic_length": 4
}
```

```json
{
  "question_id": "07333405",
  "imageId": "2375429",
  "question": "Is that pipe red?",
  "answer": "no",
  "types": {
    "detailed": "verifyAttrC",
    "semantic": "attr",
    "structural": "verify"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "pipe (722335)"
    },
    {
      "operation": "verify color",
      "argument": "red"
    }
  ],
  "semantic_length": 2
}
```


## Three abbreviated examples: val

```json
{
  "question_id": "05515938",
  "imageId": "2405722",
  "question": "What is this bird called?",
  "answer": "parrot",
  "types": {
    "detailed": "categoryThis",
    "semantic": "cat",
    "structural": "query"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "bird (329774)"
    },
    {
      "operation": "query",
      "argument": "name"
    }
  ],
  "semantic_length": 2
}
```

```json
{
  "question_id": "17197213",
  "imageId": "2331963",
  "question": "What color is the helmet in the middle of the image?",
  "answer": "light blue",
  "types": {
    "detailed": "directWhich",
    "semantic": "attr",
    "structural": "query"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "helmet (3205899)"
    },
    {
      "operation": "filter vposition",
      "argument": "middle"
    },
    {
      "operation": "query",
      "argument": "color"
    }
  ],
  "semantic_length": 3
}
```

```json
{
  "question_id": "08223573",
  "imageId": "2400861",
  "question": "Is it an indoors or outdoors scene?",
  "answer": "indoors",
  "types": {
    "detailed": "locationChoose",
    "semantic": "global",
    "structural": "choose"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "scene"
    },
    {
      "operation": "choose location",
      "argument": "indoors|outdoors"
    }
  ],
  "semantic_length": 2
}
```


## Three abbreviated examples: testdev

```json
{
  "question_id": "201307251",
  "imageId": "n161313",
  "question": "Is it overcast?",
  "answer": "no",
  "types": {
    "detailed": "weatherVerifyC",
    "semantic": "global",
    "structural": "verify"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "scene"
    },
    {
      "operation": "verify weather",
      "argument": "overcast"
    }
  ],
  "semantic_length": 2
}
```

```json
{
  "question_id": "201640614",
  "imageId": "n235859",
  "question": "Who is wearing the dress?",
  "answer": "women",
  "types": {
    "detailed": "relS",
    "semantic": "rel",
    "structural": "query"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "dress (12)"
    },
    {
      "operation": "relate",
      "argument": "person,wearing,s (7)"
    },
    {
      "operation": "query",
      "argument": "name"
    }
  ],
  "semantic_length": 3
}
```

```json
{
  "question_id": "202225914",
  "imageId": "n336443",
  "question": "Does the utensil on top of the table look clean and black?",
  "answer": "no",
  "types": {
    "detailed": "verifyAttrsC",
    "semantic": "attr",
    "structural": "logical"
  },
  "semantic_first_3": [
    {
      "operation": "select",
      "argument": "table (2)"
    },
    {
      "operation": "relate",
      "argument": "utensil,on top of,s (1)"
    },
    {
      "operation": "verify color",
      "argument": "black"
    }
  ],
  "semantic_length": 5
}
```

