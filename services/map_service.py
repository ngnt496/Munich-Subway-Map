"""Dịch vụ nạp dữ liệu đồ thị bản đồ, các ga và ranh giới hành chính từ cache hoặc OpenStreetMap."""

from pathlib import Path
import pickle
from typing import List, Tuple
import geopandas as gpd
import osmnx as ox
import pandas as pd

import config
from services.station_store import (
    add_station_transfer_edges,
    fetch_station_records_for_place,
    load_station_records,
    remove_non_passenger_subway_edges,
    save_station_records,
)


class MapService:
    def __init__(self):
        self.place_name = config.PLACE_NAME
        self.center_lat = config.DEFAULT_CENTER_LAT
        self.center_lon = config.DEFAULT_CENTER_LON

        # Graph objects
        self.G_access = None
        self.G_rail = None
        self.station_records = []
        self.neighbor_boundaries_gdf = None

    def initialize_data(self):
        """Khởi tạo toàn bộ dữ liệu đồ thị mạng lưới đường bộ, đường sắt và các ga U-Bahn."""
        print("Loading Munich walk graph...")
        self.G_access = self._load_access_graph()

        print("Loading Munich rail graph...")
        self.G_rail = self._load_rail_graph()
        removed_edges = remove_non_passenger_subway_edges(self.G_rail)
        print(f"Removed {removed_edges} non-passenger subway service edges.")

        self._set_map_center_from_graph(self.G_access)

        print("Loading Munich U-Bahn stations...")
        self.station_records = load_station_records(config.STATION_CACHE_FILE)
        if not self.station_records:
            # Fallback nếu ở cache cũ views/cache
            legacy_cache = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_station_nodes_citywide.json"
            if legacy_cache.exists():
                self.station_records = load_station_records(legacy_cache)

        if not self.station_records:
            self.station_records = fetch_station_records_for_place(self.G_access, self.G_rail, self.place_name)
            save_station_records(self.station_records, config.STATION_CACHE_FILE)

        print(f"Loaded {len(self.station_records)} U-Bahn stations.")
        transfer_edges = add_station_transfer_edges(self.G_rail, self.station_records)
        print(f"Added {transfer_edges} internal U-Bahn station transfer edges.")

        return self.G_access, self.G_rail, self.station_records

    def _load_graph_pickle(self, pickle_path: Path):
        with Path(pickle_path).open("rb") as file:
            return pickle.load(file)

    def _save_graph_pickle(self, graph, pickle_path: Path):
        path = Path(pickle_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    def _load_access_graph(self):
        cache_path = Path(config.ACCESS_GRAPH_CACHE_FILE)
        pickle_path = Path(config.ACCESS_GRAPH_PICKLE_FILE)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Check views/cache fallback if root cache not generated yet
        views_pickle = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_walk.pkl"
        views_graphml = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_walk.graphml"

        if pickle_path.exists():
            print("Reading walk graph from fast pickle cache...")
            return self._load_graph_pickle(pickle_path)
        if views_pickle.exists():
            print("Reading walk graph from views pickle cache...")
            return self._load_graph_pickle(views_pickle)

        if cache_path.exists():
            print("Reading walk graph from GraphML cache...")
            graph = ox.load_graphml(cache_path)
            self._save_graph_pickle(graph, pickle_path)
            return graph
        if views_graphml.exists():
            print("Reading walk graph from views GraphML cache...")
            graph = ox.load_graphml(views_graphml)
            self._save_graph_pickle(graph, pickle_path)
            return graph

        print("No cache found, downloading walk graph from OpenStreetMap...")
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
            legacy_path = Path(config.LEGACY_DRIVE_GRAPH_CACHE_FILE)
            if legacy_path.exists():
                print(f"Cannot download walk graph ({exc}). Fallback to legacy drive graph.")
                return ox.load_graphml(legacy_path)
            raise

    def _load_rail_graph(self):
        cache_path = Path(config.RAIL_GRAPH_CACHE_FILE)
        pickle_path = Path(config.RAIL_GRAPH_PICKLE_FILE)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        views_pickle = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_rail_unsimplified.pkl"
        views_graphml = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_rail_unsimplified.graphml"

        if pickle_path.exists():
            print("Reading rail graph from fast pickle cache...")
            return self._load_graph_pickle(pickle_path)
        if views_pickle.exists():
            print("Reading rail graph from views pickle cache...")
            return self._load_graph_pickle(views_pickle)

        if cache_path.exists():
            print("Reading rail graph from GraphML cache...")
            graph = ox.load_graphml(cache_path)
            self._save_graph_pickle(graph, pickle_path)
            return graph
        if views_graphml.exists():
            print("Reading rail graph from views GraphML cache...")
            graph = ox.load_graphml(views_graphml)
            self._save_graph_pickle(graph, pickle_path)
            return graph

        print("No cache found, downloading rail graph from OpenStreetMap...")
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

    def load_neighbor_boundaries(self) -> gpd.GeoDataFrame:
        """Nạp dữ liệu ranh giới địa lý của Munich và các thành phố xung quanh."""
        if self.neighbor_boundaries_gdf is not None:
            return self.neighbor_boundaries_gdf

        cache_path = Path(config.BOUNDARY_CACHE_FILE)
        views_cache = Path(__file__).resolve().parent.parent / "views" / "cache" / "munich_neighbor_boundaries.geojson"
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        target_cache = cache_path if cache_path.exists() else (views_cache if views_cache.exists() else None)
        if target_cache and target_cache.exists():
            try:
                self.neighbor_boundaries_gdf = gpd.read_file(target_cache)
                return self.neighbor_boundaries_gdf
            except Exception:
                pass

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
                print(f"Cannot load boundary for {place}: {exc}")

        if not rows:
            self.neighbor_boundaries_gdf = gpd.GeoDataFrame()
            return self.neighbor_boundaries_gdf

        merged = gpd.GeoDataFrame(
            pd.concat(rows, ignore_index=True),
            geometry="geometry",
            crs=rows[0].crs,
        )

        try:
            merged.to_file(cache_path, driver="GeoJSON")
        except Exception as exc:
            print(f"Cannot save boundary cache: {exc}")

        self.neighbor_boundaries_gdf = merged
        return merged

    def _set_map_center_from_graph(self, graph):
        nodes = list(graph.nodes)
        if not nodes:
            return

        sample = nodes[: min(3000, len(nodes))]
        lat_avg = sum(graph.nodes[n]["y"] for n in sample) / len(sample)
        lon_avg = sum(graph.nodes[n]["x"] for n in sample) / len(sample)
        self.center_lat = lat_avg
        self.center_lon = lon_avg

    def find_nearest_node(self, lat: float, lon: float, graph_type: str = "access") -> int:
        """Tìm node gần nhất trong đồ thị (đi bộ hoặc đường sắt) dựa vào tọa độ lat/lon."""
        target_graph = self.G_access if graph_type == "access" else self.G_rail
        if target_graph is None:
            raise ValueError(f"Graph '{graph_type}' is not initialized.")
        return int(ox.nearest_nodes(target_graph, lon, lat))
