# Use Case Identification and Catalog - v0.1
Ngày cập nhật mô hình: 20/11/2026
Trạng thái: Cập nhật theo mô hình 5 Use Case được người dùng chốt.

Nhãn: [Xác nhận] = có căn cứ trong tài liệu đã duyệt hoặc quyết định người dùng; [Chưa xác định] = còn Open Issue.

## 1. Purpose and Sources
Ghi nhận Use Case Catalog hiện hành và truy vết FR-01..FR-14. Không tạo Actor ngoài User, không tách thuật toán thành Use Case và không thay đổi yêu cầu.

Nguồn: [BA Analysis](../01_analysis/BA-analysis_v0.1.md), [REQ-spec v0.3](../02_requirements/REQ-spec_v0.3.md), [Actor Analysis](./actor-analysis_v0.1.md), [Use Case Reassessment](./use-case-reassessment_v0.1.md), [Actor–Use Case Matrix](./actor-usecase-matrix_v0.1.md).

## 2. Confirmed Actor
| Actor | Role | Evidence |
|---|---|---|
| User | Primary Actor; chọn video, xem kết quả, nhận cảnh báo và điều khiển phiên | BA §3; FR-01, FR-08, FR-14 |

[Xác nhận] Không có Supporting Actor được xác nhận. YOLO, CNN, ByteTrack, TTS và Configuration Loading là thành phần/xử lý nội bộ; file video và cấu hình là Data Resource. Không thêm Driver hoặc Administrator.

## 3. Use Case ID Migration
| ID trước mô hình 5 UC | Xử lý trong mô hình hiện hành |
|---|---|
| UC-01 — Phân tích video biển báo giao thông | Giữ UC-01; thu hẹp phạm vi về phân tích và hiển thị kết quả. Cảnh báo chuyển sang UC-02. |
| UC-02 — Điều khiển quá trình xử lý video | ID cũ được thay thế; các thao tác được phân thành UC-03 Pause, UC-04 Resume và UC-05 Stop. Không giữ UC-02 cũ làm Use Case hiện hành. |
| UCC-04 — Receive traffic-sign alerts | Candidate cũ được chuẩn hóa thành UC-02 — Phát cảnh báo biển báo. |
| UCC-03 — Select a video file | Không phải Use Case độc lập; giữ là trigger/bước đầu vào của UC-01. |
| UCC-05 — Configure system parameters | Không phải Use Case; Configuration Loading là xử lý nội bộ hỗ trợ UC-01. |

## 4. Use Case Catalog
| Use Case ID | Use Case Name | Primary Actor | Goal / Outcome chính | Related FR |
|---|---|---|---|---|
| UC-01 | Phân tích video biển báo giao thông | User | Phân tích video theo timeline và xem kết quả nhận diện | FR-01..FR-06, FR-08, FR-13 |
| UC-02 | Phát cảnh báo biển báo | User (người nhận) | Nghe cảnh báo theo lớp hoặc âm thanh chung khi đủ điều kiện | FR-07, FR-09..FR-12 |
| UC-03 | Tạm dừng xử lý video | User | Giữ Frame hiện tại và ngừng xử lý Frame mới | FR-14 AC-1 |
| UC-04 | Tiếp tục xử lý video | User | Tiếp tục xử lý từ Frame đang dừng | FR-14 AC-2 |
| UC-05 | Dừng xử lý video | User | Kết thúc phiên và đưa ứng dụng về trạng thái sẵn sàng chọn video mới | FR-14 AC-3 |

## 5. Use Case Descriptions

### UC-01 — Phân tích video biển báo giao thông
- **Trigger:** User chọn file video (FR-01).
- **Precondition:** Video được chọn và đọc được để vào luồng thành công; file lỗi thuộc luồng ngoại lệ FR-01.
- **Main behavior:** Đọc Frame theo timeline; phát hiện, theo dõi, phân loại và tổng hợp theo Track ID; hiển thị video, bounding box, nhãn và Track ID.
- **Outcome:** User quan sát kết quả; hệ thống báo hoàn tất khi video kết thúc.
- **Supporting/internal behavior:** FR-03..FR-07 và FR-13; UC-02 xử lý cảnh báo có điều kiện.

### UC-02 — Phát cảnh báo biển báo
- **Trigger:** Hệ thống đánh giá trạng thái nhận diện của một track trong UC-01.
- **Precondition:** UC-01 đang xử lý video; Track ID chưa từng được cảnh báo; trạng thái track đạt điều kiện cảnh báo theo tiêu chí được duyệt.
- **Outcome:** Phát cảnh báo giọng nói riêng cho lớp đã nhận diện (FR-09) hoặc âm thanh chung cho track không nhận diện được (FR-10); chống trùng theo Track ID (FR-11), xếp hàng theo FR-12.
- **Extension point trong UC-01:** Sau khi xác định trạng thái nhận diện của Track ID, tại bước đánh giá quyết định cảnh báo.
- **Điều kiện `extend`:** Track chưa được cảnh báo và trạng thái là “đã nhận diện” theo tiêu chí được duyệt hoặc “không nhận diện được” theo tiêu chí được duyệt. Tiêu chí cụ thể còn mở tại A-16/OI-02; không đặt ngưỡng tại đây.
- **Kết luận quan hệ:** UC-02 `extend` UC-01. UC-01 vẫn có kết quả giá trị khi không có track đủ điều kiện cảnh báo. FR-09 và FR-10 là hai nhánh loại cảnh báo bên trong UC-02, không phải Use Case riêng.

### UC-03 — Tạm dừng xử lý video
- **Trigger:** User yêu cầu Pause.
- **Precondition:** Có phiên video đang được xử lý/phát.
- **Outcome:** Giữ Frame hiện tại và không xử lý Frame mới (FR-14 AC-1).
- **Open behavior:** Tác động Pause lên cảnh báo/queue/track còn mở tại OI-04.

### UC-04 — Tiếp tục xử lý video
- **Trigger:** User yêu cầu Resume.
- **Precondition:** Phiên đang tạm dừng tại một Frame.
- **Outcome:** Tiếp tục xử lý từ Frame đang dừng (FR-14 AC-2).
- **Open behavior:** Tác động Resume lên cảnh báo/queue/track còn mở tại OI-04.

### UC-05 — Dừng xử lý video
- **Trigger:** User yêu cầu Stop.
- **Precondition:** Có phiên xử lý hiện hành làm đối tượng để kết thúc; việc Stop khi đang Pause chưa được xác định.
- **Outcome:** Kết thúc phiên và đưa ứng dụng về trạng thái sẵn sàng chọn video mới (FR-14 AC-3).
- **Open behavior:** Tác động Stop lên cảnh báo/queue/track theo OI-04.

## 6. Candidate Disposition
| Candidate | Disposition | Rationale |
|---|---|---|
| Chọn video đầu vào | Bước/trigger của UC-01; không Use Case riêng | Không có mục tiêu độc lập ngoài cung cấp đầu vào cho phân tích (FR-01). |
| Phân tích video | UC-01 | Mục tiêu cốt lõi, kết quả quan sát được ngay cả khi không có cảnh báo. |
| Xem kết quả nhận diện | Hành vi chính của UC-01 | Chỉ hiển thị kết quả đồng bộ với phiên; không có chức năng xem lại/lưu kết quả (FR-08, Q-05). |
| Nhận cảnh báo biển báo | UC-02, `extend` UC-01 | Có giá trị riêng cho User nhưng chỉ xảy ra theo điều kiện trong phiên phân tích. |
| Pause / Resume / Stop | UC-03 / UC-04 / UC-05 | Mỗi lệnh có trigger, trạng thái tiền điều kiện và kết quả quan sát được riêng (FR-14). |
| Detection, tracking, classification, aggregation, configuration | Internal Processing | Không phải Actor hoặc mục tiêu Use Case độc lập. |

## 7. Internal Processing Mapping
| Processing | Related FR | Supported Use Case | Classification |
|---|---|---|---|
| YOLO detection | FR-03 | UC-01 | Internal component |
| ByteTrack tracking | FR-04 | UC-01 | Internal component |
| CNN classification | FR-05 | UC-01 | Internal component |
| Temporal aggregation | FR-06 | UC-01 | Internal processing; method remains OI-05 |
| Recognition state | FR-07 | UC-02 | Internal processing; criteria remain OI-02 |
| Alert decision, dedup and queue | FR-09..FR-12 | UC-02 | Internal rules/processing |
| Configuration Loading | FR-13 | UC-01 | Internal processing; configuration owner not determined |

## 8. Requirement Coverage
| Requirement ID | Use Case coverage | Coverage type / note |
|---|---|---|
| FR-01 | UC-01 | Direct trigger/input |
| FR-02 | UC-01 | Direct video timeline behavior |
| FR-03 | UC-01 | Supporting internal detection |
| FR-04 | UC-01 | Supporting internal tracking |
| FR-05 | UC-01 | Supporting internal classification |
| FR-06 | UC-01 | Supporting aggregation by Track ID |
| FR-07 | UC-02 | Supporting alert-state decision; criteria pending OI-02 |
| FR-08 | UC-01 | Direct visible result |
| FR-09 | UC-02 | Direct class-specific alert |
| FR-10 | UC-02 | Direct generic alert |
| FR-11 | UC-02 | Cross-cutting alert deduplication by Track ID |
| FR-12 | UC-02 | Cross-cutting queue behavior; policy pending OI-04 |
| FR-13 | UC-01 | Supporting Configuration Loading |
| FR-14 | UC-03, UC-04, UC-05 | Direct Pause, Resume and Stop outcomes respectively |

## 9. UML Relationship Review
- **Associations:** User—UC-01, User—UC-02, User—UC-03, User—UC-04 and User—UC-05.
- **Extend:** UC-02 `extend` UC-01. Extension point and guard are specified in §5; alert eligibility still depends on the approved A-16 criteria. Do not invent a numeric threshold.
- **Include:** None. No mandatory reusable Use Case has been identified.
- **Generalization:** None. No specialized Actor or Use Case is established.
- UC-03/04/05 depend on the existence/state of a processing session, but this precondition does not create an Include/Extend relationship to UC-01.

## 10. Open Issues
- [Chưa xác định] A-16/OI-02: criteria for recognized/unrecognized state; determines UC-02 guard.
- [Chưa xác định] A-17/OI-01: behavior when processing cannot maintain source video timeline.
- [Chưa xác định] OI-04: queue policy and alert/track behavior when Pause/Stop occurs; whether Stop is valid while paused.
- [Chưa xác định] OI-05: aggregation algorithm and frame selection.
- [Chưa xác định] A-14/A-15/OI-03: detector, input size, classes, dataset and preprocessing.
- [Chưa xác định] A-18/OI-06: spoken alert language.
- [Chưa xác định] Configuration file owner; TTS deployment boundary; A-19/OI-07 report management.

## 11. Review Checklist
- [Xác nhận] Exactly five Use Cases and one Actor (User); no feature outside FR-01..FR-14.
- [Xác nhận] Old UC-02 replacement and UCC-04 promotion are recorded in §3.
- [Xác nhận] UC-02 extension point/condition is stated without deciding A-16 thresholds.
- [Xác nhận] Pause/Resume/Stop have separate preconditions and outcomes; unresolved Stop/Pause behavior remains open.
- [Xác nhận] No Include or Generalization; no relation added between control Use Cases and UC-01 based only on session dependency.
- [Xác nhận] All FR-01..FR-14 are covered.
