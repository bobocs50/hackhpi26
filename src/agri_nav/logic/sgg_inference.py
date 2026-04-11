"""Deterministic SGG inference using TTC (Time-To-Collision) heuristics.

Derives ``SemanticEntity`` (certainty ``c_i`` and danger quality ``q_i``)
from kinematics data without any learned weights.  This is the
zero-training-data baseline that feeds into the APF controller.

Formulas
--------
**Certainty** — combines YOLO detection confidence with ByteTrack track
maturity (a mature track is more certain than a freshly-spawned one):

    c_i = Conf_YOLO · (1 − e^(−λ · Age_track))

**Time-To-Collision** — relative closing speed projected onto the
ego→entity direction vector:

    TTC_i = dist / max(ε, −V_rel_towards_ego)

    If the entity is moving away, TTC → ∞ (no collision imminent).

**Danger Quality** — class-severity weight decayed by TTC:

    q_i = (W_class / W_max) · e^(−k · TTC_i)

    Normalised to [0, 1] by dividing by the maximum class weight.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from agri_nav.dto.perception import KinematicsEntity, SemanticEntity


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Hardcoded severity weights per YOLO class (higher = more dangerous)
DEFAULT_CLASS_WEIGHTS: dict[str, float] = {
    # Must-avoid
    "human": 100.0,
    "person": 100.0,
    "child": 100.0,
    # High danger
    "dog": 50.0,
    "deer": 60.0,
    "animal": 45.0,
    # Medium danger
    "tractor": 30.0,
    "vehicle": 30.0,
    "car": 35.0,
    # Low danger / crossable
    "bush": 5.0,
    "post": 3.0,
    "cone": 8.0,
    "rock": 6.0,
    "crop": -10.0,
    # Terrain hazards (not dynamic, but the machine must avoid them)
    "mud": 12.0,
    "ditch": 15.0,
    "puddle": 10.0,
}

DEFAULT_WEIGHT_UNKNOWN: float = 20.0


class SGGInferenceConfig(BaseModel):
    """Tuning knobs for the deterministic TTC-based SGG inference."""

    class_weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_CLASS_WEIGHTS),
        description="Severity weight per YOLO class label",
    )
    weight_unknown: float = Field(
        default=DEFAULT_WEIGHT_UNKNOWN,
        ge=0.0,
        description="Default weight for classes not in the lookup table",
    )
    lambda_track: float = Field(
        default=0.15,
        gt=0.0,
        description="Exponential maturity rate for track-age certainty",
    )
    k_ttc_decay: float = Field(
        default=0.5,
        gt=0.0,
        description="Exponential decay rate for TTC → danger quality",
    )
    v_rel_epsilon: float = Field(
        default=0.1,
        gt=0.0,
        description="Minimum closing speed to prevent TTC → ∞ division",
    )
    ego_vx: float = Field(
        default=0.0,
        description="Ego-vehicle lateral velocity [m/s]",
    )
    ego_vy: float = Field(
        default=0.0,
        description="Ego-vehicle forward velocity [m/s] (usually ≈ V_base)",
    )


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_certainty(
    detection_confidence: float,
    track_age: int,
    lambda_track: float,
) -> float:
    """Derive certainty c_i from YOLO confidence and track maturity.

    c_i = Conf_YOLO · (1 − e^(−λ · Age_track))
    """
    maturity = 1.0 - math.exp(-lambda_track * track_age)
    return detection_confidence * maturity


def compute_ttc(
    x: float,
    y: float,
    vx: float,
    vy: float,
    ego_vx: float,
    ego_vy: float,
    epsilon: float,
) -> float:
    """Compute Time-To-Collision between ego and entity.

    TTC = dist / max(ε, −V_rel_towards_ego)

    V_rel_towards_ego is the projection of the *relative* velocity
    onto the unit vector from entity → ego (i.e. towards the origin).
    A positive projection means the entity is closing in on us.

    Returns ``float('inf')`` if the entity is moving away.
    """
    dist = math.sqrt(x**2 + y**2)
    if dist < 1e-9:
        return 0.0  # entity is at the ego — immediate collision

    # Relative velocity (entity velocity in ego frame)
    rel_vx = vx - ego_vx
    rel_vy = vy - ego_vy

    # Unit vector from entity towards ego (origin)
    ux = -x / dist
    uy = -y / dist

    # Closing speed = dot(rel_vel, towards_ego_unit)
    closing_speed = rel_vx * ux + rel_vy * uy

    if closing_speed <= 0:
        # Entity is moving away or stationary — no collision imminent
        return float("inf")

    return dist / max(epsilon, closing_speed)


def compute_danger_quality(
    ttc: float,
    class_weight: float,
    max_weight: float,
    k_decay: float,
) -> float:
    """Compute normalised danger quality q_i from TTC and class weight.

    q_i = (W_class / W_max) · e^(−k · TTC)

    Returns a value in [0, 1].
    """
    if max_weight <= 0:
        return 0.0
    normalised_weight = class_weight / max_weight
    return normalised_weight * math.exp(-k_decay * ttc)


# ---------------------------------------------------------------------------
# High-level inference entry point
# ---------------------------------------------------------------------------


def infer_semantics(
    kinematics: list[KinematicsEntity],
    config: SGGInferenceConfig | None = None,
) -> list[SemanticEntity]:
    """Deterministically infer ``SemanticEntity`` for each tracked entity.

    Uses TTC-based danger quality and confidence × track-age certainty.
    No neural network weights required.

    Parameters
    ----------
    kinematics:
        Upstream detections from YOLOv10 + ByteTrack.
    config:
        Inference tuning knobs; uses defaults if ``None``.

    Returns
    -------
    One ``SemanticEntity`` per input entity, matched by ``id``.
    """
    if config is None:
        config = SGGInferenceConfig()

    max_weight = max(config.class_weights.values(), default=100.0)
    results: list[SemanticEntity] = []

    for kin in kinematics:
        # Certainty: YOLO conf × track maturity
        c_i = compute_certainty(
            kin.detection_confidence,
            kin.track_age,
            config.lambda_track,
        )

        # TTC
        ttc = compute_ttc(
            kin.x, kin.y, kin.vx, kin.vy,
            config.ego_vx, config.ego_vy,
            config.v_rel_epsilon,
        )

        # Danger quality
        w_class = config.class_weights.get(
            kin.cls.lower(), config.weight_unknown
        )
        q_i = compute_danger_quality(ttc, w_class, max_weight, config.k_ttc_decay)

        results.append(
            SemanticEntity(
                id=kin.id,
                certainty=round(max(0.0, min(c_i, 1.0)), 6),
                danger_quality=round(max(0.0, min(q_i, 1.0)), 6),
            )
        )

    return results
