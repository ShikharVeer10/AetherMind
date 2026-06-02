"""
Builds a lightweight diagram understanding summary from elements
and their relationships.
"""

from typing import List

from models.document_model import (
    DiagramUnderstandingModel,
    DocumentElementModel,
    FlowchartModel,
    RelationshipModel,
)


class DiagramUnderstandingService:
    def analyse(
        self,
        elements: List[DocumentElementModel],
        relationships: List[RelationshipModel],
        flowchart: FlowchartModel,
    ) -> DiagramUnderstandingModel:
        nodes = [
            {
                "element_id": e.element_id,
                "type": e.element_type,
                "text": e.text,
            }
            for e in elements
            if e.element_type not in {"arrow", "connector"}
        ]
        edges = [
            {
                "type": r.relationship_type,
                "source": r.source_element_id,
                "target": r.target_element_id,
                "label": r.label,
            }
            for r in relationships
        ]

        is_diagram = flowchart.is_flowchart or any(
            e.element_type in {"shape", "image", "chart"} for e in elements
        )
        diagram_type = "flowchart" if flowchart.is_flowchart else "diagram" if is_diagram else "none"

        summary = (
            f"{diagram_type} with {len(nodes)} node(s) and {len(edges)} relationship(s)."
            if is_diagram
            else "No diagram detected."
        )

        return DiagramUnderstandingModel(
            is_diagram=is_diagram,
            diagram_type=diagram_type,
            node_count=len(nodes),
            edge_count=len(edges),
            nodes=nodes,
            edges=edges,
            summary=summary,
        )
