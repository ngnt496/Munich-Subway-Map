"""Controller điều phối toàn bộ luồng nghiệp vụ giữa View (giao diện) và Service (dữ liệu & thuật toán)."""

import time
from typing import List, Tuple
import config
from models.ubahn_network import UBAHN_LINES
from services.algorithms import find_route_multimodal_via_rail
from services.route_geometry import (
    add_visible_endpoints,
    find_subway_transfers,
    geometry_to_boundary_paths,
    get_rail_path_station_names,
    get_station_display_points,
    get_unique_station_names,
    line_coords,
    path_to_map_coords,
    selected_ubahn_route_coords,
)


class AppController:
    def __init__(self, view=None, map_service=None, admin_credentials=None):
        self.view = view
        self.map_service = map_service
        self.admin_credentials = admin_credentials or config.ADMIN_CREDENTIALS

        # Trạng thái người dùng và phân quyền
        self.is_admin = False

        # Trạng thái điều hướng
        self.start_node = None
        self.end_node = None
        self.start_coords = None
        self.end_coords = None

        # Danh sách tuyến và ga bị đóng (được tách biệt rõ ràng)
        self.blocked_line_names = set()
        self.blocked_station_names = set()

        # Cache dữ liệu ga
        self.station_points = {}
        self.all_station_names = []

    def set_view(self, view):
        self.view = view

    def get_effective_blocked_stations(self) -> set:
        """Trả về tập hợp toàn bộ tên các ga bị chặn (bao gồm cả ga lẻ và toàn bộ ga thuộc các tuyến bị đóng)."""
        effective = set(self.blocked_station_names)
        for line_name in self.blocked_line_names:
            line_info = UBAHN_LINES.get(line_name)
            if line_info and "stations" in line_info:
                effective.update(line_info["stations"])
        return effective

    def initialize(self):
        """Khởi tạo toàn bộ dữ liệu ứng dụng và cập nhật View ban đầu."""
        G_access, G_rail, station_records = self.map_service.initialize_data()

        self.station_points = get_station_display_points(station_records)
        self.all_station_names = get_unique_station_names(station_records)

        # 1. Đặt tâm bản đồ
        if self.view:
            self.view.set_map_center(self.map_service.center_lat, self.map_service.center_lon, zoom=14)

            # 2. Vẽ ranh giới các vùng lân cận
            print("Loading Munich and neighbor boundaries...")
            gdf_boundaries = self.map_service.load_neighbor_boundaries()
            boundary_paths = []
            if not gdf_boundaries.empty:
                for _, row in gdf_boundaries.iterrows():
                    paths = geometry_to_boundary_paths(row.get("geometry"))
                    boundary_paths.extend(paths)
            self.view.draw_boundaries(boundary_paths)

            # 3. Vẽ tất cả các tuyến U-Bahn
            print("Rendering U-Bahn lines...")
            ubahn_lines_to_draw = []
            for line_name, line_data in UBAHN_LINES.items():
                coords = line_coords(line_data["stations"], self.station_points, samples_per_segment=14)
                if len(coords) >= 2:
                    ubahn_lines_to_draw.append({"name": line_name, "coords": coords, "color": line_data["color"]})
            self.view.draw_ubahn_lines(ubahn_lines_to_draw)

            # 4. Hiển thị tất cả các ga
            print("Rendering subway stations...")
            effective_blocked = self.get_effective_blocked_stations()
            self.view.draw_stations(self.station_points, effective_blocked)

            # 5. Cập nhật nhãn ga bị chặn & quyền người dùng
            self.view.update_blocked_status(
                self.blocked_line_names,
                self.blocked_station_names,
                total_effective_count=len(effective_blocked),
            )
            self.view.update_admin_status(self.is_admin)

    # --- XÁC THỰC QUYỀN ADMIN ---
    def verify_admin_login(self, username, password) -> bool:
        """Kiểm tra tài khoản và mật khẩu admin."""
        valid_user = self.admin_credentials.get("username")
        valid_pass = self.admin_credentials.get("password")

        if username == valid_user and password == valid_pass:
            self.is_admin = True
            if self.view:
                self.view.update_admin_status(self.is_admin)
            print(f"[AUTH] Dang nhap thanh cong voi quyen Admin ({username})")
            return True

        print(f"[AUTH] Dang nhap that bai cho tai khoan: {username}")
        return False

    def logout_admin(self):
        """Đăng xuất quyền Admin."""
        self.is_admin = False
        if self.view:
            self.view.update_admin_status(self.is_admin)

    # --- QUẢN LÝ ĐÓNG / MỞ GA VÀ TUYẾN (YÊU CẦU QUYỀN ADMIN) ---
    def request_blocked_stations_dialog(self):
        """Mở hộp thoại chặn ga/tuyến. Nếu chưa là Admin -> bắt buộc đăng nhập."""
        if not self.is_admin:
            if self.view:
                self.view.open_admin_login_dialog(
                    on_login_success=lambda: self._open_blocked_dialog_internal()
                )
        else:
            self._open_blocked_dialog_internal()

    def _open_blocked_dialog_internal(self):
        if self.view:
            self.view.open_blocked_stations_dialog(
                all_station_names=self.all_station_names,
                current_blocked_lines=self.blocked_line_names,
                current_blocked_stations=self.blocked_station_names,
                on_apply=self.apply_blocked,
            )

    def request_toggle_blocked_station(self, station_name: str):
        """Click trực tiếp vào ga trên bản đồ để đóng/mở. Yêu cầu quyền Admin."""
        if not self.is_admin:
            if self.view:
                self.view.open_admin_login_dialog(
                    on_login_success=lambda: self._toggle_blocked_station_internal(station_name)
                )
        else:
            self._toggle_blocked_station_internal(station_name)

    def _toggle_blocked_station_internal(self, station_name: str):
        if station_name in self.blocked_station_names:
            self.blocked_station_names.remove(station_name)
        else:
            self.blocked_station_names.add(station_name)

        effective = self.get_effective_blocked_stations()
        if self.view:
            self.view.clear_route_display()
            self.view.update_blocked_status(
                self.blocked_line_names,
                self.blocked_station_names,
                total_effective_count=len(effective),
            )
            self.view.draw_stations(self.station_points, effective)

    def apply_blocked(self, selected_lines: set, selected_stations: set = None):
        """Áp dụng danh sách các tuyến và ga bị chặn từ hộp thoại BlockedStationsDialog."""
        if selected_stations is None:
            self.blocked_station_names = set(selected_lines)
        else:
            self.blocked_line_names = set(selected_lines)
            self.blocked_station_names = set(selected_stations)

        effective = self.get_effective_blocked_stations()
        if self.view:
            self.view.clear_route_display()
            self.view.update_blocked_status(
                self.blocked_line_names,
                self.blocked_station_names,
                total_effective_count=len(effective),
            )
            self.view.draw_stations(self.station_points, effective)

    def apply_blocked_stations(self, selected_names: set):
        """Tương thích ngược."""
        self.apply_blocked(set(), selected_names)

    # --- CHỌN ĐIỂM ĐI / ĐIỂM ĐẾN ---
    def set_start(self, coords: Tuple[float, float]):
        """Người dùng chọn điểm bắt đầu trên bản đồ."""
        self.start_coords = (coords[0], coords[1])
        self.start_node = self.map_service.find_nearest_node(coords[0], coords[1], "access")
        if self.view:
            self.view.set_start_marker(coords[0], coords[1])

    def set_end(self, coords: Tuple[float, float]):
        """Người dùng chọn điểm kết thúc trên bản đồ."""
        self.end_coords = (coords[0], coords[1])
        self.end_node = self.map_service.find_nearest_node(coords[0], coords[1], "access")
        if self.view:
            self.view.set_end_marker(coords[0], coords[1])

    # --- TÌM ĐƯỜNG ---
    def find_route(self, algo_name: str = "A*"):
        """Thực thi thuật toán tìm đường kết hợp Đi bộ - Tàu điện ngầm - Đi bộ."""
        if self.start_node is None or self.end_node is None:
            if self.view:
                self.view.show_message("Vui lòng chọn cả điểm bắt đầu và điểm kết thúc!")
            return

        if not self.map_service.station_records:
            if self.view:
                self.view.show_message("Không có dữ liệu ga U-Bahn trong khu vực bản đồ hiện tại.")
            return

        start_time = time.time()
        try:
            result = find_route_multimodal_via_rail(
                self.map_service.G_access,
                self.map_service.G_rail,
                self.start_node,
                self.end_node,
                self.map_service.station_records,
                algo_name,
                walking_weight=config.WALKING_WEIGHT,
                max_access_walk_m=config.MAX_ACCESS_WALK_M,
                blocked_station_names=self.get_effective_blocked_stations(),
            )

            if not result:
                raise ValueError(
                    f"Không tìm thấy lộ trình phù hợp tránh các ga bị chặn (giới hạn đi bộ {config.MAX_ACCESS_WALK_M:.0f}m mỗi chặng)."
                )

            elapsed_ms = (time.time() - start_time) * 1000

            # Tính toán tọa độ hiển thị cho 3 chặng
            board = result["boarding_station"]
            alight = result["alighting_station"]
            access_start_path = result["access_start_path"]
            rail_path = result["rail_path"]
            access_end_path = result["access_end_path"]

            start_coords = path_to_map_coords(self.map_service.G_access, access_start_path)
            rail_coords = selected_ubahn_route_coords(
                rail_path, board, alight, self.map_service.station_records, self.map_service.G_rail
            )
            end_coords = path_to_map_coords(self.map_service.G_access, access_end_path)

            rail_start = rail_coords[0] if rail_coords else (board["lat"], board["lon"])
            rail_end = rail_coords[-1] if rail_coords else (alight["lat"], alight["lon"])

            start_coords = add_visible_endpoints(start_coords, self.start_coords, rail_start)
            end_coords = add_visible_endpoints(end_coords, rail_end, self.end_coords)

            route_stations = get_rail_path_station_names(
                rail_path, board, alight, self.map_service.station_records
            )

            # Tính toán các lần chuyển tuyến
            transfer_count, transfers, line_sequence = find_subway_transfers(
                route_stations, self.station_points
            )

            stats = {
                "distance_km": result["distance_m"] / 1000,
                "walk_km": result["walk_distance_m"] / 1000,
                "rail_km": result["rail_distance_m"] / 1000,
                "cost_km": result["route_cost_m"] / 1000,
                "expanded_nodes": result["expanded_nodes"],
                "elapsed_ms": elapsed_ms,
                "boarding": board.get("name", "Station"),
                "alighting": alight.get("name", "Station"),
                "route_stations": route_stations,
                "transfer_count": transfer_count,
                "transfers": transfers,
                "line_sequence": line_sequence,
            }

            segments = [
                {"coords": start_coords, "color": "#1f77b4", "width": 5},   # Đi bộ đầu
                {"coords": rail_coords, "color": "#ff6f00", "width": 10},  # Tàu điện ngầm
                {"coords": end_coords, "color": "#1f77b4", "width": 5},     # Đi bộ cuối
            ]

            if self.view:
                self.view.display_route_result(stats, segments)

        except Exception as exc:
            print(f"Route finding error: {exc}")
            if self.view:
                self.view.clear_route_display()
                self.view.display_route_error(f"U-Bahn: {exc}")

    def clear_map(self):
        """Xóa toàn bộ điểm chọn và đường đi hiện tại."""
        self.start_node = None
        self.end_node = None
        self.start_coords = None
        self.end_coords = None
        if self.view:
            self.view.clear_selection_and_route()
            self.view.draw_stations(self.station_points, self.blocked_station_names)
