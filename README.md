# Traffic Sign Video Demo 1.1

Ứng dụng desktop Windows nhận diện biển báo giao thông từ video. Demo dùng YOLO để tìm vị trí biển báo và CNN để phân loại 43 lớp. Giao diện hiển thị khung nhận diện, nhãn tiếng Việt và mục **Simulation Events**. Cảnh báo tiếng Việt phát từ WAV có sẵn trên máy.

Đây là bản mã nguồn phục vụ học tập, nghiên cứu và trình diễn. Ứng dụng chưa được xác thực để sử dụng khi lái xe hoặc điều khiển phương tiện thật.

## Cài đặt trên Windows

Cài **CPython 3.13 x64** với Tkinter, Git và Git LFS. Mở PowerShell và đăng nhập GitHub bằng tài khoản có quyền truy cập repo Private.

```powershell
git lfs install
git clone https://github.com/qzuong/Traffic-sign-project.git
Set-Location -LiteralPath '.\Traffic-sign-project' -ErrorAction Stop
git lfs pull
```

Tạo hai môi trường riêng để TensorFlow và PyTorch dùng đúng phiên bản thư viện:

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

## Model và tài nguyên đi kèm

Git tải model, ảnh và âm thanh cùng mã nguồn. Git LFS tải riêng video mẫu.

| Đường dẫn | Nội dung |
| --- | --- |
| `models/candidates/gtsdb_yolov8n.pt` | Checkpoint YOLO mặc định. Ứng dụng kiểm tra SHA-256 của checkpoint. |
| `models/model.h5` | CNN tương thích với bảng 43 lớp trong `models/model.py`. |
| `assets/traffic_signs/0.png` đến `42.png` | Ảnh xem trước biển báo. |
| `assets/voice_google/00.wav` đến `42.wav` | Cảnh báo tiếng Việt. Thư mục `assets/voice_vi/` chứa WAV dự phòng. |
| `data/videos/test_video.mp4` | Video mẫu, khoảng 177 MB, tải bằng Git LFS. |

Ứng dụng phát WAV có sẵn và không cần gTTS hay kết nối mạng khi chạy. Repo dành cho nhóm có quyền truy cập. Chỉ chia sẻ tiếp tài liệu, model và media khi đã xác minh quyền phân phối.

## Chạy demo

```powershell
.\.venv-cnn\Scripts\python.exe -m src.traffic_sign_demo
```

Mở `data/videos/test_video.mp4` trong ứng dụng, đợi hai worker báo **Ready** và theo dõi khung nhận diện trên video. Ứng dụng tự phân tích trong lúc phát. Có thể dùng Pause, Resume, Stop và Replay. Các dấu hiệu đủ điều kiện phát cảnh báo có thể xuất hiện trong **Simulation Events**. Nhật ký sự kiện JSONL mặc định được lưu tại `%LOCALAPPDATA%\TrafficSignDemo\simulation-events`.

Nếu worker báo lỗi, kiểm tra đường dẫn model và quá trình cài thư viện ở đúng môi trường. Nếu dùng môi trường Python ở vị trí khác, đặt biến `TRAFFIC_SIGN_CNN_PYTHON` hoặc `TRAFFIC_SIGN_YOLO_PYTHON` thành đường dẫn đầy đủ tới `python.exe` tương ứng. Nếu video mẫu chỉ có vài dòng văn bản, chạy lại `git lfs pull`.

## Kiểm thử

```powershell
.\.venv-cnn\Scripts\python.exe -m unittest discover -s tests
```
