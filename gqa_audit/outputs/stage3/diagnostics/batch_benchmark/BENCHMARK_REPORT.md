# Inference batch benchmark

Fixed 256-question dev sample, template A, two timed repeats after warmup for each
batch size and condition. Same checkpoint, bf16, sdpa, image resolution and scoring.
Only benchmark output files were written; the existing full-run configuration was
not changed. CPU/GPU timing was measured with the user's full-run process paused.
The benchmark model was released, then PID 219254 was automatically resumed.

## Throughput

| batch_size | image_questions_per_second | no_image_questions_per_second | estimated_main_minutes | estimated_time_saved_percent |
| --- | --- | --- | --- | --- |
| 1 | 6.9524 | 57.8992 | 191.5405 | 0.0000 |
| 2 | 7.3072 | 62.8106 | 181.6313 | 5.1734 |
| 4 | 6.6493 | 155.6576 | 186.4381 | 2.6639 |
| 8 | 5.4931 | 197.8828 | 222.4440 | -16.1342 |
| 16 | 4.8886 | 228.7255 | 248.3980 | -29.6843 |

Estimated minutes cover 71,334 questions per condition (image plus no_image),
excluding setup, template-B checks, generation and evaluation. These are estimates
from a small sample; modest differences such as 5% are subject to host and sample
variation. Reported throughput is the arithmetic mean of two per-repeat rates;
all raw repeats are in timings.csv.

Batch 2 reduced the estimated main duration by about 10 minutes (5%). Batch 4
saved about 5 minutes. Batches 8 and 16 increased overall duration because image
inference dominates the workload, even though no-image inference became faster.

## Numerical stability

All tested batch sizes >1 exceeded the frozen 0.05 maximum score-difference bound
against batch 1. Each changed one image-condition prediction among 256 questions;
no-image prediction changes ranged from 4 to 8 among 256. These are answer changes,
not an assertion that accuracy necessarily decreased. Both repeated batch-1 runs
matched. The active full run therefore remains at its validated batch size 1.
No model, frozen protocol, scoring threshold or accepted audit output was changed.

| batch_size | image_max_score_difference | no_image_max_score_difference | image_changed_predictions | no_image_changed_predictions |
| --- | --- | --- | --- | --- |
| 1 | 0.0000 | 0.0000 | 0 | 0 |
| 2 | 0.3222 | 0.1358 | 1 | 6 |
| 4 | 0.3750 | 0.1358 | 1 | 8 |
| 8 | 0.3750 | 0.1295 | 1 | 4 |
| 16 | 0.3750 | 0.1292 | 1 | 4 |

## Why bigger image batches were slower

Image sequence lengths differ. At batch 16, padding increased total image-condition
input tokens from 99,445 to 245,088 (+146.5%) on this sample. For no-image inputs,
the increase was only 16.8%. This supports padding as an important cause of the
weaker image throughput. It does not isolate all kernel and hardware effects.
Lengths were reconstructed from rendered chat tokens plus actual image token
counts and checked against CPU processor attention masks for the first 8 inputs
in each condition. See padding_analysis.csv.

## Reproduce

```bash
conda activate datpt_mtl
python scripts/benchmark_batches.py --batch-sizes 1 2 4 8 16 --repeats 2
```

Run with an idle GPU. If this project's full run is active, supply its PID with
`--pause-pid PID`; the helper verifies the target, pauses it, and resumes it on
normal completion or a handled interruption. Three pause/resume cleanup tests
passed (tests/test_benchmark.py).

The pause must be excluded when interpreting the active full run's overall
wall-clock duration. A per-question or shard timer crossing the pause also
includes that interruption; the separately measured throughput benchmark is not
affected by the paused process's GPU compute. Its resident GPU memory remained
allocated and is recorded in manifest.json. Benchmark max_allocated_mib refers
only to the benchmark process, including its model weights.
