# Requirements traceability — evidence snapshot

The approved [REQ-spec v0.3](../../docs/design/02_requirements/REQ-spec_v0.3.md) is the requirements source. Status reflects the current inspected working tree and the evidence linked below; “implemented” does not mean every criterion is satisfied or that an NFR target has been met.

## Functional requirements

| Requirement | Evidence-based status | Notes |
|---|---|---|
| FR-01 — Choose video file | Implemented | Tk file picker; MP4/AVI reader. Invalid/open failures surface to the UI. |
| FR-02 — Read/display on playback timeline | Partial | Playback is scheduled against source FPS; buffered display and frame skipping keep the timeline moving. Inference is latest-value/bounded and does not process every frame. Historical display FPS is measured below source/AI rates; no approved target exists. |
| FR-03 — Detect common sign class | Implemented | Default YOLO model returns the common `traffic_sign` detection class and boxes. Sampled detection precision/recall varies by evaluation set. |
| FR-04 — Track and assign IDs | Partial | Custom appearance/velocity/overlap tracker assigns IDs for alert logic; not ByteTrack. Hand-reviewed ID switches and reacquisition risk are recorded. Track ID is not included in the visual overlay. |
| FR-05 — Classify German sign | Implemented | CNN returns one of 43 mapped classes from 30×30 RGB crops. Provenance and cross-domain performance remain limited. |
| FR-06 — Aggregate across frames | Implemented in code; not reflected in approved RTM | Weighted five-vote/1.3 s aggregation with configurable minimum 2–5 observations and a 0.65 vote-share threshold. Approved SRS leaves this method open. |
| FR-07 — Determine recognition state | Partial | Tracks become class-confirmed or blocked for speech evidence; no separate “unrecognized” class/state/transition behavior matching the unresolved A-16 criteria was found. |
| FR-08 — Show video, class, and Track ID | Partial | Video, bounding boxes, and Vietnamese labels are drawn. `draw_overlay` receives detections, not Track IDs, and renders no Track ID; the current event card also omits it. |
| FR-09 — Class-specific voice alert | Implemented with eligibility limits | Confirmed tracks can queue a class-specific local WAV after agreement and image-evidence checks. Some valid tracks are deliberately withheld; Roundabout speech is disabled. |
| FR-10 — Generic alert for unrecognized sign | Not implemented | No unknown CNN class or generic unknown-sign audio branch. Evidence veto/withheld status is not a generic sound. |
| FR-11 — One alert per Track ID | Partial | `offered` suppresses another offer for that alert-track lifetime. ID switches/reacquisition under a new ID can permit a repeat for the same physical sign. |
| FR-12 — Alert queue | Implemented with bounded/expiry policy | Voice queue capacity 3, priority, freshness checks, expiration, and overflow eviction. JSONL export has a separate capacity-128 queue and can drop on saturation. The approved SRS leaves detailed policy open. |
| FR-13 — Parameters from configuration file | Not implemented as specified | CLI and worker-Python environment overrides exist; no configuration-file loader or config files were found. |
| FR-14 — Pause, resume, stop | Implemented | `PlaybackController` and desktop controls implement these states; historical live reports exercise the controls. |

## Non-functional requirements and trace maturity

- NFR-01 has no numeric acceptance target. Historical evidence records display FPS, AI rate, turnaround, overlay timing, and detection-to-speech separately; they do not establish that all frames are analyzed at real-time speed.
- NFR-02 through NFR-08 have some test or experimental evidence, but no approved quantitative acceptance criteria. Dataset composition and collection limitations are in [experiments_and_results.md](./experiments_and_results.md).
- NFR-09's approved expectation that parameters are outside source code is not met by a file-based configuration mechanism.
- NFR-10 is marked as a proposal in REQ-spec v0.3, not an approved requirement.
- The RTM v0.3 currently lists Use Case IDs and several module/test links as “not yet identified.” Later Use Case documentation defines UC-01–UC-05 and coverage, but RTM v0.3 was not synchronized. UML source exists but is documented as not rendered.

## Scope and design decisions

- German signs and local video/desktop operation are documented requirements.
- Live camera input and a 2D taxi simulator are explicitly future/out-of-scope. Local JSONL event generation is implemented, but it does not constitute simulator integration.
- BA A-05 and design documents name ByteTrack, while source uses project-specific tracking and classifies each detected crop before alert-track association.
- BA A-08 / FR-10 require a generic unknown-sign sound, but the implemented speech path has class-specific WAVs and vetoes, with no unknown class path.
- BA A-11 / FR-13 require configuration files, but source offers CLI/environment overrides only.
- Q-05 excludes user-facing result-log export, while `SimulationSession` persists event JSONL internally. This distinction and the unresolved BA A-12 storage decision should be recorded explicitly.

