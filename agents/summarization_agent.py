"""
AI agent that generates a concise summary of what a slide *depicts*.

Now receives the full slide context (visual inventory, layout, relationships,
flowchart info) so the summary is aware of the slide's structure, not just
its text.
"""

from pydantic import BaseModel
from pydantic_ai import Agent


class SlideSummaryResponse(BaseModel):
    summary: str


slide_summary_agent = Agent(
    model="google-gla:gemini-2.0-flash",
    output_type=SlideSummaryResponse,
    system_prompt=(
        "You are an enterprise document analysis assistant. "
        "Generate concise, accurate slide summaries that describe "
        "what the slide DEPICTS — not just its text. "
        "Consider the visual layout, element counts, relationships, "
        "flowcharts, and images when summarising. "
        "Focus on key information, decisions, and action items. "
        "Do not repeat the same information across summaries."
    ),
)


class SummarizationAgent:
    system_prompt = (
        "Summarize slide intent and visuals using verbatim text, layout, "
        "relationships, and image descriptions."
    )

    async def summarize_slide(
        self,
        slide,
        context_outline: str = "",
        image_summaries: str = "",
    ) -> str:
        """
        Build a rich prompt from the slide's text AND its structural
        context, then ask Gemini for a summary.
        """
        text_lines: list[str] = []
        if getattr(slide, "text_points", None):
            for point in slide.text_points:
                text_lines.append(f"  [L{point.level}] {point.text}")
        else:
            for element in slide.elements:
                if element.paragraphs:
                    for para in element.paragraphs:
                        text_lines.append(f"  [L{para.level}] {para.text}")
                elif element.text:
                    text_lines.append(f"  {element.text}")

        slide_text = "\n".join(text_lines) if text_lines else "(no text)"

        prompt = f"""\
Slide {slide.slide_number}
Title: {slide.title or '(none)'}

--- Extracted Text (verbatim, one bullet per line) ---
{slide_text}

--- Slide Context ---
{context_outline or '(no context available)'}

--- Image Descriptions ---
{image_summaries or '(no images)'}

Generate a concise enterprise-style summary of what this slide depicts.
Include:
- The main message or purpose of the slide
- Key data, statistics, or figures mentioned
- Any decisions, conclusions, or action items
- A brief description of the visual layout or diagram if relevant
"""

        result = await slide_summary_agent.run(prompt)
        return result.output.summary
