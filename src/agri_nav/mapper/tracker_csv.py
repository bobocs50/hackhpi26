"""Map YOLO tracker CSV rows to agri-nav KinematicsEntity DTOs.

The tracker CSV format (one row per detection per frame):
    frame_idx, class_name, track_id, foot_x, foot_y,
    bbox_x1, bbox_y1, bbox_x2, bbox_y2

All pixel coordinates are converted to a vehicle-local metric frame where
the ego vehicle sits at the centre of the image (origin), x grows right,
and y grows upward (forward).  Pixel→metre conversion uses a configurable
``pixels_per_metre`` scale factor.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from agri_nav.dto.perception import EntityType, KinematicsEntity


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_PIXELS_PER_METRE = 50.0
"""Approximate scale: how many image pixels correspond to 1 real-world metre."""

DEFAULT_FPS = 10.0
"""Assumed frame rate of the input video for velocity estimation."""


# ---------------------------------------------------------------------------
# CSV → KinematicsEntity
# ---------------------------------------------------------------------------


def _pixel_to_vehicle(
    px: float,
    py: float,
    img_width: float,
    img_height: float,
    ppm: float,
) -> tuple[float, float]:
    """Convert pixel coords to vehicle-local metre coords.

    Origin = image centre.  x-right positive, y-up (forward) positive.
    """
    x_m = (px - img_width / 2.0) / ppm
    y_m = (img_height / 2.0 - py) / ppm   # flip y: pixel-down → metre-up
    return x_m, y_m


def parse_tracker_csv(
    csv_path: str | Path,
    img_width: float = 800.0,
    img_height: float = 600.0,
    pixels_per_metre: float = DEFAULT_PIXELS_PER_METRE,
    fps: float = DEFAULT_FPS,
) -> dict[int, list[KinematicsEntity]]:
    """Parse a multiclass tracking CSV and return entities grouped by frame.

    Returns ``{frame_idx: [KinematicsEntity, ...]}``.
    Velocity is estimated from consecutive-frame displacement for tracks
    that span at least two frames.
    """
    csv_path = Path(csv_path)
    dt = 1.0 / fps

    # ── 1. Read all rows ───────────────────────────────────────────────
    rows: list[dict] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # ── 2. Group by track_id to compute velocities ─────────────────────
    # {track_id: [(frame, x_m, y_m, cls, conf, bbox_w, bbox_h)]}
    tracks: dict[int, list[tuple[int, float, float, str, float, float]]] = {}
    for row in rows:
        frame = int(row["frame_idx"])
        tid = int(row["track_id"])
        cls = row["class_name"]
        foot_x = float(row["foot_x"])
        foot_y = float(row["foot_y"])
        bbox_x1 = float(row["bbox_x1"])
        bbox_y1 = float(row["bbox_y1"])
        bbox_x2 = float(row["bbox_x2"])
        bbox_y2 = float(row["bbox_y2"])

        x_m, y_m = _pixel_to_vehicle(
            foot_x, foot_y, img_width, img_height, pixels_per_metre,
        )
        # Entity extent (half-size in metres) from bbox
        ext_x = abs(bbox_x2 - bbox_x1) / (2.0 * pixels_per_metre)
        ext_y = abs(bbox_y2 - bbox_y1) / (2.0 * pixels_per_metre)

        tracks.setdefault(tid, []).append((frame, x_m, y_m, cls, ext_x, ext_y))

    # Sort each track by frame
    for tid in tracks:
        tracks[tid].sort(key=lambda t: t[0])

    # ── 3. Build per-frame entity lists with velocity ──────────────────
    # For each track at each frame, velocity = displacement / dt from
    # the previous frame (or 0 if first appearance).
    per_frame: dict[int, list[KinematicsEntity]] = {}

    for tid, pts in tracks.items():
        track_age = 0
        for i, (frame, x, y, cls, ext_x, ext_y) in enumerate(pts):
            if i == 0:
                vx, vy = 0.0, 0.0
            else:
                prev_frame, prev_x, prev_y = pts[i - 1][0], pts[i - 1][1], pts[i - 1][2]
                frame_gap = frame - prev_frame
                if frame_gap > 0:
                    vx = (x - prev_x) / (frame_gap * dt)
                    vy = (y - prev_y) / (frame_gap * dt)
                else:
                    vx, vy = 0.0, 0.0
            track_age += 1

            ent = KinematicsEntity(
                id=tid,
                cls=cls,
                x=round(x, 4),
                y=round(y, 4),
                vx=round(vx, 4),
                vy=round(vy, 4),
                detection_confidence=0.9,  # YOLO conf not in CSV; use default
                track_age=track_age,
                entity_type=EntityType.AREA if (ext_x > 0.2 or ext_y > 0.2) else EntityType.POINT,
                extent_x=round(ext_x, 4),
                extent_y=round(ext_y, 4),
            )
            per_frame.setdefault(frame, []).append(ent)

    return per_frame


def get_latest_frame_entities(
    csv_path: str | Path,
    img_width: float = 800.0,
    img_height: float = 600.0,
    pixels_per_metre: float = DEFAULT_PIXELS_PER_METRE,
    fps: float = DEFAULT_FPS,
) -> list[KinematicsEntity]:
    """Convenience: return KinematicsEntity list for the last frame only."""
    per_frame = parse_tracker_csv(csv_path, img_width, img_height, pixels_per_metre, fps)
    if not per_frame:
        return []
    last_frame = max(per_frame.keys())
    return per_frame[last_frame]
