"""
Chart Understanding Service
Extracts semantic components of a chart.
"""

from typing import Any
from models.document_model import DocumentElementModel, ChartUnderstandingModel, ChartAxisModel, ChartSeriesModel

class ChartUnderstandingService:
    def extract_understanding(self, element: DocumentElementModel) -> ChartUnderstandingModel:
        """
        Extracts axes, series, categories, and legends.
        """
        chart_type = element.metadata.get("detected_chart_type", "unknown_chart")
        
        # In a real CV system, this extracts exact visual data.
        # Here we mock the structural extraction.
        
        series = [
            ChartSeriesModel(name="Series 1", values=[10, 20, 30], color="#ff0000")
        ]
        axes = {
            "x": ChartAxisModel(min=0, max=100, ticks=["0", "50", "100"], axis_type="linear"),
            "y": ChartAxisModel(ticks=["A", "B", "C"], axis_type="category")
        }
        
        model = ChartUnderstandingModel(
            chart_id=element.element_id,
            chart_type=chart_type,
            title="Extracted Chart Title",
            categories=["A", "B", "C"],
            series=series,
            legend=["Series 1"],
            axes=axes,
            data_labels=["10%", "20%", "30%"],
            insights=["Series 1 peaks at category C"],
            visual_relationships=["Legend maps to bar colors"]
        )
        return model

