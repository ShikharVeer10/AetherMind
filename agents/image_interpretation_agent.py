from typing import Optional
from openai import AsyncOpenAI
class ImageInterpretationAgent:
    def __init__(self):
        self.client = AsyncOpenAI()
    async def interpret_image(self,image_bytes: bytes,slide_title: Optional[str] = None) -> str:
        prompt = self._build_prompt(slide_title=slide_title)
        response = await self.client.responses.create(
            model="gpt-4.1",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_data": image_bytes
                        }
                    ]
                }
            ]
        )
        return response.output_text
    def _build_prompt(self,slide_title: Optional[str]) -> str:
        title_context = ""
        if slide_title:
            title_context = f"Slide Title: {slide_title}\n\n"

        return f"""
{title_context}

You are an expert researcher,
educator,
presentation analyst,
diagram analyst,
and visual reasoning expert.

Your task is NOT to describe pixels.

Your task is to understand:

1. What is happening in the image.
2. What concept is being taught.
3. Why the image exists.
4. What information the author is trying to communicate.
5. The semantic meaning of every major visual component.
6. The flow of information from one component to another.
7. The relationships between entities.
8. The educational interpretation.
9. The conceptual abstraction shown.
10. A complete reconstruction description such that another LLM could recreate a near-identical image.

Return your response EXACTLY in this format:

Semantic Flow
<detailed explanation>

Step-by-step Meaning
<detailed numbered explanation>

Conceptual Layers
<identify all concepts>

Visual Design Details
<layout, colours, connectors, shapes, hierarchy>

Educational Interpretation
<how a professor would explain it>

Plain English Summary
<simple explanation>

Image Recreation Blueprint
<extremely detailed image generation description>

Do not talk about pixels.

Do not give OCR.

Focus on meaning,
relationships,
flow,
reasoning,
and educational intent.
"""