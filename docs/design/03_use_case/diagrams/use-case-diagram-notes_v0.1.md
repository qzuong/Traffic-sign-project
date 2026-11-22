# Use Case Diagram Notes - v0.1
Ngày: 20/11/2026

## 1. Diagram Purpose
Biểu diễn System Boundary, Actor User và năm Use Case của mô hình đã được người dùng chốt. Sơ đồ không mô tả luồng xử lý nội bộ hoặc Use Case Specification.

## 2. Source Documents
- [Xác nhận] `docs/design/02_requirements/REQ-spec_v0.3.md` — yêu cầu đã duyệt FR-01..FR-14 và Open Issues.
- [Xác nhận] `docs/design/03_use_case/actor-analysis_v0.1.md` — Actor và System Boundary.
- [Xác nhận] `docs/design/03_use_case/use-case-catalog_v0.1.md` — catalog hiện hành UC-01..UC-05.
- [Xác nhận] `docs/design/03_use_case/actor-usecase-matrix_v0.1.md` — matrix hiện hành, gồm association và quan hệ UC-02 `extend` UC-01.
- [Xác nhận] `docs/design/03_use_case/use-case-reassessment_v0.1.md` — lý do phân rã và mô hình 5 UC đã chốt.

## 3. System Boundary
Boundary được biểu diễn bằng rectangle có nhãn **“Hệ thống phát hiện, nhận diện và cảnh báo biển báo giao thông từ video”** theo yêu cầu của sơ đồ.

[Đề xuất] Actor Analysis ghi tên này là tên mô tả; tên sản phẩm chính thức chưa được xác nhận. Nhãn Boundary không đưa ra quyết định mới về tên sản phẩm.

## 4. Actors
- **User** — Primary Actor duy nhất được xác nhận; hiển thị bên ngoài System Boundary.
- Không có Supporting Actor hoặc External System nào được thêm vào sơ đồ.

## 5. Use Cases
- **UC-01 — Phân tích video biển báo giao thông:** nằm trong System Boundary; User chọn video và quan sát kết quả.
- **UC-02 — Phát cảnh báo biển báo:** nằm trong System Boundary; User là người nhận cảnh báo có điều kiện.
- **UC-03 — Tạm dừng xử lý video:** nằm trong System Boundary; User yêu cầu Pause.
- **UC-04 — Tiếp tục xử lý video:** nằm trong System Boundary; User yêu cầu Resume.
- **UC-05 — Dừng xử lý video:** nằm trong System Boundary; User yêu cầu Stop.

Tên và ID khớp catalog mô hình hiện hành. UC-02 cũ “Điều khiển quá trình xử lý video” đã được thay thế bằng UC-03..UC-05.

## 6. UML Notation
- `actor` biểu diễn vai trò bên ngoài tương tác với hệ thống.
- `rectangle` biểu diễn System Boundary; các Use Case nằm bên trong.
- `usecase` biểu diễn Use Case bằng hình ellipse trong sơ đồ được render.
- `User -- UC01` đến `User -- UC05` dùng đường liền không hướng, biểu diễn Association. Association thể hiện Actor tham gia hoặc nhận giá trị từ Use Case; không biểu thị thứ tự hay hướng luồng điều khiển.
- `UC02 ..> UC01 : <<extend>>` dùng đường nét đứt với đầu mũi tên mở từ extension UC-02 về base UC-01; điều kiện đặt trong nhãn quan hệ.

## 7. Association Analysis
- **User — UC-01:** User chọn video và xem kết quả theo FR-01..FR-08, FR-13.
- **User — UC-02:** User là người nhận cảnh báo theo FR-07, FR-09..FR-12.
- **User — UC-03/UC-04/UC-05:** User yêu cầu Pause, Resume hoặc Stop tương ứng theo FR-14.

## 8. Excluded Relationships
- **Include:** không sử dụng; không có hành vi bắt buộc chung cần được mô hình hóa bằng quan hệ này.
- **Extend:** UC-02 `extend` UC-01 tại điểm sau khi xác định trạng thái Track ID, khi Track ID chưa được cảnh báo và trạng thái thỏa tiêu chí cảnh báo đã duyệt (FR-09/FR-10). Tiêu chí cụ thể A-16/OI-02 còn mở; sơ đồ không đặt ngưỡng.
- **Generalization:** không sử dụng; không có Actor/Use Case chuyên biệt kế thừa hành vi.
- UC-03/UC-04/UC-05 có precondition về trạng thái phiên xử lý; điều này không tạo Include/Extend hoặc quan hệ trực tiếp với UC-01.

## 9. Requirement Mapping
| Use Case ID | Requirements |
|---|---|
| UC-01 | FR-01..FR-06, FR-08, FR-13 |
| UC-02 | FR-07, FR-09..FR-12 |
| UC-03 | FR-14 AC-1 |
| UC-04 | FR-14 AC-2 |
| UC-05 | FR-14 AC-3 |

Mapping chi tiết theo từng FR được duy trì tại Actor–Use Case Matrix; sơ đồ không biến mỗi FR thành một Use Case riêng.

## 10. Diagram Validation
- [Xác nhận] Một Actor duy nhất, User, nằm ngoài System Boundary.
- [Xác nhận] UC-01..UC-05 nằm trong System Boundary và ID/tên khớp catalog.
- [Xác nhận] PlantUML source dùng một Actor `User`, năm `usecase`, năm Association dạng đường liền và một quan hệ `extend` có guard.
- [Xác nhận] Không có Include, Generalization, Actor hoặc Use Case bổ sung.
- [Xác nhận] Source có cặp `@startuml` / `@enduml`.
- [Chưa xác định] Không có PlantUML renderer/compiler khả dụng trong các công cụ hiện có; chưa render PNG và chưa kiểm tra hình ảnh. Kiểm tra hiện tại chỉ giới hạn ở việc đối chiếu source text với mô hình đã duyệt.

## 11. Open Issues
- [Chưa xác định] Tên sản phẩm/hệ thống chính thức; nhãn Boundary hiện dùng theo yêu cầu và là tên mô tả.
- [Chưa xác định] Open Issues về nhận diện/cảnh báo, timeline, hàng đợi, detector, tổng hợp, ngôn ngữ giọng nói, cấu hình và quản lý báo cáo vẫn giữ nguyên theo SRS và Actor Analysis.
- [Chưa xác định] Trạng thái cụ thể cho phép Stop khi đang Pause và hành vi điều khiển khi không có phiên hoặc phiên đã kết thúc.
- [Chưa xác định] Cần render bằng PlantUML để kiểm tra trực quan và tạo PNG khi renderer khả dụng.
