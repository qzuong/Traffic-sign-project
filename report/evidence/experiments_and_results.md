# Experiments and results

## Interpretation rules

Results below remain grouped by their recorded experiment/version. They are not pooled. Static-scene/crop benchmarks, short manually sampled video frames, and continuous desktop runs measure different tasks. Precision/recall values apply only to the listed detector sample and matching procedure; crop accuracy is not end-to-end video accuracy. No numeric NFR acceptance thresholds are specified in the approved SRS.

## Detection and classification

| Experiment and source | Sample / condition | Result | Limitation |
|---|---|---|---|
| Step H localized video frames: [detections.json](../../data/validation/step_h/detections.json), summarized in [final-demo summary](../../data/validation/final_demo/summary.md) | 17 manually selected frames from one source video; 31 labeled signs and 4 negative frames; report uses one-to-one matching at IoU ≥ 0.50 | 24 TP, 2 FP, 7 FN; precision **92.3%**, recall **77.4%** | Small frame sample from one route; not an independently sampled road-video benchmark. |
| Step H readable localized CNN crops: [final-demo summary](../../data/validation/final_demo/summary.md) | 21 readable crops associated with the selected video sample | **17/21** classifications reported as correct | Conditional crop sample; not whole-scene accuracy or a full 43-class independent evaluation. |
| Step J GTSRB test crops: [gtsrb-roi-results.json](../../data/validation/step_j/gtsrb-roi-results.json) | 12,630 rows from the local `Test/` crop set, 43 classes | **12,216/12,630 = 96.72%** top-1 classification accuracy | The artifact does not establish the upstream dataset release/version or the trained checkpoint's provenance. A split audit found 8 exact file matches between the local test crops and tuning crop set. |
| Step J GTSDB still scenes: [gtsdb-results.json](../../data/validation/step_j/gtsdb-results.json) | 55 scenes, 75 signs, 10 negative scenes | Detector: 75 TP, 2 FP, 0 FN; precision **97.4%**, recall **100%**. CNN: **75/75** matched crops correct. | The validation report says this set includes scenes in the detector author's published training/validation conversion; historical checkpoint exposure is uncertain. Still scenes are not moving-road generalization. |
| Step K additional GTSDB still-scene holdout: [gtsdb-holdout-results.json](../../data/validation/step_k/gtsdb-holdout-results.json) | 64 scenes, 87 signs, 12 negative scenes | Detector: 83 TP, 1 FP, 4 FN; precision **98.8%**, recall **95.4%**. CNN: **83/83** matched crops correct. | The set excludes duplicate Step J images and the author's published training partition according to the validation report. Exposure of the checkpoint to all source data remains uncertain. |
| Step K BelgiumTSC mapped crop holdout: [belgium-holdout-results.json](../../data/validation/step_k/belgium-holdout-results.json) | 607 mapped labeled crops grouped into 202 physical signs; consensus uses supplied views, minimum two | Top-1: **513/607 = 84.5%** correct. Under the stable speech policy, 410 correct predictions were eligible, 103 correct predictions withheld, 73 incorrect predictions eligible, and 21 incorrect predictions withheld. Group consensus: 138 correct, 48 withheld, 16 incorrect. | This is crop-level mapped classification, not full-scene detection/tracking. The source notes no capture timestamps or complete scene tracks. |

## Tracking, deduplication, and speech

- Step H's manual tracking review reports **4 ID switches over 12 observations** for a Yield sign and **2 switches over 11 observations** for an adjacent right-turn sign. See [tracking-review.json](../../data/validation/step_h/tracking-review.json). These are small, hand-followed observations, not a population tracking score.
- The Step H live voice review contains 8 outcomes: **6 correct, 1 incorrect, 1 unresolved**. One recorded mismatch is class 12 (Priority Road) expected but class 38 (Keep Right) spoken; one outcome has no resolved expected class. See [voice-review.json](../../data/validation/step_h/voice-review.json).
- Step I replayed recorded traces for city, motorway, and blue-panel cases. City alerts changed from **6 correct / 1 incorrect** to **7 correct / 0 incorrect**, with 3 suppressed tracks and no previously correct alert missed. Motorway changed from **0 / 1** to **0 / 0** with 2 suppressed tracks; blue panel changed from **0 / 1** to **0 / 0** with 1 suppressed track. Source: [replay-metrics.json](../../data/validation/step_i/replay-metrics.json). This is a replay of selected traces, not a new live-road test.
- Step J's 13-second motorway negative check spoke zero alerts in both builds. A motion replay on the original video reported identical IDs/confirmations over 148 associations; positive moving footage remained concentrated on the single original video. Source and caveats are in the [final-demo summary](../../data/validation/final_demo/summary.md), with raw artifacts under [Step J validation](../../data/validation/step_j/).
- Known recorded failure modes include electronic speed-sign confusion (a reported 100 km/h sign classified/spoken as 70 km/h), Priority Road confused with Keep Right, ID fragmentation, and silent/withheld correct predictions due to conservative evidence vetoes. Roundabout voice is explicitly disabled pending positive validation. These are observed limitations, not exhaustive error rates.

## Continuous desktop performance

Values below are distinct live runs on [test_video.mp4](../../data/videos/test_video.mp4). Display FPS and AI FPS are measured separately; AI FPS is a rolling endpoint measurement. Detection-to-speech latency is from first valid YOLO detection to audio start.

| Run / artifact | Source frames | Display FPS | AI FPS at endpoint | Detection-to-speech median / max |
|---|---:|---:|---:|---:|
| Step H performance [performance-live.json](../../data/validation/step_h/performance-live.json) | 0–1511 | 19.00 | 6.97 | 2.12 / 2.98 s |
| Step J positive regression [positive-regression-live.json](../../data/validation/step_j/positive-regression-live.json) | 0–1501 | 18.63 | 6.21 | 1.86 / 3.54 s |
| Step K stable native [stable-native.json](../../data/validation/step_k/stable-native.json) | 0–1501 | 18.14 | 5.46 | 1.93 / 3.11 s |
| Final freeze [continuous-live.json](../../data/validation/final_demo/continuous-live.json) | 0–1501 | 18.80 | 6.12 | 1.97 / 3.09 s |

The final-freeze trace recorded 8 logical CPUs, YOLO `imgsz=640`/one class and CNN output shape 43. The BA separately documents the target machine as i7-8550U/8 GB/Windows 11. Startup in that run was 23.79 s to worker readiness and 25.05 s from video open to first overlay. These timings are one run and include model startup.

The distinct Demo 1.1 simulation-integration comparison is in [validation-metrics.json](../../data/validation/demo_1_1/validation-metrics.json):

| Metric | Frozen baseline | Candidate (uncontended) |
|---|---:|---:|
| Video interval | frames 0–1500 | frames 0–1503 |
| Display FPS | 16.12 | 16.65 |
| Whole-run AI results/sec after frame zero | 4.48 | 4.52 |
| Warm submit-to-result median | 190.1 ms | 185.7 ms |
| Detection-to-speech median | 1.88 s | 1.86 s |
| Rolling AI FPS at endpoint | 7.18 | 1.23 |
| AI results | 231 | 231 |
| Local Google-directory clip plays | 8 | 8 |

The similar whole-run rates alongside different endpoint AI FPS show why the endpoint rate should not be treated as whole-run throughput. The report notes that an earlier candidate run overlapping the real-model suite was excluded. The candidate run wrote 16 JSONL events, with zero recorded export errors/drops; one event was withheld and six events had audio expire later.

## Automated tests

| Run | Command / condition | Result |
|---|---|---|
| Current full default suite | `python -m unittest discover -s tests -q` | **123 tests; 122 passed, 1 skipped**, exit code 0. The skipped class is gated by `TRAFFIC_SIGN_REAL_MODEL_TEST=1`. |
| Current opt-in model pipeline | `TRAFFIC_SIGN_REAL_MODEL_TEST=1`, `python -m unittest discover -s tests -p test_ai_pipeline.py -q` | **24 tests passed**, exit code 0, including the real-model frame-1358 regression. It asserted one valid YOLO “Give Way” detection classified by CNN as “Yield”. Runtime was 52.17 s. |
| Historical final-demo suite | [final_demo/summary.md](../../data/validation/final_demo/summary.md) | **96 passed**, including real-model inference; distinct historical snapshot. |
| Historical simulation-integration suite | [demo_1_1/report.md](../../data/validation/demo_1_1/report.md) | **110 passed**, including 14 simulation tests; distinct historical snapshot. |

The historical counts are not summed or substituted for the current run. The current default full suite and the opt-in `test_ai_pipeline.py` subset are also separate invocations.

