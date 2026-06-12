import os
import json
import base64
from typing import Any,Dict
from models.document_model import DocumentElementModel,ChartUnderstandingModel, ChartAxisModel, ChartSeriesModel

_CHART_EXTRACTION_PROMPT="""
You are an expert data visualization and document reconstruction analyst. Your task is to analyze the provided chart image and extract its structure and data with EXTREME precision so it can be recreated identically.

### 1. High-Density Stacked Bar Charts (Critical)
Many charts in this set are horizontal stacked bar charts where each bar represents a 'Process' or 'Location' and each segment of the bar represents a 'Division' or 'Funding Type'.
- **Exhaustive Extraction**: You MUST extract EVERY segment of EVERY bar. Do not skip small segments or group them as 'Other' unless the chart explicitly does so.
- **Segment Order**: Preserve the exact left-to-right (or bottom-to-top) order of segments within each stack.
- **Values**: Extract the numerical values (absolute or percentage) for each segment. If not explicitly labeled, estimate the proportion based on the visual width of the segment.

### 2. Legend & Color Mapping
- **Identical Colors**: Extract the exact or closest Hex color code for every series in the legend.
- **Label Mapping**: Create a precise mapping between colors and their textual labels in the legend.

### 3. Axis & Scales
- **Units**: Identify the units (e.g., 'FTE', 'Cost ($K)', 'Percentage (%)', 'Number of Employees').
- **Scales**: Extract the min, max, and major tick marks for all axes.

### 4. Specialized Charts
- **Span of Control**: For 'Span of Control by Layer' charts, extract the Layer Number (1, 2, 3...) and the corresponding Avg. SoC value (e.g., 7.0, 4.8) and the Number of Managers.
- **Pie Charts**: Extract the exact segments, their values, and their associated legend labels.

### Output Structure (JSON)
Provide the output strictly as a JSON object:
{
    "chart_type": "stacked_bar_chart | grouped_bar_chart | pie_chart | line_chart | span_of_control_pyramid | etc",
    "orientation": "horizontal | vertical",
    "stacking": "100_percent_stacked | stacked | grouped | none",
    "title": "Exact title text",
    "subtitle": "Exact subtitle text",
    "units": "The unit of measurement",
    "categories": ["Y-Axis labels for horizontal charts", "X-Axis labels for vertical charts"],
    "series": [
        {
            "name": "Series Name (from legend)",
            "color": "Hex color code",
            "values": [number, number, ...] // Corresponding to categories
        }
    ],
    "legend_mapping": {
        "color_code": "label_name"
    },
    "axes": {
        "x": {"min": 0, "max": 100, "ticks": ["0", "20", ...], "label": "X-axis title"},
        "y": {"min": 0, "max": 100, "ticks": ["A", "B", ...], "label": "Y-axis title"}
    },
    "data_labels_visible": true,
    "reconstruction_hints": "Specific instructions for identical visual reproduction"
}

Do not include markdown blocks like ```json. Return ONLY the raw JSON string.
"""
class ChartUnderstandingService:
    def extract_understanding(self,element:DocumentElementModel) -> ChartUnderstandingModel:
        chart_type=element.metadata.get("detected_chart_type", "unknown_chart")
        image_bytes=element.metadata.get("__image_bytes")
        if image_bytes:
            extracted_data = self.call_vision_llm(image_bytes)
            if extracted_data:
                return self._parse_json_to_model(element.element_id, extracted_data)
        return ChartUnderstandingModel(
            chart_id=element.element_id,
            chart_type=chart_type,
            title="Extraction has failed or no image detected",
        )

    def call_vision_llm(self,image_bytes:bytes) ->dict:
        openai_key=os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                client=OpenAI(api_key=openai_key)
                base64_image=base64.b64encode(image_bytes).decode('utf-8')

                response=client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": _CHART_EXTRACTION_PROMPT
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type":"text", "text": "Extract the exact chart details into JSON."},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=4000,
                    temperature=0.0
                )
                content=response.choices[0].message.content.strip()
                return self._clean_and_load_json(content)
            except Exception as e:
                print(f"Error calling OpenAI chart service: {e}")
        gemini_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=gemini_key)

                response = client.models.generate_content(
                      model='gemini-2.5-pro',
                      contents=[
                          _CHART_EXTRACTION_PROMPT,
                          "Extract the exact chart details into JSON.",
                          types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
                      ],
                      config=types.GenerateContentConfig(
                          temperature=0.0,
                          response_mime_type="application/json",
                      )
                  )
                return json.loads(response.text.strip())
            except Exception as e:
                print(f"[ChartUnderstanding] Gemini Vision extraction failed: {e}")

        print("[ChartUnderstanding] No suitable Vision API key found or all requests failed.")
        return None

    def _clean_and_load_json(self, content: str) -> dict:
        if content.startswith("json"):
              content = content[7:]
        if content.startswith("`"):
              content = content[3:]
        if content.endswith(" "):
            content = content[:-3]
        return json.loads(content.strip())

    def _parse_json_to_model(self, element_id: str, data: dict) -> ChartUnderstandingModel:
        series_models = []
        for s in data.get("series", []):
            series_models.append(ChartSeriesModel(
                name=s.get("name", ""),
                values=s.get("values", []),
                color=s.get("color")
            ))

        axes_models = {}
        for axis_key, axis_data in data.get("axes", {}).items():
            axes_models[axis_key] = ChartAxisModel(
                min=axis_data.get("min"),
                max=axis_data.get("max"),
                ticks=axis_data.get("ticks", []),
                label=axis_data.get("label"),
                axis_type=axis_data.get("axis_type", "linear")
            )

        return ChartUnderstandingModel(
            chart_id=element_id,
            chart_type=data.get("chart_type", "unknown_chart"),
            orientation=data.get("orientation"),
            stacking=data.get("stacking"),
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            units=data.get("units"),
            categories=data.get("categories", []),
            series=series_models,
            legend=data.get("legend", []),
            legend_mapping=data.get("legend_mapping", {}),
            axes=axes_models,
            data_labels=data.get("data_labels", []),
            data_labels_visible=data.get("data_labels_visible", False),
            reconstruction_hints=data.get("reconstruction_hints")
        )
