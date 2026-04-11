"""SGG service — stateful orchestrator for scene-graph entity processing."""

from __future__ import annotations

import math

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
        entity_sgg_rels: list[SceneRelationship] | None = None,
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
        
        # Add external real SGG entity relationships
        if entity_sgg_rels:
            semantic_rels.extend(entity_sgg_rels)

        # 4. Collapse semantic graph (adjust danger_quality based on semantics)
        collapsed_nodes = collapse_semantic_graph(nodes, semantic_rels)

        # Persist smoothed certainties for the next tick
        self._prev_smoothed = {e.id: e.smoothed_certainty for e in collapsed_nodes if not e.is_ego}

        # 5. Visualization
        viz_data = None
        if render_viz:
            from agri_nav.dto.visualization import SGGVisualData, SGGNodeViz, SGGEdgeViz, SGGDistanceLineViz

            viz_nodes = []
            for n in collapsed_nodes:
                ttc_str = "" if n.is_ego else ("∞" if n.ttc == float("inf") else f"{n.ttc:.1f}s")
                viz_nodes.append(SGGNodeViz(
                    id=n.id, cls=n.cls, is_ego=n.is_ego,
                    x=n.x, y=n.y, vx=n.vx, vy=n.vy,
                    danger_quality=n.danger_quality,
                    smoothed_certainty=n.smoothed_certainty,
                    ttc_label=ttc_str,
                ))

            viz_edges = []
            for rel in semantic_rels:
                try:
                    src = next(n for n in collapsed_nodes if n.id == rel.source_id)
                    tgt = next(n for n in collapsed_nodes if n.id == rel.target_id)
                except StopIteration:
                    continue  # Safely skip edges pointing to dropped entities
                
                color = "#95a5a6"
                if rel.danger_modifier > 0:
                    color = "#e74c3c"
                elif rel.danger_modifier < 0:
                    color = "#2ecc71"

                viz_edges.append(SGGEdgeViz(
                    source_x=src.x, source_y=src.y,
                    target_x=tgt.x, target_y=tgt.y,
                    label=f"{rel.semantic_label.value} ({rel.danger_modifier:+.2f})",
                    color=color,
                ))

            viz_dist_lines = []
            ego_node = next((n for n in collapsed_nodes if n.is_ego), None)
            if ego_node:
                for n in collapsed_nodes:
                    if not n.is_ego:
                        dist = math.sqrt((n.x - ego_node.x)**2 + (n.y - ego_node.y)**2)
                        viz_dist_lines.append(SGGDistanceLineViz(
                            target_x=n.x, target_y=n.y, distance=dist
                        ))
                
            viz_data = SGGVisualData(nodes=viz_nodes, edges=viz_edges, distance_lines=viz_dist_lines)

        # NOTE: APF still needs the area entities that were filtered out from the graph
        # Let's add them back to the nodes list so APF has full knowledge
        area_ents = [e for e in tracked if e.entity_type == "area"]
        final_nodes = collapsed_nodes + area_ents

        return SGGOutput(
            nodes=final_nodes,
            relationships=semantic_rels,
            visual_data=viz_data,
        )

    def reset(self) -> None:
        """Clear all EMA state (e.g. on scene change)."""
        self._prev_smoothed.clear()
