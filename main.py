import customtkinter as ctk
from tkintermapview import TkinterMapView
import osmnx as ox
import geopandas as gpd
import pandas as pd
from pathlib import Path
import time
import pickle
import tkinter as tk
from algorithms import find_route_multimodal_via_rail
from station_store import (
    add_station_transfer_edges,
    fetch_station_records_for_place,
    load_station_records,
    remove_non_passenger_subway_edges,
    save_station_records,
)

# Cấu hình giao diện
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class MunichNavigationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Munich U-Bahn Navigation - Shortest Subway Route")
        self.geometry("1200x800")
        self.place_name = "Munich, Bavaria, Germany"
        self.center_lat = 48.1371
        self.center_lon = 11.5754
        self.cache_dir = Path(__file__).resolve().parent / "cache"
        self.access_graph_cache_file = self.cache_dir / "munich_walk.graphml"
        self.access_graph_pickle_file = self.cache_dir / "munich_walk.pkl"
        self.legacy_drive_graph_cache_file = self.cache_dir / "munich_drive.graphml"
        self.rail_graph_cache_file = self.cache_dir / "munich_rail_unsimplified.graphml"
        self.rail_graph_pickle_file = self.cache_dir / "munich_rail_unsimplified.pkl"
        self.station_cache_file = self.cache_dir / "munich_station_nodes_citywide.json"
        self.boundary_cache_file = self.cache_dir / "munich_neighbor_boundaries.geojson"
        self.walking_weight = 2.5
        self.max_access_walk_m = 2500.0
        self.boundary_places = [
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

        # Khởi tạo dữ liệu
        self.start_node = None
        self.end_node = None
        self.start_coords = None
        self.end_coords = None
        self.start_marker = None
        self.end_marker = None
        self.path_line = None
        self.station_path_lines = []
        self.station_markers = []  # Markers for boarding/alighting stations in route
        self.all_station_markers = []  # Markers for all available stations
        self.all_line_paths = []
        self.station_dot_icon = None
        self.blocked_station_dot_icon = None
        self.station_tooltip_items = []
        self.station_records = []
        self.blocked_station_names = set()
        self.route_station_names = []
        self.boundary_lines = []
        
        print("Đang tải dữ liệu bản đồ đi bộ Munich...")
        self.G_access = self._load_access_graph()
        self.G_rail = self._load_rail_graph()
        removed_edges = remove_non_passenger_subway_edges(self.G_rail)
        print(f"Removed {removed_edges} non-passenger subway service edges.")
        self._set_map_center_from_graph(self.G_access)
        print("Tải dữ liệu thành công!")

        print("Đang tải dữ liệu ga U-Bahn Munich...")
        self.station_records = load_station_records(self.station_cache_file)
        if not self.station_records:
            self.station_records = fetch_station_records_for_place(self.G_access, self.G_rail, self.place_name)
            save_station_records(self.station_records, self.station_cache_file)
        print(f"Đã nạp {len(self.station_records)} ga U-Bahn khả dụng cho tìm đường.")

        transfer_edges = add_station_transfer_edges(self.G_rail, self.station_records)
        print(f"Added {transfer_edges} internal U-Bahn station transfer edges.")
        self._choose_blocked_stations_dialog()

        # --- LAYOUT ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # 1. Khung bên trái: Bản đồ
        self.map_widget = TkinterMapView(self, corner_radius=0)
        self.map_widget.grid(row=0, column=0, sticky="nsew")
        self.map_widget.set_position(self.center_lat, self.center_lon) # Tọa độ Munich
        self.map_widget.set_zoom(15)

        print("Đang tải ranh giới Munich và các thành phố lân cận...")
        self._draw_neighbor_boundaries()
        print("Dang hien thi cac tuyen U-Bahn...")
        self._draw_all_ubahn_lines()
        print("Da hien thi cac tuyen U-Bahn.")
        print("Đã hiển thị ranh giới hành chính.")

        print("Đang hiển thị tất cả các ga tàu...")
        self._draw_all_stations()
        print("Đã hiển thị các ga tàu.")

        # Chuột phải để chọn điểm
        self.map_widget.add_right_click_menu_command(label="Choose a starting point", command=self.set_start, pass_coords=True)
        self.map_widget.add_right_click_menu_command(label="Choose an ending point", command=self.set_end, pass_coords=True)

        # 2. Khung bên phải: Sidebar điều khiển
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.label_title = ctk.CTkLabel(self.sidebar, text="Find Route", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=20)

        self.algo_label = ctk.CTkLabel(self.sidebar, text="Algorithm:")
        self.algo_label.pack(pady=5)
        self.algo_menu = ctk.CTkOptionMenu(self.sidebar, values=["A*", "Dijkstra"])
        self.algo_menu.pack(pady=10)

        self.btn_search = ctk.CTkButton(self.sidebar, text="Find Route", command=self.find_route, fg_color="#3b8ed0")
        self.btn_search.pack(pady=10)

        self.btn_clear = ctk.CTkButton(self.sidebar, text="Clear Selection", command=self.clear_map, fg_color="#db4437")
        self.btn_clear.pack(pady=10)

        self.btn_blocked = ctk.CTkButton(
            self.sidebar,
            text="Blocked Stations",
            command=self._choose_blocked_stations_dialog,
            fg_color="#5f6368",
        )
        self.btn_blocked.pack(pady=(8, 4))

        self.lbl_blocked = ctk.CTkLabel(
            self.sidebar,
            text="Blocked stations: None",
            anchor="w",
            justify="left",
            wraplength=230,
        )
        self.lbl_blocked.pack(fill="x", padx=10, pady=(0, 10))
        self._update_blocked_station_label()

        # Hiển thị kết quả
        self.result_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.result_box.pack(pady=20, fill="x", padx=10)
        
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
        self.lbl_route_stations = ctk.CTkLabel(
            self.result_box,
            text="Stations passed:",
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        self.lbl_route_stations.pack(fill="x", pady=(10, 2))
        self.route_stations_box = ctk.CTkTextbox(
            self.result_box,
            height=145,
            wrap="word",
        )
        self.route_stations_box.pack(fill="x")
        self._set_route_station_list([])

    def _unique_station_names(self):
        return sorted({
            str(station.get("name") or "Station").strip()
            for station in self.station_records
            if str(station.get("name") or "").strip()
        })

    def _update_blocked_station_label(self):
        if not hasattr(self, "lbl_blocked"):
            return

        if not self.blocked_station_names:
            self.lbl_blocked.configure(text="Blocked stations: None")
            return

        names = sorted(self.blocked_station_names)
        shown_names = ", ".join(names[:4])
        if len(names) > 4:
            shown_names += f", +{len(names) - 4} more"
        self.lbl_blocked.configure(text=f"Blocked stations ({len(names)}): {shown_names}")

    def _set_route_station_list(self, station_names):
        self.route_station_names = list(station_names)
        if not hasattr(self, "route_stations_box"):
            return

        self.route_stations_box.configure(state="normal")
        self.route_stations_box.delete("1.0", "end")
        if self.route_station_names:
            station_text = "\n".join(
                f"{index}. {name}"
                for index, name in enumerate(self.route_station_names, start=1)
            )
            self.route_stations_box.insert("1.0", station_text)
        else:
            self.route_stations_box.insert("1.0", "N/A")
        self.route_stations_box.configure(state="disabled")

    def _clear_route_result(self):
        if self.path_line:
            self.path_line.delete()
            self.path_line = None

        for line in self.station_path_lines:
            line.delete()
        self.station_path_lines = []

        for marker in self.station_markers:
            marker.delete()
        self.station_markers = []

        if hasattr(self, "lbl_dist"):
            self.lbl_dist.configure(text="Distance: N/A")
            self.lbl_walk.configure(text="Walk/Subway: N/A")
            self.lbl_cost.configure(text="Weighted cost: N/A")
            self.lbl_nodes.configure(text="Nodes visited: N/A")
            self.lbl_time.configure(text="Time: N/A")
            self.lbl_station.configure(text="U-Bahn stations: N/A")
        self._set_route_station_list([])

    def _toggle_blocked_station(self, station_name):
        if station_name in self.blocked_station_names:
            self.blocked_station_names.remove(station_name)
        else:
            self.blocked_station_names.add(station_name)

        self._clear_route_result()
        self._update_blocked_station_label()
        self._draw_all_stations()

    def _choose_blocked_stations_dialog(self):
        station_names = self._unique_station_names()
        if not station_names:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Choose Blocked U-Bahn Stations")
        dialog.geometry("420x620")
        dialog.transient(self)
        dialog.grab_set()

        title = ctk.CTkLabel(
            dialog,
            text="Choose blocked stations",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title.pack(padx=16, pady=(16, 4), anchor="w")

        subtitle = ctk.CTkLabel(
            dialog,
            text="Routes will not start, end, transfer, or pass through checked stations.",
            wraplength=370,
            justify="left",
        )
        subtitle.pack(padx=16, pady=(0, 12), anchor="w")

        scroll_frame = ctk.CTkScrollableFrame(dialog, width=370, height=430)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        station_vars = {}
        for station_name in station_names:
            var = tk.BooleanVar(value=station_name in self.blocked_station_names)
            checkbox = ctk.CTkCheckBox(scroll_frame, text=station_name, variable=var)
            checkbox.pack(fill="x", padx=8, pady=3, anchor="w")
            station_vars[station_name] = var

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=16, pady=(0, 16))

        def apply_selection():
            selected_names = {
                name for name, var in station_vars.items() if var.get()
            }
            if selected_names != self.blocked_station_names:
                self.blocked_station_names = selected_names
                self._clear_route_result()
            self._update_blocked_station_label()
            if hasattr(self, "map_widget") and self.all_station_markers:
                self._draw_all_stations()
            dialog.destroy()

        def clear_selection():
            for var in station_vars.values():
                var.set(False)

        btn_apply = ctk.CTkButton(button_frame, text="Apply", command=apply_selection)
        btn_apply.pack(side="right", padx=(8, 0))
        btn_clear = ctk.CTkButton(
            button_frame,
            text="Clear All",
            command=clear_selection,
            fg_color="#5f6368",
        )
        btn_clear.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", apply_selection)
        dialog.wait_window()

    def _load_neighbor_boundaries(self):
        cache_path = Path(self.boundary_cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if cache_path.exists():
            try:
                return gpd.read_file(cache_path)
            except Exception:
                pass

        rows = []
        for place in self.boundary_places:
            try:
                gdf = ox.geocode_to_gdf(place)
                if gdf.empty:
                    continue
                row = gdf.iloc[[0]].copy()
                row["place_name"] = place
                rows.append(row)
            except Exception as exc:
                print(f"Không thể tải ranh giới cho {place}: {exc}")

        if not rows:
            return gpd.GeoDataFrame()

        merged = gpd.GeoDataFrame(
            pd.concat(rows, ignore_index=True),
            geometry="geometry",
            crs=rows[0].crs,
        )

        try:
            merged.to_file(cache_path, driver="GeoJSON")
        except Exception as exc:
            print(f"Không thể lưu cache ranh giới: {exc}")

        return merged

    def _geometry_to_boundary_paths(self, geometry):
        paths = []
        if geometry is None or geometry.is_empty:
            return paths

        if geometry.geom_type == "Polygon":
            exterior = list(geometry.exterior.coords)
            if exterior:
                paths.append([(lat, lon) for lon, lat in exterior])
            return paths

        if geometry.geom_type == "MultiPolygon":
            for polygon in geometry.geoms:
                exterior = list(polygon.exterior.coords)
                if exterior:
                    paths.append([(lat, lon) for lon, lat in exterior])
            return paths

        return paths

    def _ubahn_line_definitions(self):
        return {
            "U1": {
                "color": "#0B8F45",
                "stations": [
                    "Olympia-Einkaufszentrum", "Georg-Brauchle-Ring", "Westfriedhof", "Gern",
                    "Rotkreuzplatz", "Maillingerstraße", "Stiglmaierplatz", "Hauptbahnhof",
                    "Sendlinger Tor", "Fraunhoferstraße", "Kolumbusplatz", "Candidplatz",
                    "Wettersteinplatz", "Sankt-Quirin-Platz", "Mangfallplatz",
                ],
            },
            "U2": {
                "color": "#C8102E",
                "stations": [
                    "Feldmoching", "Hasenbergl", "Dülferstraße", "Harthof", "Am Hart",
                    "Frankfurter Ring", "Milbertshofen", "Scheidplatz", "Hohenzollernplatz",
                    "Josephsplatz", "Theresienstraße", "Königsplatz", "Hauptbahnhof",
                    "Sendlinger Tor", "Fraunhoferstraße", "Kolumbusplatz", "Silberhornstraße",
                    "Untersbergstraße", "Giesing", "Karl-Preis-Platz", "Innsbrucker Ring",
                    "Josephsburg", "Kreillerstraße", "Trudering", "Moosfeld",
                    "Messestadt West", "Messestadt Ost",
                ],
            },
            "U3": {
                "color": "#F58220",
                "stations": [
                    "Moosach", "Moosacher St.-Martins-Platz", "Olympia-Einkaufszentrum",
                    "Oberwiesenfeld", "Olympiazentrum", "Petuelring", "Scheidplatz",
                    "Bonner Platz", "Münchner Freiheit", "Giselastraße", "Universität",
                    "Odeonsplatz", "Marienplatz", "Sendlinger Tor", "Goetheplatz",
                    "Poccistraße", "Implerstraße", "Brudermühlstraße", "Thalkirchen (Tierpark)",
                    "Obersendling", "Aidenbachstraße", "Machtlfinger Straße",
                    "Forstenrieder Allee", "Basler Straße", "Fürstenried West",
                ],
            },
            "U4": {
                "color": "#00A3AD",
                "stations": [
                    "Westendstraße", "Heimeranplatz", "Schwanthalerhöhe", "Theresienwiese",
                    "Hauptbahnhof", "Karlsplatz (Stachus)", "Odeonsplatz", "Lehel",
                    "Max-Weber-Platz", "Prinzregentenplatz", "Böhmerwaldplatz",
                    "Richard-Strauss-Straße", "Arabellapark",
                ],
            },
            "U5": {
                "color": "#A66A00",
                "stations": [
                    "Laimer Platz", "Friedenheimer Straße", "Westendstraße", "Heimeranplatz",
                    "Schwanthalerhöhe", "Theresienwiese", "Hauptbahnhof",
                    "Karlsplatz (Stachus)", "Odeonsplatz", "Lehel", "Max-Weber-Platz",
                    "Ostbahnhof", "Innsbrucker Ring", "Michaelibad", "Quiddestraße",
                    "Neuperlach Zentrum", "Therese-Giehse-Allee", "Neuperlach Süd",
                ],
            },
            "U6": {
                "color": "#0065BD",
                "stations": [
                    "Klinikum Großhadern", "Großhadern", "Haderner Stern", "Holzapfelkreuth",
                    "Westpark", "Partnachplatz", "Harras", "Implerstraße", "Poccistraße",
                    "Goetheplatz", "Sendlinger Tor", "Marienplatz", "Odeonsplatz",
                    "Universität", "Giselastraße", "Münchner Freiheit", "Dietlindenstraße",
                    "Nordfriedhof", "Alte Heide", "Studentenstadt", "Freimann",
                    "Kieferngarten", "Fröttmaning",
                ],
            },
            "U7": {
                "color": "#7A1E74",
                "stations": [
                    "Olympia-Einkaufszentrum", "Georg-Brauchle-Ring", "Westfriedhof", "Gern",
                    "Rotkreuzplatz", "Maillingerstraße", "Stiglmaierplatz", "Hauptbahnhof",
                    "Sendlinger Tor", "Fraunhoferstraße", "Kolumbusplatz", "Silberhornstraße",
                    "Untersbergstraße", "Giesing", "Karl-Preis-Platz", "Innsbrucker Ring",
                    "Michaelibad", "Quiddestraße", "Neuperlach Zentrum",
                ],
            },
            "U8": {
                "color": "#E4007F",
                "stations": [
                    "Olympiazentrum", "Petuelring", "Scheidplatz", "Hohenzollernplatz",
                    "Josephsplatz", "Theresienstraße", "Königsplatz", "Hauptbahnhof",
                    "Sendlinger Tor",
                ],
            },
        }

    def _draw_all_ubahn_lines(self):
        for path in self.all_line_paths:
            path.delete()
        self.all_line_paths = []

        for line_name, line_data in self._ubahn_line_definitions().items():
            coords = self._line_coords(line_data["stations"], samples_per_segment=14)
            if len(coords) < 2:
                continue
            path = self.map_widget.set_path(coords, color=line_data["color"], width=4)
            self.all_line_paths.append(path)

    def _station_dot_image(self):
        if self.station_dot_icon is not None:
            return self.station_dot_icon

        size = 13
        radius = 5.5
        center = (size - 1) / 2
        image = tk.PhotoImage(width=size, height=size)
        for x in range(size):
            for y in range(size):
                distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                if distance <= radius - 1:
                    image.put("#FFFFFF", (x, y))
                elif distance <= radius:
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
                distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                if distance <= radius - 2:
                    image.put("#FFFFFF", (x, y))
                elif distance <= radius:
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
        def enter(event=None, marker=marker, station_name=station_name):
            self._show_station_tooltip(marker, station_name)

        def leave(event=None):
            self._clear_station_tooltip()

        marker.mouse_enter = enter
        marker.mouse_leave = leave
        if marker.canvas_icon is not None:
            self.map_widget.canvas.tag_bind(marker.canvas_icon, "<Enter>", enter)
            self.map_widget.canvas.tag_bind(marker.canvas_icon, "<Leave>", leave)

    def _draw_all_stations(self):
        """Display all available U-Bahn stations on the map."""
        self._clear_station_tooltip()
        # Clear previous station markers
        for marker in self.all_station_markers:
            marker.delete()
        self.all_station_markers = []

        station_points = self._station_display_points()

        # Show one marker per station name. The routing data still keeps all
        # platform/entrance records internally for accurate rail connections.
        for name, coords in sorted(station_points.items()):
            is_blocked = name in self.blocked_station_names
            tooltip_name = (
                f"{name} (blocked - click to unblock)"
                if is_blocked
                else f"{name} (click to block)"
            )
            marker = self.map_widget.set_marker(
                coords[0],
                coords[1],
                icon=self._blocked_station_dot_image() if is_blocked else self._station_dot_image(),
                icon_anchor="center",
                command=lambda _marker, station_name=name: self._toggle_blocked_station(station_name),
            )
            self._bind_station_tooltip(marker, tooltip_name)
            self.all_station_markers.append(marker)

    def _station_display_points(self):
        stations_by_name = {}
        for station in self.station_records:
            name = str(station.get("name") or "Station").strip()
            stations_by_name.setdefault(name, []).append(station)

        station_points = {}
        for name, stations in sorted(stations_by_name.items()):
            lat = sum(float(station["lat"]) for station in stations) / len(stations)
            lon = sum(float(station["lon"]) for station in stations) / len(stations)
            station_points[name] = (lat, lon)

        return station_points

    def _rail_node_station_names(self):
        node_to_station = {}
        for station in self.station_records:
            try:
                rail_node = int(station["rail_node"])
            except (KeyError, TypeError, ValueError):
                continue
            name = str(station.get("name") or "Station").strip()
            node_to_station[rail_node] = name

        return node_to_station

    def _rail_path_to_station_coords(self, rail_path, boarding_station, alighting_station):
        station_names = self._rail_path_station_names(rail_path, boarding_station, alighting_station)
        station_points = self._station_display_points()

        coords = [station_points[name] for name in station_names if name in station_points]
        if len(coords) >= 2:
            return coords

        return self._path_to_map_coords(self.G_rail, rail_path)

    def _rail_path_station_names(self, rail_path, boarding_station, alighting_station):
        station_points = self._station_display_points()
        node_to_station = self._rail_node_station_names()

        station_names = []

        def add_station(name):
            name = str(name or "").strip()
            if name and name in station_points and (not station_names or station_names[-1] != name):
                station_names.append(name)

        add_station(boarding_station.get("name"))
        for node in rail_path:
            add_station(node_to_station.get(int(node)))
        add_station(alighting_station.get("name"))

        return station_names

    def _line_coords(self, station_names, samples_per_segment=14):
        station_points = self._station_display_points()
        coords = []
        for station_name in station_names:
            if station_name not in station_points:
                continue
            coords.append(station_points[station_name])

        return self._smooth_route_coords(coords, samples_per_segment=samples_per_segment)

    def _smooth_route_segment(self, coords, segment_index, samples_per_segment=14):
        if len(coords) < 2:
            return coords

        if len(coords) < 3:
            return [coords[segment_index], coords[segment_index + 1]]

        p0 = coords[segment_index - 1] if segment_index > 0 else coords[segment_index]
        p1 = coords[segment_index]
        p2 = coords[segment_index + 1]
        p3 = coords[segment_index + 2] if segment_index + 2 < len(coords) else coords[segment_index + 1]

        segment = [p1]
        for step in range(1, samples_per_segment + 1):
            segment.append(self._catmull_rom_interpolate(p0, p1, p2, p3, step / samples_per_segment))

        return segment

    def _line_section_coords(self, line_station_names, start_idx, end_idx, samples_per_segment=14):
        station_points = self._station_display_points()
        named_line_coords = []
        for station_name in line_station_names:
            if station_name in station_points:
                named_line_coords.append((station_name, station_points[station_name]))

        from_station = line_station_names[start_idx]
        to_station = line_station_names[end_idx]
        available_station_names = [station_name for station_name, _coords in named_line_coords]
        if from_station not in available_station_names or to_station not in available_station_names:
            return []

        available_start_idx = available_station_names.index(from_station)
        available_end_idx = available_station_names.index(to_station)
        line_coords = [coords for _station_name, coords in named_line_coords]

        direction = 1 if available_end_idx > available_start_idx else -1
        coords = []
        current_idx = available_start_idx

        while current_idx != available_end_idx:
            segment_idx = current_idx if direction > 0 else current_idx - 1
            segment = self._smooth_route_segment(line_coords, segment_idx, samples_per_segment=samples_per_segment)
            if direction < 0:
                segment = list(reversed(segment))

            if coords and segment:
                if self._coords_are_different(coords[-1], segment[0]):
                    coords.extend(segment)
                else:
                    coords.extend(segment[1:])
            else:
                coords.extend(segment)

            current_idx += direction

        return coords

    def _ubahn_segment_coords_for_pair(self, from_station, to_station):
        line_definitions = self._ubahn_line_definitions()

        # Reverse order matches the drawing order, so shared tracks use the
        # same visible curve that is on top in the base map.
        for line_name in reversed(list(line_definitions)):
            station_names = line_definitions[line_name]["stations"]
            for idx in range(len(station_names) - 1):
                if station_names[idx] == from_station and station_names[idx + 1] == to_station:
                    segment = self._line_section_coords(station_names, idx, idx + 1)
                    if segment:
                        return segment
                if station_names[idx] == to_station and station_names[idx + 1] == from_station:
                    segment = self._line_section_coords(station_names, idx + 1, idx)
                    if segment:
                        return segment

        return None

    def _selected_ubahn_route_coords(self, rail_path, boarding_station, alighting_station):
        station_names = self._rail_path_station_names(rail_path, boarding_station, alighting_station)
        if len(station_names) < 2:
            return self._path_to_map_coords(self.G_rail, rail_path)

        station_points = self._station_display_points()
        route_coords = []
        for from_station, to_station in zip(station_names, station_names[1:]):
            segment = self._ubahn_segment_coords_for_pair(from_station, to_station)
            if not segment and from_station in station_points and to_station in station_points:
                segment = [station_points[from_station], station_points[to_station]]
            if not segment:
                continue

            if route_coords and self._coords_are_different(route_coords[-1], segment[0]):
                route_coords.extend(segment)
            elif route_coords:
                route_coords.extend(segment[1:])
            else:
                route_coords.extend(segment)

        if len(route_coords) >= 2:
            return route_coords

        return self._path_to_map_coords(self.G_rail, rail_path)

    def _catmull_rom_interpolate(self, p0, p1, p2, p3, t):
        t2 = t * t
        t3 = t2 * t
        lat = 0.5 * (
            (2 * p1[0])
            + (-p0[0] + p2[0]) * t
            + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
        )
        lon = 0.5 * (
            (2 * p1[1])
            + (-p0[1] + p2[1]) * t
            + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
        )
        return (lat, lon)

    def _smooth_route_coords(self, coords, samples_per_segment=18):
        """Return a Catmull-Rom curve that passes through each station point."""
        if len(coords) < 3:
            return coords

        smooth_coords = [coords[0]]
        for idx in range(len(coords) - 1):
            segment = self._smooth_route_segment(coords, idx, samples_per_segment=samples_per_segment)
            smooth_coords.extend(segment[1:])

        return smooth_coords

    def _draw_neighbor_boundaries(self):
        gdf = self._load_neighbor_boundaries()
        if gdf.empty:
            print("Không có dữ liệu ranh giới để hiển thị.")
            return

        for line in self.boundary_lines:
            line.delete()
        self.boundary_lines = []

        for _, row in gdf.iterrows():
            geometry = row.get("geometry")
            paths = self._geometry_to_boundary_paths(geometry)
            for coords in paths:
                line = self.map_widget.set_path(coords, color="#2e7d32", width=2)
                self.boundary_lines.append(line)

    def _edge_coords(self, graph, u, v):
        """Return edge polyline coords as (lat, lon), following actual road geometry when available."""
        edge_data = graph.get_edge_data(u, v)
        if not edge_data:
            return [(graph.nodes[u]["y"], graph.nodes[u]["x"]), (graph.nodes[v]["y"], graph.nodes[v]["x"])]

        attrs = self._edge_attrs(edge_data)

        geometry = attrs.get("geometry")
        if geometry is not None:
            coords = [(lat, lon) for lon, lat in geometry.coords]
            if len(coords) >= 2:
                u_lat, u_lon = graph.nodes[u]["y"], graph.nodes[u]["x"]
                first = coords[0]
                last = coords[-1]
                d_first = (first[0] - u_lat) ** 2 + (first[1] - u_lon) ** 2
                d_last = (last[0] - u_lat) ** 2 + (last[1] - u_lon) ** 2
                if d_last < d_first:
                    coords.reverse()
                return coords

        return [(graph.nodes[u]["y"], graph.nodes[u]["x"]), (graph.nodes[v]["y"], graph.nodes[v]["x"])]

    def _edge_attrs(self, edge_data):
        if "length" in edge_data:
            return edge_data
        return min(edge_data.values(), key=lambda item: float(item.get("length", 1.0)))

    def _is_transfer_edge(self, graph, u, v):
        edge_data = graph.get_edge_data(u, v)
        if not edge_data:
            return False
        attrs = self._edge_attrs(edge_data)
        return attrs.get("transfer") is True

    def _path_to_map_coords(self, graph, path):
        """Expand node path into a drawable road polyline using edge geometries."""
        if len(path) < 2:
            return [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in path]

        route_coords = []
        for idx in range(len(path) - 1):
            u = path[idx]
            v = path[idx + 1]
            segment = self._edge_coords(graph, u, v)

            if not segment:
                continue

            if route_coords and route_coords[-1] == segment[0]:
                route_coords.extend(segment[1:])
            else:
                route_coords.extend(segment)

        return route_coords

    def _path_to_map_segments(self, graph, path, skip_transfers=False):
        """Expand a path into drawable polyline segments without drawing skipped edges."""
        if len(path) < 2:
            coords = [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in path]
            return [coords] if len(coords) >= 2 else []

        route_segments = []
        current_segment = []
        skipped_transfer = False

        for idx in range(len(path) - 1):
            u = path[idx]
            v = path[idx + 1]
            if skip_transfers and self._is_transfer_edge(graph, u, v):
                skipped_transfer = True
                continue

            segment = self._edge_coords(graph, u, v)
            if not segment:
                continue

            if current_segment:
                if current_segment[-1] == segment[0]:
                    current_segment.extend(segment[1:])
                elif skipped_transfer:
                    # Draw one clean connector through the station transfer,
                    # instead of drawing every internal platform edge.
                    current_segment.extend(segment)
                else:
                    if len(current_segment) >= 2:
                        route_segments.append(current_segment)
                    current_segment = list(segment)
            else:
                current_segment = list(segment)

            skipped_transfer = False

        if len(current_segment) >= 2:
            route_segments.append(current_segment)

        return route_segments

    def _draw_route_segment(self, coords, color, width):
        if len(coords) < 2:
            return None
        return self.map_widget.set_path(coords, color=color, width=width)

    def _coords_are_different(self, first, second):
        return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2 > 1e-12

    def _add_visible_endpoints(self, coords, start_point, end_point):
        route_coords = list(coords)

        if start_point is not None:
            start_point = (float(start_point[0]), float(start_point[1]))
            if not route_coords or self._coords_are_different(start_point, route_coords[0]):
                route_coords.insert(0, start_point)

        if end_point is not None:
            end_point = (float(end_point[0]), float(end_point[1]))
            if not route_coords or self._coords_are_different(end_point, route_coords[-1]):
                route_coords.append(end_point)

        return route_coords

    def _load_graph_pickle(self, pickle_path):
        with Path(pickle_path).open("rb") as file:
            return pickle.load(file)

    def _save_graph_pickle(self, graph, pickle_path):
        path = Path(pickle_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    def _load_access_graph(self):
        cache_path = Path(self.access_graph_cache_file)
        pickle_path = Path(self.access_graph_pickle_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if pickle_path.exists():
            print("Dang doc walk graph Munich tu cache nhanh...")
            return self._load_graph_pickle(pickle_path)

        if cache_path.exists():
            print("Đang đọc walk graph Munich từ cache local...")
            graph = ox.load_graphml(cache_path)
            self._save_graph_pickle(graph, pickle_path)
            return graph

        print("Không thấy cache walk graph, đang tải từ OpenStreetMap...")
        try:
            graph = ox.graph_from_place(
                self.place_name,
                network_type="walk",
                simplify=True,
                retain_all=False,
            )
            ox.save_graphml(graph, cache_path)
            self._save_graph_pickle(graph, pickle_path)
            return graph
        except Exception as exc:
            legacy_path = Path(self.legacy_drive_graph_cache_file)
            if legacy_path.exists():
                print(f"Không thể tải walk graph ({exc}). Tạm dùng drive graph cache cũ.")
                return ox.load_graphml(legacy_path)
            raise

    def _load_rail_graph(self):
        cache_path = Path(self.rail_graph_cache_file)
        pickle_path = Path(self.rail_graph_pickle_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if pickle_path.exists():
            print("Dang doc rail graph Munich tu cache nhanh...")
            return self._load_graph_pickle(pickle_path)

        if cache_path.exists():
            print("Đang đọc rail graph Munich từ cache local...")
            graph = ox.load_graphml(cache_path)
            self._save_graph_pickle(graph, pickle_path)
            return graph

        print("Không thấy cache rail graph, đang tải từ OpenStreetMap...")
        graph = ox.graph_from_place(
            self.place_name,
            network_type="all",
            custom_filter='["railway"="subway"]',
            simplify=False,
            retain_all=True,
        )
        ox.save_graphml(graph, cache_path)
        self._save_graph_pickle(graph, pickle_path)
        return graph

    def _set_map_center_from_graph(self, graph):
        nodes = list(graph.nodes)
        if not nodes:
            return

        sample = nodes[: min(3000, len(nodes))]
        lat_avg = sum(graph.nodes[n]["y"] for n in sample) / len(sample)
        lon_avg = sum(graph.nodes[n]["x"] for n in sample) / len(sample)
        self.center_lat = lat_avg
        self.center_lon = lon_avg

    def set_start(self, coords):
        if self.start_marker: self.start_marker.delete()
        self.start_coords = (coords[0], coords[1])
        self.start_node = ox.nearest_nodes(self.G_access, coords[1], coords[0])
        self.start_marker = self.map_widget.set_marker(coords[0], coords[1], text="Start", marker_color_circle="green")

    def set_end(self, coords):
        if self.end_marker: self.end_marker.delete()
        self.end_coords = (coords[0], coords[1])
        self.end_node = ox.nearest_nodes(self.G_access, coords[1], coords[0])
        self.end_marker = self.map_widget.set_marker(coords[0], coords[1], text="End", marker_color_circle="red")

    def find_route(self):
        if self.start_node is None or self.end_node is None:
            print("Please select both start and end points!")
            return
        if not self.station_records:
            print("No U-Bahn station data available in current map area.")
            return

        algo = self.algo_menu.get()
        start_time = time.time()

        try:
            result = find_route_multimodal_via_rail(
                self.G_access,
                self.G_rail,
                self.start_node,
                self.end_node,
                self.station_records,
                algo,
                walking_weight=self.walking_weight,
                max_access_walk_m=self.max_access_walk_m,
                blocked_station_names=self.blocked_station_names,
            )
            if not result:
                raise ValueError(
                    f"No valid subway route found avoiding blocked stations with max {self.max_access_walk_m:.0f} m walking per access leg"
                )

            end_time = time.time()
            distance = result["distance_m"]
            walk_distance = result["walk_distance_m"]
            rail_distance = result["rail_distance_m"]
            visited_nodes = result["expanded_nodes"]
            board = result["boarding_station"]
            alight = result["alighting_station"]
            access_start_path = result["access_start_path"]
            rail_path = result["rail_path"]
            access_end_path = result["access_end_path"]
            
            # Cập nhật UI
            self.lbl_dist.configure(text=f"Distance: {distance/1000:.2f} km")
            walk_note = " (walk-heavy)" if walk_distance > rail_distance else ""
            self.lbl_walk.configure(text=f"Walk/Subway: {walk_distance/1000:.2f} / {rail_distance/1000:.2f} km{walk_note}")
            self.lbl_cost.configure(text=f"Weighted cost: {result['route_cost_m']/1000:.2f} km-eq")
            self.lbl_nodes.configure(text=f"Nodes visited: {visited_nodes}")
            self.lbl_time.configure(text=f"Time: {(end_time - start_time)*1000:.2f} ms")
            self.lbl_station.configure(text=f"U-Bahn: {board.get('name', 'Station')} -> {alight.get('name', 'Station')}")
            self._set_route_station_list(
                self._rail_path_station_names(rail_path, board, alight)
            )

            # Xoa ket qua cu
            if self.path_line: self.path_line.delete()
            for line in self.station_path_lines:
                line.delete()
            self.station_path_lines = []
            for marker in self.station_markers:
                marker.delete()
            self.station_markers = []

            # Ve 3 chang: di bo -> U-Bahn -> di bo
            start_coords = self._path_to_map_coords(self.G_access, access_start_path)
            rail_coords = self._selected_ubahn_route_coords(rail_path, board, alight)
            end_coords = self._path_to_map_coords(self.G_access, access_end_path)
            rail_start = rail_coords[0] if rail_coords else (board["lat"], board["lon"])
            rail_end = rail_coords[-1] if rail_coords else (alight["lat"], alight["lon"])
            start_coords = self._add_visible_endpoints(
                start_coords,
                self.start_coords,
                rail_start,
            )
            end_coords = self._add_visible_endpoints(
                end_coords,
                rail_end,
                self.end_coords,
            )

            line1 = self._draw_route_segment(start_coords, color="#1f77b4", width=5)
            line2 = self._draw_route_segment(rail_coords, color="#ff6f00", width=10)
            line3 = self._draw_route_segment(end_coords, color="#1f77b4", width=5)
            self.station_path_lines.extend(line for line in [line1, line2, line3] if line is not None)

        except Exception as e:
            print(f"Cannot find route: {e}")
            self._clear_route_result()
            self.lbl_station.configure(text="U-Bahn: No valid route")

    def clear_map(self):
        if self.start_marker: self.start_marker.delete()
        if self.end_marker: self.end_marker.delete()
        self.start_marker = None
        self.end_marker = None
        self._clear_route_result()
        self.start_node = self.end_node = None
        self.start_coords = self.end_coords = None
        # Redraw all station markers
        self._draw_all_stations()

if __name__ == "__main__":
    app = MunichNavigationApp()
    app.mainloop()
