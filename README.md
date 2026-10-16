# Munich U-Bahn Navigation & Route Finding

Ứng dụng mô phỏng và tìm tuyến đường tối ưu kết hợp giữa **Đi bộ** và **Tàu điện ngầm (Munich U-Bahn)** tại thành phố Munich (Đức), hỗ trợ so sánh hiệu năng giữa thuật toán **A\*** và **Dijkstra**, tích hợp hệ thống **Phân quyền Quản trị viên (Admin)** để quản lý đóng/mở các tuyến và ga tàu, cùng tính năng **Tự động nhận diện & Đánh dấu vị trí chuyển tuyến U-Bahn (U1 - U8)** trực quan trên bản đồ.

---

## 📌 1. Giới thiệu & Cơ chế tính toán

* **Dữ liệu mạng lưới:** Được trích xuất và ánh xạ từ **OpenStreetMap (OSM)** bao gồm mạng lưới đi bộ (`walk`), mạng lưới đường ray ngầm (`railway=subway`) và danh sách các nhà ga U-Bahn.
* **Hàm chi phí tối ưu hóa (Weighted Cost):**
  $$\text{Cost} = 2.5 \times (\text{Đi bộ chặng đầu} + \text{Đi bộ chặng cuối}) + 1.0 \times \text{Đi tàu điện ngầm}$$
* **Giới hạn đi bộ:** Mặc định tối đa `2500m` cho mỗi chặng đi bộ đầu/cuối (tránh việc thuật toán chọn đi bộ toàn tuyến thay vì đi tàu ngầm).
* **Tối ưu hóa chuyển tuyến:** Tự động xác định số lần đổi tàu và lựa chọn chuỗi tuyến tàu (U1 - U8) thông minh bằng Quy hoạch động (Dynamic Programming) sao cho hành khách phải đổi tàu ít lần nhất.

---

## 🔄 2. Tính năng Nhận diện & Đánh dấu Chuyển tuyến (Subway Transfers)

Khi lộ trình tàu điện ngầm yêu cầu đổi giữa các tuyến khác nhau (ví dụ: đang đi tuyến `U1` cần chuyển sang `U3` tại ga *Sendlinger Tor*):

1. **Thống kê số lần chuyển tuyến:** Hiển thị rõ ràng trên thanh Sidebar mục `Subway transfers: X (lần đổi tàu)`.
2. **Đánh dấu trực quan trên bản đồ:**
   * Tại mỗi nhà ga cần chuyển tuyến, hệ thống tự động cắm **Marker màu tím nổi bật** (`#9c27b0`) với nhãn:
     $$\text{🔄 Transfer: [Tuyến cũ] ➔ [Tuyến mới]}$$
   * Giúp hành khách dễ dàng quan sát điểm cần xuống tàu để chuyển sang chuyến tàu tiếp theo.
3. **Chỉ dẫn chi tiết từng chặng:**
   * Trong danh sách các ga đi qua, ga chuyển tuyến sẽ được làm nổi bật với thông báo:
     ```text
     3. Sendlinger Tor
        └── 🔄 CHUYỂN TUYẾN: U1 ➔ U3
     ```

---

## 🏛️ 3. Kiến trúc Dự án (MVC Architecture)

Mã nguồn được thiết kế theo mô hình **Model - View - Controller (MVC)** tách biệt rõ ràng trách nhiệm:

```text
Munich_Subway_Map/
├── config.py                      # Cấu hình hệ thống, tài khoản Admin (tk/mk) và đường dẫn cache
├── main.py                        # Entry point chính của ứng dụng
├── cache/                         # Thư mục chứa dữ liệu đồ thị cache nhanh (.pkl, .graphml, .geojson)
├── models/
│   ├── __init__.py
│   └── ubahn_network.py           # Định nghĩa các tuyến U1 - U8 (màu sắc, thứ tự các ga)
├── services/
│   ├── algorithms.py              # Thuật toán tìm đường đa phương thức A* và Dijkstra
│   ├── map_service.py             # Quản lý đọc/ghi đồ thị OSMnx, GeoJSON ranh giới, tìm node gần nhất
│   ├── route_geometry.py          # Thuật toán Catmull-Rom spline, tính chuyển tuyến, sinh tọa độ polyline
│   ├── station_store.py           # Đọc/ghi thông tin và tạo liên kết chuyển tuyến giữa các ga U-Bahn
│   └── preload_data.py            # Script tải trước và tạo cache dữ liệu từ OpenStreetMap
├── controllers/
│   └── app_controller.py          # "Bộ não" điều phối nghiệp vụ, quản lý state và phân quyền Admin
└── views/
    ├── window.py                  # Giao diện chính (CustomTkinter + TkinterMapView)
    ├── admin_login_dialog.py      # Hộp thoại xác thực đăng nhập tài khoản Quản trị viên
    └── blocked_stations_dialog.py # Hộp thoại quản lý đóng theo Tuyến (U1-U8) hoặc đóng từng Ga lẻ
```

---

## 🔐 4. Tính năng Phân quyền Quản trị viên (Admin)

Để bảo vệ các cấu hình giao thông, chỉ **Admin** mới có quyền can thiệp vào tình trạng vận hành của các tuyến và nhà ga:

* **Tài khoản mặc định:**
  - **Tài khoản:** `admin`
  - **Mật khẩu:** `admin`
  *(Có thể thay đổi trong file `config.py` tại biến `ADMIN_CREDENTIALS`)*.
* **Quyền hạn của Admin:**
  1. **Đóng theo Tuyến:** Cho phép khóa toàn bộ một tuyến metro (U1 đến U8).
  2. **Đóng từng Ga lẻ:** Tìm kiếm và chọn những nhà ga đang sửa chữa/bảo trì để đóng.
  3. **Click trực tiếp trên bản đồ:** Admin có thể click vào biểu tượng chấm tròn của ga trên bản đồ để đóng hoặc mở lại ga ngay lập tức.
* **Người dùng khách (Guest):** Chỉ có quyền chọn điểm xuất phát/đích và tìm đường. Nếu khách cố tình nhấn nút đóng tuyến hoặc click đổi trạng thái ga, ứng dụng sẽ yêu cầu đăng nhập Admin.

---

## ⚙️ 5. Cài đặt Môi trường

Yêu cầu **Python 3.10+**. Khuyến nghị sử dụng môi trường ảo (`venv` hoặc `conda`).

1. Cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```

---

## 💾 6. Dữ liệu Cache & Khởi tạo (Preload Data)

### ❓ Khi nào cần chạy `preload_data.py`?
* **NẾU THƯ MỤC `cache/` ĐÃ CÓ SẴN CÁC FILE:** Bạn **KHÔNG CẦN** chạy preload. Hãy chuyển sang Bước 7 để mở ứng dụng ngay.
* **NẾU THƯ MỤC `cache/` CHƯA CÓ DỮ LIỆU (Lần đầu clone dự án):** Bạn cần chạy script preload để tải dữ liệu OpenStreetMap về máy, tạo cache pickle tốc độ cao giúp các lần khởi động sau chỉ mất vài giây:

### 💻 Câu lệnh chạy Preload trong Terminal:
Mở terminal tại thư mục gốc của dự án (`Munich_Subway_Map`), chạy một trong hai lệnh sau:

```bash
# Cách 1 (Khuyến nghị):
python -m services.preload_data

# Cách 2:
python services/preload_data.py
```

> **Cơ chế thông minh:** Script sẽ tự động kiểm tra xem các file cache đã tồn tại chưa. Nếu đã có sẵn, script hoàn thành ngay lập tức trong 1 giây mà không tải lại qua mạng. Nếu thực sự muốn ép tải lại từ đầu, hãy thêm cờ `--force`.

---

## 🚀 7. Chạy Ứng Dụng

Chạy câu lệnh sau tại thư mục dự án:

```bash
python main.py
```

---

## 📖 8. Hướng dẫn Sử dụng Giao diện

1. **Chọn điểm đi & điểm đến:**
   - **Click chuột phải** tại vị trí bất kỳ trên bản đồ -> Chọn **"Choose a starting point"** (Điểm xuất phát - Marker màu xanh lá).
   - **Click chuột phải** tại vị trí thứ hai -> Chọn **"Choose an ending point"** (Điểm đích - Marker màu đỏ).
2. **Chọn thuật toán:**
   - Tại sidebar bên phải, chọn giải thuật **`A*`** hoặc **`Dijkstra`**.
3. **Tìm đường & Theo dõi chuyển tuyến:**
   - Nhấn nút **`Tìm đường`** (`Find Route`).
   - Lộ trình sẽ hiển thị trực quan:
     - **Màu xanh dương:** Chặng đi bộ (từ điểm chọn đến ga lên tàu và từ ga xuống tàu đến đích).
     - **Màu cam:** Chặng đi trên tàu điện ngầm U-Bahn.
     - **Marker màu tím (🔄):** Đánh dấu chính xác vị trí ga cần chuyển tuyến và chỉ rõ tuyến cần đổi sang (ví dụ: `🔄 Transfer: U1 ➔ U3`).
   - Bảng kết quả sẽ cung cấp: Tổng khoảng cách (km), Tỷ lệ Đi bộ / Tàu điện ngầm, Chi phí có trọng số, Số nút mở rộng (Nodes visited), Thời gian tính toán (ms), **Số lần chuyển tuyến (Subway transfers)** và chi tiết các ga đổi tàu.
4. **Bảng Chú thích màu các tuyến (Lines Legend):**
   - Nằm ngay dưới phần kết quả trên sidebar, hiển thị rõ ràng huy hiệu màu sắc và tên viết tắt ga đầu/cuối của cả 8 tuyến metro Munich:
     - **U1:** Xanh lá cây (`#0B8F45`)
     - **U2:** Đỏ tươi (`#C8102E`)
     - **U3:** Cam (`#F58220`)
     - **U4:** Xanh mòng két (`#00A3AD`)
     - **U5:** Nâu vàng (`#A66A00`)
     - **U6:** Xanh lam (`#0065BD`)
     - **U7:** Tím đậm (`#7A1E74`)
     - **U8:** Hồng cánh sen (`#E4007F`)
     - Kèm quy ước màu đường vẽ lộ trình (Đi bộ: Xanh dương, Tàu: Cam, Đổi tuyến: Marker tím).
5. **Quản lý đóng ga/tuyến (Dành cho Admin):**
   - Nhấn **`Đóng tuyến / Ga [Admin]`** hoặc nút **`Đăng nhập`** trên góc phải sidebar.
   - Nhập tài khoản `admin` / `admin`.
   - Chọn tab **"Đóng theo Tuyến"** hoặc **"Đóng từng Ga lẻ"** -> Nhấn **`Áp dụng`**.
   - Các ga bị đóng sẽ chuyển sang biểu tượng màu đỏ. Thuật toán tìm đường sẽ tự động tính toán tránh hoàn toàn các ga và tuyến đã bị đóng.
6. **Xóa lựa chọn:**
   - Nhấn **`Xóa lựa chọn`** (`Clear Selection`) để đặt lại bản đồ về trạng thái ban đầu.
