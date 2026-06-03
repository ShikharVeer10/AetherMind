from models.document_model import ImageReconstructionModel
from models.document_model import SlideModel


class ImageReconstructionService:

    def analyze_slide(
        self,
        slide: SlideModel
    ) -> ImageReconstructionModel:

        reconstruction = ImageReconstructionModel()

        reconstruction.layout_description = (
            self._build_layout_description(slide)
        )

        reconstruction.color_palette = (
            self._extract_color_palette(slide)
        )

        reconstruction.object_location = (
            self._extract_object_locations(slide)
        )

        reconstruction.connector_layout = (
            self._extract_connector_layout(slide)
        )

        reconstruction.object_inventory = (
            self._extract_object_inventory(slide)
        )

        reconstruction.visual_hierarchy = (
            self._build_visual_hierarchy(slide)
        )

        reconstruction.layout_regions = (
            self._extract_layout_regions(slide)
        )

        reconstruction.design_style = (
            self._detect_design_style(slide)
        )

        reconstruction.recreation_prompt = (
            self._build_recreation_prompt(slide)
        )

        return reconstruction

    def _build_layout_description(
        self,
        slide: SlideModel
    ) -> str:

        if slide.layout_structure:
            return (
                f"Layout type is "
                f"{slide.layout_structure.layout_type}"
            )

        return "Mixed presentation layout"

    def _extract_color_palette(
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

    def _extract_object_locations(
        self,
        slide: SlideModel
    ) -> list[str]:

        locations = []

        for element in slide.elements:

            location = (
                f"{element.element_id}"
                f" at "
                f"({element.position.x},"
                f"{element.position.y})"
            )

            locations.append(location)

        return locations

    def _extract_connector_layout(
        self,
        slide: SlideModel
    ) -> list[str]:

        connectors = []

        for relationship in slide.relationships:

            connectors.append(
                f"{relationship.source_element_id}"
                f" -> "
                f"{relationship.target_element_id}"
            )

        return connectors

    def _extract_object_inventory(
        self,
        slide: SlideModel
    ) -> list[str]:

        inventory = []

        for element in slide.elements:

            if element.text:

                inventory.append(
                    f"{element.element_type}: "
                    f"{element.text}"
                )

            else:

                inventory.append(
                    element.element_type
                )

        return inventory

    def _build_visual_hierarchy(
        self,
        slide: SlideModel
    ) -> list[str]:

        hierarchy = []

        if slide.title:

            hierarchy.append(
                f"Primary Title: {slide.title}"
            )

        for element in slide.elements:

            if element.text:

                hierarchy.append(
                    f"Content: {element.text}"
                )

        return hierarchy

    def _extract_layout_regions(
        self,
        slide: SlideModel
    ) -> list[str]:

        if not slide.layout_structure:
            return []

        regions = []

        for region in slide.layout_structure.regions:

            regions.append(
                f"{region.name}"
            )

        return regions

    def _detect_design_style(
        self,
        slide: SlideModel
    ) -> str:

        if (
            slide.flowchart
            and
            slide.flowchart.flow_detected
        ):
            return "flowchart"

        if (
            slide.diagram_understanding
            and
            slide.diagram_understanding.is_diagram
        ):
            return "diagram"

        return "presentation"

    def _build_recreation_prompt(
        self,
        slide: SlideModel
    ) -> str:

        title = slide.title or "Untitled Slide"

        prompt = (
            f"Create a presentation slide titled "
            f"'{title}'. "
        )

        if slide.semantic_flow:

            prompt += (
                f"Semantic meaning: "
                f"{slide.semantic_flow.overall_flow}. "
            )

        if slide.image_understanding:

            prompt += (
                f"Scene description: "
                f"{slide.image_understanding.scene_description}. "
            )

        prompt += (
            "Preserve object positions, "
            "visual hierarchy, colors, "
            "relationships, flow direction, "
            "and layout structure."
        )

        return prompt