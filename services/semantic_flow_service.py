from models.document_model import SemanticFlowModel, SlideModel

_SLIDE_WIDTH_EMU = 12192000.0
_SLIDE_HEIGHT_EMU = 6858000.0


class SemanticFlowService:

    async def analyze_slide_async(
        self,
        slide: SlideModel,
        image_summaries: str = "",
    ) -> SemanticFlowModel:
        return self.analyze_slide(slide, image_summaries=image_summaries)

    def analyze_slide(
        self,
        slide: SlideModel,
        image_summaries: str = "",
    ) -> SemanticFlowModel:
        labels = self._element_label_lookup(slide)

        semantic_flow = SemanticFlowModel()
        semantic_flow.overall_flow = self._build_overall_flow(slide, labels)
        semantic_flow.step_by_step_explanation = self._build_step_by_step_flow(slide, labels)
        semantic_flow.conceptual_layers = self._extract_conceptual_layers(slide, labels)
        semantic_flow.visual_design_details = self._extract_visual_design_details(slide)
        semantic_flow.plain_english_summary = self._build_plain_english_summary(slide, labels)
        semantic_flow.decision_points = self._extract_decision_points(slide)
        semantic_flow.cause_effect_chain = self._build_cause_effect_chain(slide, labels)
        semantic_flow.image_generation_prompt = self._build_reconstruction_image_prompt(
            slide, labels, image_summaries
        )
        return semantic_flow

    def _element_label_lookup(self, slide: SlideModel) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for element in slide.elements:
            label = (element.text or "").strip().replace("\n", " ")
            if not label and element.paragraphs:
                label = " ".join(
                    p.text.strip() for p in element.paragraphs if p.text
                ).strip()
            lookup[element.element_id] = label or f"[{element.element_id}]"
        return lookup

    def _build_overall_flow(self, slide: SlideModel, labels: dict[str, str]) -> str:
        if slide.diagram_understanding and slide.diagram_understanding.flow_description:
            return slide.diagram_understanding.flow_description

        if slide.flowchart and slide.flowchart.is_flowchart and slide.flowchart.reading_order:
            order_labels = [
                labels.get(eid, eid) for eid in slide.flowchart.reading_order
            ]
            return " → ".join(order_labels)

        if slide.flowchart and slide.flowchart.is_flowchart:
            return (
                "The slide represents a process flow "
                "through multiple connected stages."
            )

        if slide.diagram_understanding and slide.diagram_understanding.is_diagram:
            return (
                "The slide represents conceptual "
                "relationships between visual components."
            )

        return (
            "The slide presents information using "
            "textual and visual elements."
        )

    def _build_step_by_step_flow(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> list[str]:
        steps: list[str] = []

        if slide.flowchart and slide.flowchart.is_flowchart:
            for rel in slide.flowchart.relationships:
                src = labels.get(rel.source_element_id, rel.source_element_id)
                tgt = labels.get(rel.target_element_id, rel.target_element_id)
                step = f"{src} → {tgt}"
                if rel.label:
                    step = f"{rel.label}: {step}"
                steps.append(step)

        if not steps and slide.relationships:
            for relationship in slide.relationships:
                if relationship.relationship_type != "connector":
                    continue
                src = labels.get(relationship.source_element_id, relationship.source_element_id)
                tgt = labels.get(relationship.target_element_id, relationship.target_element_id)
                step = f"{src} → {tgt}"
                if relationship.label:
                    step = f"{relationship.label}: {step}"
                steps.append(step)

        if not steps and slide.flowchart and slide.flowchart.reading_order:
            for i, eid in enumerate(slide.flowchart.reading_order, start=1):
                steps.append(f"Step {i}: {labels.get(eid, eid)}")

        if not steps:
            for element in slide.elements:
                if element.text:
                    steps.append(f"Present concept: {element.text}")

        return steps

    def _extract_conceptual_layers(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> list[str]:
        layers: list[str] = []

        if slide.title:
            layers.append(f"Primary Concept: {slide.title}")

        if slide.text_points:
            for point in slide.text_points:
                if point.level == 0 and point.text and point.text != slide.title:
                    layers.append(f"Section: {point.text}")

        if slide.image_understanding and slide.image_understanding.semantic_meaning:
            layers.append(slide.image_understanding.semantic_meaning)

        if slide.diagram_understanding and slide.diagram_understanding.summary:
            layers.append(slide.diagram_understanding.summary)

        return layers

    def _extract_visual_design_details(self, slide: SlideModel) -> list[str]:
        details: list[str] = []

        if slide.image_understanding and slide.image_understanding.visual_design:
            visual_design = slide.image_understanding.visual_design
            details.append(f"Layout Style: {visual_design.layout_style}")
            details.append(f"Background Style: {visual_design.background_style}")

        if slide.layout_structure:
            details.append(f"Layout Type: {slide.layout_structure.layout_type}")
            for region in slide.layout_structure.regions or []:
                details.append(f"Region '{region.name}': {len(region.element_ids)} element(s)")

        colors: list[str] = []
        for element in slide.elements:
            if element.style and element.style.background_color:
                colors.append(element.style.background_color)
            if element.style and element.style.text_color:
                colors.append(element.style.text_color)
        if colors:
            details.append(f"Colors: {', '.join(dict.fromkeys(colors))}")

        return details

    def _build_plain_english_summary(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> str:
        title = slide.title or "Untitled Slide"
        parts: list[str] = [f"The slide titled '{title}'"]

        if slide.diagram_understanding and slide.diagram_understanding.flow_description:
            parts.append(
                f"shows the flow: {slide.diagram_understanding.flow_description}"
            )
        elif slide.flowchart and slide.flowchart.is_flowchart and slide.flowchart.reading_order:
            order_labels = [
                labels.get(eid, eid) for eid in slide.flowchart.reading_order
            ]
            parts.append(f"depicts a process: {' → '.join(order_labels)}")
        else:
            text_snippets = [
                labels[e.element_id]
                for e in slide.elements
                if labels.get(e.element_id, "").startswith("[") is False
                and labels.get(e.element_id, "")
            ][:5]
            if text_snippets:
                parts.append(f"contains: {'; '.join(text_snippets)}")

        return " ".join(parts) + "."

    def _extract_decision_points(self, slide: SlideModel) -> list[str]:
        decision_points: list[str] = []
        keywords = ["?", "if", "yes", "no", "decision", "choice"]

        for element in slide.elements:
            if not element.text:
                continue
            text = element.text.strip()
            if "?" in text or any(
                f" {keyword} " in f" {text.lower()} " for keyword in keywords
            ):
                decision_points.append(text)

        return decision_points

    def _build_cause_effect_chain(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> list[str]:
        chains: list[str] = []

        rels = []
        if slide.flowchart and slide.flowchart.relationships:
            rels = slide.flowchart.relationships
        elif slide.relationships:
            rels = [
                r for r in slide.relationships
                if r.relationship_type == "connector"
            ] or slide.relationships

        for relationship in rels:
            src = labels.get(relationship.source_element_id, relationship.source_element_id)
            tgt = labels.get(relationship.target_element_id, relationship.target_element_id)
            chain = f"{src} → {tgt}"
            if relationship.label:
                chain = f"{relationship.label}: {chain}"
            chains.append(chain)

        return chains

    def _region_for_element(self, element) -> str:
        cx = element.position.x + element.position.width / 2
        cy = element.position.y + element.position.height / 2
        x_pct = cx / _SLIDE_WIDTH_EMU
        y_pct = cy / _SLIDE_HEIGHT_EMU

        if y_pct < 0.2:
            return "top"
        if y_pct > 0.8:
            return "bottom"
        if x_pct < 0.4:
            return "left"
        if x_pct > 0.6:
            return "right"
        return "center"

    def _build_layout_blueprint(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> str:
        regions: dict[str, list[str]] = {
            "left": [],
            "right": [],
            "top": [],
            "bottom": [],
            "center": [],
        }

        for element in slide.elements:
            if element.element_type in {"arrow", "connector"}:
                continue
            label = labels.get(element.element_id, "")
            if label.startswith("["):
                continue
            region = self._region_for_element(element)
            regions[region].append(f"{label} ({element.element_type})")

        lines = ["=== LAYOUT ==="]
        for name in ("left", "right", "top", "bottom", "center"):
            items = regions[name]
            if items:
                lines.append(f"{name.capitalize()} section: {'; '.join(items)}")
            else:
                lines.append(f"{name.capitalize()} section: (empty)")

        if slide.layout_structure:
            lines.append(f"Layout type: {slide.layout_structure.layout_type}")

        return "\n".join(lines)

    def _build_diagram_structure(
        self,
        slide: SlideModel,
        labels: dict[str, str],
    ) -> str:
        lines = ["=== DIAGRAM STRUCTURE ==="]

        decisions = self._extract_decision_points(slide)
        if decisions:
            lines.append("Decision nodes:")
            for decision in decisions:
                lines.append(f"  - {decision}")

        if slide.flowchart and slide.flowchart.is_flowchart:
            for rel in slide.flowchart.relationships:
                src = labels.get(rel.source_element_id, rel.source_element_id)
                tgt = labels.get(rel.target_element_id, rel.target_element_id)
                branch = f"  {src} → {tgt}"
                if rel.label:
                    branch = f"  {rel.label} → {tgt}" if src in decisions else f"  {rel.label}: {src} → {tgt}"
                lines.append(branch)
        elif slide.diagram_understanding and slide.diagram_understanding.edges:
            for edge in slide.diagram_understanding.edges:
                src = labels.get(edge.get("source", ""), edge.get("source", ""))
                tgt = labels.get(edge.get("target", ""), edge.get("target", ""))
                line = f'  "{src}" → "{tgt}"'
                if edge.get("label"):
                    line += f' [{edge["label"]}]'
                lines.append(line)

        if slide.diagram_understanding and slide.diagram_understanding.flow_description:
            lines.append(f"Flow: {slide.diagram_understanding.flow_description}")

        return "\n".join(lines)

    def _build_reconstruction_image_prompt(
        self,
        slide: SlideModel,
        labels: dict[str, str],
        image_summaries: str = "",
    ) -> str:
        sections: list[str] = []

        if slide.title:
            sections.append(f"Slide title: {slide.title}")

        sections.append(self._build_layout_blueprint(slide, labels))

        object_lines = ["=== OBJECTS ==="]
        for i, element in enumerate(slide.elements, start=1):
            if element.element_type in {"arrow", "connector"}:
                continue
            label = labels.get(element.element_id, element.element_id)
            region = self._region_for_element(element)
            object_lines.append(
                f"Object {i}: {label} (type: {element.element_type}, region: {region})"
            )
        sections.append("\n".join(object_lines))

        if (
            (slide.flowchart and slide.flowchart.is_flowchart)
            or (slide.diagram_understanding and slide.diagram_understanding.is_diagram)
        ):
            sections.append(self._build_diagram_structure(slide, labels))

        hierarchy_lines = ["=== VISUAL HIERARCHY ==="]
        if slide.title:
            hierarchy_lines.append(f"Primary focus: slide title '{slide.title}'")
        if slide.layout_structure:
            hierarchy_lines.append(f"Layout pattern: {slide.layout_structure.layout_type}")
        if slide.text_points:
            top_level = [p.text for p in slide.text_points if p.level == 0][:3]
            if top_level:
                hierarchy_lines.append(f"Top-level headings: {'; '.join(top_level)}")
        sections.append("\n".join(hierarchy_lines))

        spatial_lines = ["=== SPATIAL RELATIONSHIPS ==="]
        for rel in slide.relationships or []:
            if rel.relationship_type != "connector":
                continue
            src = labels.get(rel.source_element_id, rel.source_element_id)
            tgt = labels.get(rel.target_element_id, rel.target_element_id)
            line = f'"{src}" connects to "{tgt}"'
            if rel.label:
                line += f" (label: {rel.label})"
            spatial_lines.append(line)
        sections.append("\n".join(spatial_lines))

        design_lines = ["=== VISUAL DESIGN ==="]
        design_lines.extend(self._extract_visual_design_details(slide))
        sections.append("\n".join(design_lines))

        if image_summaries:
            sections.append(f"=== IMAGE CONTENT ===\n{image_summaries}")

        if slide.image_reconstruction and slide.image_reconstruction.recreation_prompt:
            sections.append(
                f"=== IMAGE RECONSTRUCTION ===\n"
                f"{slide.image_reconstruction.recreation_prompt}"
            )

        return "\n\n".join(sections)
