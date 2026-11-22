# Quy tắc làm việc cho Cline - Đồ án phát hiện biển báo giao thông

## Nguyên tắc dữ liệu
- Không bịa: yêu cầu, Actor, Use Case, chức năng, ngưỡng confidence, số Frame, thời gian chờ, số liệu thực nghiệm, tài liệu tham khảo.
- Khi thiếu thông tin: nêu thông tin thiếu, lý do cần, phương án đề xuất, rồi HỎI người dùng. Không tự quyết.
- Luôn phân biệt: [Đã xác nhận] / [Từ tài liệu] / [Nghiên cứu ngoài] / [Giả định chờ xác nhận] / [Đề xuất kỹ thuật].

## Cổng chặn code
- Trước mọi nhiệm vụ, đọc docs/00_project/project-status.md.
- Chỉ được tạo hoặc sửa file trong src/, tests/, scripts/ khi dòng "Code allowed" là YES.
- Chỉ người dùng được đổi giá trị này, sau khi nghiệm thu tài liệu thiết kế (Phase 8).

## Kiểm soát thay đổi
- Đọc file hiện có trước khi sửa. Không xóa, ghi đè, di chuyển file khi chưa được đồng ý.
- Không đổi kiến trúc, không cài thư viện, không thêm chức năng ngoài phạm vi khi chưa giải thích và được đồng ý.
- Không để code hoặc tài liệu mâu thuẫn tài liệu thiết kế đã duyệt.
- Không dùng dữ liệu giả để tuyên bố hệ thống hoạt động. Không che giấu lỗi bằng cách nuốt Exception.
- Không tuyên bố hoàn thành nếu chưa chạy kiểm thử.
- Mọi thay đổi thiết kế đã duyệt phải được ghi vào docs/00_project/change-log.md. Không tạo tài liệu mới thay thế tài liệu cũ mà không ghi nhận.
- Không sửa file trong report/template/.

## Quy ước
- Thuật ngữ chuyên ngành giữ nguyên tiếng Anh (Use Case, Actor, Basic Flow, Object Detection...).
- Tên file: <mã>_<tên-không-dấu>_v<major>.<minor>.<đuôi>, ví dụ UC-spec_v0.1.md.
- Tài liệu thiết kế nằm trong docs/design/, báo cáo chính thức trong report/.

## Báo cáo sau mỗi nhiệm vụ
1. Đã thực hiện gì. 2. File đã tạo. 3. File đã sửa. 4. Chức năng đã hoàn thành. 5. Kết quả kiểm thử. 6. Lỗi còn tồn tại. 7. Việc tiếp theo.
