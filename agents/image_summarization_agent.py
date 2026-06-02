import base64
import os
from typing import Optional

import requests


_IMAGE_PROMPT = """\
Analyse this image in exhaustive detail, detect and count its components, and interpret what it depicts. Your response must cover:

1. **Detection and Counts**: Count and list the exact number of boxes, arrows, shapes, panels, or other visual layout constraints visible in the image. Specify their colors, text content, and visual roles.
2. **Objects and people**: List every distinct object, person, icon, or symbol visible. Describe their appearance, colors, sizes, and positions.
3. **Text overlays**: Transcribe any text or labels visible in the image verbatim.
4. **Spatial layout and Constraints**: Describe where objects/panels are located relative to each other (e.g., side-by-side comparison, grid layout, groupings).
5. **Diagrams and flowcharts**: If the image depicts a process, flow, or diagram, describe each step/node and the connections between them. Clearly identify which boxes are linked by which arrows, including the direction of the flow.
6. **Charts and data**: If the image contains a chart or graph, extract the data points, axis labels, legend items, and overall trend.
7. **Mood and context**: Describe the overall scene, mood, or purpose of the image.
8. **Interpretation**: Explain what the image is trying to communicate, explain, or illustrate.

Be extremely detailed, precise, and structured. Use numbered lists or bullet points.
"""


class ImageSummaryAgent:
    system_prompt = _IMAGE_PROMPT

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self.model = model or os.getenv("OLLAMA_VISION_MODEL", "llava")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def summarize_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Send image bytes to a vision model and return a detailed description.
        First attempts to use Gemini 2.0 Flash (if API key is present).
        Falls back to local Ollama.
        """
        if not image_bytes:
            return None

        # 1. Attempt to use Gemini 2.0 Flash Vision
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client()

                # Determine MIME type from file signature
                mime_type = "image/png"
                if image_bytes.startswith(b"\xff\xd8"):
                    mime_type = "image/jpeg"
                elif image_bytes.startswith(b"GIF8"):
                    mime_type = "image/gif"

                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type,
                        ),
                        _IMAGE_PROMPT
                    ]
                )
                if response.text:
                    return response.text
            except Exception as e:
                print(f"Gemini image summarization failed: {e}. Falling back to Ollama.")

        # 2. Fallback to local Ollama
        payload = {
            "model": self.model,
            "prompt": _IMAGE_PROMPT,
            "images": [base64.b64encode(image_bytes).decode("ascii")],
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response")
        except Exception:
            return None
