
from models.document_model import ChartUnderstandingModel

class ChartReconstructionService:
    def build_reconstruction_data(self, understanding: ChartUnderstandingModel) -> dict:

        if not understanding:
            return {}
            
        return {
            "chart_type": understanding.chart_type,
            "categories": understanding.categories,
            "series": [s.model_dump() for s in understanding.series],
            "axis": {k: v.model_dump() for k, v in understanding.axes.items()},
            "legend": understanding.legend,
            "data_labels": understanding.data_labels,
            "reconstruction_prompt": f"Recreate a {understanding.chart_type} with categories {understanding.categories}."
        }
