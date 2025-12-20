from __future__ import annotations

"""In-memory demo watchlist store for module adapters."""

from typing import Dict, List

_watchlist: List[Dict[str, object]] = []


def init_db():  # no-op for in-memory
    _watchlist.clear()


def upsert_person(id: str, source: str, name: str, metadata: Dict[str, object], face_embedding, voice_embedding, gait_embedding, soft_biometrics, created_at: str):
    # replace if exists
    for idx, row in enumerate(_watchlist):
        if row.get("id") == id:
            _watchlist[idx] = {
                "id": id,
                "source": source,
                "name": name,
                "metadata": metadata,
                "face_embedding": face_embedding,
                "voice_embedding": voice_embedding,
                "gait_embedding": gait_embedding,
                "soft_biometrics": soft_biometrics,
                "created_at": created_at,
            }
            return
    _watchlist.append(
        {
            "id": id,
            "source": source,
            "name": name,
            "metadata": metadata,
            "face_embedding": face_embedding,
            "voice_embedding": voice_embedding,
            "gait_embedding": gait_embedding,
            "soft_biometrics": soft_biometrics,
            "created_at": created_at,
        }
    )


def fetch_all() -> List[Dict[str, object]]:
    return list(_watchlist)
