from models.document_model import LayoutStructureModel, RegionModel
from models.document_model import SlideModel


class LayoutStructureService:

    DEFAULT_WIDTH = 12_192_000.0
    DEFAULT_HEIGHT = 6_858_000.0

    def analyze_layout(self, slide: SlideModel) -> LayoutStructureModel:
        layout = LayoutStructureModel()
        layout.layout_type = self._detect_layout_type(slide)
        layout.regions = self._detect_regions(slide)
        return layout

    def _detect_layout_type(self, slide: SlideModel) -> str:
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

    def _detect_regions(self, slide: SlideModel) -> list[RegionModel]:
        left_region: list[str] = []
        center_region: list[str] = []
        right_region: list[str] = []

        for element in slide.elements:
            x_position = element.position.x

            if x_position < 300:
                left_region.append(element.element_id)
            elif x_position < 700:
                center_region.append(element.element_id)
            else:
                right_region.append(element.element_id)

        regions: list[RegionModel] = []

        if left_region:
            regions.append(
                RegionModel(
                    name="left",
                    x_start=0,
                    y_start=0,
                    x_end=300,
                    y_end=self.DEFAULT_HEIGHT,
                    element_ids=left_region,
                )
            )

        if center_region:
            regions.append(
                RegionModel(
                    name="center",
                    x_start=300,
                    y_start=0,
                    x_end=700,
                    y_end=self.DEFAULT_HEIGHT,
                    element_ids=center_region,
                )
            )

        if right_region:
            regions.append(
                RegionModel(
                    name="right",
                    x_start=700,
                    y_start=0,
                    x_end=self.DEFAULT_WIDTH,
                    y_end=self.DEFAULT_HEIGHT,
                    element_ids=right_region,
                )
            )

        return regions