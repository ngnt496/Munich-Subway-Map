"""Giao diện chính ứng dụng Munich U-Bahn Navigation (View trong kiến trúc MVC)."""

import tkinter as tk
import customtkinter as ctk
from tkintermapview import TkinterMapView
from views.admin_login_dialog import AdminLoginDialog
from views.blocked_stations_dialog import BlockedStationsDialog
from models.ubahn_network import UBAHN_LINES

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class MunichNavigationApp(ctk.CTk):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller

        self.title("Munich U-Bahn Navigation - Shortest Subway Route")
        self.geometry("1200x820")

        # Map drawing objects
        self.start_marker = None
        self.end_marker = None
        self.boundary_lines = []
        self.ubahn_line_paths = []
        self.all_station_markers = []
        self.route_path_lines = []
        self.transfer_markers = []
        self.station_dot_icon = None
        self.blocked_station_dot_icon = None
        self.station_tooltip_items = []

        # --- XÂY DỰNG GIAO DIỆN ---
        self._build_layout()

    def set_controller(self, controller):
        """Gán Controller cho View."""
        self.controller = controller

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # 1. Khung bản đồ bên trái
        self.map_widget = TkinterMapView(self, corner_radius=0)
        self.map_widget.grid(row=0, column=0, sticky="nsew")

        # Chuột phải để chọn điểm đi và điểm đến
        self.map_widget.add_right_click_menu_command(
            label="Choose a starting point",
            command=lambda coords: self.controller.set_start(coords) if self.controller else None,
            pass_coords=True,
        )
        self.map_widget.add_right_click_menu_command(
            label="Choose an ending point",
            command=lambda coords: self.controller.set_end(coords) if self.controller else None,
            pass_coords=True,
        )

        # 2. Khung điều khiển Sidebar bên phải (dạng cuộn CTkScrollableFrame để xem đầy đủ mọi nội dung)
        self.sidebar = ctk.CTkScrollableFrame(self, width=310, corner_radius=0)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.label_title = ctk.CTkLabel(
            self.sidebar,
            text="Munich Subway Map",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.label_title.pack(pady=(10, 4))

        # Trạng thái đăng nhập Admin
        self.frame_auth = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_auth.pack(fill="x", padx=10, pady=(0, 8))

        self.lbl_admin_status = ctk.CTkLabel(
            self.frame_auth,
            text="Vai trò: Khách",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.lbl_admin_status.pack(side="left")

        self.btn_auth = ctk.CTkButton(
            self.frame_auth,
            text="Đăng nhập",
            command=self._on_auth_button_click,
            width=75,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#3b8ed0",
        )
        self.btn_auth.pack(side="right")

        # Lựa chọn thuật toán
        self.algo_label = ctk.CTkLabel(self.sidebar, text="Thuật toán tìm đường:")
        self.algo_label.pack(pady=(4, 2))
        self.algo_menu = ctk.CTkOptionMenu(self.sidebar, values=["A*", "Dijkstra"])
        self.algo_menu.pack(pady=(0, 8))

        # Các nút thao tác
        self.btn_search = ctk.CTkButton(
            self.sidebar,
            text="Tìm đường",
            command=lambda: self.controller.find_route(self.algo_menu.get()) if self.controller else None,
            fg_color="#3b8ed0",
        )
        self.btn_search.pack(pady=4)

        self.btn_clear = ctk.CTkButton(
            self.sidebar,
            text="Xóa lựa chọn",
            command=lambda: self.controller.clear_map() if self.controller else None,
            fg_color="#db4437",
        )
        self.btn_clear.pack(pady=4)

        self.btn_blocked = ctk.CTkButton(
            self.sidebar,
            text="Đóng tuyến / Ga [Admin]",
            command=lambda: self.controller.request_blocked_stations_dialog() if self.controller else None,
            fg_color="#5f6368",
        )
        self.btn_blocked.pack(pady=(6, 4))

        self.lbl_blocked = ctk.CTkLabel(
            self.sidebar,
            text="Blocked stations: None",
            anchor="w",
            justify="left",
            wraplength=270,
            font=ctk.CTkFont(size=12),
        )
        self.lbl_blocked.pack(fill="x", padx=10, pady=(0, 6))

        # Hộp hiển thị kết quả
        self.result_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.result_box.pack(pady=6, fill="x", padx=10)

        self.lbl_dist = ctk.CTkLabel(self.result_box, text="Distance: N/A", anchor="w")
        self.lbl_dist.pack(fill="x")
        self.lbl_walk = ctk.CTkLabel(self.result_box, text="Walk/Subway: N/A", anchor="w")
        self.lbl_walk.pack(fill="x")
        self.lbl_cost = ctk.CTkLabel(self.result_box, text="Weighted cost: N/A", anchor="w")
        self.lbl_cost.pack(fill="x")
        self.lbl_nodes = ctk.CTkLabel(self.result_box, text="Nodes visited: N/A", anchor="w")
        self.lbl_nodes.pack(fill="x")
        self.lbl_time = ctk.CTkLabel(self.result_box, text="Time: N/A", anchor="w")
        self.lbl_time.pack(fill="x")
        self.lbl_station = ctk.CTkLabel(self.result_box, text="U-Bahn stations: N/A", anchor="w")
        self.lbl_station.pack(fill="x")
        self.lbl_transfers = ctk.CTkLabel(self.result_box, text="Subway transfers: N/A", anchor="w")
        self.lbl_transfers.pack(fill="x")

        self.lbl_transfer_detail = ctk.CTkLabel(
            self.result_box,
            text="",
            anchor="w",
            justify="left",
            wraplength=270,
            text_color="#ce93d8",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.lbl_transfer_detail.pack(fill="x", pady=(4, 0))

        # Khung chú thích các tuyến U-Bahn theo màu sắc
        self.legend_frame = ctk.CTkFrame(self.sidebar, corner_radius=6)
        self.legend_frame.pack(fill="x", padx=8, pady=(10, 16))

        self.lbl_legend_title = ctk.CTkLabel(
            self.legend_frame,
            text="Chú thích các tuyến U-Bahn:",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_legend_title.pack(fill="x", padx=10, pady=(8, 4))

        # Danh sách các tuyến U1 - U8 hiển thị rõ ràng từng dòng
        self.lines_frame = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
        self.lines_frame.pack(fill="x", padx=8, pady=(0, 6))

        for line_name, line_info in UBAHN_LINES.items():
            item_frame = ctk.CTkFrame(self.lines_frame, fg_color="transparent")
            item_frame.pack(fill="x", padx=2, pady=2)

            badge = ctk.CTkLabel(
                item_frame,
                text=f" {line_name} ",
                fg_color=line_info["color"],
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=11, weight="bold"),
                width=36,
                height=20,
            )
            badge.pack(side="left", padx=(0, 6))

            first_st = line_info["stations"][0]
            last_st = line_info["stations"][-1]
            desc = ctk.CTkLabel(
                item_frame,
                text=f"{first_st} ↔ {last_st}",
                font=ctk.CTkFont(size=11),
                text_color="#e0e0e0",
                anchor="w",
            )
            desc.pack(side="left", fill="x", expand=True)

        # Chú thích thành phần lộ trình đường vẽ
        self.route_legend_frame = ctk.CTkFrame(self.legend_frame, fg_color="#D0F350", corner_radius=4)
        self.route_legend_frame.pack(fill="x", padx=8, pady=(4, 8))

        lbl_r1 = ctk.CTkLabel(
            self.route_legend_frame,
            text="🚶 Đi bộ: Xanh dương  |  🚇 Tàu: Nét cam",
            font=ctk.CTkFont(size=11),
        )
        lbl_r1.pack(pady=(4, 2), padx=6)

        lbl_r2 = ctk.CTkLabel(
            self.route_legend_frame,
            text="🔄 Điểm đổi tuyến: Marker màu tím",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ce93d8",
        )
        lbl_r2.pack(pady=(0, 4), padx=6)

    # --- SỰ KIỆN TƯƠNG TÁC GIAO DIỆN ---
    def _on_auth_button_click(self):
        if self.controller and self.controller.is_admin:
            self.controller.logout_admin()
        else:
            self.open_admin_login_dialog()

    def open_admin_login_dialog(self, on_login_success=None):
        """Mở cửa sổ đăng nhập admin."""
        AdminLoginDialog(
            parent=self,
            on_login_success=on_login_success,
            verify_callback=self.controller.verify_admin_login if self.controller else lambda u, p: False,
        )

    def open_blocked_stations_dialog(
        self,
        all_station_names,
        current_blocked_lines=None,
        current_blocked_stations=None,
        on_apply=None,
        current_blocked_names=None,
    ):
        """Mở cửa sổ chọn đóng/mở ga và tuyến."""
        BlockedStationsDialog(
            parent=self,
            all_station_names=all_station_names,
            current_blocked_lines=current_blocked_lines,
            current_blocked_stations=current_blocked_stations,
            on_apply=on_apply,
            current_blocked_names=current_blocked_names,
        )

    def update_admin_status(self, is_admin: bool):
        """Cập nhật nhãn trạng thái và nút Đăng nhập / Đăng xuất."""
        if is_admin:
            self.lbl_admin_status.configure(text="Vai trò: Admin", text_color="#2e7d32")
            self.btn_auth.configure(text="Đăng xuất", fg_color="#db4437")
        else:
            self.lbl_admin_status.configure(text="Vai trò: Khách", text_color="#888888")
            self.btn_auth.configure(text="Đăng nhập", fg_color="#3b8ed0")

    def update_blocked_status(self, blocked_lines: set, blocked_stations: set, total_effective_count: int = 0):
        """Hiển thị trạng thái các tuyến và ga đang bị đóng."""
        parts = []
        if blocked_lines:
            parts.append(f"Tuyến: {', '.join(sorted(blocked_lines))}")
        if blocked_stations:
            st_list = sorted(blocked_stations)
            if len(st_list) <= 2:
                parts.append(f"Ga lẻ: {', '.join(st_list)}")
            else:
                parts.append(f"Ga lẻ: {', '.join(st_list[:2])} (+{len(st_list) - 2})")

        if not parts:
            self.lbl_blocked.configure(
                text="Đang đóng: Không có",
                text_color="#888888",
            )
        else:
            text = "Đang đóng: " + " | ".join(parts)
            if total_effective_count > 0:
                text += f"\n(Tổng ảnh hưởng: {total_effective_count} ga)"
            self.lbl_blocked.configure(
                text=text,
                text_color="#e57373",
            )

    def update_blocked_station_label(self, blocked_names: set):
        """Phương thức tương thích ngược."""
        if not blocked_names:
            self.lbl_blocked.configure(text="Đang đóng: Không có", text_color="#888888")
            return

        names = sorted(blocked_names)
        shown_names = ", ".join(names[:3])
        if len(names) > 3:
            shown_names += f", +{len(names) - 3} more"
        self.lbl_blocked.configure(text=f"Đang đóng ({len(names)} ga): {shown_names}", text_color="#e57373")

    def show_message(self, message: str):
        print(f"[THÔNG BÁO] {message}")

    # --- BẢN ĐỒ: ĐẶT VỊ TRÍ & VẼ CÁC LỚP ---
    def set_map_center(self, lat: float, lon: float, zoom: int = 14):
        self.map_widget.set_position(lat, lon)
        self.map_widget.set_zoom(zoom)

    def set_start_marker(self, lat: float, lon: float):
        if self.start_marker:
            self.start_marker.delete()
        self.start_marker = self.map_widget.set_marker(lat, lon, text="Start", marker_color_circle="green")

    def set_end_marker(self, lat: float, lon: float):
        if self.end_marker:
            self.end_marker.delete()
        self.end_marker = self.map_widget.set_marker(lat, lon, text="End", marker_color_circle="red")

    def draw_boundaries(self, boundary_paths):
        for line in self.boundary_lines:
            line.delete()
        self.boundary_lines = []

        for coords in boundary_paths:
            line = self.map_widget.set_path(coords, color="#2e7d32", width=2)
            self.boundary_lines.append(line)

    def draw_ubahn_lines(self, lines_data):
        for path in self.ubahn_line_paths:
            path.delete()
        self.ubahn_line_paths = []

        for item in lines_data:
            path = self.map_widget.set_path(item["coords"], color=item["color"], width=4)
            self.ubahn_line_paths.append(path)

    def draw_stations(self, station_points, blocked_names):
        self._clear_station_tooltip()
        for marker in self.all_station_markers:
            marker.delete()
        self.all_station_markers = []

        for name, coords in sorted(station_points.items()):
            is_blocked = name in blocked_names
            tooltip_name = (
                f"{name} (đang đóng - click để mở)"
                if is_blocked
                else f"{name} (click để đóng)"
            )
            marker = self.map_widget.set_marker(
                coords[0],
                coords[1],
                icon=self._blocked_station_dot_image() if is_blocked else self._station_dot_image(),
                icon_anchor="center",
                command=lambda _m, st=name: self.controller.request_toggle_blocked_station(st) if self.controller else None,
            )
            self._bind_station_tooltip(marker, tooltip_name)
            self.all_station_markers.append(marker)

    # --- KẾT QUẢ ĐƯỜNG ĐI ---
    def display_route_result(self, stats: dict, segments: list):
        self.clear_route_display()

        # Cập nhật thông số
        self.lbl_dist.configure(text=f"Distance: {stats['distance_km']:.2f} km")
        walk_note = " (walk-heavy)" if stats['walk_km'] > stats['rail_km'] else ""
        self.lbl_walk.configure(text=f"Walk/Subway: {stats['walk_km']:.2f} / {stats['rail_km']:.2f} km{walk_note}")
        self.lbl_cost.configure(text=f"Weighted cost: {stats['cost_km']:.2f} km-eq")
        self.lbl_nodes.configure(text=f"Nodes visited: {stats['expanded_nodes']}")
        self.lbl_time.configure(text=f"Time: {stats['elapsed_ms']:.2f} ms")
        self.lbl_station.configure(text=f"U-Bahn: {stats['boarding']} -> {stats['alighting']}")

        transfer_count = stats.get("transfer_count", 0)
        self.lbl_transfers.configure(text=f"Subway transfers: {transfer_count} (lần đổi tàu)")

        # Hiển thị chi tiết các ga chuyển tuyến nếu có
        transfers = stats.get("transfers", [])
        if transfers:
            trans_texts = [f"• Ga {t['station']}: {t['from_line']} ➔ {t['to_line']}" for t in transfers]
            self.lbl_transfer_detail.configure(text="Điểm đổi tuyến:\n" + "\n".join(trans_texts))
        else:
            self.lbl_transfer_detail.configure(text="")

        # Vẽ các đoạn polyline lộ trình
        for seg in segments:
            line = self.map_widget.set_path(seg["coords"], color=seg["color"], width=seg["width"])
            if line:
                self.route_path_lines.append(line)

        # Đánh dấu các ga chuyển tuyến trên bản đồ
        for t in transfers:
            coords = t.get("coords")
            if coords:
                marker = self.map_widget.set_marker(
                    coords[0],
                    coords[1],
                    text=f"🔄 Transfer: {t['from_line']} ➔ {t['to_line']}",
                    marker_color_circle="#9c27b0",
                    marker_color_outside="#4a148c",
                )
                self.transfer_markers.append(marker)

    def display_route_error(self, message: str):
        self.lbl_dist.configure(text="Distance: N/A")
        self.lbl_walk.configure(text="Walk/Subway: N/A")
        self.lbl_cost.configure(text="Weighted cost: N/A")
        self.lbl_nodes.configure(text="Nodes visited: N/A")
        self.lbl_time.configure(text="Time: N/A")
        self.lbl_station.configure(text=message)
        self.lbl_transfers.configure(text="Subway transfers: N/A")
        self.lbl_transfer_detail.configure(text="")

    def clear_route_display(self):
        for line in self.route_path_lines:
            line.delete()
        self.route_path_lines = []

        for marker in self.transfer_markers:
            marker.delete()
        self.transfer_markers = []

    def clear_selection_and_route(self):
        if self.start_marker:
            self.start_marker.delete()
            self.start_marker = None
        if self.end_marker:
            self.end_marker.delete()
            self.end_marker = None

        self.clear_route_display()
        self.display_route_error("U-Bahn stations: N/A")

    # --- ICONS & TOOLTIPS ---
    def _station_dot_image(self):
        if self.station_dot_icon is not None:
            return self.station_dot_icon

        size = 13
        radius = 5.5
        center = (size - 1) / 2
        image = tk.PhotoImage(width=size, height=size)
        for x in range(size):
            for y in range(size):
                dist = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                if dist <= radius - 1:
                    image.put("#FFFFFF", (x, y))
                elif dist <= radius:
                    image.put("#222222", (x, y))
                else:
                    try:
                        image.transparency_set(x, y, True)
                    except tk.TclError:
                        image.put("#FFFFFF", (x, y))

        self.station_dot_icon = image
        return image

    def _blocked_station_dot_image(self):
        if self.blocked_station_dot_icon is not None:
            return self.blocked_station_dot_icon

        size = 15
        radius = 6.5
        center = (size - 1) / 2
        image = tk.PhotoImage(width=size, height=size)
        for x in range(size):
            for y in range(size):
                dist = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                if dist <= radius - 2:
                    image.put("#FFFFFF", (x, y))
                elif dist <= radius:
                    image.put("#D93025", (x, y))
                else:
                    try:
                        image.transparency_set(x, y, True)
                    except tk.TclError:
                        image.put("#FFFFFF", (x, y))

        self.blocked_station_dot_icon = image
        return image

    def _clear_station_tooltip(self):
        for item in self.station_tooltip_items:
            self.map_widget.canvas.delete(item)
        self.station_tooltip_items = []

    def _show_station_tooltip(self, marker, station_name):
        self._clear_station_tooltip()
        x, y = marker.get_canvas_pos(marker.position)
        text = self.map_widget.canvas.create_text(
            x,
            y - 16,
            text=station_name,
            anchor=tk.S,
            fill="#111111",
            font=("Arial", 10, "bold"),
            tag="station_tooltip",
        )
        bbox = self.map_widget.canvas.bbox(text)
        if bbox is not None:
            pad = 4
            rect = self.map_widget.canvas.create_rectangle(
                bbox[0] - pad,
                bbox[1] - pad,
                bbox[2] + pad,
                bbox[3] + pad,
                fill="#FFFFFF",
                outline="#444444",
                tag="station_tooltip",
            )
            self.map_widget.canvas.tag_lower(rect, text)
            self.station_tooltip_items = [rect, text]
        else:
            self.station_tooltip_items = [text]

    def _bind_station_tooltip(self, marker, station_name):
        def enter(event=None, m=marker, name=station_name):
            self._show_station_tooltip(m, name)

        def leave(event=None):
            self._clear_station_tooltip()

        marker.mouse_enter = enter
        marker.mouse_leave = leave
        if marker.canvas_icon is not None:
            self.map_widget.canvas.tag_bind(marker.canvas_icon, "<Enter>", enter)
            self.map_widget.canvas.tag_bind(marker.canvas_icon, "<Leave>", leave)
