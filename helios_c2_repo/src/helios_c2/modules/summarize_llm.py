from __future__ import annotations

import os
from typing import Dict, Iterable, List, Tuple


def _round_pct(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.0f}%"


def _collect_detections(events: Iterable[dict]) -> List[dict]:
    found: List[dict] = []
    for event in events or []:
        props = event.get("properties", {}) or {}
        for det in props.get("detections", []) or []:
            found.append(det)
    return found


def _top_item(items: Iterable[dict], score_key: str) -> dict | None:
    items_list = [item for item in items if isinstance(item, dict)]
    if not items_list:
        return None
    return max(items_list, key=lambda item: float(item.get(score_key, 0.0)))


def _llm_enhance_summary(
    case_id: str,
    summary_bits: List[str],
    transcript_excerpt: str,
    geoline: str,
    timestamp: str,
) -> str:
    """Generate LLM-enhanced narrative summary if available."""
    # Check if LLM enhancement is enabled
    if os.getenv("ARES_LLM_MODE", "stub") == "stub":
        # Use template-based summary
        summary_sentence = "; ".join(summary_bits) if summary_bits else (
            "Automated sensors reported activity with no dominant signals."
        )
        return f"At {timestamp} near {geoline}, {summary_sentence}."
    
    try:
        from .worker.llm import llm_summarize
        
        # Prepare data for LLM
        data_points = "\n".join(f"- {bit}" for bit in summary_bits) if summary_bits else "No specific detections"
        context = f"Case: {case_id}\nLocation: {geoline}\nTime: {timestamp}\nTranscript: {transcript_excerpt}"
        
        enhanced = llm_summarize(
            text=f"Sensor findings:\n{data_points}",
            context=context,
        )
        return enhanced
    except Exception:
        # Fall back to template-based summary
        summary_sentence = "; ".join(summary_bits) if summary_bits else (
            "Automated sensors reported activity with no dominant signals."
        )
        return f"At {timestamp} near {geoline}, {summary_sentence}."


def _llm_enhance_explainability(explainability: dict | None) -> List[str]:
    """Generate LLM-enhanced explainability narrative."""
    if not explainability:
        return []
    
    drivers = explainability.get("top_drivers", []) or []
    if not drivers:
        return []
    
    lines: List[str] = []
    
    # Check if LLM enhancement is enabled
    if os.getenv("ARES_LLM_MODE", "stub") != "stub":
        try:
            from .worker.llm import llm_generate
            
            # Build prompt for natural language explanation
            driver_text = []
            for axis in drivers:
                if axis:
                    primary = axis[0]
                    driver_text.append(
                        f"{primary['feature']}: weight={primary['weight']:.2f}, contribution={primary['contribution']:.2f}"
                    )
            
            if driver_text:
                prompt = (
                    "Explain why this alert was triggered based on these factors:\n"
                    + "\n".join(driver_text)
                    + "\n\nProvide a concise, factual explanation for a law enforcement reviewer:"
                )
                explanation = llm_generate(prompt, max_tokens=150, temperature=0.2)
                lines.append(explanation)
                return lines
        except Exception:
            pass  # Fall back to template-based
    
    # Template-based explainability
    for axis in drivers:
        if not axis:
            continue
        primary = axis[0]
        lines.append(
            f"- Primary driver: {primary['feature']} (weight {primary['weight']:.2f}, contribution {primary['contribution']:.2f})"
        )
    
    return lines


def make_report(case_id: str, scene: dict, analytics: dict | None = None, explainability: dict | None = None) -> str:
    events = scene.get("events", [])
    actions = scene.get("actions", []) or []
    sounds = scene.get("sounds", []) or []
    detections = _collect_detections(events)
    transcript = scene.get("asr", {}).get("segments", [])
    thermal_info = scene.get("thermal", {}) or {}
    thermal_summary = thermal_info.get("summary", {}) or {}
    thermal_frames = list(thermal_info.get("frames", []))

    lines = [f"# Incident {case_id}", ""]

    if not events:
        lines.append("No events detected.")
        return "\n".join(lines)

    first_event = events[0]
    location = first_event.get("location", {}) or {}
    primary_det = _top_item(detections, "confidence")
    primary_action = _top_item(actions, "confidence")
    primary_sound = _top_item(sounds, "confidence") or (sounds[0] if sounds else None)
    transcript_excerpt = transcript[0]["text"] if transcript else "No voice traffic captured."

    summary_bits: List[str] = []
    if primary_det:
        summary_bits.append(
            f"vision flagged a {primary_det.get('label', 'subject')} with {_round_pct(primary_det.get('confidence'))} confidence"
        )
    if primary_action:
        summary_bits.append(
            f"motion analysis suggests {primary_action.get('label', 'unspecified action').replace('_', ' ')}"
        )
    if primary_sound:
        summary_bits.append(f"audio cues included {primary_sound.get('label', 'ambient_noise').replace('_', ' ')}")
    if thermal_summary:
        summary_bits.append(
            f"thermal scan highlighted {thermal_summary.get('top_label', 'ambient patterns').replace('_', ' ')}"
        )

    geoline = "Location unknown"
    if location:
        lat = location.get("lat")
        lon = location.get("lon")
        geoline = f"Lat {lat:.5f}, Lon {lon:.5f}" if lat is not None and lon is not None else "Location withheld"

    lines.append("## Executive summary")
    # Use LLM-enhanced summary if available
    enhanced_summary = _llm_enhance_summary(
        case_id=case_id,
        summary_bits=summary_bits,
        transcript_excerpt=transcript_excerpt,
        geoline=geoline,
        timestamp=first_event.get('ts', 'unknown time'),
    )
    lines.append(enhanced_summary)
    lines.append(f"First radio transcript: {transcript_excerpt}")

    lines.append("\n## Event timeline")
    for ev in events:
        lat = ev.get("location", {}).get("lat")
        lon = ev.get("location", {}).get("lon")
        lat_str = f"{lat:.5f}" if lat is not None else "n/a"
        lon_str = f"{lon:.5f}" if lon is not None else "n/a"
        lines.append(f"- **{ev['event_type']}** at {ev['ts']} (lat {lat_str}, lon {lon_str})")

    sensor_sections: List[Tuple[str, List[str]]] = []
    if primary_det:
        sensor_sections.append(
            (
                "Vision",
                [
                    f"Primary classification: {primary_det.get('label', 'subject')} {_round_pct(primary_det.get('confidence'))}",
                    f"Bounding box (normalized): {primary_det.get('bbox', ['n/a'] * 4)}",
                ],
            )
        )
    if primary_action:
        features = primary_action.get("features", {}) or {}
        sensor_sections.append(
            (
                "Action",
                [
                    f"Top pattern: {primary_action.get('label', 'unspecified').replace('_', ' ')} {_round_pct(primary_action.get('confidence'))}",
                    "Motion stats: "
                    + ", ".join(
                        f"{key}={value:.3f}" for key, value in features.items()
                    ),
                ],
            )
        )
    if sounds:
        sensor_sections.append(
            (
                "Audio",
                [
                    f"Detected cues: {', '.join(sound.get('label', 'unknown').replace('_', ' ') for sound in sounds)}",
                ],
            )
        )

    if thermal_frames:
        top_thermal = thermal_summary.get("top_label") or (thermal_frames[0].get("label") if thermal_frames else None)
        sensor_sections.append(
            (
                "Thermal/IR",
                [
                    f"Dominant signature: {top_thermal or 'ambient'} {_round_pct(thermal_summary.get('max_probability', 0.0))}",
                    f"Hotspot coverage: {thermal_summary.get('hotspot_ratio_mean', 0.0):.2f}",
                    f"Sample frames: {', '.join(str(frame.get('frame')) for frame in thermal_frames[:3])}",
                ],
            )
        )

    if sensor_sections:
        lines.append("\n## Sensor highlights")
        for title, bullet_lines in sensor_sections:
            lines.append(f"### {title}")
            for item in bullet_lines:
                lines.append(f"- {item}")

    if analytics:
        hotspots = analytics.get("hotspots", {}).get("hotspots", []) or []
        convoy = analytics.get("convoys", {}).get("detections", []) or []
        persistent = analytics.get("persistent_surveillance", {}).get("orchestrations", []) or []

        if hotspots or convoy or persistent:
            lines.append("\n## Analytics insights")
        if hotspots:
            top = hotspots[0]
            lines.append(
                f"- Most active hotspot at ({top.get('lat')}, {top.get('lon')}) during {top.get('time_window')} with {top.get('count')} alerts."
            )
        if convoy:
            for det in convoy:
                lines.append(
                    f"- Convoy of {det['size']} vehicles from {det['start']} to {det['end']} (evidence: {', '.join(det['evidence'])})."
                )
        if persistent:
            for item in persistent[:3]:
                lines.append(
                    f"- Anchor {item['anchor_event']} at {item['anchor_sensor']} correlates with {len(item['related'])} supporting detections."
                )
        thermal_bundle = analytics.get("thermal", {}) or {}
        thermal_summary_payload = thermal_bundle.get("summary", {}) or {}
        top_anomalies = thermal_bundle.get("top_anomalies", []) or []
        if thermal_summary_payload or top_anomalies:
            lines.append(
                f"- Thermal sweep peak probability {thermal_summary_payload.get('max_probability', 0.0):.2f} on frame {thermal_summary_payload.get('top_frame')} ({thermal_summary_payload.get('top_label', 'ambient')})."
            )
            if top_anomalies:
                lines.append(
                    f"- Top thermal anomalies: {', '.join(anom.get('label', 'ambient') for anom in top_anomalies[:3])}."
                )

    if explainability:
        drivers = explainability.get("top_drivers", []) or []
        if drivers:
            lines.append("\n## Explainability")
            # Use LLM-enhanced explainability
            enhanced_explain = _llm_enhance_explainability(explainability)
            lines.extend(enhanced_explain)

    models = scene.get("model_versions", []) or []
    
    # Add LLM provenance if using LLM mode
    if os.getenv("ARES_LLM_MODE", "stub") != "stub":
        try:
            from worker.llm import get_provider
            llm_prov = get_provider().get_provenance()
            models.append({
                "name": llm_prov.get("name", "sentinel-llm"),
                "ver": llm_prov.get("version", "1.0.0"),
            })
        except Exception:
            pass
    
    if models:
        lines.append("\n## Model provenance")
        for model in models:
            name = model.get("name", "unknown")
            version = model.get("ver", "n/a")
            lines.append(f"- {name} v{version}")

    return "\n".join(lines) + "\n"
