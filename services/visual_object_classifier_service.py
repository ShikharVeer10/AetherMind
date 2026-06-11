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
            # Baseline heuristic: if it's already identified as an image, classify as image
            if element.element_type == "image":
                element.metadata["visual_class"] = VisualObjectClass(classification="image", confidence=0.9).model_dump()
                continue
            
            # Simple heuristic checking for chart/table features based on element metadata or type
            # In a full implementation, this uses visual/geometry heuristics or CV models.
            text_content = (element.text or "").lower()
            
            # Identify charts by content (just a baseline heuristic)
            if element.element_type == "chart" or any(keyword in text_content for keyword in ["chart", "plot", "axis", "legend", "series", "data points"]):
                element.metadata["visual_class"] = VisualObjectClass(classification="chart", confidence=0.8).model_dump()
            elif element.element_type == "table" or "table" in text_content:
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

