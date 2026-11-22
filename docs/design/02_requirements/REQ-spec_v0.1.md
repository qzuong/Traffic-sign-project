# Đặc tả yêu cầu hệ thống (Requirement Specification) - v0.1
Trạng thái: Bản nháp chờ duyệt | Phase 2 | Ngày: 20/11/2026
Căn cứ: docs/design/01_analysis/BA-analysis_v0.1.md (A-xx là ID quyết định trong tài liệu đó).
Nhãn: [Đề xuất] = đề xuất chờ duyệt. Priority: Must/Should (đề xuất).

## 1. Functional Requirements

| ID | Name | Description | Priority | Source |
|---|---|---|---|---|
| FR-01 | Chọn file video | Người dùng chọn một file video ghi sẵn trên máy để xử lý | Must | A-01 |
| FR-02 | Đọc Frame theo tốc độ phát | Hệ thống đọc lần lượt các Frame và xử lý, hiển thị theo tốc độ phát của video | Must | A-01 |
| FR-03 | Phát hiện biển báo | Hệ thống xác định vị trí các biển báo trong Frame (một lớp chung "biển báo") | Must | Mô tả đề tài, A-04 |
| FR-04 | Theo dõi biển báo | Hệ thống gán Track ID cho từng biển và duy trì định danh qua các Frame | Must | Mô tả đề tài, A-05 |
| FR-05 | Phân loại biển báo | Hệ thống xác định loại biển (tập biển báo Đức) từ ảnh vùng biển | Must | A-02, A-05 |
| FR-06 | Tổng hợp dự đoán | Hệ thống tổng hợp kết quả phân loại qua nhiều Frame theo từng Track ID | Must | Mô tả đề tài, A-05 |
| FR-07 | Xác định trạng thái nhận diện | Hệ thống xác định trạng thái nhận diện của mỗi track (đã nhận diện / không nhận diện được) | Must | A-08, A-16 |
| FR-08 | Hiển thị kết quả trực quan | Hệ thống hiển thị video cùng kết quả nhận diện | Must | Mô tả đề tài |
| FR-09 | Cảnh báo giọng nói theo loại biển | Hệ thống phát nội dung giọng nói riêng cho từng loại biển đã nhận diện | Must | A-07 |
| FR-10 | Cảnh báo chung | Hệ thống phát một âm thanh chung cho biển không nhận diện được | Must | A-08 |
| FR-11 | Chống cảnh báo trùng | Hệ thống không phát cảnh báo lặp cho cùng một Track ID | Must | Mô tả đề tài, A-09 |
| FR-12 | Hàng đợi cảnh báo | Hệ thống xếp hàng các cảnh báo khi nhiều biển cùng xuất hiện | Must | A-09 |
| FR-13 | Cấu hình qua file | Các tham số của hệ thống được đọc từ file cấu hình | Must | A-11 |

### Acceptance Criteria
- FR-01:
  1. Người dùng chọn được một file video từ máy.
  2. Nếu file không mở hoặc không đọc được, hệ thống thông báo lỗi và không bắt đầu xử lý.
  3. Danh sách định dạng video hỗ trợ: chưa xác định (Q-02).
- FR-02:
  1. Frame được đọc theo thứ tự thời gian.
  2. Thời gian hiển thị tương ứng tốc độ phát gốc của video.
  3. Khi xử lý không kịp tốc độ phát, ứng xử theo chính sách chưa chốt (A-17).
  4. Khi video kết thúc, hệ thống dừng xử lý và báo hoàn tất.
- FR-03:
  1. Với mỗi Frame được xử lý, hệ thống trả về danh sách vùng chứa biển, mỗi vùng có bounding box và detection score, không mang nhãn loại biển.
  2. Frame không có biển cho danh sách rỗng và hệ thống tiếp tục xử lý.
- FR-04:
  1. Cùng một biển ở các Frame liên tiếp mang cùng Track ID khi theo dõi thành công.
  2. Biển mới xuất hiện nhận Track ID chưa dùng.
  3. Khi mất track, hệ thống không dừng và xử lý theo FR-07.
  4. Mức ổn định Track ID đánh giá theo NFR-05.
- FR-05:
  1. Với mỗi vùng được đưa vào phân loại, hệ thống trả về lớp dự đoán và độ tin cậy.
  2. Lớp thuộc tập biển báo Đức của model (danh sách lớp chưa có, A-15).
  3. Việc chọn Frame nào của track để phân loại: chưa xác định (Phase 6).
- FR-06:
  1. Kết quả tổng hợp gắn với một Track ID.
  2. Kết quả tổng hợp được cập nhật khi có kết quả phân loại mới.
  3. Phương pháp tổng hợp chưa chọn (Phase 6).
- FR-07:
  1. Tại mọi thời điểm, mỗi track ở đúng một trạng thái xác định.
  2. Trạng thái "chưa kết luận" (track mới, chưa đủ căn cứ) là [Đề xuất].
  3. Tiêu chí chuyển trạng thái: chưa xác định (A-16, chốt ở Phase 4 và thực nghiệm Phase 12).
- FR-08:
  1. Hệ thống hiển thị video kèm bounding box của các biển đang theo dõi.
  2. Biển đã nhận diện hiển thị tên loại.
  3. Biển không nhận diện được hiển thị khác biệt rõ ràng.
  4. Hiển thị Track ID hay không: chưa xác định (Q-03).
- FR-09:
  1. Khi track ở trạng thái đã nhận diện và đủ điều kiện cảnh báo, hệ thống phát nội dung giọng nói tương ứng loại biển.
  2. Mỗi loại biển có nội dung riêng.
  3. Bảng ánh xạ loại biển sang câu cảnh báo chưa có (phụ thuộc A-15).
  4. Ngôn ngữ giọng nói chưa xác định (A-18).
- FR-10:
  1. Khi track chuyển sang "không nhận diện được", hệ thống phát đúng một âm thanh chung cho mọi track ở trạng thái này.
  2. Âm thanh này khác nội dung cảnh báo của FR-09.
- FR-11:
  1. Cảnh báo cho cùng một Track ID không bị lặp.
  2. Quy tắc chi tiết (ví dụ cảnh báo lại khi nhãn thay đổi): chưa xác định (Q-04).
- FR-12:
  1. Nhiều cảnh báo phát sinh cùng lúc được xếp hàng và phát lần lượt, không phát chồng nhau [Đề xuất].
  2. Thứ tự phát và xử lý khi hàng đợi tồn đọng: chưa xác định.
- FR-13:
  1. Tham số được lấy từ file cấu hình, thay đổi không cần sửa mã nguồn.
  2. Giá trị thiếu hoặc không hợp lệ cho thông báo lỗi rõ ràng, hệ thống không tự đoán giá trị.
  3. Danh sách tham số cấu hình được chốt ở Phase 6 và 7.

## 2. Non-functional Requirements
Không đặt chỉ tiêu số. Chỉ tiêu chốt sau khi đo trên phần cứng ở mục 3.

| ID | Category | Description | Cách đo | Chỉ tiêu |
|---|---|---|---|---|
| NFR-01 | Real-time Processing | Xử lý và hiển thị theo tốc độ phát của video | FPS xử lý trung bình; độ trễ end-to-end (từ lúc đọc Frame đến lúc hiển thị hoặc phát cảnh báo); số Frame bị bỏ (nếu có) | Chưa xác định |
| NFR-02 | Accuracy - Detection | Phát hiện đúng vị trí biển báo | Precision và Recall trên tập kiểm thử có nhãn | Chưa xác định |
| NFR-03 | Accuracy - Classification | Phân loại đúng loại biển | Độ chính xác trên tập kiểm thử, trước và sau tổng hợp theo track | Chưa xác định |
| NFR-04 | Prediction Stability | Nhãn của một track ít dao động theo thời gian | Số lần đổi nhãn trong một track, so sánh trước và sau Temporal Aggregation | Chưa xác định |
| NFR-05 | Tracking Stability | Track ID ổn định | Số lần đổi ID (ID switch) trên video thử | Chưa xác định |
| NFR-06 | Alert Quality | Cảnh báo đúng, đủ, không trùng | Số cảnh báo trùng, sai, bỏ sót so với ground truth gán thủ công; so sánh có và không có cơ chế chống trùng | Chưa xác định |
| NFR-07 | Reliability | Không dừng đột ngột khi gặp tình huống bất thường (video hỏng, Frame lỗi, không có biển, mất track, TTS lỗi); lỗi được thông báo, không bị bỏ qua | Bộ tình huống lỗi kiểm thử, kết quả pass/fail từng tình huống | Chưa xác định |
| NFR-08 | Usability | Người dùng chọn video và xem kết quả mà không cần sửa mã; thông báo lỗi dễ hiểu | Kịch bản thao tác kiểm tra thủ công | Chưa xác định |
| NFR-09 | Maintainability | Mỗi bước pipeline là một module riêng, giao tiếp qua Interface xác định; tham số nằm ngoài mã | Rà soát đối chiếu thiết kế và mã nguồn | Không áp dụng số |
| NFR-10 | Scalability [Đề xuất] | Có thể thay model hoặc thêm loại biển mà không sửa lõi pipeline | Rà soát thiết kế; thử thay model | Không áp dụng số |

## 3. Ràng buộc
| ID | Nội dung | Source |
|---|---|---|
| CON-01 | Phần cứng chạy: Intel Core i7-8550U (4 nhân, 8 luồng), RAM 8 GB, Windows 11, không có GPU NVIDIA; giả định suy luận bằng CPU | BA §10 |
| CON-02 | Tài nguyên hiện có: model CNN phân loại Keras .h5; chưa có detector | BA §10, A-14 |

## 4. Ứng viên chờ xác nhận (chưa là yêu cầu)
| ID | Nội dung |
|---|---|
| Q-01 | Có cần điều khiển phát video (tạm dừng, tiếp tục, dừng) không? |
| Q-02 | Cần hỗ trợ những định dạng video nào? |
| Q-03 | Có hiển thị Track ID trên giao diện không? |
| Q-04 | Quy tắc chống trùng chi tiết: mỗi track cảnh báo một lần, hay có cảnh báo lại khi nhãn đổi? |
| Q-05 | Có lưu video đã gắn kết quả hay lưu log kết quả không? (liên quan A-12) |
