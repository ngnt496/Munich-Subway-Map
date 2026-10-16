"""Module xử lý các thuật toán hình học, nội suy đường cong Catmull-Rom và chuyển đổi đường đi thành tọa độ GPS."""

from typing import Dict, List, Tuple
from models.ubahn_network import UBAHN_LINES


def catmull_rom_interpolate(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    """Nội suy Catmull-Rom spline giữa p1 và p2 với tham số t trong [0, 1]."""
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


def smooth_route_segment(
    coords: List[Tuple[float, float]],
    segment_index: int,
    samples_per_segment: int = 14,
) -> List[Tuple[float, float]]:
    """Làm mượt một đoạn segment giữa 2 điểm trong chuỗi coords."""
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
        segment.append(catmull_rom_interpolate(p0, p1, p2, p3, step / samples_per_segment))

    return segment


def smooth_route_coords(
    coords: List[Tuple[float, float]],
    samples_per_segment: int = 18,
) -> List[Tuple[float, float]]:
    """Tạo đường cong Catmull-Rom đi qua tất cả các điểm trong coords."""
    if len(coords) < 3:
        return coords

    smooth_coords = [coords[0]]
    for idx in range(len(coords) - 1):
        segment = smooth_route_segment(coords, idx, samples_per_segment=samples_per_segment)
        smooth_coords.extend(segment[1:])

    return smooth_coords


def coords_are_different(
    first: Tuple[float, float],
    second: Tuple[float, float],
    epsilon: float = 1e-12,
) -> bool:
    """Kiểm tra hai tọa độ có khác nhau vượt ngưỡng sai số không."""
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2 > epsilon


def add_visible_endpoints(
    coords: List[Tuple[float, float]],
    start_point: Tuple[float, float] | None,
    end_point: Tuple[float, float] | None,
) -> List[Tuple[float, float]]:
    """Đảm bảo điểm đầu và điểm cuối click chuột được nối liền vào polyline."""
    route_coords = list(coords)

    if start_point is not None:
        start_point = (float(start_point[0]), float(start_point[1]))
        if not route_coords or coords_are_different(start_point, route_coords[0]):
            route_coords.insert(0, start_point)

    if end_point is not None:
        end_point = (float(end_point[0]), float(end_point[1]))
        if not route_coords or coords_are_different(end_point, route_coords[-1]):
            route_coords.append(end_point)

    return route_coords


def get_station_display_points(station_records: List[dict]) -> Dict[str, Tuple[float, float]]:
    """Gộp các điểm ga có cùng tên để tính tọa độ đại diện trung bình (trọng tâm)."""
    stations_by_name = {}
    for station in station_records:
        name = str(station.get("name") or "Station").strip()
        stations_by_name.setdefault(name, []).append(station)

    station_points = {}
    for name, stations in sorted(stations_by_name.items()):
        lat = sum(float(s["lat"]) for s in stations) / len(stations)
        lon = sum(float(s["lon"]) for s in stations) / len(stations)
        station_points[name] = (lat, lon)

    return station_points


def get_rail_node_station_names(station_records: List[dict]) -> Dict[int, str]:
    """Map từ rail_node ID sang tên ga."""
    node_to_station = {}
    for station in station_records:
        try:
            rail_node = int(station["rail_node"])
        except (KeyError, TypeError, ValueError):
            continue
        name = str(station.get("name") or "Station").strip()
        node_to_station[rail_node] = name

    return node_to_station


def get_unique_station_names(station_records: List[dict]) -> List[str]:
    """Trả về danh sách tên các ga U-Bahn duy nhất, đã sắp xếp theo bảng chữ cái."""
    return sorted({
        str(station.get("name") or "Station").strip()
        for station in station_records
        if str(station.get("name") or "").strip()
    })


def get_rail_path_station_names(
    rail_path: List[int],
    boarding_station: dict,
    alighting_station: dict,
    station_records: List[dict],
) -> List[str]:
    """Lấy danh sách các ga U-Bahn đi qua trên đường ray."""
    station_points = get_station_display_points(station_records)
    node_to_station = get_rail_node_station_names(station_records)

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


def find_subway_transfers(
    station_names: List[str],
    station_points: Dict[str, Tuple[float, float]] | None = None,
) -> Tuple[int, List[dict], List[str]]:
    """Xác định số lần chuyển tuyến và các ga phải chuyển tuyến (từ U1 đến U8).

    Sử dụng Quy hoạch động (Dynamic Programming) để tìm chuỗi các tuyến tàu
    tối ưu sao cho số lần đổi tàu giữa các chặng là nhỏ nhất.
    """
    if len(station_names) < 2:
        return 0, [], []

    def get_lines(s1: str, s2: str) -> set[str]:
        lines = set()
        for name, data in UBAHN_LINES.items():
            sts = data["stations"]
            for j in range(len(sts) - 1):
                if (sts[j] == s1 and sts[j + 1] == s2) or (sts[j] == s2 and sts[j + 1] == s1):
                    lines.add(name)
        if not lines:
            # Dự phòng: các tuyến đi qua cả 2 ga
            for name, data in UBAHN_LINES.items():
                if s1 in data["stations"] and s2 in data["stations"]:
                    lines.add(name)
        if not lines:
            for name, data in UBAHN_LINES.items():
                if s1 in data["stations"] or s2 in data["stations"]:
                    lines.add(name)
        return lines or {"U-Bahn"}

    segment_lines = [get_lines(station_names[i], station_names[i + 1]) for i in range(len(station_names) - 1)]

    # Quy hoạch động để tìm chuỗi tuyến có ít lần đổi nhất
    dp = [{line: (0, [line]) for line in segment_lines[0]}]
    for i in range(1, len(segment_lines)):
        curr_dp = {}
        for curr_line in segment_lines[i]:
            best_cost = float("inf")
            best_seq = []
            for prev_line, (prev_cost, prev_seq) in dp[-1].items():
                cost = prev_cost + (0 if prev_line == curr_line else 1)
                if cost < best_cost:
                    best_cost = cost
                    best_seq = prev_seq + [curr_line]
            curr_dp[curr_line] = (best_cost, best_seq)
        dp.append(curr_dp)

    _best_cost, best_sequence = min(dp[-1].values(), key=lambda item: item[0])

    transfers = []
    for i in range(len(best_sequence) - 1):
        if best_sequence[i] != best_sequence[i + 1]:
            st_name = station_names[i + 1]
            coords = station_points.get(st_name) if station_points else None
            transfers.append({
                "station": st_name,
                "from_line": best_sequence[i],
                "to_line": best_sequence[i + 1],
                "index": i + 1,
                "coords": coords,
            })

    return len(transfers), transfers, best_sequence


def edge_attrs(edge_data: dict) -> dict:
    """Lấy thuộc tính cạnh hỗ trợ cả đơn cạnh và đa cạnh OSMnx."""
    if "length" in edge_data:
        return edge_data
    return min(edge_data.values(), key=lambda item: float(item.get("length", 1.0)))


def edge_coords(graph, u: int, v: int) -> List[Tuple[float, float]]:
    """Trả về danh sách tọa độ (lat, lon) của cạnh nối giữa u và v theo hình học thực tế."""
    edge_data = graph.get_edge_data(u, v)
    if not edge_data:
        return [(graph.nodes[u]["y"], graph.nodes[u]["x"]), (graph.nodes[v]["y"], graph.nodes[v]["x"])]

    attrs = edge_attrs(edge_data)
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


def is_transfer_edge(graph, u: int, v: int) -> bool:
    """Kiểm tra xem cạnh giữa u và v có phải là cạnh chuyển tuyến nội bộ không."""
    edge_data = graph.get_edge_data(u, v)
    if not edge_data:
        return False
    attrs = edge_attrs(edge_data)
    return attrs.get("transfer") is True


def path_to_map_coords(graph, path: List[int]) -> List[Tuple[float, float]]:
    """Chuyển đổi danh sách node ID thành polyline tọa độ GPS nối tiếp nhau."""
    if len(path) < 2:
        return [(graph.nodes[n]["y"], graph.nodes[n]["x"]) for n in path]

    route_coords = []
    for idx in range(len(path) - 1):
        u = path[idx]
        v = path[idx + 1]
        segment = edge_coords(graph, u, v)

        if not segment:
            continue

        if route_coords and route_coords[-1] == segment[0]:
            route_coords.extend(segment[1:])
        else:
            route_coords.extend(segment)

    return route_coords


def line_coords(
    station_names: List[str],
    station_points: Dict[str, Tuple[float, float]],
    samples_per_segment: int = 14,
) -> List[Tuple[float, float]]:
    """Tạo polyline mượt mà cho toàn bộ một tuyến metro."""
    coords = []
    for station_name in station_names:
        if station_name not in station_points:
            continue
        coords.append(station_points[station_name])

    return smooth_route_coords(coords, samples_per_segment=samples_per_segment)


def line_section_coords(
    line_station_names: List[str],
    start_idx: int,
    end_idx: int,
    station_points: Dict[str, Tuple[float, float]],
    samples_per_segment: int = 14,
) -> List[Tuple[float, float]]:
    """Tạo polyline mượt mà cho một phân đoạn giữa 2 ga trên một tuyến."""
    named_line_coords = []
    for station_name in line_station_names:
        if station_name in station_points:
            named_line_coords.append((station_name, station_points[station_name]))

    from_station = line_station_names[start_idx]
    to_station = line_station_names[end_idx]
    available_station_names = [name for name, _coords in named_line_coords]
    if from_station not in available_station_names or to_station not in available_station_names:
        return []

    available_start_idx = available_station_names.index(from_station)
    available_end_idx = available_station_names.index(to_station)
    line_pts = [coords for _name, coords in named_line_coords]

    direction = 1 if available_end_idx > available_start_idx else -1
    coords = []
    current_idx = available_start_idx

    while current_idx != available_end_idx:
        segment_idx = current_idx if direction > 0 else current_idx - 1
        segment = smooth_route_segment(line_pts, segment_idx, samples_per_segment=samples_per_segment)
        if direction < 0:
            segment = list(reversed(segment))

        if coords and segment:
            if coords_are_different(coords[-1], segment[0]):
                coords.extend(segment)
            else:
                coords.extend(segment[1:])
        else:
            coords.extend(segment)

        current_idx += direction

    return coords


def ubahn_segment_coords_for_pair(
    from_station: str,
    to_station: str,
    station_points: Dict[str, Tuple[float, float]],
) -> List[Tuple[float, float]] | None:
    """Tìm đường vẽ khớp với đường cong tuyến U-Bahn đã vẽ trên bản đồ giữa 2 trạm."""
    for line_name in reversed(list(UBAHN_LINES)):
        station_names = UBAHN_LINES[line_name]["stations"]
        for idx in range(len(station_names) - 1):
            if station_names[idx] == from_station and station_names[idx + 1] == to_station:
                segment = line_section_coords(station_names, idx, idx + 1, station_points)
                if segment:
                    return segment
            if station_names[idx] == to_station and station_names[idx + 1] == from_station:
                segment = line_section_coords(station_names, idx + 1, idx, station_points)
                if segment:
                    return segment

    return None


def selected_ubahn_route_coords(
    rail_path: List[int],
    boarding_station: dict,
    alighting_station: dict,
    station_records: List[dict],
    rail_graph,
) -> List[Tuple[float, float]]:
    """Tạo polyline hoàn chỉnh cho chặng đi tàu điện ngầm."""
    station_names = get_rail_path_station_names(rail_path, boarding_station, alighting_station, station_records)
    if len(station_names) < 2:
        return path_to_map_coords(rail_graph, rail_path)

    station_points = get_station_display_points(station_records)
    route_coords = []
    for from_station, to_station in zip(station_names, station_names[1:]):
        segment = ubahn_segment_coords_for_pair(from_station, to_station, station_points)
        if not segment and from_station in station_points and to_station in station_points:
            segment = [station_points[from_station], station_points[to_station]]
        if not segment:
            continue

        if route_coords and coords_are_different(route_coords[-1], segment[0]):
            route_coords.extend(segment)
        elif route_coords:
            route_coords.extend(segment[1:])
        else:
            route_coords.extend(segment)

    if len(route_coords) >= 2:
        return route_coords

    return path_to_map_coords(rail_graph, rail_path)


def geometry_to_boundary_paths(geometry) -> List[List[Tuple[float, float]]]:
    """Chuyển đổi Polygon / MultiPolygon thành danh sách polyline GPS để vẽ ranh giới."""
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

