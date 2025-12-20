from __future__ import annotations

from hashlib import sha256
from pathlib import Path

SAMPLE_TRANSCRIPTS = [
    {
        "lang": "en",
        "segments": [
            {"start": 0.0, "end": 4.5, "text": "Unit three observing individual placing rifle into trunk."},
            {"start": 4.6, "end": 8.2, "text": "Conversation references possible hand-off near service road."},
        ],
    },
    {
        "lang": "en",
        "segments": [
            {"start": 0.0, "end": 5.3, "text": "Convoy spacing holding two vehicles, speed twenty miles per hour."},
            {"start": 5.4, "end": 9.0, "text": "Command post requests confirmation on cargo securement."},
        ],
    },
    {
        "lang": "en",
        "segments": [
            {"start": 0.0, "end": 3.8, "text": "Patrol identifies hot spot on wharf, same suspects as last quarter."},
            {"start": 3.9, "end": 7.4, "text": "Audio picks mention of explosives training schedule."},
        ],
    },
]


def _select_index(path: Path) -> int:
    digest = sha256(str(path).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % len(SAMPLE_TRANSCRIPTS)


def transcribe(media_path: Path) -> dict:
    transcript = SAMPLE_TRANSCRIPTS[_select_index(media_path)]
    return transcript
