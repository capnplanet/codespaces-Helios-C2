import numpy as np, json, uuid, time
from .worker.storage.db import init_db, upsert_person, fetch_all
from pathlib import Path

# Initialize DB on import for demo simplicity
init_db()

def _cosine(a, b):
    if a is None or b is None: return None
    a = np.array(a); b = np.array(b)
    if np.linalg.norm(a)==0 or np.linalg.norm(b)==0: return 0.0
    return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b)))

# thresholds
FACE_THRESHOLD = 0.67   # demo
VOICE_THRESHOLD = 0.65  # demo
GAIT_THRESHOLD = 0.62   # demo

def match_face(embedding):
    candidates = fetch_all()
    best = None
    for c in candidates:
        score = _cosine(embedding, c["face_embedding"]) if c["face_embedding"] is not None else 0.0
        if best is None or score>best["score"]:
            best = {"row": c, "score": score}
    if best and best["score"]>=FACE_THRESHOLD:
        return {"match_id": best["row"]["id"], "name": best["row"]["name"], "score": best["score"], "type":"face"}
    return None

def match_voice(embedding):
    candidates = fetch_all()
    best = None
    for c in candidates:
        score = _cosine(embedding, c["voice_embedding"]) if c["voice_embedding"] is not None else 0.0
        if best is None or score>best["score"]:
            best = {"row": c, "score": score}
    if best and best["score"]>=VOICE_THRESHOLD:
        return {"match_id": best["row"]["id"], "name": best["row"]["name"], "score": best["score"], "type":"voice"}
    return None

def match_gait(embedding):
    candidates = fetch_all()
    best = None
    for c in candidates:
        score = _cosine(embedding, c["gait_embedding"]) if c.get("gait_embedding") is not None else 0.0
        if best is None or score>best["score"]:
            best = {"row": c, "score": score}
    if best and best["score"]>=GAIT_THRESHOLD:
        return {"match_id": best["row"]["id"], "name": best["row"]["name"], "score": best["score"], "type":"gait"}
    return None


def upsert_demo_person(name, source="demo", metadata=None, face_embedding=None, voice_embedding=None, gait_embedding=None, soft_biometrics=None):
    # create random small embeddings for demo
    fid = str(uuid.uuid4())
    fe = face_embedding if face_embedding is not None else np.random.randn(256).tolist()
    ve = voice_embedding if voice_embedding is not None else np.random.randn(256).tolist()
    ge = gait_embedding if gait_embedding is not None else np.random.randn(64).tolist()
    upsert_person(fid, source, name, metadata or {}, fe, ve, ge, soft_biometrics or {}, time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    return fid
