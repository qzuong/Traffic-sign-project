# Actor–Use Case Matrix - v0.1
Ngày cập nhật mô hình: 20/11/2026
Trạng thái: Cập nhật theo mô hình 5 Use Case được người dùng chốt.

## 1. Purpose
Ánh xạ Actor với mô hình UC-01..UC-05, phân tích điều kiện phiên, quan hệ UML và coverage FR-01..FR-14. Các Open Issues tiếp tục giữ nguyên; tài liệu này không thay đổi SRS.

## 2. Source Documents
- [BA Analysis](../01_analysis/BA-analysis_v0.1.md)
- [REQ-spec v0.3](../02_requirements/REQ-spec_v0.3.md)
- [RTM v0.3](../02_requirements/RTM_v0.3.md)
- [Actor Analysis](./actor-analysis_v0.1.md)
- [Use Case Catalog](./use-case-catalog_v0.1.md)
- [Use Case Reassessment](./use-case-reassessment_v0.1.md)

## 3. Confirmed Actor
| Actor | Role | Evidence |
|---|---|---|
| User | Primary Actor; chọn video, xem kết quả, nhận cảnh báo, điều khiển phiên | BA §3; FR-01, FR-08, FR-14 |

[Xác nhận] Không có Supporting Actor. YOLO, CNN, ByteTrack, TTS và Configuration Loading là thành phần/xử lý nội bộ; không thêm Driver/Administrator.

## 4. Approved Use Cases
| Use Case ID | Use Case Name | Primary Actor | Goal | Requirements |
|---|---|---|---|---|
| UC-01 | Phân tích video biển báo giao thông | User | Phân tích video theo timeline, xem kết quả nhận diện | FR-01..FR-06, FR-08, FR-13 |
| UC-02 | Phát cảnh báo biển báo | User (người nhận) | Nghe cảnh báo phù hợp khi đủ điều kiện | FR-07, FR-09..FR-12 |
| UC-03 | Tạm dừng xử lý video | User | Giữ Frame hiện tại và tạm ngừng xử lý | FR-14 AC-1 |
| UC-04 | Tiếp tục xử lý video | User | Tiếp tục từ Frame đang dừng | FR-14 AC-2 |
| UC-05 | Dừng xử lý video | User | Kết thúc phiên, sẵn sàng chọn video mới | FR-14 AC-3 |

### ID migration
- UC-01 cũ được giữ lại với phạm vi thu hẹp; alert chuyển sang UC-02.
- UC-02 cũ “Điều khiển quá trình xử lý video” bị thay thế bằng UC-03, UC-04 và UC-05.
- Candidate UCC-04 được chuẩn hóa thành UC-02.
- UCC-03 (chọn file) là bước đầu vào UC-01; UCC-05 (cấu hình) vẫn không phải Use Case.

## 5. Actor–Use Case Matrix
| Actor | Use Case ID | Use Case Name | Actor Goal | Interaction | Related Requirements | Evidence |
|---|---|---|---|---|---|---|
| User | UC-01 | Phân tích video biển báo giao thông | Phân tích video và xem kết quả | Chọn video; quan sát timeline, bounding box, nhãn và Track ID | FR-01..FR-06, FR-08, FR-13 | BA §1, §5; FR-01..FR-06, FR-08, FR-13 |
| User | UC-02 | Phát cảnh báo biển báo | Nhận thông tin âm thanh phù hợp | Là người nhận giọng nói riêng theo lớp hoặc âm thanh chung khi trạng thái track đủ điều kiện | FR-07, FR-09..FR-12 | BA §7; FR-07, FR-09..FR-12; Q-04/D-12 |
| User | UC-03 | Tạm dừng xử lý video | Tạm giữ phiên xử lý | Gửi lệnh Pause; hệ thống giữ Frame hiện tại, không xử lý Frame mới | FR-14 AC-1 | FR-14; Q-01/D-11 |
| User | UC-04 | Tiếp tục xử lý video | Tiếp tục phiên đã tạm dừng | Gửi lệnh Resume; hệ thống tiếp tục từ điểm đang dừng | FR-14 AC-2 | FR-14; Q-01/D-11 |
| User | UC-05 | Dừng xử lý video | Kết thúc phiên hiện tại | Gửi lệnh Stop; hệ thống kết thúc phiên và trở về trạng thái sẵn sàng chọn video | FR-14 AC-3 | FR-14; Q-01/D-11 |

## 6. Actor Interaction and Preconditions
- **UC-01:** Trigger là User chọn video. File cần đọc được để vào luồng thành công; file lỗi theo FR-01 không bắt đầu xử lý.
- **UC-02:** Do xử lý của hệ thống kích hoạt trong UC-01; User là người nhận cảnh báo. Preconditions: phiên UC-01 đang chạy; Track ID chưa được cảnh báo; trạng thái thỏa tiêu chí đã duyệt.
- **UC-03:** Yêu cầu Pause khi phiên đang xử lý/phát.
- **UC-04:** Yêu cầu Resume khi phiên đang tạm dừng tại Frame.
- **UC-05:** Yêu cầu Stop cho phiên hiện hành. SRS chưa xác định Stop có được phép khi đang Pause hay không.

Các điều kiện trên không bổ sung hành vi khi chưa có phiên, sau khi phiên kết thúc, hay tác động đến cảnh báo đang phát. Các nội dung chưa rõ giữ tại Open Issues.

## 7. Use Case Dependency and UML Relationship Analysis
### UC-02 extension point and condition
- **Extension point trong UC-01:** sau khi trạng thái nhận diện của một Track ID được xác định, tại bước đánh giá quyết định cảnh báo.
- **Condition:** Track ID chưa từng được cảnh báo và trạng thái theo tiêu chí được duyệt là đã nhận diện (FR-09) hoặc không nhận diện được (FR-10).
- A-16/OI-02 chưa xác định tiêu chí trạng thái; điều kiện này không tự đặt ngưỡng và cần giữ liên kết tới Open Issue.
- [Xác nhận theo mô hình 5 UC] UC-02 `extend` UC-01; base UC-01 vẫn có kết quả giá trị nếu không có cảnh báo đủ điều kiện.

### Relationships
- **Association:** User—UC-01, User—UC-02, User—UC-03, User—UC-04, User—UC-05.
- **Include:** Không có. Chọn file, hiển thị và các bước thuật toán là luồng/xử lý hỗ trợ, không phải Use Case được gọi bắt buộc, dùng chung.
- **Extend:** Chỉ UC-02 `extend` UC-01 tại extension point và guard nêu trên.
- **Generalization:** Không có căn cứ.
- UC-03/04/05 cần một phiên xử lý phù hợp làm ngữ cảnh. Tiền điều kiện này không tự tạo Include/Extend hoặc quan hệ trực tiếp với UC-01.

## 8. Requirement Coverage
| Requirement ID | Related Use Case | Coverage Type | Explanation |
|---|---|---|---|
| FR-01 | UC-01 | Direct | Chọn video là trigger/input |
| FR-02 | UC-01 | Direct | Timeline video và kết quả được trình bày |
| FR-03 | UC-01 | Supporting | Detection nội bộ |
| FR-04 | UC-01 | Supporting | Tracking/Track ID nội bộ |
| FR-05 | UC-01 | Supporting | Classification nội bộ |
| FR-06 | UC-01 | Supporting | Aggregation theo track nội bộ |
| FR-07 | UC-02 | Supporting | Trạng thái track hỗ trợ điều kiện cảnh báo; A-16 còn mở |
| FR-08 | UC-01 | Direct | User xem kết quả trực quan và Track ID |
| FR-09 | UC-02 | Direct | Cảnh báo giọng nói theo lớp |
| FR-10 | UC-02 | Direct | Âm thanh chung cho track không nhận diện được |
| FR-11 | UC-02 | Cross-cutting | Tối đa một cảnh báo mỗi Track ID |
| FR-12 | UC-02 | Cross-cutting | Hàng đợi cảnh báo; chính sách OI-04 còn mở |
| FR-13 | UC-01 | Supporting | Configuration Loading nội bộ |
| FR-14 | UC-03, UC-04, UC-05 | Direct | Ba outcome riêng: Pause, Resume, Stop |

## 9. Open Issues
### Ảnh hưởng trực tiếp đến hành vi/interaction
- [Chưa xác định] OI-02/A-16: trạng thái nhận diện và guard cảnh báo UC-02.
- [Chưa xác định] OI-04: hàng đợi/cảnh báo đang phát và tương tác Pause/Stop; Stop trong lúc Pause.
- [Chưa xác định] UC-03/04/05: hành vi điều khiển khi chưa có phiên hoặc phiên đã kết thúc.
- [Chưa xác định] OI-06/A-18: ngôn ngữ giọng nói trong UC-02.
- [Chưa xác định] OI-01/A-17: xử lý khi không theo kịp timeline UC-01.

### Technical/design and other inherited issues
- [Chưa xác định] OI-03/A-14/A-15: detector, kích thước đầu vào, lớp, dataset và preprocessing.
- [Chưa xác định] OI-05: phương pháp tổng hợp và chọn Frame.
- [Chưa xác định] FR-13: người tạo/cập nhật Configuration File; chưa có Actor riêng.
- [Chưa xác định] TTS triển khai nội bộ hay dùng dịch vụ ngoài.
- [Chưa xác định] OI-07/A-19: quản lý báo cáo cá nhân hay nhóm.

Các vấn đề được giữ nguyên theo SRS/BA; matrix không tự giải quyết.

## 10. Review Checklist
- [Xác nhận] User là Actor duy nhất; có đúng năm Use Case theo mô hình người dùng chọn.
- [Xác nhận] ID migration UC-01/UC-02/UCC-04 được nêu rõ.
- [Xác nhận] Tất cả FR-01..FR-14 được bao phủ.
- [Xác nhận] UC-02 có extension point và condition; A-16 tiếp tục được ghi nhận là Open Issue.
- [Xác nhận] Không có Include/Generalization và không tạo quan hệ cho các Use Case điều khiển chỉ vì cùng phụ thuộc phiên.
- [Xác nhận] Không thêm Actor, chức năng hoặc quyết định nghiệp vụ ngoài SRS.
