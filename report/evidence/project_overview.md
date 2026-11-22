# Project overview — verified evidence

## Evidence scope

This package records facts from the current working tree, project documentation, local validation artifacts, and the test runs stated below. Labels distinguish:

- **Requirement/documented** — stated in the BA/SRS or project records; not automatically proof of implementation.
- **Verified implementation** — directly checked in the current Python source.
- **Historical experiment** — result preserved from a named validation run; not a new or pooled benchmark.
- **Open / unverified** — missing, unresolved, proposed, or not independently established.

The inspected repository was on `development-v2`, at HEAD `6825fd44b4eb56e1ff97e70485a8a8a7e9513b85`; `final-demo^{commit}` resolves to `f2f61cbde310b762fd351873f546b761b631343f`. The worktree already contained modified and untracked application, test, documentation, asset, and validation files before this evidence package was created. Source observations below describe that working tree and must not be attributed automatically to the committed HEAD. No pre-existing worktree changes were intentionally changed.

## Purpose and scope

The approved [BA Analysis](../../docs/design/01_analysis/BA-analysis_v0.1.md) and [Requirement Specification v0.3](../../docs/design/02_requirements/REQ-spec_v0.3.md) describe a local desktop application that accepts user-selected recorded video, detects and classifies German traffic signs, presents visual results, and issues spoken alerts while limiting repeats per Track ID. The current source supports MP4 and AVI input and presents a local Simulation Events panel.

The requirements and [Use Case Catalog](../../docs/design/03_use_case/use-case-catalog_v0.1.md) identify one primary Actor, **User**, and five Use Cases: analyze video, issue sign alerts, pause, resume, and stop. These are requirements/design facts, not proof that every acceptance criterion is implemented.

**Out of scope:** live camera input and integration with a 2D autonomous-vehicle/taxi simulator. The application writes semantic events to local JSONL files, but no simulator, vehicle controller, network handoff, or actuation component was found. Treat simulation as future development.

## Current status and design evidence

- The user-provided task context identifies Demo 1.1 as the project baseline. The repository's [project status](../../docs/00_project/project-status.md) is not synchronized with that statement: it still says Phase 2 complete, Phase 3 current, and `Code allowed: NO`.
- [REQ-spec v0.3](../../docs/design/02_requirements/REQ-spec_v0.3.md) and [RTM v0.3](../../docs/design/02_requirements/RTM_v0.3.md) are marked approved. The RTM still records several trace fields as “not yet identified,” despite the later Phase 3 Use Case documents.
- [Use Case documents](../../docs/design/03_use_case/use-case-catalog_v0.1.md) describe UC-01–UC-05 and their requirement coverage. The [PlantUML source](../../docs/design/03_use_case/diagrams/use-case-diagram_v0.1.puml) exists; its companion notes say it was not rendered, so no rendered UML diagram was visually verified.
- The [BA Analysis](../../docs/design/01_analysis/BA-analysis_v0.1.md) is marked draft. It contains proposals and open issues that must not be presented as confirmed implementation facts.

## Hardware and execution context

The BA documents the target machine as Intel Core i7-8550U (4 cores / 8 threads), 8 GB RAM, Windows 11, 512 GB SSD, Intel UHD 620 and AMD Radeon 530, without an NVIDIA GPU. The SRS repeats the CPU/RAM/Windows/no-NVIDIA constraints. This is documented hardware information; it was not independently inventoried during this evidence collection. Historical live-run JSON records 8 logical CPUs. The YOLO worker explicitly selects CPU inference; no GPU acceleration claim is supported here.

## Model and dataset provenance

- The runtime class map contains 43 consecutive class IDs, 0–42, in [models/model.py](../../models/model.py). The runtime loads this literal mapping through [class_mapping.py](../../src/traffic_sign_demo/class_mapping.py). Vietnamese presentation labels are in [vietnamese_labels.py](../../src/traffic_sign_demo/vietnamese_labels.py).
- The CNN checkpoint [model.h5](../../models/model.h5) is present. The training script refers to an external absolute data path (`D:/CODE/Traffic_sign_classification/Data`) and its save statement is commented out. No verified run record establishes the exact training data, split, or provenance of the checkpoint.
- The default detector is the local [gtsdb_yolov8n.pt](../../models/candidates/gtsdb_yolov8n.pt). Its local [provenance record](../../models/candidates/gtsdb_yolov8n.provenance.json) names GTSDB, a one-class `traffic_sign` detector, source commit, and SHA-256. A separate [traffic_sign_yolo.pt](../../models/traffic_sign_yolo.pt) is available as an alternative; its training provenance was not verified here.
- Validation artifacts evaluate GTSRB crops, GTSDB scenes, a local moving-video sample, and a BelgiumTSC holdout. Their results and dataset limitations are documented separately in [experiments_and_results.md](./experiments_and_results.md). They do not prove the CNN checkpoint's complete training provenance.

## Important limitations

1. The source uses a project-specific tracker, not ByteTrack; actual processing order differs from the proposed BA pipeline.
2. The system has no explicit “unknown” CNN class or generic unknown-sign audio path.
3. FR-08 requires Track IDs beside visible labels, but the current video overlay draws the Vietnamese class label without a Track ID.
4. FR-13 requires configuration-file loading. The [configs directory](../../configs/) contained no files, and the inspected CLI/environment paths do not implement a parameter file.
5. Real-time display and AI processing rates are different. Historical runs show AI sampling below display rate; no numeric NFR threshold has been approved.
6. There is no evidence of real-world road-safety certification, broad operational validation, or a user study.

