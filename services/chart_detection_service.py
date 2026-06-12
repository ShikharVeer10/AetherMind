
from typing import List
from models.document_model import DocumentElementModel

class ChartDetectionService:
    def detect_charts(self, elements: List[DocumentElementModel]) -> None:
        for element in elements:
            vclass = element.metadata.get("visual_class", {})
            if isinstance(vclass, dict) and vclass.get("classification") == "chart":
                chart_type = "horizontal_bar_chart" # fallback default
                text = (element.text or "").lower()
                if "pie" in text:
                    chart_type = "pie_chart"
                elif "line" in text or "trend" in text:
                    chart_type = "line_chart"
                elif "scatter" in text:
                    chart_type = "scatter_plot"
                    
                element.metadata["detected_chart_type"] = chart_type

