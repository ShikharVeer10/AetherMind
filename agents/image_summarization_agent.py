import base64
import io
import os
from typing import Optional

import requests


_IMAGE_PROMPT = """\
Analyse this image in exhaustive detail. You MUST respond using the EXACT section headings and structure shown below. Do NOT skip any section — write "N/A" if a section does not apply. Avoid vague placeholders like "business" or "thing" — be specific based on what is actually visible.

## 1. Visual Element Counts
Count every distinct visual element:
- Number of boxes / rectangles: <count>
- Number of arrows / connectors: <count>
- Number of panels / sections: <count>
- Number of icons / symbols: <count>
- Number of people / characters: <count>
- Other shapes (circles, diamonds, etc.): list with counts

## 2. Flowchart / Process Flow Mapping
If the image depicts any kind of process, flow, or diagram:
- Map each step as: Step N: [Box/Node Label]
- Show connections: [Source Box] → [Target Box] (arrow direction)
- If there are multiple parallel flows or branches, map each separately.
- If there is a clear reading order, state it explicitly.
If not a flowchart, write "N/A — this image is not a flowchart or process diagram."

## 3. Detailed Component Breakdown
For every box, shape, arrow, icon, or visual element:
- Describe its content (text, label, color, size, position relative to others)
- Describe what it represents in the context of the image
- Group related elements together (e.g., "Panel A contains…", "Panel B contains…")

## 4. Text Transcription
Transcribe ALL text visible in the image verbatim, preserving hierarchy and position.

## 5. Charts and Data
If the image contains charts, graphs, or data visualizations:
- Extract axis labels, legend items, data points, and trends.
If not applicable, write "N/A".

## 6. Summary & Interpretation
- Explain what the image is trying to communicate, explain, or illustrate as a whole.
- Describe the overall purpose, mood, and teaching intent of the image.
- If comparing concepts (e.g., side-by-side panels), explain what each side represents and the key differences.

## 7. Plain-language Summary
Provide a 2–4 sentence, human-friendly summary of what the image depicts in your own words.

## 8. Reconstructed Diagram Code (Mermaid.js)
Generate complete, valid Mermaid.js markup that visually reconstructs this diagram or flowchart.
- Use appropriate shapes (e.g., `id1[Text]`, `id2([Text])`, `id3{Decision}`) matching the original shapes.
- Use explicit arrow connections with labels if visible (e.g., `id1 -->|Action| id2`).
- Include subgraphs if there are panels or sections.
- Make sure the Mermaid code is self-contained and free of any markdown wrapper other than standard code fences. If the image is a plain picture and not a diagram or flowchart, represent its main entities and their relationships as a conceptual node graph.

Be extremely detailed, precise, and structured. Use numbered lists or bullet points within each section.
"""


class _LocalVisionAnalyzer:
    def __init__(self):
        self._caption_processor = None
        self._caption_model = None
        self._vqa_processor = None
        self._vqa_model = None
        self._available: Optional[bool] = None
        self._device = "cpu"

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                import torch  # noqa: F401
                import transformers  # noqa: F401
                from PIL import Image  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _ensure_loaded(self):
        if self._caption_model is not None:
            return
        from transformers import BlipProcessor, BlipForConditionalGeneration, BlipForQuestionAnswering
        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        print(
            f"[ImageSummary] Loading local BLIP models on device {self._device}..."
        )
        try:
            # Try loading from local cache first (no internet lookup)
            self._caption_processor = BlipProcessor.from_pretrained(
                "Salesforce/blip-image-captioning-large", local_files_only=True
            )
            self._caption_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-large", local_files_only=True
            ).to(self._device)
            self._vqa_processor = self._caption_processor
            self._vqa_model = BlipForQuestionAnswering.from_pretrained(
                "Salesforce/blip-vqa-capfilt-large", local_files_only=True
            ).to(self._device)
            print(f"[ImageSummary] Local vision models loaded from cache onto {self._device}.")
        except Exception as cache_exc:
            print(f"[ImageSummary] Local cache load failed: {cache_exc}. Trying to fetch online...")
            self._caption_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
            self._caption_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large").to(self._device)
            self._vqa_processor = self._caption_processor
            self._vqa_model = BlipForQuestionAnswering.from_pretrained("Salesforce/blip-vqa-capfilt-large").to(self._device)
            print(f"[ImageSummary] Local vision models downloaded and ready on {self._device}.")

    @staticmethod
    def _to_pil(image_bytes: bytes):
        from PIL import Image

        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    def _caption(self, pil_img) -> str:
        inputs = self._caption_processor(images=pil_img, return_tensors="pt").to(self._device)
        outputs = self._caption_model.generate(**inputs, max_new_tokens=150)
        return self._caption_processor.decode(outputs[0], skip_special_tokens=True)

    def _ask(self, pil_img, question: str) -> str:
        inputs = self._vqa_processor(images=pil_img, text=question, return_tensors="pt").to(self._device)
        outputs = self._vqa_model.generate(**inputs, max_new_tokens=50)
        return self._vqa_processor.decode(outputs[0], skip_special_tokens=True)


    def analyze(
        self,
        image_bytes: bytes,
        slide_title: Optional[str] = None,
        slide_text: Optional[str] = None,
    ) -> Optional[str]:
        """Return a structured summary, or *None* if local models are
        unavailable (missing packages)."""
        if not self.available:
            return None
        try:
            self._ensure_loaded()
        except Exception as exc:
            print(f"[ImageSummary] Failed to load local models: {exc}")
            self._available = False
            return None

        pil_img = self._to_pil(image_bytes)

        # 1. Generate a descriptive caption
        caption = self._caption(pil_img)

        # 2. Ask targeted questions
        topic = slide_title or "this topic"
        _questions = {
            "box_count": "How many boxes or rectangles are visible in this image?",
            "arrow_count": "How many arrows or connectors are visible in this image?",
            "concept": f"What concept does this image explain or illustrate related to {topic}?",
            "text_content": "What text or labels are visible in this image?",
            "flow": f"What is the step by step sequence or flow shown in this image related to {topic}?",
            "explanation": f"Explain in 2-4 sentences what this image is depicting and trying to illustrate related to {topic}.",
        }
        answers = {}
        for key, question in _questions.items():
            try:
                answers[key] = self._ask(pil_img, question)
            except Exception:
                answers[key] = "N/A"

        # 3. Assemble into the structured output format
        flow_section = answers.get("flow", "N/A")
        if flow_section.lower() in ("no", "none", "n/a", ""):
            flow_section = "N/A - this image is not a flowchart or process diagram."

        return (
            f"## 1. Visual Element Counts\n"
            f"- Number of boxes / rectangles: {answers['box_count']}\n"
            f"- Number of arrows / connectors: {answers['arrow_count']}\n"
            f"- Number of panels / sections: N/A (local model limitation)\n"
            f"- Number of icons / symbols: N/A (local model limitation)\n"
            f"- Number of people / characters: N/A (local model limitation)\n"
            f"\n"
            f"## 2. Flowchart / Process Flow Mapping\n"
            f"- Concept/process depicted: {answers['concept']}\n"
            f"- Flow/sequence: {flow_section}\n"
            f"\n"
            f"## 3. Detailed Component Breakdown\n"
            f"Caption-based description: {caption}\n"
            f"Visible text and labels: {answers['text_content']}\n"
            f"\n"
            f"## 4. Text Transcription\n"
            f"Visible text and labels: {answers['text_content']}\n"
            f"\n"
            f"## 5. Charts and Data\n"
            f"N/A (local model limitation — use Ollama or Gemini for chart analysis)\n"
            f"\n"
            f"## 6. Summary & Interpretation\n"
            f"{caption}."
            f" In the context of the slide topic '{topic}', this image illustrates {answers['concept']}.\n"
            f"\n"
            f"## 7. Plain-language Summary\n"
            f"{answers.get('explanation', 'N/A')}\n"
            f"\n"
            f"## 8. Reconstructed Diagram Code (Mermaid.js)\n"
            f"```mermaid\n"
            f"graph TD\n"
            f"    A[\"{topic}\"] --> B[\"{caption}\"]\n"
            f"```\n"
        )


# Module-level singleton — lazy; no work until .analyze() is called.
_local_analyzer = _LocalVisionAnalyzer()


class ImageSummaryAgent:
    system_prompt = _IMAGE_PROMPT

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self.model = model or os.getenv("OLLAMA_VISION_MODEL", "moondream")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def summarize_image(
        self,
        image_bytes: bytes,
        slide_title: Optional[str] = None,
        slide_text: Optional[str] = None,
    ) -> Optional[str]:
        """
        Analyse an image and return a structured description.

        Priority order:
          1. Local Ollama server vision model (no API key, e.g. moondream)
          2. Gemini 2.0 Flash (if GEMINI_API_KEY is set)
          3. Local BLIP models via transformers (no API key fallback)
        """
        if not image_bytes:
            return None

        # Create context-aware prompt for vision LLM (Ollama or Gemini)
        context_prompt = ""
        if slide_title or slide_text:
            context_prompt += "Context of the presentation/slide where this image is placed:\n"
            if slide_title:
                context_prompt += f"Slide Title/Topic: {slide_title}\n"
            if slide_text:
                context_prompt += f"Slide Text/Bullet points:\n{slide_text}\n"
            context_prompt += "---\n\n"
            context_prompt += "Your task is to analyze the image and explain it IN THE CONTEXT of the slide's topic and text.\n"

        vision_prompt = context_prompt + _IMAGE_PROMPT

        # 1. Local Ollama server with Vision Model (Moondream/Llava)
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                # Determine target model
                target_model = self.model
                if "moondream:latest" in models or "moondream" in models:
                    target_model = "moondream"
                elif "llava:latest" in models or "llava" in models:
                    target_model = "llava"
                
                # Check if we have at least one vision model installed
                has_vision = any("moondream" in m or "llava" in m for m in models)
                if has_vision:
                    print(f"[ImageSummary] Using local Ollama vision model: {target_model}...")
                    img_b64 = base64.b64encode(image_bytes).decode("ascii")
                    try:
                        payload = {
                            "model": target_model,
                            "prompt": vision_prompt,
                            "images": [img_b64],
                            "stream": False,
                        }
                        response = requests.post(
                            f"{self.host}/api/generate",
                            json=payload,
                            timeout=120,
                        )
                        if response.status_code == 200:
                            return response.json().get("response", "").strip() or None
                    except Exception as e:
                        print(f"[ImageSummary] Ollama vision prompt failed: {e}")
        except Exception as e:
            print(f"[ImageSummary] Local Ollama execution failed: {e}")

        # 2. Gemini 2.0 Flash — only if API key is available
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
                        vision_prompt
                    ]
                )
                if response.text:
                    return response.text
            except Exception as e:
                print(f"Gemini image summarization failed: {e}")

        # 2a. Groq Llama-3.2 Vision fallback — if GROQ_API_KEY is set
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                img_b64 = base64.b64encode(image_bytes).decode("ascii")

                mime_type = "image/png"
                if image_bytes.startswith(b"\xff\xd8"):
                    mime_type = "image/jpeg"
                elif image_bytes.startswith(b"GIF8"):
                    mime_type = "image/gif"

                image_url = f"data:{mime_type};base64,{img_b64}"
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": vision_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url},
                                },
                            ],
                        }
                    ],
                    model="llama-3.2-11b-vision-preview",
                )
                if response.choices[0].message.content:
                    return response.choices[0].message.content
            except Exception as e:
                print(f"Groq vision image summarization failed: {e}")

        # 2b. OpenAI GPT-4o-mini Vision fallback — if OPENAI_API_KEY is set
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                img_b64 = base64.b64encode(image_bytes).decode("ascii")

                mime_type = "image/png"
                if image_bytes.startswith(b"\xff\xd8"):
                    mime_type = "image/jpeg"
                elif image_bytes.startswith(b"GIF8"):
                    mime_type = "image/gif"

                image_url = f"data:{mime_type};base64,{img_b64}"
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": vision_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url},
                                },
                            ],
                        }
                    ],
                    model="gpt-4o-mini",
                )
                if response.choices[0].message.content:
                    return response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI vision image summarization failed: {e}")


        # 3. Local BLIP models via transformers (fallback if Ollama / Gemini is not available)
        print("[ImageSummary] Local Ollama and Gemini unavailable. Falling back to local BLIP models...")
        local_result = _local_analyzer.analyze(
            image_bytes,
            slide_title=slide_title,
            slide_text=slide_text,
        )
        if local_result:
            return local_result

        return None

