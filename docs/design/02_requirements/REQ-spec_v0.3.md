# Đặc tả yêu cầu hệ thống (Requirement Specification) - v0.3
Trạng thái: Đã phê duyệt — PHASE 2 | Ngày: 20/11/2026
Thay đổi so với v0.2: làm rõ các chỉ số tốc độ và độ trễ ở NFR-01; ghi nhận Pending là đề xuất chưa duyệt ở FR-07; làm rõ tác động cảnh báo một lần ở FR-09..FR-11; bổ sung tiêu chí kiểm thử FR-06; chuyển chính sách hàng đợi chưa chốt vào Open Issues; cập nhật Q-02..Q-05 theo D-12; rà soát phương pháp đánh giá NFR; cập nhật RTM. Rà soát cuối: tách hành vi FR-02 khỏi phương pháp đo; đề xuất Must cho FR-14; đổi Category NFR-10 thành Extensibility; làm rõ phạm vi Q-05; ghi nhận A-19.
Căn cứ: docs/design/01_analysis/BA-analysis_v0.1.md và docs/00_project/decision-log.md (D-11, D-12).
Nhãn: [Xác nhận] = đã có căn cứ xác nhận; [Đề xuất] = chờ phê duyệt. Priority: Must/Should theo đề xuất hiện có.

## 1. Functional Requirements

| ID | Name | Description | Priority | Source |
|---|---|---|---|---|
| FR-01 | Chọn file video | Người dùng chọn một file video ghi sẵn trên máy để xử lý | Must | A-01 |
| FR-02 | Đọc Frame theo tốc độ phát | Hệ thống đọc Frame theo thứ tự thời gian và xử lý, hiển thị kết quả theo timeline phát của video | Must | A-01 |
| FR-03 | Phát hiện biển báo | Hệ thống xác định vị trí các biển báo trong Frame (một lớp chung "biển báo") | Must | Mô tả đề tài, A-04 |
| FR-04 | Theo dõi biển báo | Hệ thống gán Track ID cho từng biển và duy trì định danh qua các Frame | Must | Mô tả đề tài, A-05 |
| FR-05 | Phân loại biển báo | Hệ thống xác định loại biển (tập biển báo Đức) từ ảnh vùng biển | Must | A-02, A-05 |
| FR-06 | Tổng hợp dự đoán | Hệ thống tổng hợp kết quả phân loại qua nhiều Frame theo từng Track ID | Must | Mô tả đề tài, A-05 |
| FR-07 | Xác định trạng thái nhận diện | Hệ thống xác định trạng thái nhận diện của mỗi track theo tiêu chí sẽ được chốt | Must | A-08, A-16 |
| FR-08 | Hiển thị kết quả trực quan | Hệ thống hiển thị video cùng kết quả nhận diện và Track ID bên cạnh nhãn | Must | Mô tả đề tài, Q-03, D-12 |
| FR-09 | Cảnh báo giọng nói theo loại biển | Hệ thống phát nội dung giọng nói riêng cho từng loại biển đã nhận diện, nếu Track ID chưa được cảnh báo trước đó | Must | A-07, Q-04, D-12 |
| FR-10 | Cảnh báo chung | Hệ thống phát một âm thanh chung cho biển không nhận diện được, nếu Track ID chưa được cảnh báo trước đó | Must | A-08, Q-04, D-12 |
| FR-11 | Chống cảnh báo trùng | Mỗi Track ID được cảnh báo tối đa một lần, tính chung cả cảnh báo theo lớp và cảnh báo chung | Must | A-09, Q-04, D-12 |
| FR-12 | Hàng đợi cảnh báo | Hệ thống xếp hàng các cảnh báo khi nhiều biển cùng xuất hiện; chính sách vận hành chi tiết còn mở | Must | A-09 |
| FR-13 | Cấu hình qua file | Các tham số của hệ thống được đọc từ file cấu hình | Must | A-11 |
| FR-14 | Điều khiển phát video | Người dùng tạm dừng, tiếp tục và dừng việc xử lý video đang phát | Must [Xác nhận mức ưu tiên trong rà soát cuối Phase 2, 20/11/2026] | Q-01, D-11 |

### Acceptance Criteria
- FR-01:
  1. Người dùng chọn được một file video từ máy.
  2. Nếu file không mở hoặc không đọc được, hệ thống thông báo lỗi và không bắt đầu xử lý.
  3. Định dạng hỗ trợ là MP4 và AVI; khả năng đọc thực tế được kiểm tra ở Phase 9 (Q-02, D-12).
- FR-02:
  1. Frame được đọc theo thứ tự thời gian của video.
  2. Hệ thống xử lý và trình bày kết quả theo timeline phát gốc của video.
  3. Khi video kết thúc, hệ thống dừng xử lý và báo hoàn tất.
  4. Nếu không thể duy trì timeline phát, hệ thống xử lý theo chính sách A-17; chính sách này vẫn chưa được quyết định và không được suy diễn tại FR-02.
- FR-03:
  1. Với mỗi Frame được xử lý, hệ thống trả về danh sách vùng chứa biển, mỗi vùng có bounding box và detection score, không mang nhãn loại biển.
  2. Frame không có biển cho danh sách rỗng và hệ thống tiếp tục xử lý.
- FR-04:
  1. Cùng một biển ở các Frame liên tiếp mang cùng Track ID khi theo dõi thành công.
  2. Biển mới xuất hiện nhận Track ID chưa dùng trong phiên xử lý.
  3. Khi mất track, hệ thống không dừng và xử lý theo FR-07.
  4. Mức ổn định Track ID được đánh giá theo NFR-05.
- FR-05:
  1. Với mỗi vùng được đưa vào phân loại, hệ thống trả về lớp dự đoán và độ tin cậy.
  2. Lớp thuộc tập biển báo Đức của model; danh sách lớp và dữ liệu liên quan còn thiếu theo A-15.
  3. Việc chọn Frame nào của track để phân loại chưa xác định (Phase 6).
- FR-06:
  1. Mỗi kết quả phân loại đầu vào được gắn với Track ID tương ứng; kết quả của một Track ID không được đưa vào phần tổng hợp của Track ID khác.
  2. Khi cùng một Track ID có thêm kết quả phân loại, trạng thái kết quả tổng hợp của track đó được cập nhật theo phương pháp đã chọn.
  3. Tại mỗi lần cập nhật, hệ thống cung cấp kết quả tổng hợp gắn với Track ID tương ứng (nhãn và độ tin cậy nếu phương pháp được chọn cung cấp độ tin cậy).
  4. Với một bộ đầu vào kiểm thử có các kết quả được gắn sẵn Track ID, kiểm tra được tính độc lập giữa track và việc cập nhật đúng track khi nhận kết quả mới.
  5. Thuật toán tổng hợp và bộ kết quả kỳ vọng cụ thể phải được chốt trước khi kiểm thử giá trị đầu ra (Phase 6); hiện chưa đặt thuật toán hoặc ngưỡng.
- FR-07:
  1. Mỗi track được gắn trạng thái nhận diện theo tiêu chí được phê duyệt; tiêu chí phân biệt "đã nhận diện" và "không nhận diện được" chưa chốt (A-16).
  2. Trạng thái Pending cho track chưa đủ căn cứ để kết luận là [Đề xuất, chờ phê duyệt], không phải quyết định đã xác nhận và không được xem là trạng thái bắt buộc trong phiên bản này trước khi được duyệt.
  3. Sau khi trạng thái và tiêu chí chuyển trạng thái được phê duyệt, kiểm thử xác nhận mỗi track có đúng một trạng thái tại từng thời điểm và chuyển trạng thái theo tiêu chí đó.
- FR-08:
  1. Hệ thống hiển thị video kèm bounding box của các biển đang theo dõi.
  2. Biển đã nhận diện hiển thị tên loại; biển không nhận diện được hiển thị khác biệt rõ ràng.
  3. Track ID được hiển thị bên cạnh nhãn của mỗi biển (Q-03, D-12).
- FR-09:
  1. Khi track đã được nhận diện và đủ điều kiện cảnh báo theo tiêu chí được chốt, hệ thống phát nội dung giọng nói tương ứng loại biển nếu Track ID chưa từng được cảnh báo.
  2. Mỗi loại biển có nội dung riêng; bảng ánh xạ loại biển sang câu cảnh báo còn phụ thuộc danh sách lớp A-15.
  3. Ngôn ngữ giọng nói chưa xác định (A-18).
  4. Nếu cùng Track ID đã nhận cảnh báo chung ở FR-10, quy tắc tối đa một cảnh báo ngăn phát thêm cảnh báo giọng nói theo lớp cho track đó. Hệ quả là loại biển có thể không được đọc thành tiếng trong track đó; không tự phát cảnh báo lần hai.
- FR-10:
  1. Khi track được xác định là không nhận diện được theo tiêu chí được chốt, hệ thống phát âm thanh chung nếu Track ID chưa từng được cảnh báo.
  2. Âm thanh chung khác nội dung cảnh báo của FR-09.
  3. Nếu Track ID đã được cảnh báo theo lớp, không phát thêm âm thanh chung cho cùng Track ID.
  4. Nếu âm thanh chung phát trước khi track được phân loại thành công, không phát thêm cảnh báo theo lớp cho cùng Track ID theo FR-09 và FR-11.
- FR-11:
  1. Mỗi Track ID nhận tối đa một cảnh báo, bất kể đó là cảnh báo theo lớp hay âm thanh chung.
  2. Ghi nhận trạng thái đã cảnh báo theo Track ID để kiểm tra không có cảnh báo thứ hai cho cùng ID.
  3. Do giới hạn này, cảnh báo chung phát trước có thể thay thế cảnh báo theo lớp vốn có thể phát sau; đây là hệ quả của Q-04/D-12, không phải một lần cảnh báo bổ sung.
  4. Nếu tracker cấp ID mới cho cùng một biển sau khi mất track, chống trùng theo Track ID không đảm bảo loại bỏ cảnh báo lặp giữa hai ID; rủi ro tracking được ghi nhận tại BA §6.
- FR-12:
  1. Nhiều cảnh báo phát sinh cùng lúc được đưa vào hàng đợi và phát lần lượt, không phát chồng nhau [Đề xuất].
  2. Tiêu chí xác nhận thứ tự phát, xử lý khi hàng đợi tồn đọng và tương tác với tạm dừng/dừng được ghi tại OI-04; chưa tự đặt chính sách.
- FR-13:
  1. Tham số được lấy từ file cấu hình, thay đổi không cần sửa mã nguồn.
  2. Giá trị thiếu hoặc không hợp lệ tạo thông báo lỗi rõ ràng; hệ thống không tự đoán giá trị.
  3. Danh sách tham số cấu hình được chốt ở Phase 6 và 7.
- FR-14:
  1. Tạm dừng: hệ thống giữ nguyên Frame hiện tại và không xử lý Frame mới.
  2. Tiếp tục: hệ thống xử lý tiếp từ Frame đang dừng.
  3. Dừng: hệ thống kết thúc phiên xử lý và đưa ứng dụng về trạng thái sẵn sàng chọn video mới.
  4. Hành vi với cảnh báo đang phát, hàng đợi cảnh báo và trạng thái track khi tạm dừng hoặc dừng còn mở tại OI-04 (Phase 4).

## 2. Non-functional Requirements
Không đặt chỉ tiêu số. Chỉ tiêu định lượng, nếu có, chỉ được chốt sau khi đo trên phần cứng ở mục 3 và được phê duyệt.

### NFR-01: các khái niệm đo
- **Video Playback Rate:** tốc độ/timeline phát dự kiến theo timestamp hoặc khoảng thời gian Frame của video nguồn.
- **Processing FPS:** số Frame được hệ thống xử lý trên đơn vị thời gian thực.
- **Display FPS:** số Frame kết quả thực tế được hiển thị trên đơn vị thời gian thực.
- **End-to-end Latency:** thời gian thực từ lúc đọc một Frame đến khi hiển thị kết quả tương ứng. Nếu đánh giá cảnh báo, độ trễ từ lúc đọc Frame đến khi cảnh báo bắt đầu phát được ghi riêng.
- Các đại lượng trên được báo cáo riêng, không dùng đại lượng này thay thế đại lượng khác; chưa đặt ngưỡng số.

| ID | Category | Description | Cách đo / phương pháp đánh giá | Chỉ tiêu |
|---|---|---|---|---|
| NFR-01 | Real-time Processing | Xử lý và hiển thị theo timeline phát video; đánh giá riêng Video Playback Rate, Processing FPS, Display FPS và End-to-end Latency theo các định nghĩa trên | Đo các đại lượng trên cùng video kiểm thử và báo cáo riêng từng kết quả; chưa quy định ngưỡng đạt | Chưa xác định |
| NFR-02 | Accuracy - Detection | Phát hiện đúng vị trí biển báo | Dùng video/tập kiểm thử có bounding box gán nhãn thủ công; báo cáo Precision và Recall theo một quy trình khớp detection với ground truth được ghi rõ trước đánh giá; ngưỡng khớp chưa được quy định ở đây | Chưa xác định |
| NFR-03 | Accuracy - Classification | Phân loại đúng loại biển | So sánh lớp dự đoán với nhãn chuẩn trên các crop được đưa vào phân loại; đánh giá riêng kết quả cuối theo Track ID sau tổng hợp với nhãn chuẩn của track | Chưa xác định |
| NFR-04 | Prediction Stability | Nhãn của một track ít dao động theo thời gian | Trên cùng các track kiểm thử, đếm số lần đổi nhãn trước và sau Temporal Aggregation theo một quy tắc đếm được ghi rõ; thuật toán tổng hợp chưa chọn | Chưa xác định |
| NFR-05 | Tracking Stability | Track ID ổn định | Dùng video có định danh track chuẩn được gán thủ công; đếm ID switch theo quy trình đánh giá được ghi rõ và giữ nhất quán giữa các lần đo | Chưa xác định |
| NFR-06 | Alert Quality | Cảnh báo đúng, đủ, không trùng | Đối chiếu sự kiện cảnh báo thực tế với sự kiện kỳ vọng gán thủ công theo track và loại cảnh báo; báo cáo riêng cảnh báo trùng, sai và bỏ sót; quy tắc ghép sự kiện được ghi trước khi đánh giá | Chưa xác định |
| NFR-07 | Reliability | Không dừng đột ngột khi gặp tình huống bất thường; lỗi được thông báo, không bị bỏ qua | Thực thi các ca kiểm thử cho video hỏng, Frame lỗi, không có biển, mất track và TTS lỗi; ghi kết quả pass/fail và thông báo quan sát được cho từng ca | Chưa xác định |
| NFR-08 | Usability | Người dùng chọn video và xem kết quả mà không cần sửa mã; thông báo lỗi dễ hiểu | Thực hiện các kịch bản thao tác thủ công gồm chọn video, xem kết quả và xử lý thông báo lỗi; ghi nhận bước thành công và vấn đề quan sát được | Chưa xác định |
| NFR-09 | Maintainability | Mỗi bước pipeline là một module riêng, giao tiếp qua Interface xác định; tham số nằm ngoài mã | Rà soát thiết kế và mã ở Phase 6 trở đi, đối chiếu ranh giới module, Interface và vị trí cấu hình | Không áp dụng số |
| NFR-10 | Extensibility [Đề xuất] | Có thể thay model hoặc thêm loại biển mà không sửa lõi pipeline | Rà soát thiết kế và thực hiện thử nghiệm thay model/thêm loại biển sau khi Interface và dữ liệu lớp được xác định; đây vẫn là đề xuất chờ duyệt | Không áp dụng số |

## 3. Ràng buộc
| ID | Nội dung | Source |
|---|---|---|
| CON-01 | Phần cứng chạy: Intel Core i7-8550U (4 nhân, 8 luồng), RAM 8 GB, Windows 11, không có GPU NVIDIA; giả định suy luận bằng CPU | BA §10 |
| CON-02 | Tài nguyên hiện có: model CNN phân loại Keras .h5; chưa có detector | BA §10, A-14 |

## 4. Quyết định cho các ứng viên Q-01 đến Q-05
| ID | Quyết định | Trạng thái |
|---|---|---|
| Q-01 | Có điều khiển phát video (tạm dừng, tiếp tục, dừng) -> FR-14 | [Xác nhận] (D-11) |
| Q-02 | Hỗ trợ MP4 và AVI | [Xác nhận] (D-12) |
| Q-03 | Hiển thị Track ID cạnh nhãn | [Xác nhận] (D-12) |
| Q-04 | Mỗi Track ID cảnh báo tối đa một lần | [Xác nhận] (D-12) |
| Q-05 | Phiên bản này không cung cấp chức năng cho người dùng lưu video kết quả hoặc xuất log kết quả. Việc lưu trữ dữ liệu nội bộ không thuộc quyết định này và được phân tích riêng ở Phase 7 theo A-12. | [Xác nhận] (D-12) |

## 5. Chức năng mở rộng (để sau, chưa là yêu cầu)
- Chức năng người dùng lưu video đã gắn kết quả hoặc xuất log kết quả.
- Cảnh báo lại khi nhãn của track thay đổi.
- Chỉnh tham số qua giao diện.
- Nguồn video từ camera trực tiếp.
- Tích hợp môi trường mô phỏng taxi tự hành.

## 6. Open Issues
| ID | Vấn đề chưa chốt | Căn cứ / giai đoạn xử lý |
|---|---|---|
| OI-01 | Chính sách khi hệ thống không theo kịp tốc độ phát video | A-17, Phase 6 |
| OI-02 | Tiêu chí "đủ tin cậy", "không nhận diện được" và chuyển trạng thái; đề xuất Pending cần phê duyệt hoặc từ chối | A-16, Phase 4 |
| OI-03 | Detector, kích thước đầu vào, danh sách lớp, dữ liệu và tiền xử lý | A-14, A-15, Phase 6 |
| OI-04 | Thứ tự phát cảnh báo trong hàng đợi, cách xử lý khi hàng đợi tồn đọng và tương tác với pause/stop hoặc cảnh báo đang phát | A-09, FR-12, FR-14; Phase 4/6 |
| OI-05 | Phương pháp tổng hợp dự đoán và lựa chọn Frame phân loại | A-05, FR-05, FR-06; Phase 6 |
| OI-06 | Ngôn ngữ giọng nói | A-18, Phase 6 |
| OI-07 | Quản lý báo cáo: xác nhận cá nhân hay nhóm trước khi viết báo cáo | A-19; đã có mục theo dõi ở BA §11, cần xử lý trước khi viết báo cáo |
