import networkx as nx

from .entity_store import EntityStore


def build_pattern_graph(store: EntityStore) -> nx.DiGraph:
    """Build a directed graph of entity movements between cameras."""
    G = nx.DiGraph()
    for profile in store.get_all_profiles():
        G.add_node(profile.entity_id, type="entity")
        sorted_obs = sorted(profile.observations, key=lambda o: o.timestamp)
        for obs in sorted_obs:
            cam_node = f"cam:{obs.camera_id}"
            if cam_node not in G:
                G.add_node(cam_node, type="camera")
            G.add_edge(profile.entity_id, cam_node, timestamp=obs.timestamp)

        for prev, curr in zip(sorted_obs, sorted_obs[1:]):
            if prev.camera_id != curr.camera_id:
                edge_key = (f"cam:{prev.camera_id}", f"cam:{curr.camera_id}")
                if not G.has_edge(*edge_key):
                    G.add_edge(*edge_key, count=0)
                G[edge_key[0]][edge_key[1]]["count"] += 1
    return G
