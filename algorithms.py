import heapq
import math
from typing import Dict, List, Tuple

# hàm tính độ dài cạnh, hỗ trợ cả Graph và MultiDiGraph của OSMnx
def _edge_length(edge_data: dict) -> float:
    """Return edge length for both Graph and MultiDiGraph adjacency formats."""
    # edge_data là danh sách cạnh (MultiDiGraph) hoặc dict cạnh (Graph)
    # nếu edge_data là đơn cạnh (Graph), trả về độ dài trực tiếp
    if "length" in edge_data:
        return float(edge_data.get("length", 1.0))

    # nếu edge_data là đa cạnh (MultiDiGraph), tìm độ dài nhỏ nhất trong các cạnh
    min_length = float("inf") # khởi tạo với vô cực để tìm min
    for attrs in edge_data.values():
        length = float(attrs.get("length", 1.0))
        if length < min_length:
            min_length = length

    # nếu không tìm thấy độ dài nào, trả về 1.0 làm mặc định
    return min_length if min_length != float("inf") else 1.0

# hàm lấy danh sách hàng xóm kèm chi phí (độ dài) cho một node
def _neighbors_with_cost(graph, node: int, blocked_nodes: set | None = None) -> List[Tuple[int, float]]:
    # graph lưu trữ các node và cạnh
    neighbors = []
    # graph[node] là một dict chứa các node kề và dữ liệu cạnh 
    for neighbor, edge_data in graph[node].items():
        if blocked_nodes and neighbor in blocked_nodes:
            continue
        neighbors.append((neighbor, _edge_length(edge_data)))
    return neighbors

# hàm truy vết đường đi ngắn nhất từ end về start dựa trên came_from
def _reconstruct_path(came_from: Dict[int, int], start: int, end: int) -> List[int]:
    # came_from[i] là node cha của node i trên đường đi ngắn nhất đã tìm được
    if start == end:
        return [start]
    
    if end not in came_from:
        return []

    path = [end]
    current = end
    while current != start:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

# thuật toán Dijkstra để tìm đường đi ngắn nhất giữa start và end
def dijkstra_search(graph, start: int, end: int, blocked_nodes: set | None = None) -> Tuple[List[int], float, int]:
    """Return (path, total_distance_m, expanded_nodes)."""
    if blocked_nodes and (start in blocked_nodes or end in blocked_nodes):
        return [], float("inf"), 0
    # distances[node] là khoảng cách ngắn nhất đã biết từ start đến node
    distances = {start: 0.0}
    # came_from[node] là node cha của node trên đường đi ngắn nhất
    came_from: Dict[int, int] = {}
    # visited là tập các node đã được mở rộng để tránh lặp lại
    visited = set()
    # expanded_nodes đếm số node đã được mở rộng trong quá trình tìm kiếm
    expanded_nodes = 0
    # pq là hàng đợi ưu tiên chứa các node chưa được mở rộng, ưu tiên theo khoảng cách ngắn nhất đã biết
    pq = [(0.0, start)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)
        # nếu node đã được mở rộng, bỏ qua
        if current_node in visited:
            continue

        # đánh dấu node hiện tại là đã được mở rộng
        visited.add(current_node)
        expanded_nodes += 1

        # nếu đã đến đích, dừng tìm kiếm
        if current_node == end:
            break

        for neighbor, weight in _neighbors_with_cost(graph, current_node, blocked_nodes):
            # nếu neighbor đã được mở rộng, bỏ qua
            if neighbor in visited:
                continue

            new_distance = current_distance + weight

            # nếu tìm được đường đi ngắn hơn đến neighbor, cập nhật khoảng cách và node cha
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                came_from[neighbor] = current_node
                heapq.heappush(pq, (new_distance, neighbor))

    path = _reconstruct_path(came_from, start, end)
    if not path:
        return [], float("inf"), expanded_nodes
    return path, distances[end], expanded_nodes


def _single_source_dijkstra(
    graph,
    start: int,
    cutoff: float | None = None,
    targets: set | None = None,
    blocked_nodes: set | None = None,
) -> Tuple[Dict[int, float], Dict[int, int], int]:
    """Return shortest distances from start to all reachable nodes."""
    if blocked_nodes and start in blocked_nodes:
        return {}, {}, 0

    distances = {start: 0.0}
    came_from: Dict[int, int] = {}
    visited = set()
    expanded_nodes = 0
    remaining_targets = set(targets) if targets else None
    pq = [(0.0, start)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)
        if cutoff is not None and current_distance > cutoff:
            break
        if current_node in visited:
            continue

        visited.add(current_node)
        expanded_nodes += 1
        if remaining_targets is not None:
            remaining_targets.discard(current_node)
            if not remaining_targets:
                break

        for neighbor, weight in _neighbors_with_cost(graph, current_node, blocked_nodes):
            if neighbor in visited:
                continue

            new_distance = current_distance + weight
            if cutoff is not None and new_distance > cutoff:
                continue
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                came_from[neighbor] = current_node
                heapq.heappush(pq, (new_distance, neighbor))

    return distances, came_from, expanded_nodes

# hàm heuristic cho A* sử dụng khoảng cách Haversine giữa hai node
# Haversine là công thức tính khoảng cách giữa hai điểm trên bề mặt trái đất dựa trên vĩ độ và kinh độ
def _heuristic_meters(graph, node_a: int, node_b: int) -> float:
    """Haversine distance in meters between two graph nodes."""
    # chuyển đổi vĩ độ và kinh độ từ độ sang radian
    #lat1 là vĩ độ của node_a, lon1 là kinh độ của node_a
    lat1 = math.radians(graph.nodes[node_a]["y"])
    lon1 = math.radians(graph.nodes[node_a]["x"])
    #lat2 là vĩ độ của node_b, lon2 là kinh độ của node_b
    lat2 = math.radians(graph.nodes[node_b]["y"])
    lon2 = math.radians(graph.nodes[node_b]["x"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # công thức Haversine: dist = 2 * earth_radius * arcsin(sqrt(sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)))
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    earth_radius_m = 6371000
    return earth_radius_m * c

# thuật toán A* để tìm đường đi ngắn nhất giữa start và end, sử dụng heuristic để ưu tiên các node gần đích hơn
def astar_search(graph, start: int, end: int, blocked_nodes: set | None = None) -> Tuple[List[int], float, int]:
    """Return (path, total_distance_m, expanded_nodes)."""
    if blocked_nodes and (start in blocked_nodes or end in blocked_nodes):
        return [], float("inf"), 0

    g_score = {start: 0.0}
    came_from: Dict[int, int] = {}
    visited = set()
    expanded_nodes = 0

    start_f_score = _heuristic_meters(graph, start, end)
    open_set = [(start_f_score, start)]

    while open_set:
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue

        visited.add(current)
        expanded_nodes += 1

        if current == end:
            break

        for neighbor, weight in _neighbors_with_cost(graph, current, blocked_nodes):
            if neighbor in visited:
                continue

            tentative_g = g_score[current] + weight
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + _heuristic_meters(graph, neighbor, end)
                heapq.heappush(open_set, (f_score, neighbor))

    path = _reconstruct_path(came_from, start, end)
    if not path:
        return [], float("inf"), expanded_nodes
    return path, g_score[end], expanded_nodes


def find_route_custom(
    graph,
    start: int,
    end: int,
    algorithm: str,
    blocked_nodes: set | None = None,
) -> Tuple[List[int], float, int]:
    if algorithm == "A*":
        return astar_search(graph, start, end, blocked_nodes=blocked_nodes)
    return dijkstra_search(graph, start, end, blocked_nodes=blocked_nodes)


def _coerce_node_id(record: dict, keys: Tuple[str, ...]):
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _station_rail_node(record: dict):
    return _coerce_node_id(record, ("rail_node",))


def _valid_station_records(access_graph, rail_graph, station_records: List[dict]) -> List[dict]:
    valid_records = []
    seen = set()

    for record in station_records:
        access_node = None
        for key in ("access_node", "walk_node", "drive_node"):
            candidate_node = _coerce_node_id(record, (key,))
            if candidate_node is not None and candidate_node in access_graph.nodes:
                access_node = candidate_node
                break

        rail_node = _station_rail_node(record)
        if access_node is None or rail_node is None:
            continue
        if rail_node not in rail_graph.nodes:
            continue

        key = (access_node, rail_node)
        if key in seen:
            continue
        seen.add(key)

        normalized = dict(record)
        normalized["access_node"] = access_node
        normalized["rail_node"] = rail_node
        valid_records.append(normalized)

    return valid_records


def _station_name(record: dict) -> str:
    return str(record.get("name") or "Station").strip()


def _normalize_station_name_set(station_names) -> set:
    if not station_names:
        return set()
    return {str(name).strip() for name in station_names if str(name).strip()}


def _blocked_rail_nodes(station_records: List[dict], blocked_station_names) -> set:
    blocked_names = _normalize_station_name_set(blocked_station_names)
    if not blocked_names:
        return set()

    blocked_nodes = set()
    for record in station_records:
        if _station_name(record) not in blocked_names:
            continue
        rail_node = _station_rail_node(record)
        if rail_node is not None:
            blocked_nodes.add(int(rail_node))

    return blocked_nodes


def _nearest_station_group(
    access_graph,
    start_node: int,
    valid_records: List[dict],
    reverse: bool = False,
    max_access_walk_m: float | None = 2500.0,
):
    """Pick the nearest station name by walking-network distance."""
    station_access_nodes = {int(record["access_node"]) for record in valid_records}
    graph = access_graph.reverse(copy=False) if reverse else access_graph
    distances, _, expanded_nodes = _single_source_dijkstra(
        graph,
        start_node,
        cutoff=max_access_walk_m,
        targets=station_access_nodes,
    )

    best_by_name = {}
    for record in valid_records:
        name = _station_name(record)
        access_node = int(record["access_node"])
        distance = distances.get(access_node)
        if distance is None:
            continue

        score = (distance, name, access_node, int(record["rail_node"]))
        current = best_by_name.get(name)
        if current is None or score < current["score"]:
            best_by_name[name] = {
                "name": name,
                "record": record,
                "distance_m": distance,
                "score": score,
            }

    if not best_by_name:
        return None

    nearest = min(best_by_name.values(), key=lambda item: item["score"])
    nearest["records"] = [
        record for record in valid_records if _station_name(record) == nearest["name"]
    ]
    nearest["expanded_nodes"] = expanded_nodes
    return nearest


def _shortest_rail_record_pair(
    rail_graph,
    board_records: List[dict],
    alight_records: List[dict],
    blocked_nodes: set | None = None,
):
    """Choose the shortest rail-node pair between two already selected stations."""
    target_rail_nodes = {int(record["rail_node"]) for record in alight_records}
    best_pair = None
    best_score = None

    rail_distance_cache = {}
    for board in board_records:
        board_rail = int(board["rail_node"])
        if board_rail not in rail_distance_cache:
            rail_distances, _, _ = _single_source_dijkstra(
                rail_graph,
                board_rail,
                targets=target_rail_nodes,
                blocked_nodes=blocked_nodes,
            )
            rail_distance_cache[board_rail] = rail_distances
        else:
            rail_distances = rail_distance_cache[board_rail]

        for alight in alight_records:
            alight_rail = int(alight["rail_node"])
            rail_distance = rail_distances.get(alight_rail)
            if rail_distance is None:
                continue

            score = (rail_distance, board_rail, alight_rail)
            if best_score is None or score < best_score:
                best_score = score
                best_pair = {
                    "board_record": board,
                    "alight_record": alight,
                    "rail_distance_m": rail_distance,
                }

    return best_pair


def select_nearest_subway_station_pair(
    access_graph,
    rail_graph,
    start_access_node: int,
    end_access_node: int,
    station_records: List[dict],
    walking_weight: float = 2.5,
    max_access_walk_m: float | None = 2500.0,
    blocked_station_names=None,
):
    """
    Select stations in the order a passenger normally would:
    nearest U-Bahn station to the start, nearest U-Bahn station to the end,
    then shortest subway path between those two station names.
    """
    all_valid_records = _valid_station_records(access_graph, rail_graph, station_records)
    blocked_names = _normalize_station_name_set(blocked_station_names)
    blocked_nodes = _blocked_rail_nodes(all_valid_records, blocked_names)
    valid_records = [
        record for record in all_valid_records
        if _station_name(record) not in blocked_names
    ]
    if not valid_records:
        return None

    boarding_group = _nearest_station_group(
        access_graph,
        start_access_node,
        valid_records,
        reverse=False,
        max_access_walk_m=max_access_walk_m,
    )
    alighting_group = _nearest_station_group(
        access_graph,
        end_access_node,
        valid_records,
        reverse=True,
        max_access_walk_m=max_access_walk_m,
    )
    if boarding_group is None or alighting_group is None:
        return None

    rail_pair = _shortest_rail_record_pair(
        rail_graph,
        boarding_group["records"],
        alighting_group["records"],
        blocked_nodes=blocked_nodes,
    )
    if rail_pair is None:
        return None

    boarding_station = dict(boarding_group["record"])
    boarding_station["rail_node"] = int(rail_pair["board_record"]["rail_node"])
    alighting_station = dict(alighting_group["record"])
    alighting_station["rail_node"] = int(rail_pair["alight_record"]["rail_node"])

    total_walk_distance = boarding_group["distance_m"] + alighting_group["distance_m"]
    rail_distance = rail_pair["rail_distance_m"]
    total_distance = total_walk_distance + rail_distance

    return {
        "boarding_station": boarding_station,
        "alighting_station": alighting_station,
        "access_start_distance_m": boarding_group["distance_m"],
        "rail_distance_m": rail_distance,
        "access_end_distance_m": alighting_group["distance_m"],
        "walk_distance_m": total_walk_distance,
        "distance_m": total_distance,
        "route_cost_m": total_walk_distance * walking_weight + rail_distance,
        "walking_weight": walking_weight,
        "max_access_walk_m": max_access_walk_m,
        "blocked_station_names": sorted(blocked_names),
        "blocked_rail_nodes": blocked_nodes,
        "selection_mode": "nearest_station_then_shortest_subway",
    }


def build_route_for_subway_station_pair(
    access_graph,
    rail_graph,
    start_access_node: int,
    end_access_node: int,
    selected_pair: dict,
    algorithm: str,
    blocked_rail_nodes: set | None = None,
):
    """Build the three graph paths for a selected subway station pair."""
    if not selected_pair:
        return None

    best_board = selected_pair["boarding_station"]
    best_alight = selected_pair["alighting_station"]
    board_access = int(best_board["access_node"])
    board_rail = int(best_board["rail_node"])
    alight_access = int(best_alight["access_node"])
    alight_rail = int(best_alight["rail_node"])

    leg1_path, leg1_dist, leg1_expanded = find_route_custom(
        access_graph,
        start_access_node,
        board_access,
        algorithm,
    )
    rail_path, rail_dist, rail_expanded = find_route_custom(
        rail_graph,
        board_rail,
        alight_rail,
        algorithm,
        blocked_nodes=blocked_rail_nodes,
    )
    leg3_path, leg3_dist, leg3_expanded = find_route_custom(
        access_graph,
        alight_access,
        end_access_node,
        algorithm,
    )

    if not leg1_path or not rail_path or not leg3_path:
        return None

    result = dict(selected_pair)
    result.update(
        {
            "access_start_path": leg1_path,
            "rail_path": rail_path,
            "access_end_path": leg3_path,
            "access_start_distance_m": leg1_dist,
            "rail_distance_m": rail_dist,
            "access_end_distance_m": leg3_dist,
            "walk_distance_m": leg1_dist + leg3_dist,
            "distance_m": leg1_dist + rail_dist + leg3_dist,
            "route_cost_m": (leg1_dist + leg3_dist) * float(selected_pair.get("walking_weight", 1.0)) + rail_dist,
            "expanded_nodes": leg1_expanded + rail_expanded + leg3_expanded,
        }
    )
    return result


def find_route_multimodal_via_rail(
    access_graph,
    rail_graph,
    start_access_node: int,
    end_access_node: int,
    station_records: List[dict],
    algorithm: str,
    walking_weight: float = 2.5,
    max_access_walk_m: float | None = 2500.0,
    blocked_station_names=None,
):
    """
    Find a 3-leg route:
    walk(start->boarding_station) + subway(boarding->alighting) + walk(alighting->end).
    Return None if no valid route exists.
    """
    selected_pair = select_nearest_subway_station_pair(
        access_graph,
        rail_graph,
        start_access_node,
        end_access_node,
        station_records,
        walking_weight=walking_weight,
        max_access_walk_m=max_access_walk_m,
        blocked_station_names=blocked_station_names,
    )
    return build_route_for_subway_station_pair(
        access_graph,
        rail_graph,
        start_access_node,
        end_access_node,
        selected_pair,
        algorithm,
        blocked_rail_nodes=selected_pair.get("blocked_rail_nodes") if selected_pair else None,
    )
