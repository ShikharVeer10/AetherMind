"""
Counts all visual elements on a slide, grouped by element_type.
"""

from typing import List
from models.document_model import DocumentElementModel, VisualInventoryModel


class VisualInventoryService:

    def count(
        self, elements: List[DocumentElementModel]
    ) -> VisualInventoryModel:
        """Iterate elements and tally by type."""
        counts = {
            "text_box": 0,
            "shape": 0,
            "arrow": 0,
            "connector": 0,
            "image": 0,
            "table": 0,
            "group": 0,
            "chart": 0,
            "placeholder": 0,
            "unknown": 0,
        }

        for element in elements:
            t = element.element_type
            if t in counts:
                counts[t] += 1
            else:
                counts["unknown"] += 1

        return VisualInventoryModel(
            text_box_count=counts["text_box"],
            shape_count=counts["shape"],
            arrow_count=counts["arrow"],
            connector_count=counts["connector"],
            image_count=counts["image"],
            table_count=counts["table"],
            group_count=counts["group"],
            chart_count=counts["chart"],
            placeholder_count=counts["placeholder"],
            unknown_count=counts["unknown"],
            total_elements=len(elements),
        )
