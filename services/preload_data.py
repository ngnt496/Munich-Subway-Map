import sys
from pathlib import Path
import pickle
import osmnx as ox
import geopandas as gpd
import pandas as pd

# Cho phép chạy trực tiếp: python services/preload_data.py
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Cấu hình UTF-8 an toàn cho console Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from services.station_store import (
    fetch_station_records_for_place,
    remove_non_passenger_subway_edges,
    save_station_records,
)

# Cấu hình OSMnx tối ưu đường truyền
ox.settings.requests_timeout = 300
ox.settings.use_cache = True
ox.settings.cache_folder = str(config.CACHE_DIR)


def save_graph_pickle(graph, file_path):
    with Path(file_path).open("wb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)


def preload_neighbor_boundaries(force=False):
    if not force and config.BOUNDARY_CACHE_FILE.exists():
        print(f"[CACHE] Neighbor boundaries already exist: {config.BOUNDARY_CACHE_FILE}", flush=True)
        return

    print("Loading neighbor boundaries...", flush=True)
    rows = []
    for place in config.BOUNDARY_PLACES:
        try:
            gdf = ox.geocode_to_gdf(place)
            if gdf.empty:
                continue
            row = gdf.iloc[[0]].copy()
            row["place_name"] = place
            rows.append(row)
        except Exception as exc:
            print(f"Warning: Cannot load boundary for {place}: {exc}", flush=True)

    if rows:
        merged = gpd.GeoDataFrame(
            pd.concat(rows, ignore_index=True),
            geometry="geometry",
            crs=rows[0].crs,
        )
        merged.to_file(config.BOUNDARY_CACHE_FILE, driver="GeoJSON")
        print(f"Saved boundaries cache: {config.BOUNDARY_CACHE_FILE}", flush=True)


def download_graph_with_fallback(place_name, network_type, custom_filter=None, simplify=True, retain_all=False):
    """Tải đồ thị OSMnx có hỗ trợ tự động đổi server Overpass dự phòng nếu server chính quá tải (502/504)."""
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    for endpoint in endpoints:
        ox.settings.overpass_url = endpoint
        try:
            print(f"Attempting download via Overpass endpoint: {endpoint}...", flush=True)
            if custom_filter:
                return ox.graph_from_place(
                    place_name,
                    network_type=network_type,
                    custom_filter=custom_filter,
                    simplify=simplify,
                    retain_all=retain_all,
                )
            else:
                return ox.graph_from_place(
                    place_name,
                    network_type=network_type,
                    simplify=simplify,
                    retain_all=retain_all,
                )
        except Exception as exc:
            print(f"Endpoint {endpoint} failed ({exc}). Retrying next endpoint...", flush=True)

    raise RuntimeError("All Overpass API servers are currently busy or down. Please use the existing cache files.")


def main():
    force = "--force" in sys.argv
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Mạng lưới đường đi bộ
    access_graph = None
    if not force and (config.ACCESS_GRAPH_PICKLE_FILE.exists() or config.ACCESS_GRAPH_CACHE_FILE.exists()):
        print(f"[CACHE] Walk graph cache already exists ({config.ACCESS_GRAPH_PICKLE_FILE}). Skipping download.", flush=True)
    else:
        print("Downloading Munich walk graph from OpenStreetMap...", flush=True)
        access_graph = download_graph_with_fallback(
            config.PLACE_NAME,
            network_type="walk",
            simplify=True,
            retain_all=False,
        )
        ox.save_graphml(access_graph, config.ACCESS_GRAPH_CACHE_FILE)
        save_graph_pickle(access_graph, config.ACCESS_GRAPH_PICKLE_FILE)
        print(f"Saved walk graph cache: {config.ACCESS_GRAPH_CACHE_FILE}", flush=True)

    # 2. Mạng lưới đường ray tàu điện ngầm
    rail_graph = None
    if not force and (config.RAIL_GRAPH_PICKLE_FILE.exists() or config.RAIL_GRAPH_CACHE_FILE.exists()):
        print(f"[CACHE] Rail graph cache already exists ({config.RAIL_GRAPH_PICKLE_FILE}). Skipping download.", flush=True)
    else:
        print("Downloading Munich rail graph from OpenStreetMap...", flush=True)
        rail_graph = download_graph_with_fallback(
            config.PLACE_NAME,
            network_type="all",
            custom_filter='["railway"="subway"]',
            simplify=False,
            retain_all=True,
        )
        removed_edges = remove_non_passenger_subway_edges(rail_graph)
        print(f"Removed non-passenger subway service edges: {removed_edges}", flush=True)
        ox.save_graphml(rail_graph, config.RAIL_GRAPH_CACHE_FILE)
        save_graph_pickle(rail_graph, config.RAIL_GRAPH_PICKLE_FILE)
        print(f"Saved rail graph cache: {config.RAIL_GRAPH_CACHE_FILE}", flush=True)

    # 3. Dữ liệu các ga U-Bahn
    if not force and config.STATION_CACHE_FILE.exists():
        print(f"[CACHE] Station cache already exists: {config.STATION_CACHE_FILE}", flush=True)
    else:
        if access_graph is None:
            if config.ACCESS_GRAPH_PICKLE_FILE.exists():
                with open(config.ACCESS_GRAPH_PICKLE_FILE, "rb") as f:
                    access_graph = pickle.load(f)
            else:
                access_graph = ox.load_graphml(config.ACCESS_GRAPH_CACHE_FILE)
        if rail_graph is None:
            if config.RAIL_GRAPH_PICKLE_FILE.exists():
                with open(config.RAIL_GRAPH_PICKLE_FILE, "rb") as f:
                    rail_graph = pickle.load(f)
            else:
                rail_graph = ox.load_graphml(config.RAIL_GRAPH_CACHE_FILE)

        print("Loading Munich U-Bahn stations...", flush=True)
        station_records = fetch_station_records_for_place(access_graph, rail_graph, config.PLACE_NAME)
        save_station_records(station_records, config.STATION_CACHE_FILE)
        print(f"Saved station cache: {config.STATION_CACHE_FILE} ({len(station_records)} stations)", flush=True)

    # 4. Ranh giới các vùng lân cận
    preload_neighbor_boundaries(force=force)

    print("\n>>> ALL DATA PRELOAD COMPLETED & CACHED SUCCESSFULLY! <<<", flush=True)
    print("You can now start the application with: python main.py", flush=True)


if __name__ == "__main__":
    main()
