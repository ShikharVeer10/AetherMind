from pydantic import BaseModel
from pydantic_ai import Agent


class SlideSummaryResponse(BaseModel):
    summary: str


slide_summary_agent = Agent(
    model="groq:llama-3.3-70b-versatile",
    output_type=SlideSummaryResponse,
    system_prompt=(
        """
        You are an enterprise document summarization assistant.
        You need to generate concise and accurate slide summaries based on extracted slide content.
        Focus on key information, decisions, structure, and action items.
        Preserve the meaning of the slide without repeating the same information across summaries.
        """
    ),
)


class SummarizationAgent:
    async def summarize_slide(self, slide) -> str:
        slide_text_content = []
        for element in slide.elements:
            if element.text:
                slide_text_content.append(element.text)
        combined_slide_text = "\n".join(slide_text_content)

        header_texts = [header.text for header in getattr(slide, "headers", []) if header.text]
        footer_texts = [footer.text for footer in getattr(slide, "footers", []) if footer.text]
        context = getattr(slide, "context", None)
        context_summary = ""
        if context:
            context_summary = (
                f"Context: title_count={context.title_count}, box_count={context.box_count}, "
                f"arrow_count={context.arrow_count}, flowchart_detected={context.flowchart_detected}, "
                f"image_count={context.image_count}, table_count={context.table_count}."
            )

        prompt = f"""
Slide Title: {slide.title}
Headers: {"; ".join(header_texts) if header_texts else "None"}
Footers: {"; ".join(footer_texts) if footer_texts else "None"}
{context_summary}
Slide Content:
{combined_slide_text}

Generate a concise enterprise-style summary for the slide.
Key information to highlight:
- Main message of the slide
- Important data, statistics, or figures
- Any decisions made
- If the slide shows a flowchart or diagram, briefly describe the structure and flow

Output a clear, well-structured summary that captures the essence of the slide.
"""
        result = await slide_summary_agent.run(prompt)
        return result.output.summary
