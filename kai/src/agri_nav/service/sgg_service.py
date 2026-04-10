"""SGG service — stateful orchestrator for scene-graph entity processing."""

from __future__ import annotations

from agri_nav.dto.config import SGGConfig
from agri_nav.dto.perception import KinematicsEntity, SemanticEntity
from agri_nav.logic.sgg_processor import (
    SGGOutput,
    build_scene_graph,
    collapse_semantic_graph,
    infer_semantic_relations,
    merge_perception,
)


class SGGService:
    """Wraps the SGG processing pipeline, maintaining EMA state per entity.

    Usage::

        svc = SGGService(config)
        out = svc.process(kinematics, semantics, ego_vy=3.0, render_viz=True)
    """

    def __init__(self, config: SGGConfig | None = None) -> None:
        self._config = config or SGGConfig()
        self._prev_smoothed: dict[int, float] = {}

    # -- public API ----------------------------------------------------------

    def process(
        self,
        kinematics: list[KinematicsEntity],
        semantics: list[SemanticEntity],
        ego_vy: float = 0.0,
        render_viz: bool = False,
    ) -> SGGOutput:
        """Run the full SGG processing pipeline for one tick.

        * Merges kinematics + semantics by ID.
        * Classifies each entity and applies temporal EMA smoothing.
        * Builds the spatial scene graph (with ego node and TTC edges).
        * Infers semantic relationships (blocking, crossing, etc.).
        * Collapses semantic modifiers into the danger_quality.
        * Optionally generates a Plotly JSON payload for the frontend.
        """
        # 1. Merge and smooth
        tracked = merge_perception(
            kinematics,
            semantics,
            self._config,
            self._prev_smoothed,
            ego_vy=ego_vy,
        )

        # 2. Build spatial graph (nodes without area entities but ego included)
        nodes, spatial_rels = build_scene_graph(tracked, ego_vy=ego_vy)

        # 3. Infer semantic relationships
        semantic_rels = infer_semantic_relations(nodes, ego_vy=ego_vy)

        # 4. Collapse semantic graph (adjust danger_quality based on semantics)
        collapsed_nodes = collapse_semantic_graph(nodes, semantic_rels)

        # Persist smoothed certainties for the next tick
        self._prev_smoothed = {e.id: e.smoothed_certainty for e in collapsed_nodes if not e.is_ego}

        # 5. Visualization
        viz_json = None
        if render_viz:
            from agri_nav.viz.viz_sgg_graph import plot_scene_graph
            # Plot using the collapsed nodes and semantic edges
            fig = plot_scene_graph(collapsed_nodes, semantic_rels, show=False)
            viz_json = fig.to_json()

        # NOTE: APF still needs the area entities that were filtered out from the graph
        # Let's add them back to the nodes list so APF has full knowledge
        area_ents = [e for e in tracked if e.entity_type == "area"]
        final_nodes = collapsed_nodes + area_ents

        return SGGOutput(
            nodes=final_nodes,
            relationships=semantic_rels,
            frontend_viz_json=viz_json,
        )

    def reset(self) -> None:
        """Clear all EMA state (e.g. on scene change)."""
        self._prev_smoothed.clear()
