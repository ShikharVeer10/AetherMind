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
    model="google:gemini-2.0-flash",
    output_type=SlideSummaryResponse,
    system_prompt=(
        "You are an enterprise document analysis assistant. "
        "Generate concise, accurate slide summaries that explain in your own words "
        "what the slide DEPICTS, explains, or illustrates. "
        "CRITICAL: Do NOT copy exact sentences, statements, or bullet points from the slide text verbatim. "
        "Instead, synthesize the visual layout, element counts, relationships, flowcharts, "
        "tables, images, and text to explain the core concept, purpose, and intent of the slide "
        "in your own original phrasing."
    ),
)


class SummarizationAgent:
    system_prompt = (
        "Summarize slide intent, visuals, and structure in original words, "
        "avoiding verbatim text copying."
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

Explain in your own words what this slide depicts, explains, or illustrates.
CRITICAL: Do NOT repeat the exact statements or copy-paste verbatim sentences from the extracted text. Use original phrasing to synthesize the slide's main concept, intent, visual layout, and diagrams/images.
Include:
- The main message or purpose of the slide
- Key data, statistics, or figures mentioned
- Any decisions, conclusions, or action items
- A brief description of the visual layout or diagram if relevant
"""

        result = await slide_summary_agent.run(prompt)
        return result.output.summary
