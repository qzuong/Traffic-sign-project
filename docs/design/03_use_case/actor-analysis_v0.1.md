# Actor Analysis - v0.1
Ngày: 20/11/2026

Nhãn nguồn: [Xác nhận] = có căn cứ trong tài liệu Phase 1/2 đã duyệt; [Đề xuất] = cách phân loại hoặc tên mô tả cần rà soát; [Chưa xác định] = tài liệu hiện tại chưa đủ căn cứ kết luận.

## 1. Purpose
Phân tích ranh giới hệ thống, Actor và mục tiêu Actor dựa trên BA Analysis và Requirement Specification đã duyệt. Tài liệu này chỉ ghi nhận phân tích ở Step 3.1; chưa đặt Use Case ID, chưa đặc tả Use Case và không tạo Use Case Diagram.

## 2. System Boundary

### Tên hệ thống
[Đề xuất] **Hệ thống phát hiện, nhận diện và cảnh báo biển báo giao thông từ video** là tên mô tả dùng trong phân tích. Tài liệu Phase 1/2 chưa xác nhận tên sản phẩm chính thức.

### Mục đích
[Xác nhận] Tiếp nhận video ghi sẵn do người dùng chọn, phát hiện và nhận diện biển báo giao thông Đức, hiển thị kết quả trực quan và phát cảnh báo bằng giọng nói, đồng thời hạn chế cảnh báo lặp theo Track ID. Căn cứ: BA §1, §4; FR-01..FR-12.

### Bên trong ranh giới hệ thống
[Xác nhận] Các hành vi và xử lý thuộc hệ thống desktop chạy cục bộ (BA A-06, D-06):
- Chọn, đọc và phát video theo timeline: FR-01, FR-02, FR-14.
- Phát hiện biển báo, theo dõi Track ID, phân loại và tổng hợp dự đoán: FR-03..FR-07.
- Hiển thị kết quả: FR-08.
- Quyết định, xếp hàng và phát cảnh báo theo lớp hoặc cảnh báo chung; chống lặp theo Track ID: FR-09..FR-12.
- Đọc tham số từ file cấu hình: FR-13.

YOLO, ByteTrack, CNN, Temporal Aggregation, Alert Decision, TTS và Visualization là các thành phần trong pipeline được mô tả ở BA §5–§6; chúng không phải Actor chỉ vì có tên hoặc chức năng riêng.

### Bên ngoài ranh giới hệ thống
- [Xác nhận] Người dùng chọn video và tương tác với ứng dụng.
- [Xác nhận] File video và file cấu hình là dữ liệu/tài nguyên được hệ thống sử dụng, không phải hệ thống bên ngoài.
- [Xác nhận] Taxi simulation nằm ngoài phạm vi triển khai hiện tại; chỉ được nêu như hướng phát triển (BA §1, §3; A-10/D-09).
- [Chưa xác định] Tài liệu không xác nhận dịch vụ TTS, ứng dụng hay hệ thống bên ngoài nào được tích hợp. TTS hiện chỉ được mô tả như thành phần của pipeline.

**Kết luận:** [Xác nhận] Không có External System nào được xác định là tích hợp trong phạm vi hiện tại. Người dùng là Actor bên ngoài; video và cấu hình là Data Resource. Taxi simulation là hệ thống tương lai ngoài boundary hiện tại.

### Đối tượng không được xem là Actor
YOLO, CNN, ByteTrack, TTS trong pipeline hiện tại là Internal Component. Video File và Configuration File là Data Resource. Những đối tượng này không có mục tiêu độc lập tương tác với hệ thống theo tài liệu đã duyệt.

## 3. Actor Identification Criteria
Một ứng viên được phân loại là Actor trong phân tích này khi tài liệu có căn cứ cho thấy đó là người hoặc hệ thống bên ngoài boundary, có mục tiêu và tương tác trực tiếp với hệ thống để đạt mục tiêu đó.

- Thành phần thực hiện xử lý bên trong boundary không phải Actor.
- File hoặc dữ liệu đầu vào không phải Actor.
- Không tách một vai trò thành Actor riêng nếu chưa có căn cứ về tương tác hoặc mục tiêu khác biệt.
- Không tạo Supporting Actor chỉ để bổ sung đối tượng cho biểu đồ.

## 4. Actor Candidate Analysis

| Candidate | Role | Supporting Evidence | Classification | Reason | Status |
|---|---|---|---|---|---|
| User | Chọn video, xem kết quả và tương tác với ứng dụng | BA §3; FR-01, FR-08, FR-14 | Primary Actor | Là người dùng bên ngoài khởi tạo xử lý và nhận kết quả; mục tiêu được thể hiện trực tiếp trong phạm vi đã duyệt | [Xác nhận] |
| Driver | Người lái được hệ thống hỗ trợ | BA §1, §3 có cụm “hỗ trợ người lái”; không có yêu cầu riêng về tương tác của Driver | Chưa xác định là Actor riêng | Chưa có căn cứ cho biết Driver là người chọn video hay là một người khác với User. Không suy diễn hai vai trò là một hoặc tạo Actor thứ hai | [Chưa xác định] |
| Administrator | Quản trị người dùng hoặc cấu hình | FR-13 yêu cầu đọc tham số từ file cấu hình; không có vai trò quản trị hay chức năng quản lý người dùng | Không phải Actor đã xác nhận | Việc hệ thống đọc file không xác lập một Administrator hoặc quyền quản trị | [Xác nhận trong phạm vi hiện tại] |
| YOLO | Phát hiện vị trí biển báo | BA §4–§6; FR-03 | Internal Component | Là thành phần kỹ thuật bên trong pipeline, không phải hệ thống bên ngoài tương tác với hệ thống | [Xác nhận] |
| CNN | Phân loại biển báo | BA §4–§6; FR-05 | Internal Component | Là thành phần kỹ thuật bên trong pipeline | [Xác nhận] |
| ByteTrack | Theo dõi biển và gán Track ID | BA §5–§6; FR-04 | Internal Component | Là thành phần kỹ thuật bên trong pipeline | [Xác nhận] |
| TTS | Phát lời cảnh báo | BA §5, §7; FR-09, FR-10 | Internal Component theo boundary hiện tại | TTS được mô tả như bước của pipeline; không có căn cứ về dịch vụ TTS bên ngoài được tích hợp | [Xác nhận về vai trò pipeline; cách triển khai TTS chưa xác định] |
| Video File | Cung cấp video ghi sẵn để xử lý | A-01; FR-01, FR-02 | Data Resource | Là đầu vào dữ liệu do User chọn, không phải chủ thể có mục tiêu hoặc tương tác | [Xác nhận] |
| Configuration File | Chứa tham số hệ thống | A-11; FR-13 | Data Resource | Là nguồn dữ liệu được hệ thống đọc; ai tạo/cập nhật file chưa được xác định | [Xác nhận về việc sử dụng file; người quản lý file chưa xác định] |
| Taxi Simulation | Môi trường taxi tự hành mô phỏng | BA §1, §3; A-10/D-09 | External System tương lai, ngoài boundary hiện tại | Chỉ là hướng phát triển; chưa có tích hợp hoặc tương tác trong phạm vi triển khai | [Xác nhận ngoài phạm vi hiện tại] |

## 5. Confirmed Actor Candidates

### Primary Actor
**User** — [Xác nhận]. Người dùng chọn video ghi sẵn, sử dụng chức năng điều khiển phát đã được xác nhận, xem kết quả và nhận cảnh báo.

### Supporting Actors
**Chưa xác định Supporting Actor nào.** Tài liệu hiện có không xác nhận hệ thống hoặc dịch vụ bên ngoài hỗ trợ hệ thống trong phạm vi triển khai. Không coi TTS là Supporting Actor vì hiện được mô tả là thành phần trong pipeline.

## 6. Actor Goals

### User
- Chọn một video ghi sẵn để hệ thống xử lý.
- Theo dõi video và kết quả biển báo được hiển thị.
- Nhận cảnh báo bằng giọng nói theo loại biển hoặc cảnh báo chung khi không nhận diện được.
- Tạm dừng, tiếp tục hoặc dừng việc xử lý video.

Các mục tiêu trên tương ứng với FR-01..FR-02, FR-08..FR-10 và FR-14. FR-03..FR-07 và FR-11..FR-13 mô tả hành vi hỗ trợ của hệ thống; không biến từng yêu cầu thành một mục tiêu Actor riêng.

## 7. Requirement Mapping

| Actor / Goal | Related Requirements | Mapping Note |
|---|---|---|
| User — chọn video và bắt đầu xử lý | FR-01, FR-02 | Video File là tài nguyên đầu vào; không phải Actor |
| User — xem video và kết quả biển báo | FR-02..FR-08 | FR-03..FR-07 là xử lý nội bộ hỗ trợ kết quả hiển thị |
| User — nhận cảnh báo | FR-07, FR-09..FR-12 | Các điều kiện nhận diện và chính sách hàng đợi còn có Open Issues trong SRS |
| User — điều khiển xử lý video | FR-14 | Hành vi đã xác nhận; mức ưu tiên Must được người dùng phê duyệt trong rà soát Phase 2 |
| Actor chưa xác định — cung cấp/cập nhật file cấu hình | FR-13 | SRS chỉ yêu cầu đọc file; chưa xác định người tạo hoặc quản lý file. Không gán mục tiêu này cho Administrator |

Không có Use Case ID chính thức nào được tạo trong Step 3.1.

## 8. Open Questions
- [Chưa xác định] Driver có phải chính User thao tác với ứng dụng hay là một vai trò khác? Tài liệu chỉ xác nhận User, chưa xác nhận Driver là Actor riêng.
- [Chưa xác định] Ai tạo, cập nhật hoặc cung cấp Configuration File? FR-13 chỉ xác nhận hệ thống đọc tham số từ file.
- [Chưa xác định] TTS được triển khai hoàn toàn nội bộ hay sẽ dùng một engine/service bên ngoài? Boundary hiện tại không giả định có External System tích hợp.
- [Chưa xác định] Tên sản phẩm/hệ thống chính thức là gì? Tên ở mục 2 chỉ là tên mô tả đề xuất.

## 9. Review Checklist
- [Xác nhận] System Boundary và mục đích truy về BA/SRS đã duyệt.
- [Xác nhận] User là Primary Actor duy nhất có căn cứ trong phạm vi hiện tại.
- [Xác nhận] Không tạo Supporting Actor hoặc External System chưa được xác nhận.
- [Xác nhận] YOLO, CNN, ByteTrack và TTS được phân biệt là Internal Component; video/configuration file là Data Resource.
- [Xác nhận] Taxi Simulation được giữ ngoài phạm vi triển khai hiện tại.
- [Xác nhận] Mục tiêu Actor ánh xạ về FR hiện có; không thêm chức năng mới.
- [Xác nhận] Không tạo Use Case ID, Use Case Specification hoặc Use Case Diagram.
- [Chưa xác định] Các câu hỏi ở mục 8 cần được giải quyết ở bước phù hợp; chưa tự suy diễn trong phân tích này.
