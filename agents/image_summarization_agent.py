import base64
import os
from typing import Optional

import requests


_IMAGE_PROMPT = """\
Analyse this image in exhaustive detail and interpret what it depicts. Your response must cover:

1. **Objects and people**: List every distinct object, person, icon, or symbol
   visible in the image.  Describe colours, sizes, and positions.
2. **Text overlays**: Transcribe any text visible in the image verbatim.
3. **Spatial layout**: Describe where objects are relative to each other
   (left/right, above/below, inside/outside).
4. **Diagrams and flowcharts**: If the image depicts a process, flow, or
   architecture diagram, describe each step/node and the connections
   between them.  State the direction of arrows.
5. **Charts and data**: If the image contains a chart or graph, extract the
   data points, axis labels, legend items, and overall trend.
6. **Mood and context**: Describe the overall scene, mood, or purpose of the
   image (e.g., "a corporate org chart", "a photo of a city skyline").
7. **Interpretation**: Explain what the image is meant to communicate or
   illustrate, even if it is a photograph or artwork.

Be detailed but structured.  Use numbered lists or bullet points.
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
        Send image bytes to Ollama and return a detailed description.
        Returns None if the image is empty or the call fails.
        """
        if not image_bytes:
            return None

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
