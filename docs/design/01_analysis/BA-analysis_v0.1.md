# Tài liệu phân tích nghiệp vụ (BA Analysis) - v0.1
Trạng thái: Bản nháp chờ duyệt | Phase 1 | Ngày: 20/11/2026

Nhãn nguồn: [Xác nhận] = từ người dùng/mô tả đề tài; [Đề xuất] = đề xuất kỹ thuật chờ duyệt; [Giả định] = chờ xác nhận; [Ngoài] = nghiên cứu ngoài, cần kiểm chứng nguồn.

## 1. Mục đích và phạm vi
[Xác nhận] Hệ thống phát hiện, nhận diện và cảnh báo biển báo giao thông theo thời gian thực từ video ghi sẵn do người dùng chọn, hiển thị trực quan, cảnh báo bằng giọng nói theo loại biển, hạn chế cảnh báo trùng lặp.
- Trong phạm vi [Xác nhận]: tiếp nhận file video, phát hiện, theo dõi, phân loại, tổng hợp qua nhiều Frame, hiển thị, cảnh báo giọng nói, chống cảnh báo trùng.
- Ngoài phạm vi [Xác nhận]: camera trực tiếp; triển khai tích hợp taxi tự hành mô phỏng (chỉ nêu khả năng tích hợp và hướng phát triển).
- Tập biển báo [Xác nhận]: biển báo giao thông của Đức. Tên bộ dữ liệu cụ thể chưa xác nhận.

## 2. Bối cảnh (hướng trình bày cho mục 1.1 báo cáo)
[Đề xuất] Người lái có thể bỏ sót biển báo do mất tập trung, biển bị che hoặc điều kiện ánh sáng; hệ thống tự hành cũng cần nhận biết biển báo. Chưa có số liệu hay nguồn; phải tìm nguồn thật trước khi viết Chương 1. Mục 1.1 chỉ nêu lý do, không nêu giải pháp.

## 3. Đối tượng liên quan (ứng viên, Actor chính thức xác định ở Phase 3)
- Người dùng (chọn video, xem kết quả, nghe cảnh báo): [Xác nhận] ("hỗ trợ người lái", người dùng tải file lên).
- Hệ thống mô phỏng taxi tự hành: chỉ là hướng phát triển [Xác nhận], không là Actor trong phạm vi triển khai.

## 4. Quyết định đã chốt
| ID | Nội dung |
|---|---|
| A-01 | Nguồn video là file người dùng chọn; xử lý và hiển thị theo đúng tốc độ phát |
| A-02 | Biển báo giao thông Đức |
| A-04 | YOLO phát hiện một lớp chung ("biển báo"); CNN phân loại |
| A-05 | Pipeline: Detect -> Track -> Classify -> Aggregate -> Alert |
| A-06 | Ứng dụng desktop chạy cục bộ |
| A-07 | Mỗi loại biển có nội dung giọng nói riêng |
| A-08 | Biển không nhận diện được: phát một âm thanh chung |
| A-09 | Chống trùng theo Track ID; cảnh báo xếp hàng đợi |
| A-10 | Taxi tự hành mô phỏng: chỉ nêu khả năng tích hợp, hướng phát triển |
| A-11 | Tham số thay đổi qua file cấu hình |
| A-12 | Lưu trữ dữ liệu lâu dài: quyết định ở Phase 7 |

## 5. Quy trình hoạt động tổng thể
[Đề xuất, theo A-05]
Frame -> YOLO (bounding box) -> ByteTrack (Track ID) -> crop theo track -> CNN (lớp) -> Temporal Aggregation (theo Track ID) -> Alert Decision -> TTS + Visualization

| Bước | Đầu vào | Đầu ra |
|---|---|---|
| Frame Acquisition | File video | Frame |
| Object Detection (YOLO) | Frame | Bounding box + detection score |
| Object Tracking (ByteTrack) | Box + score của Frame hiện tại | Track ID gắn với box |
| Image Classification (CNN) | Ảnh crop từ box | Xác suất theo lớp |
| Temporal Aggregation | Track ID + kết quả CNN theo thời gian | Nhãn tổng hợp + độ tin cậy |
| Alert Decision | Kết quả tổng hợp + trạng thái cảnh báo | Quyết định phát cảnh báo |
| TTS, Visualization | Quyết định cảnh báo, kết quả | Âm thanh, hình ảnh |

Nhận xét kỹ thuật: CNN và ByteTrack không phụ thuộc lẫn nhau (ByteTrack chỉ cần box và score). Phương án A cho phép chỉ phân loại một số Frame của mỗi track, giảm tải trên CPU. Detection và classification đều có thể sai; việc kiểm chứng bằng thực nghiệm.

## 6. Vai trò và dữ liệu giữa các thành phần
- YOLO trả lời "biển ở đâu" (một lớp chung); CNN trả lời "biển nào". Dữ liệu truyền giữa hai thành phần là vùng ảnh cắt theo bounding box.
- ByteTrack [Ngoài: Zhang và cộng sự, ECCV 2022, cần kiểm chứng khi trích dẫn]: liên kết detection qua các Frame dựa trên chuyển động/IoU, cấp Track ID ổn định. Rủi ro: camera gắn trên xe đang chạy làm biển đổi vị trí và kích thước nhanh, có thể gây ID switch; cần đo bằng thực nghiệm.
- Temporal Aggregation: gom kết quả CNN của nhiều Frame theo cùng Track ID thành một nhãn ổn định. Phương án thuật toán chưa chọn (xem mục 11).

## 7. Cơ chế cảnh báo
[Xác nhận một phần theo A-07, A-08, A-09; phần còn lại là Đề xuất]
- Hai loại cảnh báo: (1) cảnh báo theo lớp: nội dung giọng nói riêng cho từng loại biển; (2) cảnh báo chung: một âm thanh chung cho biển không nhận diện được.
- Chống trùng: theo Track ID. Cảnh báo xếp vào hàng đợi khi nhiều biển cùng xuất hiện.
- Rủi ro đã ghi nhận: biển bị che rồi xuất hiện lại với ID mới có thể bị cảnh báo lặp; chất lượng chống trùng phụ thuộc chất lượng tracking.
- Điều kiện "đủ tin cậy" và điều kiện "không nhận diện được": chưa xác định (A-16).

## 8. Chức năng ứng viên (ID chính thức đặt ở Phase 2)
1. Chọn và tiếp nhận file video.
2. Phát hiện vị trí biển báo.
3. Theo dõi biển báo qua các Frame.
4. Phân loại biển báo.
5. Tổng hợp dự đoán qua nhiều Frame.
6. Hiển thị kết quả trực quan.
7. Cảnh báo bằng giọng nói theo loại biển; âm thanh chung cho biển không nhận diện được.
8. Hạn chế cảnh báo trùng lặp, xếp hàng đợi cảnh báo.
9. Thay đổi tham số qua file cấu hình.

## 9. Yêu cầu phi chức năng ứng viên (chưa đặt chỉ tiêu số)
Real-time Processing (xử lý theo đúng tốc độ phát video), Accuracy, Reliability, Performance, Usability, Maintainability, Scalability. Chỉ tiêu định lượng chốt sau khi đo trên máy thực tế.

## 10. Giới hạn và ràng buộc
- Chỉ hỗ trợ tập biển báo Đức; chất lượng phụ thuộc điều kiện video (ánh sáng, độ phân giải, che khuất).
- [Đề xuất] Hệ thống hỗ trợ ở mức đồ án, không khẳng định đạt chuẩn an toàn cho xe thực tế.
- Phần cứng [Xác nhận]: Intel Core i7-8550U (4 nhân, 8 luồng), RAM 8 GB, Windows 11, SSD 512 GB, Intel UHD 620 và AMD Radeon 530; không có GPU NVIDIA. Giả định suy luận bằng CPU; không dựa vào GPU để tăng tốc.
- Tài nguyên hiện có [Xác nhận]: model CNN phân loại Keras .h5 (chỉ phân loại). Chưa có detector.

## 11. Mục mở
| ID | Nội dung | Cần chốt trước |
|---|---|---|
| A-14 | Nguồn detector (weights có sẵn hay tự huấn luyện, dataset có bounding box) | Phase 6 |
| A-15 | Thiếu: kích thước ảnh vào, danh sách lớp, dataset huấn luyện, tiền xử lý | Phase 6 |
| A-16 | Khi nào kết luận "không nhận diện được" | Phase 4 |
| A-17 | Chính sách khi xử lý không kịp tốc độ phát video | Phase 6 |
| A-18 | Ngôn ngữ giọng nói (suy luận: tiếng Việt, chờ xác nhận) | Phase 6 |
| A-19 | Cá nhân hay nhóm | Trước khi viết báo cáo |

Tham số chưa xác định, không đặt giá trị khi chưa có căn cứ: ngưỡng confidence, số Frame tối thiểu, kích thước cửa sổ tổng hợp, thời gian giữ lịch sử track, khoảng chờ cảnh báo, FPS mục tiêu, độ trễ mục tiêu. Các giá trị này chốt bằng thực nghiệm (Phase 12) hoặc theo hướng dẫn của GVHD.
