import os
import json
import base64
from typing import Any,Dict
from models.document_model import DocumentElementModel,ChartUnderstandingModel, ChartAxisModel, ChartSeriesModel

_CHART_EXTRACTION_PROMPT="""
You are an expert data visualization analyst. Your task is to analyze the provided chart image and extract its structure and data perfectly so that it can be reconstructed identically.

1. Detect the exact type of chart(e.g., 'bar_chart', 'stacked_bar_chart', 'horizontal_bar_chart','line_graph','pie_chart','tornado_chart','donut_chart',etc.)
2. Extract the title,subtitle, categories(X-Axis or Y-Axis labels depending on the orientation), all data series(with their exact numerical values and legend names),data labes, and axis configurations.
3. Pay close attention to the stacked bars(extract values for each stack segment) and diverging or tornado charts(preserve positive directions or negative directions).

Provide the output strictly as a JSON object matching the following structure"
{
    "chart_type":"string",
    "title":"string or null",
    "categories":["string","string"],
    "series":[
    {
        "name": "string",
        "values": [number,number],
        "color": "string or null"
    }
],
"legend":["string"],
"axes": {
"x":{"min" number or null, "max":number or null,"ticks": ["string"], "label": "string","axis_type": "linear or category"},
"y":{"min" number or null, "max":number or null,"ticks": ["string"], "label": "string","axis_type": "linear or category"}
},
"data_labels": ["string"],
"insights": ["string"],
"visual_relationships": ["string"]
}

Do not include markdown blocks like '''json or any other text outside the JSON. Return only the raw JSON string.
"""
class ChartUnderstandingService:
    def extract_understanding(self,element:DocumentElementModel) -> ChartUnderstandingModel:
        chart_type=element.metadata.get("detected_chart_type", "unknown_chart")
        image_bytes=element.metadata.get("__image_bytes")
        if image_bytes:
            extracted_data = self._call_vision_llm(image_bytes)
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
                            "content:" [
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
                return self.__clean__load__json(content)
            except Exception as e:
                print("Error calling OpenAI chart service")
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
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            categories=data.get("categories", []),
              series=series_models,
              legend=data.get("legend", []),
              axes=axes_models,
              data_labels=data.get("data_labels", [])
        )
