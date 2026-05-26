import base64
import os
from typing import Optional

import requests


class ImageSummaryAgent:
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_VISION_MODEL", "llava")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def summarize_image(self, image_bytes: bytes) -> Optional[str]:
        if not image_bytes:
            return None
        payload = {
            "model": self.model,
            "prompt": (
                "Summarize the image or diagram clearly. Describe the main objects, "
                "relationships, and any flow/sequence shown. Keep it detailed but concise."
            ),
            "images": [base64.b64encode(image_bytes).decode("ascii")],
            "stream": False,
        }
        response = requests.post(
            f"{self.host}/api/generate", json=payload, timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response")