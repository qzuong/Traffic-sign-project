# Source references

Paths are relative to this evidence directory. Code links target the working-tree file inspected; the repository had pre-existing uncommitted changes, so do not equate every source observation with committed HEAD.

## Requirements, design, and project records

| Source | Evidence supported |
|---|---|
| [BA Analysis v0.1](../../docs/design/01_analysis/BA-analysis_v0.1.md) | Scope, German sign domain, hardware declaration, proposed pipeline, A-05/A-08/A-11 decisions, limitations, and unresolved A-14–A-19. Marked draft. |
| [Decision Log](../../docs/00_project/decision-log.md) | Confirmed design decisions, including video input, detection/classification split, future simulator, configuration-file decision, and control requirements. |
| [Project Status](../../docs/00_project/project-status.md) | Phase status and `Code allowed: NO`; stale relative to later Demo 1.1 validation context. |
| [REQ-spec v0.3](../../docs/design/02_requirements/REQ-spec_v0.3.md) | Approved FR-01–FR-14, NFR definitions, constraints, Q decisions, open issues. |
| [RTM v0.3](../../docs/design/02_requirements/RTM_v0.3.md) | Requirement sources and planned verification; unresolved Use Case/module/test trace fields. |
| [Use Case Catalog](../../docs/design/03_use_case/use-case-catalog_v0.1.md) | UC-01–UC-05, User Actor, flow/coverage, current design open issues. |
| [Actor–Use Case Matrix](../../docs/design/03_use_case/actor-usecase-matrix_v0.1.md) | Actor associations, requirement coverage, UC-02 extend relationship. |
| [Use Case diagram source](../../docs/design/03_use_case/diagrams/use-case-diagram_v0.1.puml) and [diagram notes](../../docs/design/03_use_case/diagrams/use-case-diagram-notes_v0.1.md) | PlantUML actor/use cases and recorded unrendered status. |
| [Change Log](../../docs/00_project/change-log.md) | Design-stage approvals and historical changes. |

## Implementation source and tests

| Source | Key symbols / inspected sections |
|---|---|
| [main.py](../../src/traffic_sign_demo/main.py#L12) | `_parse_args`, CLI defaults/options, `main`, logging initialization. |
| [inference_service.py](../../src/traffic_sign_demo/inference_service.py#L32) | `DEFAULT_DEMO_DETECTOR`, detector files, `InferenceService`, bounded queues, worker selection, `_infer`. |
| [yolo_worker.py](../../src/traffic_sign_demo/yolo_worker.py#L20) | Worker CLI, local checkpoint load, `device="cpu"`, one-class candidate validation and prediction. |
| [cnn_worker.py](../../src/traffic_sign_demo/cnn_worker.py#L18) | Keras model load, 30×30 input validation, 43-output check, top-1 prediction. |
| [models/model.py](../../models/model.py#L15) | External training-data path, 30×30 settings, `classes` IDs 0–42, model/training script. |
| [class_mapping.py](../../src/traffic_sign_demo/class_mapping.py#L11) | `load_class_mapping` parses and validates consecutive IDs. |
| [vietnamese_labels.py](../../src/traffic_sign_demo/vietnamese_labels.py#L3) | Vietnamese class names and spoken sentence formatting. |
| [vision.py](../../src/traffic_sign_demo/vision.py#L80) | `preprocess_crop`; `draw_overlay` at line 120 renders class labels without IDs. |
| [alert_tracking.py](../../src/traffic_sign_demo/alert_tracking.py#L15) | Track gaps, vote window, `AlertTrack.record`, custom `AlertTracks` association. |
| [sign_tracking.py](../../src/traffic_sign_demo/sign_tracking.py#L31) | Separate image-template-based visual carry-forward tracker. |
| [tracked_voice_alerts.py](../../src/traffic_sign_demo/tracked_voice_alerts.py#L31) | `TrackedVoiceAlerts`, confirmation callback, per-track offer, bounded queue, priorities and expiry. |
| [speech_evidence.py](../../src/traffic_sign_demo/speech_evidence.py#L13) | Class/crop evidence veto rules. |
| [voice_alerts.py](../../src/traffic_sign_demo/voice_alerts.py#L18) | Local WAV directories, Google-directory preference, local fallback, asynchronous `winsound`. |
| [simulation_events.py](../../src/traffic_sign_demo/simulation_events.py#L32) | `DECISIONS`, event schema/dataclasses, `SimulationSession.observe`, JSONL publisher. |
| [desktop_ui.py](../../src/traffic_sign_demo/desktop_ui.py#L38) | `DesktopVideoPlayer`, 7:3 columns, event panel, controls, `_display_frame`, `_observe_simulation_event`, image cache, status/debug metrics. |
| [video_reader.py](../../src/traffic_sign_demo/video_reader.py#L14) and [playback_controller.py](../../src/traffic_sign_demo/playback_controller.py#L63) | Supported formats, decoding and playback states/actions. |
| [logging_config.py](../../src/traffic_sign_demo/logging_config.py#L26) | Queued console/file logging and rotation policy. |
| [real-model regression test](../../tests/test_ai_pipeline.py#L618) | `TRAFFIC_SIGN_REAL_MODEL_TEST` opt-in and frame-1358 assertion. |
| [desktop UI tests](../../tests/test_desktop_ui.py#L153) | Class mapping and all-class image loading/fallback coverage. |
| [simulation tests](../../tests/test_simulation_events.py#L47) | Full 43-class decision-map coverage and event behavior. |
| [logging tests](../../tests/test_logging_config.py#L14) | File logging and debug/rotation behavior. |

## Local model and media evidence

| Source | Evidence supported |
|---|---|
| [GTSDB detector provenance](../../models/candidates/gtsdb_yolov8n.provenance.json) | Detector origin URL/commit, GTSDB label, one class, artifact size and SHA-256. |
| [Traffic-sign image directory](../../assets/traffic_signs/) | Local class-index PNG assets 0–42; 43 files present at inspection. |
| [assets/voice_google/](../../assets/voice_google/) and [assets/voice_vi/](../../assets/voice_vi/) | 43 local WAVs in each directory; application code selects local files. |
| [models/model.h5](../../models/model.h5) | Local CNN checkpoint; training history/provenance is not embedded as verified evidence in this package. |

## Experimental and validation artifacts

| Evidence source | Experiment and claim |
|---|---|
| [Step H detections](../../data/validation/step_h/detections.json) | 17 localized frames; raw references, predictions, matches, FP/FN and elapsed times. |
| [Step H tracking review](../../data/validation/step_h/tracking-review.json) and [voice review](../../data/validation/step_h/voice-review.json) | Manually reviewed ID switches and spoken outcomes. |
| [Step H performance](../../data/validation/step_h/performance-live.json) | Continuous desktop display/AI FPS, control flags, trace and audio timing. |
| [Step J GTSRB ROI results](../../data/validation/step_j/gtsrb-roi-results.json) | 12,630 crop rows used for the 43-class top-1 result. |
| [Step J GTSDB results](../../data/validation/step_j/gtsdb-results.json) | Still-scene detector and matched-crop results. |
| [Step J split-overlap audit](../../data/validation/step_j/published-split-overlap.json) | Published split and local overlap caveats. |
| [Step I replay metrics](../../data/validation/step_i/replay-metrics.json) | Paired selected-trace correct/incorrect/suppression counts. |
| [Step K GTSDB holdout](../../data/validation/step_k/gtsdb-holdout-results.json) | Additional still-scene detector and crop-policy results. |
| [Step K BelgiumTSC holdout](../../data/validation/step_k/belgium-holdout-results.json) and [dataset integrity](../../data/validation/step_k/dataset-integrity.json) | Mapped crop and grouped-view holdout evidence and integrity notes. |
| [Final-demo summary](../../data/validation/final_demo/summary.md) and [continuous run](../../data/validation/final_demo/continuous-live.json) | Historical final-demo results, live controls, workers, rates, latencies, and limitations. |
| [Demo 1.1 report](../../data/validation/demo_1_1/report.md), [metrics](../../data/validation/demo_1_1/validation-metrics.json), and [sample events](../../data/validation/demo_1_1/sample-real-events.json) | Historical simulation-event integration run, paired baseline, event JSONL evidence, test count, and caveats. |

