# Data Model

## Domains

Helios supports the following domains out of the box:

- air
- land
- sea
- subsea
- space
- cyber
- human
- facility

Domains are simple strings in this reference implementation.

## Core Types

### SensorReading

- `id`: string
- `sensor_id`: string
- `domain`: string
- `source_type`: e.g. "radar", "eo_ir", "radio", "log"
- `ts_ms`: integer UTC timestamp in ms
- `geo`: optional { lat, lon }
- `details`: free-form dict

### EntityTrack

- `id`: string
- `domain`: string
- `label`: short name
- `attributes`: dict
- `last_seen_ms`: integer

### Event

- `id`: string
- `category`: string (e.g. "threat", "safety", "intel", "status")
- `severity`: string ("info","notice","warning","critical")
- `status`: string ("open","acked","in_progress","resolved")
- `domain`: string or "multi"
- `summary`: human-readable text
- `time_window`: { start_ms, end_ms }
- `entities`: list of entity IDs
- `sources`: list of sensor IDs
- `tags`: list of strings

### TaskRecommendation

- `id`: string
- `event_id`: string
- `action`: string ("investigate","intercept","notify","ignore")
- `assignee_domain`: string
- `priority`: int (1 highest)
- `rationale`: human-readable text
- `confidence`: float 0..1
