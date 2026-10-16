"""Hộp thoại quản lý ga và tuyến tàu điện ngầm bị đóng (dành cho Admin)."""

import tkinter as tk
import customtkinter as ctk
from models.ubahn_network import UBAHN_LINES


class BlockedStationsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        all_station_names,
        current_blocked_lines=None,
        current_blocked_stations=None,
        on_apply=None,
        current_blocked_names=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.all_station_names = sorted(all_station_names)

        # Phân biệt rõ ràng giữa tuyến bị đóng và ga lẻ bị đóng
        self.current_blocked_lines = set(current_blocked_lines or [])
        if current_blocked_stations is not None:
            self.current_blocked_stations = set(current_blocked_stations)
        elif current_blocked_names is not None:
            self.current_blocked_stations = set(current_blocked_names)
        else:
            self.current_blocked_stations = set()

        self.on_apply = on_apply

        self.title("Quản lý Tuyến & Ga U-Bahn bị đóng [Admin]")
        self.geometry("520x720")
        self.minsize(460, 600)
        self.transient(parent)
        self.grab_set()

        # Tiêu đề
        self.lbl_title = ctk.CTkLabel(
            self,
            text="Quản lý Tuyến / Ga U-Bahn bị đóng",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.lbl_title.pack(padx=16, pady=(16, 4), anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self,
            text="Tuyến hoặc ga được chọn sẽ tạm ngừng phục vụ. Thuật toán tìm đường sẽ tự động đổi hướng tránh các khu vực này.",
            wraplength=480,
            justify="left",
            font=ctk.CTkFont(size=12),
            text_color="#b0bec5",
        )
        self.lbl_subtitle.pack(padx=16, pady=(0, 10), anchor="w")

        # Tabview để chọn theo Tuyến hoặc chọn theo từng Ga lẻ
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self.tab_lines = self.tabview.add("Đóng theo Tuyến (U1 - U8)")
        self.tab_stations = self.tabview.add("Đóng từng Ga lẻ")

        # --- TAB 1: ĐÓNG THEO TUYẾN ---
        self._init_lines_tab()

        # --- TAB 2: ĐÓNG TỪNG GA LẺ ---
        self._init_stations_tab()

        # Cập nhật gợi ý trạng thái ban đầu cho tab ga lẻ
        self._update_station_hints()

        # --- THANH NÚT HÀNH ĐỘNG CUỐI CÙNG ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=16, pady=(0, 16))

        btn_apply = ctk.CTkButton(
            button_frame,
            text="Áp dụng thay đổi",
            command=self._apply_selection,
            fg_color="#1976d2",
            hover_color="#1565c0",
            font=ctk.CTkFont(weight="bold"),
            width=130,
            height=32,
        )
        btn_apply.pack(side="right", padx=(8, 0))

        btn_clear_all = ctk.CTkButton(
            button_frame,
            text="Mở toàn bộ hệ thống",
            command=self._clear_all_selection,
            fg_color="#546e7a",
            hover_color="#455a64",
            width=140,
            height=32,
        )
        btn_clear_all.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._apply_selection)

    def _init_lines_tab(self):
        quick_frame = ctk.CTkFrame(self.tab_lines, fg_color="transparent")
        quick_frame.pack(fill="x", padx=8, pady=(4, 6))

        btn_clear_lines = ctk.CTkButton(
            quick_frame,
            text="Mở tất cả tuyến",
            command=self._clear_all_lines,
            width=120,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#424242",
        )
        btn_clear_lines.pack(side="right", padx=(4, 0))

        lbl_line_desc = ctk.CTkLabel(
            quick_frame,
            text="Chọn tuyến để tạm dừng toàn bộ hoạt động:",
            font=ctk.CTkFont(size=12),
            text_color="#cfd8dc",
        )
        lbl_line_desc.pack(side="left")

        self.line_scroll = ctk.CTkScrollableFrame(self.tab_lines)
        self.line_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self.line_vars = {}
        for line_name, line_info in UBAHN_LINES.items():
            card = ctk.CTkFrame(self.line_scroll, fg_color="#2b2b2b", corner_radius=6)
            card.pack(fill="x", padx=4, pady=4)

            # Badge màu tên tuyến
            badge = ctk.CTkLabel(
                card,
                text=f" {line_name} ",
                fg_color=line_info["color"],
                text_color="white",
                corner_radius=4,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=42,
                height=24,
            )
            badge.pack(side="left", padx=(10, 8), pady=8)

            # Thông tin tuyến
            first_st = line_info["stations"][0]
            last_st = line_info["stations"][-1]
            st_count = len(line_info["stations"])
            lbl_desc = ctk.CTkLabel(
                card,
                text=f"{first_st} ↔ {last_st}\n({st_count} ga)",
                font=ctk.CTkFont(size=11),
                text_color="#e0e0e0",
                justify="left",
                anchor="w",
            )
            lbl_desc.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)

            # Checkbox trạng thái đóng
            is_blocked = line_name in self.current_blocked_lines
            var = tk.BooleanVar(value=is_blocked)
            self.line_vars[line_name] = var

            chk = ctk.CTkCheckBox(
                card,
                text="Đóng tuyến",
                variable=var,
                fg_color="#e53935",
                hover_color="#c62828",
                text_color="#ff8a80" if is_blocked else "#ffffff",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self._on_line_checked_changed,
            )
            chk.pack(side="right", padx=12, pady=8)

    def _init_stations_tab(self):
        search_bar = ctk.CTkFrame(self.tab_stations, fg_color="transparent")
        search_bar.pack(fill="x", padx=6, pady=(6, 6))

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="Tìm kiếm tên ga cần đóng...",
            height=30,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.search_entry.bind("<KeyRelease>", lambda event: self._filter_stations())

        btn_clear_stations = ctk.CTkButton(
            search_bar,
            text="Mở tất cả ga lẻ",
            command=self._clear_all_stations,
            width=110,
            height=30,
            font=ctk.CTkFont(size=11),
            fg_color="#424242",
        )
        btn_clear_stations.pack(side="right")

        self.station_scroll = ctk.CTkScrollableFrame(self.tab_stations)
        self.station_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self.station_vars = {}
        self.station_frames = {}
        self.station_hint_labels = {}

        for station_name in self.all_station_names:
            row_frame = ctk.CTkFrame(self.station_scroll, fg_color="transparent")
            row_frame.pack(fill="x", padx=6, pady=2, anchor="w")

            is_blocked = station_name in self.current_blocked_stations
            var = tk.BooleanVar(value=is_blocked)
            self.station_vars[station_name] = var

            chk = ctk.CTkCheckBox(
                row_frame,
                text=station_name,
                variable=var,
                font=ctk.CTkFont(size=12),
            )
            chk.pack(side="left", padx=4, pady=2)

            # Chú thích nếu ga này thuộc tuyến đang bị đóng ở Tab 1
            lbl_hint = ctk.CTkLabel(
                row_frame,
                text="",
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color="#ff8a80",
            )
            lbl_hint.pack(side="left", padx=(8, 0))

            self.station_frames[station_name] = row_frame
            self.station_hint_labels[station_name] = lbl_hint

    def _on_line_checked_changed(self):
        """Khi thay đổi chọn đóng/mở tuyến ở Tab 1, cập nhật chú thích ở Tab 2."""
        self._update_station_hints()

    def _update_station_hints(self):
        """Hiển thị gợi ý các ga đang nằm trong tuyến bị đóng để người dùng nhận diện ngay."""
        active_blocked_lines = {ln for ln, var in self.line_vars.items() if var.get()}
        for st_name, hint_label in self.station_hint_labels.items():
            lines_covering = [
                ln for ln, info in UBAHN_LINES.items()
                if st_name in info["stations"] and ln in active_blocked_lines
            ]
            if lines_covering:
                hint_label.configure(text=f"(Tuyến {', '.join(lines_covering)} đang đóng)")
            else:
                hint_label.configure(text="")

    def _filter_stations(self):
        query = self.search_entry.get().strip().lower()
        for name, frame in self.station_frames.items():
            if not query or query in name.lower():
                frame.pack(fill="x", padx=6, pady=2, anchor="w")
            else:
                frame.pack_forget()

    def _clear_all_lines(self):
        for var in self.line_vars.values():
            var.set(False)
        self._update_station_hints()

    def _clear_all_stations(self):
        for var in self.station_vars.values():
            var.set(False)

    def _clear_all_selection(self):
        self._clear_all_lines()
        self._clear_all_stations()

    def _apply_selection(self):
        selected_lines = {
            line for line, var in self.line_vars.items() if var.get()
        }
        selected_stations = {
            name for name, var in self.station_vars.items() if var.get()
        }
        self.destroy()
        if self.on_apply:
            self.on_apply(selected_lines, selected_stations)
