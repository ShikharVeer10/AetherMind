"""
Detects whether a slide contains a flowchart and, if so, extracts:
    - Box count and box details (text, position)
    - Arrow/connector count
    - Relationship graph between boxes
    - Reading order (topological sort of the directed graph)
"""

from typing import Dict, List, Set
from models.document_model import (
    DocumentElementModel,
    FlowchartModel,
    RelationshipModel,
)


_MIN_BOXES = 2
_MIN_ARROWS = 1


class FlowchartService:

    def analyse(
        self,
        elements: List[DocumentElementModel],
        relationships: List[RelationshipModel],
    ) -> FlowchartModel:
        """
        Determine if the slide looks like a flowchart and, if so,
        build a FlowchartModel with counts + directed graph.
        """
        box_types = {"shape", "text_box", "placeholder", "unknown"}
        arrow_types = {"arrow", "connector", "freeform"}

        boxes = [
            e for e in elements
            if e.element_type in box_types
        ]
        arrows = [
            e for e in elements
            if e.element_type in arrow_types
        ]

        is_flowchart = (
            len(boxes) >= _MIN_BOXES and len(arrows) >= _MIN_ARROWS
        )

        box_details = [
            {
                "element_id": b.element_id,
                "text": b.text,
                "x": b.position.x,
                "y": b.position.y,
            }
            for b in boxes
        ]

        arrow_details = [
            {
                "element_id": a.element_id,
                "text": a.text,
                "type": a.element_type,
            }
            for a in arrows
        ]

        box_ids = {b.element_id for b in boxes}
        flow_rels = [
            r for r in relationships
            if r.source_element_id in box_ids
            and r.target_element_id in box_ids
        ]

        reading_order = self._topological_sort(box_ids, flow_rels, elements)

        return FlowchartModel(
            is_flowchart=is_flowchart,
            box_count=len(boxes),
            arrow_count=len(arrows),
            boxes=box_details,
            arrows=arrow_details,
            relationships=flow_rels,
            reading_order=reading_order,
        )



    @staticmethod
    def _topological_sort(
        node_ids: Set[str],
        edges: List[RelationshipModel],
        elements: List[DocumentElementModel] = None,
    ) -> List[str]:
        """
        Returns nodes in dependency order. If the graph has cycles
        (not a true DAG), remaining nodes are appended sorted by their
        spatial position (top-to-bottom, left-to-right) for a stable
        reading order.
        """
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in edges:
            src, tgt = edge.source_element_id, edge.target_element_id
            if src in adj:
                adj[src].append(tgt)
            if tgt in in_degree:
                in_degree[tgt] += 1

        queue = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0]
        )
        result: List[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbour in adj.get(node, []):
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        # Append remaining nodes (cycles or disconnected) sorted by position
        remaining = [nid for nid in node_ids if nid not in result]
        if remaining and elements:
            pos_lookup = {
                e.element_id: (e.position.y, e.position.x)
                for e in elements
            }
            remaining.sort(key=lambda nid: pos_lookup.get(nid, (0, 0)))
        result.extend(remaining)

        return result
