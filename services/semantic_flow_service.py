from models.document_model import SemanticFlowModel
from models.document_model import SlideModel


class SemanticFlowService:

    def analyze_slide(
        self,
        slide: SlideModel
    ) -> SemanticFlowModel:

        semantic_flow = SemanticFlowModel()

        semantic_flow.overall_flow = self._build_overall_flow(slide)

        semantic_flow.step_by_step_explanation = (
            self._build_step_by_step_flow(slide)
        )

        semantic_flow.conceptual_layers = (
            self._extract_conceptual_layers(slide)
        )

        semantic_flow.visual_design_details = (
            self._extract_visual_design_details(slide)
        )

        semantic_flow.plain_english_summary = (
            self._build_plain_english_summary(slide)
        )

        semantic_flow.decision_points = (
            self._extract_decision_points(slide)
        )

        semantic_flow.cause_effect_chain = (
            self._build_cause_effect_chain(slide)
        )

        return semantic_flow

    def _build_overall_flow(
        self,
        slide: SlideModel
    ) -> str:

        if (
            slide.flowchart
            and
            slide.flowchart.flow_detected
        ):
            return (
                "The slide represents a process flow "
                "through multiple connected stages."
            )

        if (
            slide.diagram_understanding
            and
            slide.diagram_understanding.is_diagram
        ):
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
        slide: SlideModel
    ) -> list[str]:

        steps = []

        if slide.relationships:

            for relationship in slide.relationships:

                step = (
                    f"{relationship.source_element_id}"
                    f" leads to "
                    f"{relationship.target_element_id}"
                )

                steps.append(step)

        if not steps:

            for element in slide.elements:

                if element.text:

                    steps.append(
                        f"Present concept: {element.text}"
                    )

        return steps

    def _extract_conceptual_layers(
        self,
        slide: SlideModel
    ) -> list[str]:

        layers = []

        if slide.title:
            layers.append(
                f"Primary Concept: {slide.title}"
            )

        if (
            slide.image_understanding
            and
            slide.image_understanding.semantic_meaning
        ):
            layers.append(
                slide.image_understanding.semantic_meaning
            )

        return layers

    def _extract_visual_design_details(
        self,
        slide: SlideModel
    ) -> list[str]:

        details = []

        if (
            slide.image_understanding
            and
            slide.image_understanding.visual_design
        ):

            visual_design = (
                slide.image_understanding.visual_design
            )

            details.append(
                f"Layout Style: {visual_design.layout_style}"
            )

            details.append(
                f"Background Style: {visual_design.background_style}"
            )

        if slide.layout_structure:

            details.append(
                f"Layout Type: {slide.layout_structure.layout_type}"
            )

        return details

    def _build_plain_english_summary(
        self,
        slide: SlideModel
    ) -> str:

        title = slide.title or "Untitled Slide"

        element_count = len(slide.elements)

        relationship_count = len(slide.relationships)

        return (
            f"The slide titled '{title}' contains "
            f"{element_count} visual elements and "
            f"{relationship_count} relationships. "
            f"It communicates information through "
            f"text, visuals and structural layout."
        )

    def _extract_decision_points(
        self,
        slide: SlideModel
    ) -> list[str]:

        decision_points = []

        keywords = [
            "?",
            "if",
            "yes",
            "no",
            "decision",
            "choice"
        ]

        for element in slide.elements:

            if not element.text:
                continue

            text = element.text.lower()

            if any(
                keyword in text
                for keyword in keywords
            ):
                decision_points.append(
                    element.text
                )

        return decision_points

    def _build_cause_effect_chain(
        self,
        slide: SlideModel
    ) -> list[str]:

        chains = []

        if not slide.relationships:
            return chains

        for relationship in slide.relationships:

            chains.append(
                f"{relationship.source_element_id}"
                f" -> "
                f"{relationship.target_element_id}"
            )

        return chains