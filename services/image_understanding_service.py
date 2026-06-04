from models.document_model import ImageUnderstandingModel
from models.document_model import SlideModel
from models.document_model import VisualDesignModel


class ImageUnderstandingService:
    def analyze_slide(
        self,
        slide: SlideModel
    ) -> ImageUnderstandingModel:
        image_understanding = ImageUnderstandingModel()
        image_understanding.image_type = self._detect_image_type(slide)
        image_understanding.scene_description = (self._build_scene_description(slide))
        image_understanding.objects_detected = (self._extract_objects(slide))
        image_understanding.actions_detected = (self._extract_actions(slide))
        image_understanding.relationships = (self._extract_relationships(slide))
        image_understanding.semantic_meaning = (self._build_semantic_meaning(slide))
        image_understanding.visual_design = (self._build_visual_design(slide))
        image_understanding.dominant_colors = (self._extract_colors(slide))
        image_understanding.visual_elements = (self._extract_visual_elements(slide))
        image_understanding.llm_recreation_prompt = (self._build_recreation_prompt(slide))

        return image_understanding

    def _detect_image_type(self,slide: SlideModel) -> str:
        if slide.flowchart and slide.flowchart.is_flowchart:
            return "flowchart"
        if slide.diagram_understanding and slide.diagram_understanding.is_diagram:
            return "diagram"

        image_count = sum(1 for element in slide.elements if element.element_type == "image")
        if image_count > 0:
            return "image_based_slide"
        return "content_slide"

    def _build_scene_description(self, slide: SlideModel) -> str:
        from services.semantic_flow_service import _collect_image_summaries, _parse_image_summary_sections

        combined = _collect_image_summaries(slide)
        if combined:
            sections = _parse_image_summary_sections(combined)
            plain = sections.get("7. Plain-language Summary", "")
            if plain:
                return plain
            breakdown = sections.get("3. Detailed Component Breakdown", "")
            if breakdown:
                return breakdown.replace("\n", " ")[:500]

        title = slide.title or "Untitled Slide"
        text_parts = [
            (element.text or "").strip()
            for element in slide.elements
            if element.text and element.element_type != "image"
        ]
        if text_parts:
            return f"Slide '{title}': " + "; ".join(text_parts[:4])

        image_count = sum(1 for element in slide.elements if element.element_type == "image")
        visual_count = sum(
            1 for element in slide.elements
            if element.element_type in {"shape", "text_box", "placeholder", "freeform", "image"}
        )
        return (
            f"Slide titled '{title}' contains "
            f"{image_count} image(s) and "
            f"{visual_count} visual element(s)."
        )

    def _extract_objects(self,slide: SlideModel) -> list[str]:
        objects = []

        for element in slide.elements:

            if element.text:

                objects.append(
                    element.text
                )

        return objects

    def _extract_actions(self, slide: SlideModel) -> list[str]:
        actions = []

        keywords = [
            "open",
            "close",
            "start",
            "stop",
            "create",
            "delete",
            "get",
            "send",
            "receive",
            "process"
        ]

        for element in slide.elements:

            if not element.text:
                continue

            text = element.text.lower()

            for keyword in keywords:

                if keyword in text:
                    actions.append(
                        element.text
                    )

        return actions

    def _extract_relationships(self, slide: SlideModel) -> list[str]:
        relationships = []

        for relationship in slide.relationships:

            relationships.append(
                f"{relationship.source_element_id}"
                f" -> "
                f"{relationship.target_element_id}"
            )

        return relationships

    def _build_semantic_meaning(self, slide: SlideModel) -> str:
        if slide.semantic_flow and slide.semantic_flow.overall_flow:
            return slide.semantic_flow.overall_flow

        from services.semantic_flow_service import _collect_image_summaries, _parse_image_summary_sections

        combined = _collect_image_summaries(slide)
        if combined:
            sections = _parse_image_summary_sections(combined)
            interp = sections.get("6. Summary & Interpretation", "")
            if interp:
                return interp

        if slide.diagram_understanding and slide.diagram_understanding.flow_description:
            return slide.diagram_understanding.flow_description

        if slide.flowchart and slide.flowchart.is_flowchart:
            return "The slide explains a process flow through connected stages."

        if slide.diagram_understanding and slide.diagram_understanding.is_diagram:
            return "The slide explains relationships between concepts."

        return "The slide presents information through visual and textual elements."

    def _build_visual_design(
        self,
        slide: SlideModel
    ) -> VisualDesignModel:
        design = VisualDesignModel()
        design.background_style = (
            "presentation"
        )
        design.layout_style = (
            slide.layout_structure.layout_type
            if slide.layout_structure
            else "mixed"
        )

        design.primary_shapes = [
            element.element_type
            for element in slide.elements
        ]

        return design

    def _extract_colors(
        self,
        slide: SlideModel
    ) -> list[str]:

        colors = set()

        for element in slide.elements:

            if (
                element.style
                and
                element.style.background_color
            ):
                colors.add(
                    element.style.background_color
                )
            if (
                element.style
                and
                element.style.text_color
            ):
                colors.add(
                    element.style.text_color
                )
        return list(colors)

    def _extract_visual_elements(
        self,
        slide: SlideModel
    ) -> list[str]:
        visual_elements = []
        for element in slide.elements:
            visual_elements.append(
                element.element_type
            )

        return list(
            set(visual_elements)
        )

    def _build_recreation_prompt(
        self,
        slide: SlideModel
    ) -> str:
        if slide.semantic_flow and slide.semantic_flow.image_generation_prompt:
            return slide.semantic_flow.image_generation_prompt

        from services.semantic_flow_service import SemanticFlowService

        return SemanticFlowService().analyze_slide(slide).image_generation_prompt