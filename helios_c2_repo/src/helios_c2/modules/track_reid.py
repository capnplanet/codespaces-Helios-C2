from __future__ import annotations


def track_and_reid(detections):
    tracked = []
    for index, det in enumerate(detections):
        tracked.append(
            {
                "frame": det.get("frame"),
                "track_id": f"track-{index:03d}",
                "detections": det.get("detections", []),
            }
        )
    return tracked
