# Verified architecture

## Runtime flow

The source-verified path is:

```text
Recorded MP4/AVI
  -> VideoReader / PlaybackController
  -> Tkinter desktop playback and bounded frame buffer
  -> InferenceService background thread
  -> YOLO worker subprocess (local detector, CPU)
  -> clipped boxes and per-box crops
  -> 30x30 RGB normalization
  -> CNN worker subprocess (local Keras model)
  -> ClassifiedDetection results
  -> display overlay and TrackedVoiceAlerts
       -> custom track association and temporal vote
       -> speech eligibility/evidence veto
       -> bounded voice queue and local WAV playback
       -> SimulationSession callback
            -> local JSONL publisher and Simulation Events panel
```

This flow follows the current source, not the proposed sequence in BA A-05. In the actual inference path, YOLO detections are cropped and classified before the active alert tracker associates classified observations across frames. The alert tracker then aggregates class predictions by its own Track ID. The [BA pipeline proposal](../../docs/design/01_analysis/BA-analysis_v0.1.md) says Detect → Track → Classify → Aggregate → Alert; this ordering is not the implemented order.

## Components and verified responsibilities

| Component | Verified responsibility |
|---|---|
| [main.py](../../src/traffic_sign_demo/main.py) | Parses `--imgsz` (default 640), `--detector` (default GTSDB), `--debug-seek`, `--alert-observations` (2–5), and `--debug`; starts the Tkinter application and logging runtime. |
| [desktop_ui.py](../../src/traffic_sign_demo/desktop_ui.py) | Tkinter/ttk desktop, 7:3 video/events columns, 960×540 maximum display size with aspect-preserving resize, playback controls, seek slider, concise Vietnamese status line, event image/card, and UI-thread polling. Technical metrics are computed internally but are not rendered as normal UI labels. |
| [video_reader.py](../../src/traffic_sign_demo/video_reader.py) and [playback_controller.py](../../src/traffic_sign_demo/playback_controller.py) | Open/decode MP4 and AVI, maintain playback state, expose seek/replay/pause/resume/stop, and handle source frame timing. |
| [inference_service.py](../../src/traffic_sign_demo/inference_service.py) | Starts isolated YOLO/CNN Python worker processes, exchanges JSON-line requests, clips detections, preprocesses crops, validates response identities/classes, and returns classified detections. Request and result queues each have capacity one and replace older queued values. |
| [yolo_worker.py](../../src/traffic_sign_demo/yolo_worker.py) | Loads a local Ultralytics detection checkpoint; validates the task; selects `device="cpu"`; runs at the requested image size and confidence. The normal app defaults are `imgsz=640`, `conf=0.25`, and detector `gtsdb`. |
| [cnn_worker.py](../../src/traffic_sign_demo/cnn_worker.py) | Loads local Keras `model.h5`, verifies `(30, 30, 3)` input and output class count against the mapping, and returns the highest-scoring class for each crop. |
| [vision.py](../../src/traffic_sign_demo/vision.py) | Converts BGR crops to resized, normalized RGB tensors; renders bounding boxes and Vietnamese labels. The renderer does not receive/render a Track ID. |
| [alert_tracking.py](../../src/traffic_sign_demo/alert_tracking.py) | Assigns alert Track IDs with custom motion/appearance association and keeps temporal class votes. This is not ByteTrack. |
| [sign_tracking.py](../../src/traffic_sign_demo/sign_tracking.py) | Carries recent visual detections between inference results using local image-template matching for up to 350 ms. It does not provide the persistent alert Track IDs. |
| [tracked_voice_alerts.py](../../src/traffic_sign_demo/tracked_voice_alerts.py) and [speech_evidence.py](../../src/traffic_sign_demo/speech_evidence.py) | Confirm per-track predictions, filter speech using crop-face evidence, suppress duplicate offers for a Track ID, and schedule spoken alerts. |
| [voice_alerts.py](../../src/traffic_sign_demo/voice_alerts.py) | Selects a local class WAV from `assets/voice_google` first, falls back to `assets/voice_vi`, and plays asynchronously with Windows `winsound`. No runtime Google TTS request is made by this path. |
| [simulation_events.py](../../src/traffic_sign_demo/simulation_events.py) | Maps confirmed class IDs to semantic event types/actions, maintains playback-session identity, and queues JSONL writes. It is an event interface/export, not an autonomous-vehicle simulator. |
| [logging_config.py](../../src/traffic_sign_demo/logging_config.py) | Queued console and UTF-8 rotating-file logging. The file target is `logs/traffic_sign_demo.log`, maximum 5 MiB per file, with three backups; file logging is DEBUG and console logging is INFO unless `--debug` enables console DEBUG. |

## Detector and classifier details

- Default detector key: `gtsdb`; file: `models/candidates/gtsdb_yolov8n.pt`. The provenance record contains SHA-256 `f1d5b008c38ea080aca89e82725fbf9080f70ea239378011df95b855f2e5797e`; the worker verifies that hash and the single `traffic_sign` class for this candidate.
- The application sends BGR frames to YOLO, clips valid boxes, crops each detection, resizes to 30×30, converts BGR to RGB, and scales pixels by 255 before CNN inference.
- Runtime CNN outputs must match the 43-entry class map. Vietnamese names are a presentation mapping; the 43 class IDs correspond directly to CNN output indices.
- `models/model.py` contains a CNN training script with 30×30 inputs and a 43-output softmax architecture. This script is not sufficient evidence that the checked-in `model.h5` was produced by those exact data/training settings.

## Tracking and temporal aggregation

`AlertTracks` associates classified observations with existing alert tracks using predicted position/velocity, box overlap, and normalized grayscale appearance features, then greedily accepts highest-scoring unambiguous pairs. Tracks expire after a 900 ms media-time gap. This is project-specific association logic, not the ByteTrack algorithm named in design documents.

Each alert track stores up to five class votes within a 1,300 ms media-time window. The weighted winner must meet the configured minimum observation count (default 2) and at least 65% of total vote weight. Speech further requires the current prediction to agree and enough eligible observations; evidence vetoes can suppress audio. These are verified implementation constants, not approved academic acceptance thresholds.

## Playback and throughput implications

Playback is scheduled against source video FPS. The UI buffers display frames, inference requests are bounded/latest-value, and requests may expire after 250 ms. Playback may skip source frames to maintain the display schedule; AI inference is not guaranteed for every displayed frame. Historical performance numbers must therefore distinguish display FPS, AI endpoint FPS, whole-run AI result rate, inference turnaround, overlay delay, and detection-to-speech latency.

## Simulation event and storage path

The event map covers all 43 classifier IDs. A temporally confirmed event can be marked `withheld` when speech evidence blocks its action. The Tkinter panel updates only for a confirmed event with an allowed suggested action. JSONL events are queued to `%LOCALAPPDATA%\\TrafficSignDemo\\simulation-events\\session-<id>.jsonl` by default, using an internal bounded queue of 128. This internal persistent event output should be reconciled with BA A-12 and requirement decision Q-05 before claiming storage behavior was fully specified.

