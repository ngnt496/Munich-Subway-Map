from pathlib import Path
import pickle

import osmnx as ox

from station_store import fetch_station_records_for_place, remove_non_passenger_subway_edges, save_station_records


PLACE_NAME = "Munich, Bavaria, Germany"
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
ACCESS_GRAPH_CACHE_FILE = CACHE_DIR / "munich_walk.graphml"
ACCESS_GRAPH_PICKLE_FILE = CACHE_DIR / "munich_walk.pkl"
RAIL_GRAPH_CACHE_FILE = CACHE_DIR / "munich_rail_unsimplified.graphml"
RAIL_GRAPH_PICKLE_FILE = CACHE_DIR / "munich_rail_unsimplified.pkl"
STATION_CACHE_FILE = CACHE_DIR / "munich_station_nodes_citywide.json"


def save_graph_pickle(graph, file_path):
    with Path(file_path).open("wb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Munich walk graph...")
    access_graph = ox.graph_from_place(
        PLACE_NAME,
        network_type="walk",
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(access_graph, ACCESS_GRAPH_CACHE_FILE)
    save_graph_pickle(access_graph, ACCESS_GRAPH_PICKLE_FILE)
    print(f"Saved walk graph cache: {ACCESS_GRAPH_CACHE_FILE}")

    print("Loading Munich rail graph...")
    rail_graph = ox.graph_from_place(
        PLACE_NAME,
        network_type="all",
        custom_filter='["railway"="subway"]',
        simplify=False,
        retain_all=True,
    )
    removed_edges = remove_non_passenger_subway_edges(rail_graph)
    print(f"Removed non-passenger subway service edges: {removed_edges}")
    ox.save_graphml(rail_graph, RAIL_GRAPH_CACHE_FILE)
    save_graph_pickle(rail_graph, RAIL_GRAPH_PICKLE_FILE)
    print(f"Saved rail graph cache: {RAIL_GRAPH_CACHE_FILE}")

    print("Loading Munich U-Bahn stations...")
    station_records = fetch_station_records_for_place(access_graph, rail_graph, PLACE_NAME)
    save_station_records(station_records, STATION_CACHE_FILE)
    print(f"Saved station cache: {STATION_CACHE_FILE} ({len(station_records)} stations)")


if __name__ == "__main__":
    main()
