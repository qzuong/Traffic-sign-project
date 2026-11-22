# Implementation inventory

Status terms: **Implemented** means directly present in the current source; **Partial** means the core behavior exists with a documented gap; **Not implemented** means no matching implementation path was found in the inspected source. This inventory does not imply that all behavior has passed broad validation.

## Application features

| Area | Verified implementation and limits |
|---|---|
| Desktop UI | Tkinter/ttk app titled “Traffic Sign Video Demo 1.1”; styled light surface, navy Simulation Events header, responsive 7:3 columns, video card, consistent primary/secondary buttons, horizontal seek control, time label, and one user-facing Vietnamese playback status. The event card shows sign image/name, event type, and suggested action. |
| Video | MP4 and AVI reader; pause, resume, stop, replay, and seek are implemented. The display is resized without cropping and capped at 960×540. AI processing uses bounded queues and does not guarantee every source frame is inferred. |
| YOLO | Default local GTSDB detector, one `traffic_sign` class, Ultralytics detection worker, CPU device, default 640 image size and 0.25 confidence for the desktop command. A separate `original` detector path exists; its provenance was not established. |
| CNN | Local Keras model with 43 output classes; each YOLO box is classified from a normalized 30×30 RGB crop. Runtime mapping is parsed from `models/model.py`; the source script uses an external absolute training-data path, so training provenance remains unverified. |
| Tracking | Persistent IDs for alert logic come from custom IoU/appearance/velocity matching in `alert_tracking.py`. `sign_tracking.py` separately uses image template matching to carry visual detections between inference frames. ByteTrack is not implemented. Historical tests observed ID switches and possible duplicate alerts after reacquisition with a new ID. |
| Temporal aggregation | Confidence-weighted vote across up to five recent observations in a 1.3 s window; default confirmation requires two observations and a winning weight share of at least 0.65. This implementation resolves BA OI-05 behavior in code, but the approved requirements/RTM were not updated with the algorithm. |
| Speech eligibility and queue | Per-class local speech clips; evidence vetoes for unsupported crop appearance and all Roundabout voice; one speech offer per alert Track ID; queue capacity 3, priority ordering, aging, staleness/expiration, and eviction on overflow. A new Track ID can still produce another alert for the same physical sign. |
| Google/eSpeak wording | Source prefers local files in `assets/voice_google` (43 WAVs present) and falls back to `assets/voice_vi` (43 WAVs present), played with Windows `winsound`. Historical validation calls them Google WAVs. The local code proves file selection/playback, not how or when those recordings were generated. |
| Unknown-sign alert | Not implemented: the CNN always returns one of its mapped classes; no unknown class or generic unknown-sign audio branch exists. A speech evidence veto blocks or withholds an action; it does not play a generic sound. |
| Simulation Events | All 43 class IDs have semantic event mappings. A confirmed event may have `decision_status="withheld"` and no suggested action if speech evidence is blocked. The UI shows only events whose decision is confirmed and action is present. The historical [sample event JSON](../../data/validation/demo_1_1/sample-real-events.json) records class 13 as `YIELD_SIGN` / “Nhường đường” and class 38 as withheld for `mandatory_blue_face_unverified`. No Track ID, FPS, confidence, recent-history list, or simulator connection control is rendered in the current card. |
| Sign images | `assets/traffic_signs` contains exactly 43 PNGs; every filename `0.png` through `42.png` exists. Runtime loads `<class_id>.png`, thumbnails to 80×80 while preserving aspect ratio, caches each class, retains the Tk image reference, updates only on allowed event changes, and logs/falls back to a neutral placeholder on missing/invalid files. Tests exercise all 43 class IDs and fallback behavior. This verifies ID/filename wiring; it does not independently prove every image's semantic provenance or pixel content. |
| Event export | Local UTF-8 JSONL event publisher with a 128-entry queue, per-session file, flush-on-write, and counters/logging for dropped or failed writes. This is local event persistence, not simulator integration or full annotated-video export. |
| Logging/debug | `--debug` enables detailed terminal diagnostics; queued rotating UTF-8 log target is `logs/traffic_sign_demo.log`. The inspected worktree contained a log file at that path. Unit tests cover configured file logging. |
| Configuration | `main.py` exposes CLI settings; worker interpreter paths can be overridden with environment variables. No settings file was found under `configs`, and no file-based parameter loader was found. FR-13 is not implemented as specified. |

## Class IDs and image numbering

The runtime `classes` literal in [models/model.py](../../models/model.py) has keys `0..42`; `load_class_mapping` rejects a non-contiguous key set. The UI constructs its image path from the model class ID, `<class_id>.png`. The test suite checks the mapping against `range(43)` and loads/caches images for every mapped ID. Thus class ID 0 selects `0.png`, class ID 13 selects `13.png`, class ID 14 selects `14.png`, and class ID 42 selects `42.png`. The naming and runtime lookup agree; independent provenance checking of the source artwork was not performed.

## Integration gaps requiring accurate reporting

1. **Track ID visibility (FR-08):** Track IDs exist in alert/event data but are not passed to the current bounding-box renderer; the visible overlay label is the Vietnamese class name only.
2. **Unknown classification (FR-07 / FR-10):** no unknown-state audio path; evidence-based suppression is not equivalent to the required generic unknown sound.
3. **Configuration (FR-13):** CLI/environment options exist, but no configuration-file loading exists.
4. **Pipeline sequence:** actual crop classification precedes alert-track matching; design documents describe tracking before classification.
5. **Storage boundary:** the app writes event JSONL although BA A-12 leaves long-term storage for a later phase and Q-05 excludes user-facing result-log export. The distinction between internal event persistence and user export needs an explicit requirement decision.
6. **Simulator:** JSONL events are available locally; a 2D taxi/vehicle simulator and live event consumer are absent.

## Test evidence

- The current default test run executed **123 tests: 122 passed, 1 opt-in real-model test skipped**.
- The supported opt-in subset (`TRAFFIC_SIGN_REAL_MODEL_TEST=1`, `test_ai_pipeline.py`) executed **24 tests, all passed**, including a real YOLO/CNN regression on `test_video.mp4` frame 1358.
- Historical summaries report different counts for different snapshots: **96 passed** in the final-demo summary and **110 passed** in the Demo 1.1 simulation-integration report. These counts are not interchangeable with the current run.

