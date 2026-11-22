# Open questions and evidence gaps

## Requirements/design issues still open in project documents

The [BA Analysis](../../docs/design/01_analysis/BA-analysis_v0.1.md), [REQ-spec v0.3](../../docs/design/02_requirements/REQ-spec_v0.3.md), and [RTM v0.3](../../docs/design/02_requirements/RTM_v0.3.md) leave the following open or incomplete:

- **A-14 / A-15 / OI-03:** CNN training dataset/version and splits, detector data and source, model input/classes/preprocessing rationale. Source identifies actual runtime settings but not complete training provenance.
- **A-16 / OI-02:** approved definition of “recognized,” “unrecognized,” sufficient confidence, and state transitions. Current evidence vetoes are implementation behavior, not a signed requirements decision.
- **A-17 / OI-01:** approved behavior when AI cannot keep pace with playback. Source uses latest-value bounded queues and frame sampling; no user-approved policy/acceptance criterion was found.
- **OI-04:** alert order, overflow/expiry, interruption and pause/stop behavior. Source now has finite queue, priorities, expiry, and cancellation behavior, but the approved documents remain open.
- **OI-05:** aggregation/frame-selection method. Source implements temporal voting, but approved requirements and RTM have not recorded the final method.
- **A-18 / OI-06:** spoken language approval. Vietnamese labels/clips are implemented; approval record was not found.
- **A-19 / OI-07:** individual vs. group report authorship/management.
- **FR-13:** who provides/updates configuration, required fields and invalid/missing-file handling. No file-based config loader exists despite the approved requirement.
- **Q-05 / A-12:** clarify whether internal Simulation Events JSONL persistence is permitted while user-facing result-log export remains out of scope and long-term storage was deferred.

## Requirements-to-implementation gaps

1. **Unknown signs:** FR-10 requires a generic sound, but the 43-class CNN path has no unknown class or generic audio. Define whether a separate unknown state is required and how it is detected.
2. **Visible Track IDs:** FR-08 requires ID beside each label. The current renderer draws Vietnamese labels and boxes but not IDs. Decide whether this is an implementation gap or whether the approved requirement should change.
3. **Tracker choice/order:** approved BA/use-case content says ByteTrack and Detect → Track → Classify. Current code uses custom association after per-detection CNN classification. Decide whether documentation should be updated to actual design or implementation should change in a future authorized phase.
4. **Configuration file:** either provide and validate the approved file mechanism or formally revise FR-13 to the supported CLI/environment interface.
5. **Event export:** define retention, privacy, user access, deletion, and failure policy for session JSONL files; identify whether they count as persistent application data under A-12.
6. **Simulator:** no 2D autonomous-vehicle simulator is present. A JSONL semantic event is not evidence that the event was consumed by a simulator.

## Experimental evidence gaps

- The exact CNN `model.h5` training run, weights provenance/hash, dataset release, class balance, split protocol, and training history are not verified. `models/model.py` points to an external absolute directory and is not proof of the checkpoint's provenance.
- The GTSRB result is a crop task; exact upstream version and whether that test split was used during model training are not established. The local audit found eight exact file matches with a tuning crop set.
- The GTSDB J still-scene evaluation overlaps scenes from the detector author's published training/validation conversion according to the validation report; checkpoint exposure is uncertain. Step K avoids identified duplicates/partition overlap, but cannot establish full historical checkpoint exposure.
- BelgiumTSC evidence is mapped crop-level consensus, not full-scene detection or tracking. The source notes no capture timestamps or full-scene track sequences.
- Positive moving-road evidence is dominated by one original video. The small manual tracking counts are not broad tracking metrics. More independently captured routes, conditions, and annotated tracks are needed.
- NFR thresholds have not been approved. AI FPS, display FPS, average result rate, inference latency, overlay delay, and detection-to-speech latency must remain separate measures.
- Hardware model/RAM/GPU are documented in BA/SRS; the live JSON verifies 8 logical CPUs, not a complete hardware inventory for every run.
- Local `voice_google` files are played by the application, and validation records call them Google WAVs; their generation provenance, date, and licensing were not established here.
- The historical desktop reports contain control checks and an event run, but no persistent full-window screenshot was found that independently verifies the latest confirmed-event image in the live UI. The existing overlay PNGs are not full-application screenshots.

## Documentation and reporting gaps

- `project-status.md` remains at Phase 3 / `Code allowed: NO`, while the user-provided task context calls Demo 1.1 finalized and later validation reports describe a completed demo.
- REQ-spec/RTM v0.3 remain marked approved but have not been updated for later UC-01–UC-05 documentation or current implementation. RTM trace fields remain unresolved.
- BA v0.1 is still draft and includes proposed ByteTrack and pipeline choices contradicted by source.
- The historical [Demo 1.1 report](../../data/validation/demo_1_1/report.md) describes a panel below the playback controls with Track ID and simulator connection status. The current [desktop UI](../../src/traffic_sign_demo/desktop_ui.py) instead places a minimal event card on the right and does not render those fields; treat the report's panel description as historical, not current UI evidence.
- PlantUML source exists, but notes record that it was not rendered. A rendered diagram and visual verification are still missing.
- No institution Word template, final chapter structure, approved external bibliography, or author/group decision was found. The BA itself says background claims require real sources before writing.
- The evidence package is not the final academic report and does not create external citations or claims beyond the local artifacts inspected.

