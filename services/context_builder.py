"""
Builds the aggregated Context block for each slide.

The context combines:
    - Header / footer
    - Slide title
    - Visual inventory counts
    - Layout structure
    - Flowchart info (if present)
    - A human-readable outline string
"""

from models.document_model import (
    FlowchartModel,
    HeaderFooterModel,
    LayoutStructureModel,
    SlideContextModel,
    VisualInventoryModel,
)


class ContextBuilder:

    def build(
        self,
        title: str | None,
        header_footer: HeaderFooterModel,
        inventory: VisualInventoryModel,
        layout: LayoutStructureModel,
        flowchart: FlowchartModel,
        text_points: list,
        position_mapping: list,
        relationships: list,
        diagram_understanding,
    ) -> SlideContextModel:
        """
        Assemble all analysis results into one SlideContextModel
        and generate a human-readable outline string.
        """
        outline_parts: list[str] = []

        if title:
            outline_parts.append(f"Title: \"{title}\"")

        inv_parts: list[str] = []
        if inventory.text_box_count:
            inv_parts.append(f"{inventory.text_box_count} text box(es)")
        if inventory.shape_count:
            inv_parts.append(f"{inventory.shape_count} shape(s)")
        if inventory.arrow_count:
            inv_parts.append(f"{inventory.arrow_count} arrow(s)")
        if inventory.connector_count:
            inv_parts.append(f"{inventory.connector_count} connector(s)")
        if inventory.image_count:
            inv_parts.append(f"{inventory.image_count} image(s)")
        if inventory.table_count:
            inv_parts.append(f"{inventory.table_count} table(s)")
        if inventory.group_count:
            inv_parts.append(f"{inventory.group_count} group(s)")
        if inventory.chart_count:
            inv_parts.append(f"{inventory.chart_count} chart(s)")
        if inv_parts:
            outline_parts.append("Elements: " + ", ".join(inv_parts))

        box_count = (
            inventory.text_box_count
            + inventory.shape_count
            + inventory.placeholder_count
        )
        outline_parts.append(f"Boxes: {box_count}, Arrows: {inventory.arrow_count}")

        outline_parts.append(f"Layout: {layout.layout_type}")

        if flowchart.is_flowchart:
            flow_str = (
                f"Flowchart detected — {flowchart.box_count} box(es), "
                f"{flowchart.arrow_count} arrow(s)"
            )
            if flowchart.reading_order:
                flow_str += (
                    ". Reading order: "
                    + " → ".join(flowchart.reading_order)
                )
            outline_parts.append(flow_str)

        if relationships:
            rel_strings = [
                f"{r.source_element_id} -> {r.target_element_id} ({r.relationship_type})"
                for r in relationships
            ]
            outline_parts.append("Relationships: " + "; ".join(rel_strings))

        hf_parts: list[str] = []
        if header_footer.header_text:
            hf_parts.append(f"Header: \"{header_footer.header_text}\"")
        if header_footer.footer_text:
            hf_parts.append(f"Footer: \"{header_footer.footer_text}\"")
        if header_footer.slide_number_text:
            hf_parts.append(f"Slide #: {header_footer.slide_number_text}")
        if header_footer.date_text:
            hf_parts.append(f"Date: {header_footer.date_text}")
        if hf_parts:
            outline_parts.append(" | ".join(hf_parts))

        outline = ". ".join(outline_parts) + "."

        return SlideContextModel(
            header_footer=header_footer,
            title=title,
            visual_inventory=inventory,
            layout_structure=layout,
            flowchart=flowchart,
            text_points=text_points,
            position_mapping=position_mapping,
            relationship_mapping=relationships,
            diagram_understanding=diagram_understanding,
            outline=outline,
        )
