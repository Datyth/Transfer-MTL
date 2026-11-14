# Experiment preparation: ready for a user-launched full run

Status: PREPARED. Full inference was stopped at the human's request; no complete
zero-shot metric table is claimed. All checks below are preparation checks.

- Source commit: `57ab8d713afd92d2c66f76dc8275159d0e91a27a`.
- Frozen protocol: `configs/stage3_protocol.FROZEN.yaml`, byte-identical SHA-256
  `a0201c1a0a163d81d102f8f1aca677812238c7328305d69774d7101e4ada7ab2`.
- Environment: `datpt_mtl`, torch 2.9.1+cu128, transformers 4.57.1.
- Model: Qwen/Qwen2.5-VL-3B-Instruct, revision `66285546d2b821cf421d4f5eb2576359d3770cd3`,
  in `checkpoints/Qwen2.5-VL-3B-Instruct/`. All 14 files checked by hash.
- Image archive: CRC verified; 148,854 extracted files; all 74,573 registry
  train/dev/val images pass verify and full decoding. testdev: 395/395 image
  IDs have a file; only existence was checked.
- Regression suite: 60 passed. The final table/figure pipeline also passes with
  frozen baseline fixtures in /tmp (288 metric rows, 16 PNG/PDF figure files).
- Existing Stage 1/2/2b output hashes are unchanged.

## Correctness and performance decisions

Grouped SDPA batches equal-length independent vision windows. On the pinned model,
256 dev questions with template A and 64 with template B, in BOTH image and no-image
conditions, have EXACTLY the same scores and predictions as official attention.
Eight greedy-generation smoke checks also match. The default batch size is 1;
256 repeated questions per condition have zero numerical score difference.

The original bf16 implementation at batch 16 differed from batch 1 by up to
0.37503 (image) and 0.12918 (no image), exceeding the frozen 0.05 rule. This evidence
is retained in `diagnostics/batch16/optimization_validation.json`. The batch size
was therefore fixed at 1 before the full experiment. The protocol itself did not
change. The full runner refuses a runtime/batch size without passing validation.

Profiling also exposed the slow Conv3D patch fallback. A faster channels-last
cuDNN path changed scores (max 0.25005) and 1/256 predictions, so it was REJECTED;
its log is in `diagnostics/rejected_channels_last/optimization.log`. The final
path retains the official patch convolution. This favors matching the pinned
reference over a larger speed improvement.

Measured template-A throughput at batch 1: 7.63 image questions/s and
54.70 no-image questions/s. The two main conditions alone take an
estimated 178 minutes. Allow roughly 3–3.5 hours including diagnostics
and evaluation; timing varies with image sizes and host load. Grouping reduced
SDPA calls on one batch-1 input from 600 to 96; observed timing gains are modest
because the patch convolution remains a bottleneck.

## Start, monitor, resume

```bash
cd /home/dat/projects/vqa-mtl
conda activate datpt_mtl
nohup python -u scripts/run_experiment.py --models 3b --batch-size 1 > gqa_audit/outputs/stage3/run.log 2>&1 &
echo $!
```

```bash
tail -f gqa_audit/outputs/stage3/run.log
```

After an interruption, run the same launch command again. Complete shards are
hash/ID checked and skipped; unfinished shards are recomputed. Only one runner
can hold the output-directory lock. Each completed shard contains up to 2,000
questions, so progress commits appear roughly every 4–5 minutes for images.

The final run will write `STAGE3_REPORT.md`, prediction parquet files, all metric
and diagnostic CSVs, and PNG/PDF figures under `gqa_audit/outputs/stage3/`. It scores
dev/val only. 7B is not enabled. Initial cancelled-run provenance is retained under
`diagnostics/initial_unoptimized/` and will not be reused as final predictions.
