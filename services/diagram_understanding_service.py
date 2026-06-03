from typing import Dict, List

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
        diagram_type = (
            "flowchart" if flowchart.is_flowchart
            else "diagram" if is_diagram
            else "none"
        )
        element_lookup: Dict[str, str] = {
            e.element_id: (e.text or "").strip().replace("\n", " ") or f"[{e.element_id}]"
            for e in elements
        }
        flow_description = ""
        if flowchart.is_flowchart and flowchart.reading_order:
            flow_steps = []
            for i, eid in enumerate(flowchart.reading_order, start=1):
                label = element_lookup.get(eid, eid)
                flow_steps.append(f"Step {i}: {label}")
            flow_description = " → ".join(flow_steps)

        summary_parts: List[str] = []

        if not is_diagram:
            summary_parts.append("No diagram detected.")
        else:
            # Section: Counts
            box_count = flowchart.box_count if flowchart.is_flowchart else len(nodes)
            arrow_count = flowchart.arrow_count if flowchart.is_flowchart else 0
            summary_parts.append(
                f"[Counts] {diagram_type.capitalize()} with "
                f"{box_count} box(es), {arrow_count} arrow(s), "
                f"{len(nodes)} node(s), and {len(edges)} relationship(s)."
            )
            if edges:
                edge_descriptions = []
                for e in edges:
                    src_label = element_lookup.get(e["source"], e["source"])
                    tgt_label = element_lookup.get(e["target"], e["target"])
                    rel_type = e["type"]
                    desc = f'"{src_label}" → "{tgt_label}" ({rel_type})'
                    if e.get("label"):
                        desc += f' [label: {e["label"]}]'
                    edge_descriptions.append(desc)
                summary_parts.append(
                    "[Connections] " + "; ".join(edge_descriptions) + "."
                )

            # Section: Flow path
            if flow_description:
                summary_parts.append(f"[Flow] {flow_description}.")

            # Section: Interpretation
            if flowchart.is_flowchart:
                first_label = element_lookup.get(
                    flowchart.reading_order[0], ""
                ) if flowchart.reading_order else ""
                last_label = element_lookup.get(
                    flowchart.reading_order[-1], ""
                ) if flowchart.reading_order else ""
                if first_label and last_label and first_label != last_label:
                    summary_parts.append(
                        f'[Interpretation] This flowchart illustrates a process '
                        f'that begins with "{first_label}" and concludes with '
                        f'"{last_label}", progressing through {box_count} stage(s).'
                    )
                else:
                    summary_parts.append(
                        f"[Interpretation] This flowchart depicts a {box_count}-step process."
                    )
            else:
                summary_parts.append(
                    f"[Interpretation] This diagram presents {len(nodes)} visual component(s) "
                    f"with {len(edges)} relationship(s) between them."
                )

        summary = " ".join(summary_parts)

        return DiagramUnderstandingModel(
            is_diagram=is_diagram,
            diagram_type=diagram_type,
            node_count=len(nodes),
            edge_count=len(edges),
            nodes=nodes,
            edges=edges,
            flow_description=flow_description,
            summary=summary,
        )

