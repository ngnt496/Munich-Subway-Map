import json
import math
from pathlib import Path
from typing import Dict, List

import osmnx as ox


StationRecord = Dict[str, float | int | str]


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _extract_point_coords(geometry):
    if geometry.geom_type == "Point":
        return geometry.y, geometry.x

    point = geometry.centroid
    return point.y, point.x


def fetch_station_nodes(graph, center_lat: float, center_lon: float, dist: int) -> List[int]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist)

    station_node_set = set()
    for _, row in features.iterrows():
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        station_node = ox.nearest_nodes(graph, lon, lat)
        station_node_set.add(int(station_node))

    return sorted(station_node_set)


def fetch_station_nodes_for_place(graph, place_name: str) -> List[int]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_place(place_name, tags=tags)

    station_node_set = set()
    for _, row in features.iterrows():
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        station_node = ox.nearest_nodes(graph, lon, lat)
        station_node_set.add(int(station_node))

    return sorted(station_node_set)


def fetch_station_records_for_place(access_graph, rail_graph, place_name: str) -> List[StationRecord]:
    tags = {"railway": ["station", "halt", "stop"]}
    features = ox.features_from_place(place_name, tags=tags)

    station_records = []
    seen = set()
    for _, row in features.iterrows():
        station_type = str(row.get("station") or "").strip().lower()
        subway_flag = str(row.get("subway") or "").strip().lower()
        if station_type != "subway" and subway_flag not in {"yes", "1", "true"}:
            continue

        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            continue

        lat, lon = _extract_point_coords(geometry)
        access_node = int(ox.nearest_nodes(access_graph, lon, lat))
        rail_node = int(ox.nearest_nodes(rail_graph, lon, lat))
        key = (access_node, rail_node)
        if key in seen:
            continue
        seen.add(key)

        station_records.append(
            {
                "name": str(row.get("name") or row.get("ref") or "Station"),
                "lat": float(lat),
                "lon": float(lon),
                "access_node": access_node,
                "rail_node": rail_node,
            }
        )

    return station_records


def ensure_station_graph_nodes(station_records: List[StationRecord], access_graph, rail_graph) -> tuple[List[StationRecord], bool]:
    """Add or refresh access_node and rail_node values for the current graphs."""
    updated_records = []
    changed = False

    for record in station_records:
        updated = dict(record)
        access_node = int(ox.nearest_nodes(access_graph, float(updated["lon"]), float(updated["lat"])))
        rail_node = int(ox.nearest_nodes(rail_graph, float(updated["lon"]), float(updated["lat"])))

        try:
            previous_access_node = int(updated["access_node"])
        except (KeyError, TypeError, ValueError):
            previous_access_node = None
        try:
            previous_rail_node = int(updated["rail_node"])
        except (KeyError, TypeError, ValueError):
            previous_rail_node = None

        if previous_access_node != access_node or previous_rail_node != rail_node:
            changed = True

        updated["access_node"] = access_node
        updated["rail_node"] = rail_node
        updated_records.append(updated)

    return updated_records, changed


def ensure_station_access_nodes(station_records: List[StationRecord], access_graph) -> tuple[List[StationRecord], bool]:
    """Add or refresh access_node values for the current walking/access graph."""
    updated_records = []
    changed = False

    for record in station_records:
        updated = dict(record)
        access_node = int(ox.nearest_nodes(access_graph, float(updated["lon"]), float(updated["lat"])))

        try:
            previous_access_node = int(updated["access_node"])
        except (KeyError, TypeError, ValueError):
            previous_access_node = None

        if previous_access_node != access_node:
            changed = True

        updated["access_node"] = access_node
        updated_records.append(updated)

    return updated_records, changed


def add_station_transfer_edges(rail_graph, station_records: List[StationRecord], max_transfer_m: float = 600.0) -> int:
    """Connect multiple rail nodes that belong to the same U-Bahn station."""
    nodes_by_station = {}
    for record in station_records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        try:
            rail_node = int(record["rail_node"])
        except (KeyError, TypeError, ValueError):
            continue
        if rail_node not in rail_graph.nodes:
            continue
        nodes_by_station.setdefault(name, set()).add(rail_node)

    added_edges = 0
    for name, nodes in nodes_by_station.items():
        node_list = sorted(nodes)
        if len(node_list) < 2:
            continue

        for i, node_a in enumerate(node_list):
            for node_b in node_list[i + 1:]:
                lat_a = float(rail_graph.nodes[node_a]["y"])
                lon_a = float(rail_graph.nodes[node_a]["x"])
                lat_b = float(rail_graph.nodes[node_b]["y"])
                lon_b = float(rail_graph.nodes[node_b]["x"])
                transfer_length = _haversine_meters(lat_a, lon_a, lat_b, lon_b)
                if transfer_length > max_transfer_m:
                    continue

                attrs = {
                    "length": transfer_length,
                    "transfer": True,
                    "name": f"{name} transfer",
                }
                rail_graph.add_edge(node_a, node_b, **attrs)
                rail_graph.add_edge(node_b, node_a, **attrs)
                added_edges += 2

    return added_edges


def remove_non_passenger_subway_edges(rail_graph) -> int:
    """Remove service/yard subway tracks that are not passenger route segments."""
    blocked_services = {"yard", "siding", "spur", "crossover"}
    edges_to_remove = []

    for u, v, key, attrs in rail_graph.edges(keys=True, data=True):
        if attrs.get("transfer") is True:
            continue

        service = str(attrs.get("service") or "").strip().lower()
        name = str(attrs.get("name") or "").strip().lower()
        if service in blocked_services or "betriebstrecke" in name:
            edges_to_remove.append((u, v, key))

    rail_graph.remove_edges_from(edges_to_remove)
    return len(edges_to_remove)


def save_station_nodes(station_nodes: List[int], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"station_nodes": station_nodes}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_station_nodes(file_path: str) -> List[int]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = payload.get("station_nodes", [])
        return [int(node) for node in nodes]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def save_station_records(station_records: List[StationRecord], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"station_records": station_records}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_station_records(file_path: str) -> List[StationRecord]:
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []

    raw_records = payload.get("station_records")
    if not isinstance(raw_records, list):
        # Old cache format only contains drive nodes, so force rebuild.
        return []

    records = []
    for row in raw_records:
        if not isinstance(row, dict):
            continue
        try:
            record = {
                "name": str(row.get("name") or "Station"),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "rail_node": int(row["rail_node"]),
            }

            for key in ("access_node", "walk_node", "drive_node"):
                if key in row:
                    record[key] = int(row[key])

            records.append(record)
        except (KeyError, TypeError, ValueError):
            continue

    return records
