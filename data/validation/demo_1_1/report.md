# Traffic Sign Recognition Demo 1.1 — Simulation Integration Ready

## Version

The application is on `development-v2`, commit `6825fd4`. The `final-demo` tag still resolves to `f2f61cbde310b762fd351873f546b761b631343f`. Step H–K evidence remains in its original folders. The existing model weights, confidence thresholds, class mapping, speech policy, Google WAVs, and tracking rules also remain in use.

## Launch and demo

~~~powershell
Set-Location D:\Traffic-sign-project
python -m src.traffic_sign_demo
~~~

Choose **Open Video**, select `data/videos/test_video.mp4`, and let playback run from frame zero. The **Simulation Events** panel below the playback controls shows the last confirmed Vietnamese sign, Track ID, semantic event type, and suggested simulation action. It starts with neutral placeholders and **Simulator: Not Connected**. Its reserved space keeps the main video and controls in their normal positions.

The overlay shows the raw CNN prediction. The panel uses the existing confirmed track. **Tạm giữ — bằng chứng chưa đủ** means the confirmation lacks supporting evidence for an action. The panel stays disconnected because this release supplies a local event interface for future simulation work.

## Event contract and export

The temporal tracker publishes through `SimulationPublisher.publish_simulation_event(event)` before the voice queue considers the alert. Queued, expired, suppressed, and failed audio cannot prevent a confirmed event from being considered for export.

- `confirmed: true` records temporal confirmation. `decision_status: "confirmed"` means the existing evidence guard allows the semantic suggestion. A blocked confirmed track produces `decision_status: "withheld"`, a null action, empty parameters, and a recorded rejection reason. An unconfirmed track produces no event.
- `video_timestamp_ms` and `source_frame_id` refer to source playback. `created_at` is a separate UTC wall-clock timestamp. Evidence includes the matching vote count, winning confidence-weight share, and a bounding box in display-frame coordinates with its frame dimensions.
- Actions express road-rule constraints or observations for a future simulator. STOP, Yield, and turn events carry semantic meaning only. The release includes no actuation, network connection, or driving controller.

The UTF‑8 JSONL files are written to `%LOCALAPPDATA%\TrafficSignDemo\simulation-events\session-<id>.jsonl` by default. Each file starts with exclusive creation, followed by ordered appends. A 128-entry worker queue bounds memory. The app reports dropped entries and write errors in the panel. It writes and closes each line on the worker and gives the queue up to two seconds to drain when closing the window. Files are created only for sessions with an event. [Event JSON Schema](event.schema.json)

| Playback change | Event session |
|---|---|
| Open Video, Replay, deliberate Seek | New UUID and a neutral panel. Old inference generations are rejected. |
| Pause / Resume | Same session and Track-ID history. The event adapter follows the new inference generation. |
| Stop or final buffered frame | Session ends and the panel clears. Already accepted entries drain into their original files. |

The live track carries the last session in which it emitted an event. This bounds deduplication by active tracking state and permits different tracks of the same class to publish separately. The first confirmed event for a Track ID is the session's only event for that ID. Later label changes do not replace it.

## Regression

~~~powershell
$env:TRAFFIC_SIGN_REAL_MODEL_TEST = '1'
python -m unittest discover -s tests
~~~

The suite passed **110 tests**, including all 96 baseline tests and 14 new simulation tests. The new coverage includes class mappings and Unicode schema, withheld and unconfirmed cases, session invalidation, same-class tracks, repeated callbacks, panel thread affinity, export failures, and event delivery after audio failure or expiration.

## Desktop validation and performance

The live Demo 1.1 run opened the original `test_video.mp4` and advanced automatically through frame **1503**. The main image showed readable **Nhường đường** and **Rẽ phải** overlays. The panel reported `YIELD_SIGN` for Track 65 and remained **Simulator: Not Connected**. The actual Windows audio backend played **eight Google WAVs** in sequence. The JSONL worker wrote **16 events** and reported zero drops or write errors. Six exported events had voice alerts that later expired. The separate EOF check wrote eight events, cleared the panel and session, and cancelled three pending voice alerts. Pause and Resume preserved the session. Seek, Stop and Replay passed the live checks. The recorded workers exited after close. [Live trace](demo-live.json) · [Yield overlay](yield-overlay.png) · [EOF trace](eof-live.json) · [Test log](regression.log)

Two examples from the actual session were `YIELD_SIGN` at **45,733.33 ms**, Track **65**, with **Chuẩn bị nhường đường** and `KEEP_RIGHT` at **14,666.67 ms**, Track **22**, with status **withheld**, null action, and reason `mandatory_blue_face_unverified`. Both original JSONL files parsed and validated against the published schema. [Full sample objects](sample-real-events.json) · [City JSONL](events/session-9c0e8e09f8a34687b54ea6186e4e8d99.jsonl) · [EOF JSONL](events/session-d649ec831c184171b2bcbf6e54a6a6fa.jsonl)

| First 50 seconds of source video on CPU | Frozen baseline | Demo 1.1 |
|---|---:|---:|
| Display FPS | 16.12 | 16.65 |
| AI results per second over the run | 4.48 | 4.52 |
| Median submit-to-result latency after frame zero | 190.1 ms | 185.7 ms |
| Median detection-to-speech latency | 1.88 s | 1.86 s |
| Rolling AI FPS at endpoint | 7.18 | 1.23 |

Each run produced 231 warm AI results. The whole-run rates show similar throughput, while the endpoint metric fluctuated substantially. One pair of runs gives limited evidence about short-term rate variation. An earlier Demo 1.1 run overlapped the real-model test suite and was excluded from the comparison. [Baseline trace](baseline-live.json) · [Measured metrics](validation-metrics.json)

## Remaining limitations

Track fragmentation can produce a second event for the same physical sign under a new Track ID. The detector retains the known electronic speed-sign and other classification limitations. The evidence guard sometimes withholds correct decisions and leaves specific Roundabout actions withheld. The queue can drop new entries when sustained disk delays exhaust capacity. The report supports a controlled desktop demonstration and a simulator-facing event handoff.

## Files

- Added `src/traffic_sign_demo/simulation_events.py`, `tests/test_simulation_events.py`, and `event.schema.json`.
- Updated `src/traffic_sign_demo/alert_tracking.py`, `src/traffic_sign_demo/tracked_voice_alerts.py`, and `src/traffic_sign_demo/desktop_ui.py`.
- Updated the integration fixtures in `tests/test_ai_pipeline.py` and `tests/test_desktop_ui.py`.

## Class-to-event mapping

| ID | Vietnamese label | Event type | Suggested semantic action | Parameters |
|---:|---|---|---|---|
| 0 | Tốc độ tối đa (20km/h) | SPEED_LIMIT_20 | Cập nhật giới hạn tốc độ | {"limit_kmh": 20} |
| 1 | Tốc độ tối đa (30km/h) | SPEED_LIMIT_30 | Cập nhật giới hạn tốc độ | {"limit_kmh": 30} |
| 2 | Tốc độ tối đa (50km/h) | SPEED_LIMIT_50 | Cập nhật giới hạn tốc độ | {"limit_kmh": 50} |
| 3 | Tốc độ tối đa (60km/h) | SPEED_LIMIT_60 | Cập nhật giới hạn tốc độ | {"limit_kmh": 60} |
| 4 | Tốc độ tối đa (70km/h) | SPEED_LIMIT_70 | Cập nhật giới hạn tốc độ | {"limit_kmh": 70} |
| 5 | Tốc độ tối đa (80km/h) | SPEED_LIMIT_80 | Cập nhật giới hạn tốc độ | {"limit_kmh": 80} |
| 6 | Hết hạn chế tốc độ (80km/h) | END_SPEED_LIMIT_80 | Ghi nhận kết thúc giới hạn 80 km/h | {"ended_limit_kmh": 80} |
| 7 | Tốc độ tối đa (100km/h) | SPEED_LIMIT_100 | Cập nhật giới hạn tốc độ | {"limit_kmh": 100} |
| 8 | Tốc độ tối đa (120km/h) | SPEED_LIMIT_120 | Cập nhật giới hạn tốc độ | {"limit_kmh": 120} |
| 9 | Cấm vượt | NO_OVERTAKING | Ghi nhận đoạn đường cấm vượt | ? |
| 10 | Cấm xe tải vượt | NO_TRUCK_OVERTAKING | Ghi nhận hạn chế vượt dành cho xe tải | ? |
| 11 | Giao nhau với đường ưu tiên | PRIORITY_AT_INTERSECTION | Ghi nhận quyền ưu tiên tại giao lộ | ? |
| 12 | Đường ưu tiên | PRIORITY_ROAD | Cập nhật thông tin quyền ưu tiên | ? |
| 13 | Nhường đường | YIELD_SIGN | Chuẩn bị nhường đường | ? |
| 14 | Dừng lại (Stop) | STOP_SIGN | Lập kế hoạch dừng tại vị trí hợp lệ | ? |
| 15 | Đường cấm | NO_VEHICLE_ACCESS | Ghi nhận đường cấm phương tiện | ? |
| 16 | Cấm xe tải (trên 3.5 tấn) | HEAVY_VEHICLE_RESTRICTION | Ghi nhận hạn chế phương tiện trên 3,5 tấn | {"mass_threshold_t": 3.5} |
| 17 | Cấm đi ngược chiều | NO_ENTRY | Đánh dấu hướng đường không hợp lệ | ? |
| 18 | Nguy hiểm khác | GENERAL_DANGER | Ghi nhận cảnh báo nguy hiểm | ? |
| 19 | Chỗ ngoặt nguy hiểm (trái) | DANGEROUS_LEFT_CURVE | Ghi nhận cảnh báo khúc cua trái | ? |
| 20 | Chỗ ngoặt nguy hiểm (phải) | DANGEROUS_RIGHT_CURVE | Ghi nhận cảnh báo khúc cua phải | ? |
| 21 | Đường cong liên tục | DOUBLE_CURVE | Ghi nhận cảnh báo đường cong liên tục | ? |
| 22 | Đường gồ ghề | UNEVEN_ROAD | Ghi nhận cảnh báo mặt đường gồ ghề | ? |
| 23 | Đường trơn trượt | SLIPPERY_ROAD | Ghi nhận cảnh báo mặt đường trơn | ? |
| 24 | Đường hẹp (phải) | ROAD_NARROWS_RIGHT | Ghi nhận cảnh báo đường hẹp bên phải | ? |
| 25 | Công trường | ROAD_WORK | Ghi nhận cảnh báo công trường | ? |
| 26 | Đèn tín hiệu giao thông | TRAFFIC_SIGNALS_AHEAD | Ghi nhận cảnh báo đèn tín hiệu phía trước | ? |
| 27 | Đường người đi bộ | PEDESTRIANS | Ghi nhận cảnh báo người đi bộ | ? |
| 28 | Trẻ em qua đường | CHILDREN_CROSSING | Ghi nhận cảnh báo trẻ em qua đường | ? |
| 29 | Đường xe đạp | BICYCLES_CROSSING | Ghi nhận cảnh báo xe đạp | ? |
| 30 | Cẩn thận băng tuyết | ICE_OR_SNOW | Ghi nhận cảnh báo băng tuyết | ? |
| 31 | Thú rừng qua đường | WILD_ANIMALS | Ghi nhận cảnh báo thú rừng qua đường | ? |
| 32 | Hết tất cả lệnh cấm | END_SPEED_AND_OVERTAKING_RESTRICTIONS | Ghi nhận kết thúc các hạn chế tốc độ và vượt | ? |
| 33 | Rẽ phải | TURN_RIGHT_ONLY | Giới hạn hướng đi hợp lệ | {"permitted_direction": "right"} |
| 34 | Rẽ trái | TURN_LEFT_ONLY | Chỉ cho phép hướng rẽ trái | {"permitted_direction": "left"} |
| 35 | Đi thẳng | STRAIGHT_ONLY | Chỉ cho phép hướng đi thẳng | {"permitted_direction": "straight"} |
| 36 | Đi thẳng hoặc rẽ phải | STRAIGHT_OR_RIGHT | Ghi nhận hướng đi thẳng hoặc rẽ phải | ? |
| 37 | Đi thẳng hoặc rẽ trái | STRAIGHT_OR_LEFT | Ghi nhận hướng đi thẳng hoặc rẽ trái | ? |
| 38 | Giữ bên phải | KEEP_RIGHT | Ghi nhận ràng buộc đi bên phải | ? |
| 39 | Giữ bên trái | KEEP_LEFT | Ghi nhận ràng buộc đi bên trái | ? |
| 40 | Vòng xuyến | ROUNDABOUT | Ghi nhận quy tắc đi qua vòng xuyến | ? |
| 41 | Hết cấm vượt | END_NO_OVERTAKING | Ghi nhận kết thúc đoạn cấm vượt | ? |
| 42 | Hết cấm xe tải vượt | END_NO_TRUCK_OVERTAKING | Ghi nhận kết thúc đoạn cấm xe tải vượt | ? |
