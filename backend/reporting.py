import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parent.parent
MOCK_RUN_PATH = ROOT_DIR / "frontend" / "src" / "data" / "mockVisionRun.json"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")


def load_default_run() -> dict[str, Any]:
    with MOCK_RUN_PATH.open("r", encoding="utf-8") as mock_run_file:
        return json.load(mock_run_file)


def build_report_response(run: dict[str, Any]) -> dict[str, Any]:
    fallback = build_fallback_report(run)
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return {
            **fallback,
            "generated_by": "fallback",
            "fallback_used": True,
        }

    try:
        generated = call_claude(prompt=build_prompt(run), api_key=api_key)
    except Exception:
        return {
            **fallback,
            "generated_by": "fallback",
            "fallback_used": True,
        }

    return {
        "headline": generated.get("headline") or fallback["headline"],
        "body": generated.get("body") or fallback["body"],
        "metadata": fallback["metadata"],
        "generated_by": "claude",
        "fallback_used": False,
    }


def build_prompt(run: dict[str, Any]) -> str:
    frames = run.get("frames", [])
    first_frame = frames[0] if frames else None
    last_frame = frames[-1] if frames else None
    peak_frame = max(
        frames,
        key=lambda frame: frame.get("danger_reasoning", {}).get("score", 0),
        default=None,
    )
    prompt_payload = {
        "run_id": run.get("run_id"),
        "source": run.get("source", {}),
        "frame_count": len(frames),
        "duration_seconds": round((frames[-1]["timestamp_ms"] / 1000) if frames else 0, 1),
        "first_frame": summarize_frame(first_frame),
        "peak_frame": summarize_frame(peak_frame),
        "last_frame": summarize_frame(last_frame),
        "hazard_counts": count_labels(frames),
        "risk_counts": count_risk_levels(frames),
        "average_speed_factor": round(
            average([frame.get("steering", {}).get("speed_factor", 0) for frame in frames]),
            2,
        ),
        "average_uncertainty": round(
            average([frame.get("uncertainty", {}).get("overall", 0) for frame in frames]),
            2,
        ),
    }

    return (
        "You are writing a concise field-operation safety report for an internal AgriVision dashboard. "
        "Use only the provided run facts. Do not invent details. Keep the tone operational and clear.\n\n"
        "Return valid JSON with exactly two string fields: "
        '{"headline":"...", "body":"..."}.\n'
        "Headline: 6 to 12 words, plain and specific.\n"
        "Body: one short paragraph in natural language, about 90 to 140 words.\n\n"
        f"Run facts:\n{json.dumps(prompt_payload, ensure_ascii=True, indent=2)}"
    )


def call_claude(prompt: str, api_key: str) -> dict[str, str]:
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 300,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("Claude request failed") from exc

    text_parts = [
        block.get("text", "")
        for block in raw.get("content", [])
        if block.get("type") == "text"
    ]
    if not text_parts:
        raise RuntimeError("Claude returned no text content")

    try:
        parsed = json.loads("".join(text_parts))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Claude returned invalid JSON") from exc

    return {
        "headline": str(parsed.get("headline", "")).strip(),
        "body": str(parsed.get("body", "")).strip(),
    }


def build_fallback_report(run: dict[str, Any]) -> dict[str, Any]:
    frames = run.get("frames", [])
    metadata = build_metadata(run, frames)

    if not frames:
        return {
            "headline": "No report data available",
            "body": "The selected run does not contain any frames yet, so there is nothing to summarize.",
            "metadata": metadata,
        }

    first_frame = frames[0]
    last_frame = frames[-1]
    peak_frame = max(frames, key=lambda frame: frame["danger_reasoning"]["score"])
    hazard_counts = count_labels(frames)
    dominant_hazard = (
        sorted(hazard_counts.items(), key=lambda item: item[1], reverse=True)[0][0]
        if hazard_counts
        else "hazard"
    )
    risk_counts = count_risk_levels(frames)
    peak_time = format_seconds(peak_frame["timestamp_ms"])
    action = humanize_action(peak_frame["steering"]["recommended_action"]).lower()
    body = (
        f"The run begins with {normalize_sentence(first_frame['summary'])}. "
        f"Risk peaks at {peak_time} when {normalize_sentence(peak_frame['danger_reasoning']['primary_reason'])}. "
        f"At that point the system chooses {action} because "
        f"{normalize_sentence(peak_frame['danger_reasoning']['secondary_reason'])}. "
        f"The dominant hazard across the run is {dominant_hazard}, and the sequence ends with "
        f"{normalize_sentence(last_frame['summary'])}. "
        f"Overall risk distribution is {risk_counts['low']} low, {risk_counts['medium']} medium, "
        f"and {risk_counts['high']} high frames."
    )

    return {
        "headline": f"{capitalize(peak_frame['danger_reasoning']['level'])}-risk event at {peak_time}",
        "body": body,
        "metadata": metadata,
    }


def build_metadata(run: dict[str, Any], frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    source = run.get("source", {})
    duration_seconds = round((frames[-1]["timestamp_ms"] / 1000) if frames else 0, 1)
    return [
        {"label": "Folder", "value": source.get("folder_name", "Unknown")},
        {"label": "Captured", "value": format_captured_at(source.get("captured_at", "Unknown"))},
        {"label": "Location", "value": source.get("location_hint", "Unknown")},
        {"label": "Run Span", "value": f"{len(frames)} frames / {duration_seconds:.1f}s"},
        {
            "label": "Resolution",
            "value": f"{source.get('frame_width', 'Unknown')} x {source.get('frame_height', 'Unknown')}",
        },
    ]


def summarize_frame(frame: dict[str, Any] | None) -> dict[str, Any] | None:
    if not frame:
        return None

    return {
        "timestamp_seconds": round(frame.get("timestamp_ms", 0) / 1000, 1),
        "summary": frame.get("summary", ""),
        "annotations": [annotation.get("label", "") for annotation in frame.get("annotations", [])],
        "danger_level": frame.get("danger_reasoning", {}).get("level"),
        "danger_score": frame.get("danger_reasoning", {}).get("score"),
        "primary_reason": frame.get("danger_reasoning", {}).get("primary_reason"),
        "secondary_reason": frame.get("danger_reasoning", {}).get("secondary_reason"),
        "recommended_action": frame.get("steering", {}).get("recommended_action"),
        "steering_angle_deg": frame.get("steering", {}).get("steering_angle_deg"),
        "speed_factor": frame.get("steering", {}).get("speed_factor"),
    }


def count_labels(frames: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for frame in frames:
        for annotation in frame.get("annotations", []):
            label = annotation.get("label", "unknown")
            counts[label] = counts.get(label, 0) + 1

    return counts


def count_risk_levels(frames: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"low": 0, "medium": 0, "high": 0}

    for frame in frames:
        level = frame.get("danger_reasoning", {}).get("level", "low")
        if level in counts:
            counts[level] += 1

    return counts


def average(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def format_captured_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    return parsed.strftime("%m/%d/%Y, %I:%M:%S %p")


def format_seconds(timestamp_ms: int) -> str:
    return f"{timestamp_ms / 1000:.1f}s"


def normalize_sentence(value: str) -> str:
    return value.strip().rstrip(".").lower()


def capitalize(value: str) -> str:
    return value[:1].upper() + value[1:]


def humanize_action(value: str) -> str:
    return " ".join(capitalize(part) for part in value.split("_"))
