# Use Case Reassessment - v0.1
Trạng thái: Mô hình 5 Use Case được người dùng chốt và chuẩn hóa thành UC-01..UC-05 | Phase 3 | Ngày: 20/11/2026

Nhãn: [Xác nhận] = có căn cứ trong tài liệu đã duyệt; [Đề xuất] = phương án cần người dùng duyệt; [Chưa xác định] = tài liệu hiện tại chưa đủ căn cứ kết luận.

## 1. Reason for Reassessment
Người dùng nhận xét Use Case Diagram v0.1 với hai Use Case có thể quá tổng quát và chưa thể hiện rõ chức năng. Tài liệu này đánh giá lại mức độ phân rã theo mục tiêu Actor, kết quả quan sát được và ngữ nghĩa Use Case của OMG UML 2.x.

Đây là phân tích lại cơ sở cho mô hình được người dùng chốt. [Xác nhận] UC-01 cũ được giữ nhưng thu hẹp phạm vi; UC-02 cũ “Điều khiển quá trình xử lý video” được thay thế bằng UC-03 Pause, UC-04 Resume và UC-05 Stop; candidate UCC-04 được chuẩn hóa thành UC-02 “Phát cảnh báo biển báo”. Các tài liệu hiện hành được cập nhật theo quyết định này.

## 2. Existing Model Review

### Mô hình trước khi rà soát
- **Actor:** User.
- **UC-01:** Phân tích video biển báo giao thông — FR-01..FR-13.
- **UC-02:** Điều khiển quá trình xử lý video — FR-14, gồm Pause, Resume, Stop.
- **Associations:** User—UC-01 và User—UC-02.
- Không có Include, Extend hoặc Generalization.

### Nhận xét
- [Xác nhận tại thời điểm đó] Mô hình hai Use Case nhất quán với Catalog và Matrix đã duyệt khi ấy, có thể hợp lệ ở mức tổng quan; số lượng Use Case ít tự nó không làm mô hình sai UML.
- [Đề xuất] UC-01 bao gồm đầu vào video, xử lý, hiển thị và cảnh báo; cách nhóm này làm mục tiêu nhận cảnh báo và các kết quả có điều kiện khó thấy riêng trên sơ đồ.
- [Đề xuất] UC-02 gom ba lệnh có trigger, điều kiện phiên và kết quả khác nhau. Mô hình hiện tại có thể giữ chúng trong một Use Case, nhưng khó truy vết và đặc tả từng chuyển trạng thái.
- Việc phân rã cần dựa trên mục tiêu và kết quả có giá trị, không tách từng FR hay từng bước kỹ thuật thành Use Case.

## 3. Use Case Candidate Analysis

### Candidate: Chọn video đầu vào
- **Actor:** User.
- **Goal:** Cung cấp video ghi sẵn làm đầu vào.
- **Trigger:** User chọn file video.
- **Preconditions:** Không có điều kiện nghiệp vụ riêng được SRS xác định trước thao tác chọn file; file phải mở/đọc được để đi tiếp luồng xử lý thành công.
- **Observable Result:** File hợp lệ được tiếp nhận để xử lý; file không mở/đọc được gây thông báo lỗi và không bắt đầu xử lý.
- **Related Functional Requirements:** FR-01.
- **Evidence:** BA A-01; REQ-spec FR-01 Acceptance Criteria; Catalog UC-01 Trigger/UCC-03.
- **Independence:** Thấp. Chọn file là bước khởi tạo/input của mục tiêu phân tích, không có kết quả giá trị độc lập sau khi tách khỏi phân tích.
- **Proposed Decision:** [Đề xuất] Giữ là Trigger/main-flow behavior và luồng lỗi của UC-01; không tạo Use Case riêng và không dùng Include.
- **Justification:** SRS chỉ xác lập lựa chọn file làm đầu vào cho xử lý. Không có chức năng quản lý, xem trước hoặc lưu file độc lập.

### Candidate: Phân tích video biển báo giao thông
- **Actor:** User.
- **Goal:** Phân tích video đã chọn để nhận biết biển báo và theo dõi kết quả.
- **Trigger:** User chọn video để xử lý (FR-01).
- **Preconditions:** Video được chọn và có thể mở/đọc để vào luồng thành công; trường hợp không đọc được thuộc luồng lỗi FR-01.
- **Observable Result:** Video được xử lý theo timeline; kết quả nhận diện được hiển thị; xử lý kết thúc khi video kết thúc. Cảnh báo phát sinh nếu điều kiện cảnh báo được đáp ứng.
- **Related Functional Requirements:** FR-01..FR-08, FR-13; cảnh báo FR-07, FR-09..FR-12 được xem xét riêng ở Candidate “Nhận cảnh báo biển báo”.
- **Evidence:** BA §1, §4–§8; REQ-spec FR-01..FR-08, FR-13; Catalog UC-01.
- **Independence:** Cao. Đây là mục tiêu cốt lõi có thể hoàn tất với kết quả trực quan ngay cả khi video không phát sinh cảnh báo.
- **Proposed Decision:** [Đề xuất] Giữ làm Use Case chính “Phân tích video biển báo giao thông”.
- **Justification:** Có mục tiêu, Actor, trigger và kết quả quan sát được; bao gồm xử lý nội bộ cần thiết mà không biến YOLO/CNN/ByteTrack/aggregation thành Use Case.

### Candidate: Xem kết quả nhận diện
- **Actor:** User.
- **Goal:** Quan sát kết quả nhận diện trên video.
- **Trigger:** Kết quả của Frame/track được cập nhật trong phiên xử lý.
- **Preconditions:** UC phân tích video đang chạy và có kết quả cần hiển thị.
- **Observable Result:** Video có bounding box, nhãn và Track ID; FR-02, FR-08.
- **Related Functional Requirements:** FR-02, FR-08; kết quả phụ thuộc FR-03..FR-07.
- **Evidence:** BA §1, §5, §8; REQ-spec FR-02, FR-08 Acceptance Criteria; Q-03/D-12.
- **Independence:** Có giá trị với User nhưng không có tương tác/truy xuất kết quả tách khỏi phiên xử lý; không lưu video kết quả hoặc log theo Q-05.
- **Proposed Decision:** [Đề xuất] Giữ là observable behavior/main flow của UC phân tích, không tạo Use Case riêng.
- **Justification:** SRS chỉ yêu cầu hiển thị đồng bộ với video đang xử lý, không có mục tiêu xem lại hoặc truy vấn kết quả sau phiên.

### Candidate: Nhận cảnh báo biển báo
- **Actor:** User là người nhận cảnh báo.
- **Goal:** Được thông báo bằng âm thanh về biển báo khi đủ điều kiện.
- **Trigger:** Hệ thống xác định một track đủ điều kiện phát cảnh báo trong phiên phân tích.
- **Preconditions:** UC phân tích đang chạy; Track ID chưa được cảnh báo; track thỏa điều kiện của loại cảnh báo. Tiêu chí nhận diện chính xác còn mở tại A-16/OI-02.
- **Observable Result:** Phát giọng nói riêng theo lớp hoặc âm thanh chung; các cảnh báo được điều phối theo chính sách hàng đợi còn mở.
- **Related Functional Requirements:** FR-07, FR-09..FR-12.
- **Evidence:** BA §4, §7; REQ-spec FR-07, FR-09..FR-12; Q-04/D-12; OI-02/OI-04.
- **Independence:** Có giá trị riêng cho User, nhưng không thể xảy ra nếu không có kết quả xử lý video; chỉ phát sinh có điều kiện.
- **Proposed Decision:** [Đề xuất] Tách thành Use Case candidate “Nhận cảnh báo biển báo” dưới dạng **Optional Extension** của UC phân tích, không phải Use Case độc lập khởi chạy riêng.
- **Justification:** Base UC phân tích vẫn có kết quả giá trị khi không có track đủ điều kiện cảnh báo. Cảnh báo là hành vi bổ sung có điều kiện và kết quả riêng có ý nghĩa cho User. Nếu người dùng chọn mô hình này, có thể xác định extension point tại bước hệ thống đánh giá track; điều kiện cụ thể vẫn phải theo A-16/OI-02, không tự đặt ngưỡng. FR-09 và FR-10 là các nhánh loại cảnh báo trong candidate này, không cần tách thêm thành hai Use Case.

### Candidate: Tạm dừng xử lý video
- **Actor:** User.
- **Goal:** Tạm dừng phiên xử lý tại Frame hiện tại.
- **Trigger:** User yêu cầu Pause.
- **Preconditions:** Có phiên đang xử lý/phát.
- **Observable Result:** Giữ nguyên Frame hiện tại và không xử lý Frame mới.
- **Related Functional Requirements:** FR-14, đặc biệt Acceptance Criterion 1; tương tác cảnh báo còn mở ở OI-04.
- **Evidence:** REQ-spec FR-14/Q-01; Catalog UC-02.
- **Independence:** Có trigger và kết quả riêng, có giá trị điều khiển trực tiếp cho User.
- **Proposed Decision:** [Đề xuất] Use Case độc lập, liên kết trực tiếp với User; không phải Include/Extend của UC phân tích.
- **Justification:** User chủ động gọi thao tác và quan sát được chuyển trạng thái. Khả năng tác động lên cảnh báo không được suy diễn.

### Candidate: Tiếp tục xử lý video
- **Actor:** User.
- **Goal:** Tiếp tục phiên xử lý từ Frame đang dừng.
- **Trigger:** User yêu cầu Resume.
- **Preconditions:** Phiên đang tạm dừng tại một Frame.
- **Observable Result:** Hệ thống tiếp tục xử lý từ điểm đang dừng.
- **Related Functional Requirements:** FR-14, đặc biệt Acceptance Criterion 2; tương tác cảnh báo còn mở ở OI-04.
- **Evidence:** REQ-spec FR-14/Q-01; Matrix UC-02 preconditions.
- **Independence:** Có trigger, trạng thái tiền điều kiện và kết quả khác Pause/Stop; có thể đặc tả riêng.
- **Proposed Decision:** [Đề xuất] Use Case độc lập, liên kết trực tiếp với User; không phải Include/Extend của UC phân tích.
- **Justification:** Resume chỉ có ý nghĩa sau Pause và có kết quả khác biệt. Tách riêng không hàm ý rằng hành vi tiếp tục khi không tạm dừng được hỗ trợ.

### Candidate: Dừng xử lý video
- **Actor:** User.
- **Goal:** Kết thúc phiên xử lý hiện tại.
- **Trigger:** User yêu cầu Stop.
- **Preconditions:** Có phiên xử lý làm đối tượng để kết thúc. SRS chưa xác định Stop có được phép khi phiên đang Pause hay không.
- **Observable Result:** Phiên xử lý kết thúc; ứng dụng sẵn sàng chọn video mới.
- **Related Functional Requirements:** FR-14, đặc biệt Acceptance Criterion 3; tác động tới hàng đợi/track còn mở ở OI-04.
- **Evidence:** REQ-spec FR-14/Q-01; Matrix UC-02 preconditions.
- **Independence:** Có trigger và kết quả cuối phiên riêng, khác với Pause/Resume.
- **Proposed Decision:** [Đề xuất] Use Case độc lập, liên kết trực tiếp với User; không phải Include/Extend của UC phân tích.
- **Justification:** Kết thúc phiên là mục tiêu có kết quả quan sát được riêng. Không giả định khả năng Stop từ mọi trạng thái.

## 4. Candidate Evaluation

| Candidate | Classification được đề xuất | Kết luận |
|---|---|---|
| Chọn video đầu vào | Trigger/main-flow behavior và luồng lỗi | Gộp vào UC phân tích; không độc lập, không Include |
| Phân tích video biển báo giao thông | Independent Use Case | Giữ làm UC cốt lõi |
| Xem kết quả nhận diện | Observable behavior/main flow | Nằm trong UC phân tích; không có chức năng xem lại độc lập |
| Nhận cảnh báo biển báo | Optional Extension candidate | Có kết quả riêng nhưng phụ thuộc có điều kiện vào phân tích; đề xuất `extend` nếu được duyệt |
| Tạm dừng xử lý video | Independent Use Case candidate | Tách khỏi UC điều khiển chung vì có trigger, trạng thái và kết quả riêng |
| Tiếp tục xử lý video | Independent Use Case candidate | Tách khỏi UC điều khiển chung vì điều kiện phiên và kết quả riêng |
| Dừng xử lý video | Independent Use Case candidate | Tách khỏi UC điều khiển chung vì kết quả kết thúc phiên riêng |

Phân loại ban đầu được lập trước khi người dùng chốt ID. Mô hình hiện hành xác nhận UC-01..UC-05 như ghi tại §6 và §11. “Independent Use Case” không đồng nghĩa mọi thao tác đều chạy độc lập với phiên phân tích; nó biểu thị một mục tiêu/interaction riêng của Actor.

### Phân biệt các loại hành vi
- **Independent Use Case:** Actor có mục tiêu, trigger và kết quả có thể mô tả riêng. UC phân tích video và các candidate Pause/Resume/Stop đáp ứng tiêu chí này ở Phương án B.
- **Included Behavior / `include`:** một Use Case khác được gọi như hành vi bắt buộc trong mọi lần thực hiện Use Case gốc. Chọn file và hiển thị kết quả là các bước/đầu ra của UC phân tích, nhưng không cần tách thành Use Case để vẽ `include`; chúng không phải hành vi tái sử dụng độc lập.
- **Optional Extension / `extend`:** hành vi bổ sung có điều kiện tại extension point; Use Case gốc vẫn có ý nghĩa khi extension không xảy ra. UC-02 được chốt theo mô hình này; tiêu chí cụ thể A-16/OI-02 vẫn mở.
- **Alternative Flow:** một nhánh khác trong cùng Use Case, không phải tự động là Use Case hay quan hệ `extend`. File lỗi là luồng ngoại lệ FR-01; cảnh báo theo lớp và âm thanh chung có thể là các nhánh của candidate cảnh báo. Trong Phương án A, Pause/Resume/Stop có thể tiếp tục được đặc tả như các luồng của UC-02.
- **Internal Processing:** detection, tracking, classification, temporal aggregation, recognition state, alert decision, alert queue và configuration loading là xử lý nội bộ; chúng hỗ trợ kết quả UC, không phải Actor hoặc Use Case riêng.

## 5. Alternative Models

### Phương án A — Giữ mô hình hai Use Case
Giữ UC-01 phân tích video và UC-02 điều khiển quá trình (Pause/Resume/Stop); giữ User associations với cả hai; không dùng Include/Extend.

### Phương án B — Phân rã theo mục tiêu và kết quả
- Giữ UC-01 phân tích video; bao gồm chọn video và hiển thị kết quả như main-flow behavior.
- Tách “Nhận cảnh báo biển báo” thành optional extension candidate của UC-01, vì là kết quả giá trị cho User nhưng chỉ xảy ra khi đủ điều kiện.
- Tách Pause, Resume và Stop thành ba Use Case candidates liên kết trực tiếp với User do mỗi thao tác có trigger, tiền điều kiện và kết quả quan sát được riêng.
- Không tạo Use Case cho từng bước phát hiện, tracking, phân loại, tổng hợp hoặc cấu hình.
- Tại thời điểm phân tích ban đầu, chưa gán ID và chưa sửa các tài liệu đã duyệt; quyết định cuối cùng và ID migration được ghi tại §6 và §11.

### So sánh
| Tiêu chí | Phương án A: 2 Use Case | Phương án B: 5 Use Case đã chốt |
|---|---|---|
| Tính đúng đắn UML | Hợp lệ ở mức tổng quan; không có quan hệ sai | Có thể hợp lệ nếu alert extension có điều kiện/extension point rõ; các thao tác điều khiển là Use Case độc lập, không cần quan hệ với UC phân tích |
| Mức độ thể hiện chức năng | Gọn nhưng cảnh báo và ba lệnh điều khiển bị gom trong Use Case rộng | Thể hiện rõ kết quả cảnh báo và từng mục tiêu điều khiển mà không đưa thuật toán vào sơ đồ |
| Khả năng đặc tả Use Case | Đặc tả UC-02 cần nhiều luồng theo từng trạng thái | Mỗi lệnh điều khiển có thể có tiền điều kiện/kết quả riêng; alert có luồng điều kiện riêng |
| Nhất quán với SRS | FR-01..FR-14 đều truy về hai UC | FR-01..FR-14 đều có UC hoặc xử lý hỗ trợ; không thêm hành vi, nhưng đề xuất cách tổ chức mới |
| Mức độ trùng lặp | Ít trùng lặp; một UC bao trùm nhiều hành vi | Có rủi ro lặp mô tả đầu vào/hiển thị giữa UC phân tích và alert; cần giữ alert như extension, không copy flow |
| Khả năng truy vết | UC-01 map FR-01..FR-13; UC-02 map FR-14 | Alert dễ truy vết FR-07/09..12; Pause/Resume/Stop truy trực tiếp các tiêu chí FR-14; FR kỹ thuật giữ là supporting |

## 6. Recommended Model
[Xác nhận] Người dùng chốt **Phương án B** để thể hiện các mục tiêu có giá trị khác nhau: phân tích video, nhận cảnh báo có điều kiện, tạm dừng, tiếp tục và kết thúc phiên. Đây không phải lựa chọn dựa trên số lượng Use Case: chọn video và xem kết quả vẫn được giữ trong UC phân tích; các module kỹ thuật không được tách.

Mô hình khái niệm được người dùng chốt và chuẩn hóa trong Catalog:
1. UC-01 hiện tại — Phân tích video biển báo giao thông (giữ làm UC cốt lõi).
2. UC-02 — Phát cảnh báo biển báo, Optional Extension của UC-01 tại điểm đánh giá trạng thái Track ID; điều kiện tham chiếu tiêu chí A-16/OI-02 đang mở.
3. UC-03 — Tạm dừng xử lý video; UC-04 — Tiếp tục xử lý video; UC-05 — Dừng xử lý video; mỗi Use Case có Association tới User.

[Xác nhận] UC-02 cũ được thay thế bằng UC-03..UC-05; không giữ UC điều khiển tổng quát đồng thời để tránh trùng lặp mục tiêu.

## 7. Requirement Coverage

| Requirement ID | Phương án A | Phương án B (mô hình đã chốt) | Coverage / Explanation |
|---|---|---|---|
| FR-01 | UC-01 | UC-01 — supporting trigger/input | Chọn file là bước khởi tạo; kiểm tra file lỗi là luồng ngoại lệ, không cần UC riêng |
| FR-02 | UC-01 | UC-01 — direct | Đọc và trình bày Frame theo timeline |
| FR-03 | UC-01 | UC-01 — supporting | Phát hiện vị trí biển là xử lý nội bộ |
| FR-04 | UC-01 | UC-01 — supporting | Tracking/Track ID hỗ trợ xuyên Frame |
| FR-05 | UC-01 | UC-01 — supporting | Classification hỗ trợ kết quả nhận diện |
| FR-06 | UC-01 | UC-01 — supporting | Tổng hợp theo Track ID hỗ trợ kết quả cuối |
| FR-07 | UC-01 | UC-02 — supporting/pending criteria | Trạng thái hỗ trợ quyết định cảnh báo; A-16/OI-02 chưa chốt |
| FR-08 | UC-01 | UC-01 — direct | Hiển thị video, box, nhãn và Track ID |
| FR-09 | UC-01 | UC-02 — direct | Cảnh báo theo lớp; điều kiện nhận diện/ngôn ngữ còn mở |
| FR-10 | UC-01 | UC-02 — direct | Âm thanh chung khi trạng thái tương ứng được xác định |
| FR-11 | UC-01 | UC-02 — cross-cutting | Giới hạn tối đa một cảnh báo cho mỗi Track ID |
| FR-12 | UC-01 | UC-02 — cross-cutting | Xếp hàng cảnh báo; chính sách vận hành OI-04 còn mở |
| FR-13 | UC-01 — supporting | UC-01 — supporting | Configuration Loading nội bộ, không cần Actor/Use Case riêng |
| FR-14 | UC-02 | UC-03 / UC-04 / UC-05 — direct | Pause, Resume, Stop truy vết tới kết quả tương ứng; không tạo chức năng ngoài Acceptance Criteria |

[Xác nhận] Tất cả FR-01..FR-14 được bao phủ trong cả hai phương án bằng Use Case hoặc xử lý hỗ trợ. Không có NFR nào cần một Use Case riêng chỉ để tạo liên kết RTM.

## 8. UML Relationship Review
- **Association:** User liên kết với UC-01..UC-05; User là Actor duy nhất và là người nhận kết quả tại UC-02. Không thêm Driver/Administrator.
- **Include:** [Xác nhận] Không đề xuất. Chọn file, hiển thị, detection/tracking/classification/aggregation là bước hoặc xử lý hỗ trợ; không phải Use Case dùng chung bắt buộc chỉ vì được yêu cầu.
- **Extend — UC-02 tới UC-01:** [Xác nhận] Quan hệ được mô hình hóa tại extension point sau khi xác định trạng thái Track ID. Guard yêu cầu Track ID chưa được cảnh báo và trạng thái thỏa tiêu chí đã duyệt để phát một trong hai loại cảnh báo. Tiêu chí A-16/OI-02 còn mở; không đặt ngưỡng.
- **Generalization:** [Xác nhận] Không đề xuất; không có Actor/Use Case chuyên biệt nào được xác định là một dạng kế thừa của phần tử khác.
- **UC-03/UC-04/UC-05:** [Xác nhận] Các hành vi điều khiển độc lập do Actor kích hoạt; không `include`/`extend` UC-01. Điều kiện phụ thuộc phiên là precondition/ngữ cảnh nghiệp vụ, không phải quan hệ UML.

## 9. Impact Analysis
- SRS và các FR giữ nguyên; không thêm yêu cầu hoặc chức năng.
- Người dùng đã chốt Phương án B với IDs UC-01..UC-05; Catalog, Matrix và PlantUML được cập nhật theo đó.
- RTM v0.3 vẫn giữ nguyên; các Use Case IDs trong RTM chỉ được cập nhật sau khi được duyệt theo quy trình traceability.
- Không thay đổi Actor, boundary, scope, quyết định nghiệp vụ hoặc Open Issues.

## 10. Open Questions
- [Chưa xác định] Tiêu chí cụ thể để phân loại trạng thái track đủ điều kiện cảnh báo (A-16/OI-02); không đặt ngưỡng tại Use Case Model.
- [Chưa xác định] Stop có được phép khi phiên đang Pause không? Hành vi với cảnh báo/hàng đợi vẫn phụ thuộc OI-04.
- [Chưa xác định] Chính sách A-17, tiêu chí A-16, OI-04, OI-05, OI-03, OI-06 và A-19 tiếp tục theo giai đoạn ghi trong SRS/BA.
- [Chưa xác định] Tên chính thức của hệ thống vẫn chưa được chốt; không ảnh hưởng quyết định phân rã.

## 11. Approval Outcome
- [Xác nhận] Người dùng chốt mô hình 5 Use Case và IDs UC-01..UC-05.
- [Xác nhận] UC-02 `extend` UC-01 tại extension point được ghi trong Catalog/Matrix; tiêu chí A-16 và hành vi OI-04 vẫn là Open Issues.
- [Xác nhận] Không tạo Use Case cho chọn file, xem kết quả riêng hoặc thành phần kỹ thuật.
- RTM và mọi Open Issue nghiệp vụ không bị sửa/đóng bởi quyết định phân rã này.
