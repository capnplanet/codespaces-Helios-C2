from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    label: str
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    type: str
    props: Dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _node_id(prefix: str, raw_id: str) -> str:
    raw_id = str(raw_id)
    if raw_id.startswith(prefix + ":"):
        return raw_id
    return f"{prefix}:{raw_id}"


def _add_node(nodes_by_id: Dict[str, GraphNode], node: GraphNode) -> None:
    # Keep first-seen label/props for stability.
    if node.id not in nodes_by_id:
        nodes_by_id[node.id] = node


def _add_edge(edges_set: Set[Tuple[str, str, str]], edges: List[GraphEdge], edge: GraphEdge) -> None:
    key = (edge.source, edge.type, edge.target)
    if key in edges_set:
        return
    edges_set.add(key)
    edges.append(edge)


def build_ontology_graph(
    *,
    events: Optional[Iterable[Dict[str, Any]]] = None,
    tasks: Optional[Iterable[Dict[str, Any]]] = None,
    pending_tasks: Optional[Iterable[Dict[str, Any]]] = None,
    casebook: Optional[Dict[str, Any]] = None,
    entity_profiles: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a minimal node/edge graph from Helios outputs.

    This is intentionally dependency-free and best-effort; missing fields are
    tolerated.
    """

    nodes_by_id: Dict[str, GraphNode] = {}
    edges: List[GraphEdge] = []
    edge_keys: Set[Tuple[str, str, str]] = set()

    def add_event(ev: Dict[str, Any]) -> str:
        ev_id = _node_id("event", ev.get("id", "unknown"))
        _add_node(
            nodes_by_id,
            GraphNode(
                id=ev_id,
                type="event",
                label=str(ev.get("summary") or ev.get("category") or ev.get("id") or "event"),
                props={
                    "category": ev.get("category"),
                    "severity": ev.get("severity"),
                    "status": ev.get("status"),
                    "domain": ev.get("domain"),
                    "time_window": ev.get("time_window"),
                    "tags": ev.get("tags") or [],
                },
            ),
        )

        for ent in ev.get("entities") or []:
            ent_id = _node_id("entity", ent)
            _add_node(nodes_by_id, GraphNode(id=ent_id, type="entity", label=str(ent), props={}))
            _add_edge(edge_keys, edges, GraphEdge(source=ev_id, target=ent_id, type="MENTIONS"))

        for src in ev.get("sources") or []:
            src_id = _node_id("source", src)
            _add_node(nodes_by_id, GraphNode(id=src_id, type="source", label=str(src), props={}))
            _add_edge(edge_keys, edges, GraphEdge(source=ev_id, target=src_id, type="DERIVED_FROM"))

        for item in ev.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            evd_raw = item.get("id") or item.get("uri") or item.get("kind") or "evidence"
            evd_id = _node_id("evidence", evd_raw)
            _add_node(
                nodes_by_id,
                GraphNode(
                    id=evd_id,
                    type="evidence",
                    label=str(item.get("description") or item.get("uri") or evd_raw),
                    props={k: v for k, v in item.items() if k in {"kind", "uri", "description", "source", "tags"}},
                ),
            )
            _add_edge(edge_keys, edges, GraphEdge(source=ev_id, target=evd_id, type="SUPPORTED_BY"))

        return ev_id

    def add_task(t: Dict[str, Any], *, pending: bool) -> str:
        tid = _node_id("task", t.get("id", "unknown"))
        _add_node(
            nodes_by_id,
            GraphNode(
                id=tid,
                type="task" if not pending else "task_pending",
                label=str(t.get("action") or t.get("id") or "task"),
                props={
                    "event_id": t.get("event_id"),
                    "assignee_domain": t.get("assignee_domain"),
                    "priority": t.get("priority"),
                    "confidence": t.get("confidence"),
                    "status": t.get("status"),
                    "asset_id": t.get("asset_id"),
                    "infrastructure_type": t.get("infrastructure_type"),
                },
            ),
        )
        ev_id = t.get("event_id")
        if ev_id:
            ev_node = _node_id("event", ev_id)
            _add_node(nodes_by_id, GraphNode(id=ev_node, type="event", label=str(ev_id), props={}))
            _add_edge(edge_keys, edges, GraphEdge(source=tid, target=ev_node, type="RESPONDS_TO"))
        return tid

    for ev in events or []:
        if isinstance(ev, dict):
            add_event(ev)

    for t in tasks or []:
        if isinstance(t, dict):
            add_task(t, pending=False)

    for t in pending_tasks or []:
        if isinstance(t, dict):
            add_task(t, pending=True)

    # Casebook: cases/evidence/hypotheses
    if isinstance(casebook, dict):
        for c in casebook.get("cases") or []:
            if not isinstance(c, dict):
                continue
            cid = _node_id("case", c.get("id", "unknown"))
            _add_node(
                nodes_by_id,
                GraphNode(
                    id=cid,
                    type="case",
                    label=str(c.get("title") or c.get("id") or "case"),
                    props={
                        "status": c.get("status"),
                        "opened_at": c.get("opened_at"),
                        "domain": c.get("domain"),
                        "classification": c.get("classification"),
                    },
                ),
            )

        for e in casebook.get("evidence") or []:
            if not isinstance(e, dict):
                continue
            eid = _node_id("evidence", e.get("id", "unknown"))
            _add_node(
                nodes_by_id,
                GraphNode(
                    id=eid,
                    type="evidence",
                    label=str(e.get("description") or e.get("uri") or e.get("id") or "evidence"),
                    props={
                        "kind": e.get("kind"),
                        "source": e.get("source"),
                        "created_at": e.get("created_at"),
                        "uri": e.get("uri"),
                        "tags": e.get("tags") or [],
                        "classification": e.get("classification"),
                    },
                ),
            )
            for case_id in e.get("case_ids") or []:
                cid = _node_id("case", case_id)
                _add_node(nodes_by_id, GraphNode(id=cid, type="case", label=str(case_id), props={}))
                _add_edge(edge_keys, edges, GraphEdge(source=eid, target=cid, type="EVIDENCE_FOR"))

        for h in casebook.get("hypotheses") or []:
            if not isinstance(h, dict):
                continue
            hid = _node_id("hypothesis", h.get("id", "unknown"))
            _add_node(
                nodes_by_id,
                GraphNode(
                    id=hid,
                    type="hypothesis",
                    label=str(h.get("title") or h.get("id") or "hypothesis"),
                    props={
                        "status": h.get("status"),
                        "confidence": h.get("confidence"),
                        "created_at": h.get("created_at"),
                        "updated_at": h.get("updated_at"),
                        "classification": h.get("classification"),
                    },
                ),
            )
            for case_id in h.get("case_ids") or []:
                cid = _node_id("case", case_id)
                _add_node(nodes_by_id, GraphNode(id=cid, type="case", label=str(case_id), props={}))
                _add_edge(edge_keys, edges, GraphEdge(source=hid, target=cid, type="HYPOTHESIS_FOR"))
            for ev_id in h.get("evidence_ids") or []:
                eid = _node_id("evidence", ev_id)
                _add_node(nodes_by_id, GraphNode(id=eid, type="evidence", label=str(ev_id), props={}))
                _add_edge(edge_keys, edges, GraphEdge(source=hid, target=eid, type="SUPPORTED_BY"))

    # Entity profiles: connect entities to tracks and camera hints (if present)
    if isinstance(entity_profiles, dict):
        for ent in entity_profiles.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            entity_id = ent.get("entity_id")
            if not entity_id:
                continue
            nid = _node_id("entity", entity_id)
            _add_node(
                nodes_by_id,
                GraphNode(
                    id=nid,
                    type="entity",
                    label=str(entity_id),
                    props={
                        "track_id": ent.get("track_id"),
                        "domain": ent.get("domain"),
                        "label": ent.get("label"),
                    },
                ),
            )
            track_id = ent.get("track_id")
            if track_id:
                tid = _node_id("track", track_id)
                _add_node(nodes_by_id, GraphNode(id=tid, type="track", label=str(track_id), props={}))
                _add_edge(edge_keys, edges, GraphEdge(source=nid, target=tid, type="TRACKED_AS"))

            for obs in ent.get("observations") or []:
                if not isinstance(obs, dict):
                    continue
                cam = obs.get("camera")
                if cam:
                    cam_id = _node_id("camera", cam)
                    _add_node(nodes_by_id, GraphNode(id=cam_id, type="camera", label=str(cam), props={}))
                    _add_edge(edge_keys, edges, GraphEdge(source=nid, target=cam_id, type="OBSERVED_BY"))

    nodes = [asdict(n) for n in nodes_by_id.values()]
    edges_out = [asdict(e) for e in edges]

    return {
        "schema_version": "0.1",
        "generated_at": _now_iso(),
        "nodes": nodes,
        "edges": edges_out,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges_out),
            "node_types": sorted({n["type"] for n in nodes}),
            "edge_types": sorted({e["type"] for e in edges_out}),
        },
    }


def build_ontology_graph_from_out_dir(out_dir: Path) -> Dict[str, Any]:
    out_dir = Path(out_dir)
    events_payload = _safe_load_json(out_dir / "events.json") or {}
    casebook_payload = _safe_load_json(out_dir / "casebook.json")
    profiles_payload = _safe_load_json(out_dir / "entity_profiles.json")

    return build_ontology_graph(
        events=events_payload.get("events") or [],
        tasks=events_payload.get("tasks") or [],
        pending_tasks=events_payload.get("pending_tasks") or [],
        casebook=casebook_payload,
        entity_profiles=profiles_payload,
    )


def write_ontology_graph(
    *,
    out_dir: Path,
    events: Optional[Iterable[Any]] = None,
    tasks: Optional[Iterable[Any]] = None,
    pending_tasks: Optional[Iterable[Any]] = None,
    casebook_path: Optional[Path] = None,
    entity_profiles_path: Optional[Path] = None,
    graph_path: Optional[Path] = None,
) -> Path:
    """Write an ontology graph JSON file under the output directory.

    If `events`/`tasks` are provided as dataclass instances (e.g. `Event`), they
    will be coerced via `__dict__`.
    """

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def to_dicts(items: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []
        out: List[Dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict):
                out.append(it)
            else:
                out.append(getattr(it, "__dict__", {"value": str(it)}))
        return out

    if casebook_path is None:
        casebook_path = out_dir / "casebook.json"
    if entity_profiles_path is None:
        entity_profiles_path = out_dir / "entity_profiles.json"
    if graph_path is None:
        graph_path = out_dir / "graph.json"

    casebook_payload = _safe_load_json(Path(casebook_path))
    profiles_payload = _safe_load_json(Path(entity_profiles_path))

    graph = build_ontology_graph(
        events=to_dicts(events),
        tasks=to_dicts(tasks),
        pending_tasks=to_dicts(pending_tasks),
        casebook=casebook_payload,
        entity_profiles=profiles_payload,
    )

    graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return graph_path
