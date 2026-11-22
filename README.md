# Traffic Sign Video Demo 1.1

Ứng dụng desktop Windows nhận diện biển báo giao thông từ video. Demo dùng YOLO để tìm vị trí biển báo và CNN để phân loại 43 lớp. Giao diện hiển thị khung nhận diện, nhãn tiếng Việt và mục **Simulation Events**. Cảnh báo tiếng Việt phát từ WAV có sẵn trên máy.

Đây là bản mã nguồn phục vụ học tập, nghiên cứu và trình diễn. Ứng dụng chưa được xác thực để sử dụng khi lái xe hoặc điều khiển phương tiện thật.

## Cài đặt trên Windows

Cài **CPython 3.13 x64** với Tkinter. Mở PowerShell trong thư mục chứa README và chạy:

```powershell
py -3.13 -m venv .venv-cnn
py -3.13 -m venv .venv-yolo
.\.venv-cnn\Scripts\python.exe -m pip install -r requirements-cnn.txt
.\.venv-yolo\Scripts\python.exe -m pip install -r requirements-yolo.txt
```

| Thành phần | Thư viện |
| --- | --- |
| Giao diện và video | Tkinter, OpenCV (`opencv-python`), NumPy, Pillow |
| CNN | TensorFlow, Keras, h5py và NumPy |
| YOLO | Ultralytics, PyTorch CPU, torchvision CPU, OpenCV và NumPy |
| Phát WAV | `winsound` của Python trên Windows |

Tkinter và `winsound` đi kèm Python trên Windows. Hai file requirements ghi phiên bản các thư viện chính. Pip tự cài các phụ thuộc gián tiếp.

## Chuẩn bị model và tài nguyên

Repo chỉ chứa mã nguồn. Trước khi chạy nhận diện, chép đúng các model từ nguồn tin cậy mà bạn có quyền sử dụng:

| Đường dẫn | Nội dung |
| --- | --- |
| `models/candidates/gtsdb_yolov8n.pt` | Checkpoint YOLO mặc định. Ứng dụng kiểm tra SHA-256 của checkpoint. |
| `models/model.h5` | CNN tương thích với bảng 43 lớp trong `models/model.py`. |
| `assets/traffic_signs/0.png` đến `42.png` | Ảnh xem trước tùy chọn. |
| `assets/voice_google/00.wav` đến `42.wav` | WAV tùy chọn cho cảnh báo tiếng Việt. Thư mục `assets/voice_vi/` là nguồn WAV dự phòng. |

Không cần gTTS để chạy ứng dụng. Chọn video trên máy qua nút mở video. Model, video, ảnh và WAV được quản lý riêng với repo.

## Chạy demo

```powershell
.\.venv-cnn\Scripts\python.exe -m src.traffic_sign_demo
```

Chọn video, đợi hai worker báo **Ready** và theo dõi khung nhận diện trên video. Ứng dụng tự phân tích trong lúc phát. Các dấu hiệu đủ điều kiện phát cảnh báo có thể xuất hiện trong **Simulation Events**. Nhật ký sự kiện JSONL mặc định được lưu tại `%LOCALAPPDATA%\TrafficSignDemo\simulation-events`.

Nếu worker báo lỗi, kiểm tra đường dẫn model và quá trình cài thư viện ở đúng môi trường. Nếu dùng môi trường Python ở vị trí khác, đặt biến `TRAFFIC_SIGN_CNN_PYTHON` hoặc `TRAFFIC_SIGN_YOLO_PYTHON` thành đường dẫn đầy đủ tới `python.exe` tương ứng.
