# Stage 3.5 P1 checkpoint

Completed P1 runs: 120. Selected recipe: {'lr_fusion': 0.0001, 'train_text': False, 'epochs': 10}.

Median P1 training time: 23.7 s; p90: 128.7 s.

Selected-recipe median training time per example seen: 0.001134 s.

Projected P2 to P4 training-only GPU-hours: 5.58. This excludes dev evaluation, checkpoint overhead and P5 Qwen, so total P2 to P5 is higher.

INFO: full P2 to P5 projection still requires P5 training cost estimate.


Full measured P2–P5 projection:

{
  "projected_gpu_hours_P2_P5": 7.848561633224873,
  "qwen_training_hours": 1.5700508812067762,
  "qwen_evaluation_hours": 0.266204621377205,
  "assumptions": "P1 median seconds/example; end-only task evaluation; Qwen 8 optimizer steps and 32 dev questions",
  "status": "PASS"
}
