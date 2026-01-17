from __future__ import annotations
from collections import deque
from typing import Deque, Dict, List, Tuple
import json
import time
from pathlib import Path

from ..types import PlatformCommand, LinkState


class PlatformCommandQueue:
    """In-memory command queue with optional persistence.

    This stub simulates degraded comms by allowing deferred send attempts
    based on LinkState availability. Persistence is best-effort to a JSONL file
    so runs can emulate edge/offline replay.
    """

    def __init__(self, persist_path: str | None = None):
        self.queue: Deque[PlatformCommand] = deque()
        self.persist_path = Path(persist_path) if persist_path else None
        if self.persist_path and self.persist_path.exists():
            self._load()

    def enqueue(self, cmd: PlatformCommand) -> None:
        self.queue.append(cmd)
        self._persist(cmd)

    def attempt_send(self, link_states: Dict[str, LinkState]) -> Tuple[List[PlatformCommand], List[PlatformCommand]]:
        sent: List[PlatformCommand] = []
        deferred: List[PlatformCommand] = []
        size = len(self.queue)
        for _ in range(size):
            cmd = self.queue.popleft()
            link = link_states.get(cmd.target)
            if link and link.available:
                cmd.status = "sent"
                sent.append(cmd)
            else:
                cmd.status = "deferred"
                deferred.append(cmd)
                self.queue.append(cmd)
        return sent, deferred

    def _persist(self, cmd: PlatformCommand) -> None:
        if not self.persist_path:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(cmd.__dict__)
            with self.persist_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _load(self) -> None:
        try:
            for line in self.persist_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                cmd = PlatformCommand(
                    id=raw.get("id", f"cmd_{time.time()}"),
                    target=raw.get("target", "unknown"),
                    command=raw.get("command", "noop"),
                    args=raw.get("args", {}),
                    phase=raw.get("phase"),
                    priority=int(raw.get("priority", 3)),
                    status=raw.get("status", "queued"),
                    intent_id=raw.get("intent_id"),
                    playbook_action_id=raw.get("playbook_action_id"),
                    link_window_required=bool(raw.get("link_window_required", False)),
                    metadata=raw.get("metadata", {}),
                    asset_id=raw.get("asset_id"),
                    domain=raw.get("domain"),
                    route=raw.get("route") or [],
                    link_state=raw.get("link_state"),
                )
                self.queue.append(cmd)
        except Exception:
            self.queue = deque()
