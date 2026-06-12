"""
Visual Object Classifier Service
Classifies visual regions to prevent charts from being processed as tables.
"""

from typing import List
from models.document_model import DocumentElementModel, VisualObjectClass

class VisualObjectClassifierService:
    def classify_elements(self, elements: List[DocumentElementModel]) -> None:
        """
        Classifies each element or region into one of the designated classes:
        table, chart, diagram, dashboard, timeline, matrix, capability_map,
        governance_framework, organization_chart, infographic, image, mixed_content.
        """
        for element in elements:
            # Baseline: images are often charts in these reports
            text_content = (element.text or "").lower()
            name = str(element.metadata.get("name", "")).lower()
            
            chart_keywords = [
                "chart", "plot", "axis", "legend", "series", "data points", 
                "centralization", "shared services", "fragmentation", 
                "labor cost", "soc", "span of control", "fte", "funding type",
                "horizontal bar", "stacked bar", "pie"
            ]
            
            is_potential_chart = (
                element.element_type == "chart" or 
                any(k in text_content for k in chart_keywords) or
                any(k in name for k in chart_keywords)
            )

            if is_potential_chart:
                element.metadata["visual_class"] = VisualObjectClass(classification="chart", confidence=0.85).model_dump()
                continue

            if element.element_type == "image":
                # Images might be charts. If they have chart-like names or text, they were handled above.
                # Otherwise, keep as image.
                element.metadata["visual_class"] = VisualObjectClass(classification="image", confidence=0.9).model_dump()
                continue
            
            if element.element_type == "table" or "table" in text_content:
                # To avoid misclassifying charts as tables, we double check
                if "axis" in text_content or "legend" in text_content:
                     element.metadata["visual_class"] = VisualObjectClass(classification="chart", confidence=0.6).model_dump()
                else:
                     element.metadata["visual_class"] = VisualObjectClass(classification="table", confidence=0.8).model_dump()
            elif "dashboard" in text_content:
                element.metadata["visual_class"] = VisualObjectClass(classification="dashboard", confidence=0.7).model_dump()
            elif "diagram" in text_content or "flow" in text_content:
                element.metadata["visual_class"] = VisualObjectClass(classification="diagram", confidence=0.7).model_dump()
            else:
                element.metadata["visual_class"] = VisualObjectClass(classification="mixed_content", confidence=0.5).model_dump()

