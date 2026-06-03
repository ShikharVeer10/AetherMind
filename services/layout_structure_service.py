from models.document_model import LayoutStructureModel
from models.document_model import SlideModel


class LayoutStructureService:
    def analyze_layout(self,slide: SlideModel) -> LayoutStructureModel:
        layout = LayoutStructureModel()
        layout.layout_type = self._detect_layout_type(slide)
        layout.regions = self._detect_regions(slide)
        return layout

    def _detect_layout_type(self,slide: SlideModel) -> str:
        if not slide.elements:
            return "empty"

        positions = [element.position.x for element in slide.elements]

        min_x = min(positions)
        max_x = max(positions)

        spread = max_x - min_x

        if spread > 600:
            return "left_to_right"

        y_positions = [element.position.y for element in slide.elements]

        min_y = min(y_positions)
        max_y = max(y_positions)

        vertical_spread = max_y - min_y

        if vertical_spread > 400:
            return "top_to_bottom"

        return "mixed"

    def _detect_regions(self, slide: SlideModel) -> list[dict]:

        left_region = []
        center_region = []
        right_region = []

        for element in slide.elements:

            x_position = element.position.x

            if x_position < 300:
                left_region.append(element.element_id)
            elif x_position < 700:
                center_region.append(element.element_id)
            else:
                right_region.append(element.element_id)

        regions = []

        regions.append(
            {
                "name": "left",
                "element_ids": left_region
            }
        )

        regions.append(
            {
                "name": "center",
                "element_ids": center_region
            }
        )

        regions.append(
            {
                "name": "right",
                "element_ids": right_region
            }
        )

        return regions