from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"

# Cấu hình tài khoản Quản trị viên (Admin)
# Có quyền quản lý đóng/mở ga và tuyến tàu điện
ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "admin",
}

# Cấu hình khu vực và bản đồ
PLACE_NAME = "Munich, Bavaria, Germany"
DEFAULT_CENTER_LAT = 48.1371
DEFAULT_CENTER_LON = 11.5754

# Trọng số đi bộ và giới hạn khoảng cách đi bộ tối đa cho mỗi chặng
WALKING_WEIGHT = 2.5
MAX_ACCESS_WALK_M = 2500.0

# Danh sách địa danh ranh giới các thành phố lân cận
BOUNDARY_PLACES = [
    "Munich, Bavaria, Germany",
    "Dachau, Bavaria, Germany",
    "Freising, Bavaria, Germany",
    "Erding, Bavaria, Germany",
    "Fürstenfeldbruck, Bavaria, Germany",
    "Starnberg, Bavaria, Germany",
    "Germering, Bavaria, Germany",
    "Ottobrunn, Bavaria, Germany",
    "Unterhaching, Bavaria, Germany",
]

# Đường dẫn file cache
ACCESS_GRAPH_CACHE_FILE = CACHE_DIR / "munich_walk.graphml"
ACCESS_GRAPH_PICKLE_FILE = CACHE_DIR / "munich_walk.pkl"
LEGACY_DRIVE_GRAPH_CACHE_FILE = CACHE_DIR / "munich_drive.graphml"
RAIL_GRAPH_CACHE_FILE = CACHE_DIR / "munich_rail_unsimplified.graphml"
RAIL_GRAPH_PICKLE_FILE = CACHE_DIR / "munich_rail_unsimplified.pkl"
STATION_CACHE_FILE = CACHE_DIR / "munich_station_nodes_citywide.json"
BOUNDARY_CACHE_FILE = CACHE_DIR / "munich_neighbor_boundaries.geojson"

