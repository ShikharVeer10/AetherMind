import re
from typing import Any, Dict, List, Optional
from models.document_model import ChartUnderstandingModel, DocumentElementModel, SlideModel

class ChartUnderstandingService:
    def analyze_chart_element(
        self,
        element: DocumentElementModel,
        slide: Optional[SlideModel] = None
    ) -> ChartUnderstandingModel:
        chart_info = ChartUnderstandingModel()
        
        # 1. Check if there is native chart data extracted from PPTX
        raw_data = element.metadata.get("chart_data")
        if raw_data:
            chart_info.raw_chart_data = raw_data
            chart_info.title = raw_data.get("title")
            
            # Extract dimensions and measures
            chart_info.dimensions = raw_data.get("categories", [])
            chart_info.measures = [s.get("name", "") for s in raw_data.get("series", [])]
            
            # Detect chart type
            chart_type_str = raw_data.get("chart_type", "").lower()
            if "bar" in chart_type_str or "column" in chart_type_str:
                chart_info.chart_type = "bar_chart"
            elif "line" in chart_type_str:
                chart_info.chart_type = "line_chart"
            elif "pie" in chart_type_str or "doughnut" in chart_type_str:
                chart_info.chart_type = "pie_chart"
            elif "stacked" in chart_type_str:
                chart_info.chart_type = "stacked_chart"
            else:
                chart_info.chart_type = "bar_chart"  # default fallback

            # Analyze trends, anomalies, and comparisons
            self._analyze_numerical_data(raw_data, chart_info)
        
        # 2. Check if we can extract chart reasoning from slide text/summaries
        if slide:
            self._extract_from_slide_context(element, slide, chart_info)
            
        return chart_info

    def _analyze_numerical_data(self, raw_data: Dict[str, Any], chart_info: ChartUnderstandingModel):
        series = raw_data.get("series", [])
        categories = raw_data.get("categories", [])
        
        trends = []
        anomalies = []
        comparisons = []
        
        for s in series:
            name = s.get("name", "Series")
            values = s.get("values", [])
            # filter out non-numeric values
            num_values = [v for v in values if isinstance(v, (int, float))]
            if not num_values:
                continue
                
            # Basic Trend Detection
            if len(num_values) >= 2:
                first = num_values[0]
                last = num_values[-1]
                diff = last - first
                pct = (diff / first * 100) if first != 0 else 0
                if pct > 5:
                    trends.append(f"Series '{name}' shows an upward trend of {pct:.1f}% from {first} to {last}.")
                elif pct < -5:
                    trends.append(f"Series '{name}' shows a downward trend of {abs(pct):.1f}% from {first} to {last}.")
                else:
                    trends.append(f"Series '{name}' remains relatively stable around {first}.")
                    
            # Basic Anomalies (Outliers) Detection
            if len(num_values) >= 3:
                avg = sum(num_values) / len(num_values)
                variance = sum((x - avg) ** 2 for x in num_values) / len(num_values)
                std_dev = variance ** 0.5
                for idx, v in enumerate(num_values):
                    if std_dev > 0 and abs(v - avg) > 2 * std_dev:
                        cat_label = categories[idx] if idx < len(categories) else f"index {idx}"
                        anomalies.append(f"Anomaly detected in '{name}' at {cat_label}: value {v} deviates significantly from the average {avg:.2f}.")

            # Comparisons
            if len(num_values) >= 1:
                max_val = max(num_values)
                min_val = min(num_values)
                max_idx = num_values.index(max_val)
                min_idx = num_values.index(min_val)
                
                max_cat = categories[max_idx] if max_idx < len(categories) else f"index {max_idx}"
                min_cat = categories[min_idx] if min_idx < len(categories) else f"index {min_idx}"
                
                comparisons.append(f"Series '{name}' peaks at {max_cat} with {max_val} and is lowest at {min_cat} with {min_val}.")

        chart_info.trends.extend(trends)
        chart_info.anomalies.extend(anomalies)
        chart_info.comparisons.extend(comparisons)

    def _extract_from_slide_context(self, element: DocumentElementModel, slide: SlideModel, chart_info: ChartUnderstandingModel):
        # Look for keywords in slide text and image summaries
        text_content = []
        if slide.title:
            text_content.append(slide.title)
        for e in slide.elements:
            if e.text:
                text_content.append(e.text)
                
        # Also check image summaries on the element or slide
        img_sum = element.metadata.get("image_summary") or element.metadata.get("summary")
        if img_sum:
            text_content.append(img_sum)
            
        combined_text = "\n".join(text_content).lower()
        
        # Infer chart type if not set
        if chart_info.chart_type == "none":
            if "bar chart" in combined_text or "column chart" in combined_text:
                chart_info.chart_type = "bar_chart"
            elif "line chart" in combined_text or "trend line" in combined_text:
                chart_info.chart_type = "line_chart"
            elif "pie chart" in combined_text or "donut chart" in combined_text:
                chart_info.chart_type = "pie_chart"
            elif "stacked" in combined_text:
                chart_info.chart_type = "stacked_chart"
            elif "dashboard" in combined_text:
                chart_info.chart_type = "dashboard"
            elif "kpi" in combined_text or "key performance indicator" in combined_text:
                chart_info.chart_type = "kpi_card"
            elif element.element_type == "chart":
                chart_info.chart_type = "bar_chart"  # default fallback for chart element
                
        # Extract title from text if missing
        if not chart_info.title:
            match = re.search(r'(?:chart|figure|graph)(?:\s+showing|\s+of)?\s+([^.\n]+)', combined_text)
            if match:
                chart_info.title = match.group(1).strip().capitalize()
            elif slide.title:
                chart_info.title = slide.title
