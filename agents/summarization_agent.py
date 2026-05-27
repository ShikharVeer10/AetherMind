from pydantic import BaseModel
from pydantic_ai import Agent


class SlideSummaryResponse(BaseModel):
    summary: str


slide_summary_agent = Agent(
    model="groq:llama-3.3-70b-versatile",
    output_type=SlideSummaryResponse,
    system_prompt=(
        """
    You are an enterprise document summarization assisstant. You need to generate concise and accurate slide summaries based on extracted slide content.
    Focus on key information, decisions, and action items.
    Avoid repeating the same information across summaries."""
    ),
)


class SummarizationAgent:
    async def summarize_slide(self, slide) -> str:
        slide_text_content = []
        for element in slide.elements:
            if element.text:
                slide_text_content.append(element.text)
        combined_slide_text = "\n".join(slide_text_content)

        prompt = f"""
        Slide Title:{slide.title}
        Slide Content:{combined_slide_text}

        Generate a concise enterprise-style summary for the slide
        Key information to highlight:
        -Main message of the slide
        -Important data, statistics, or figures
        -Any decisions made
        Output a clear, well-structured summary that captures the essence of the slide
        """
        result = await slide_summary_agent.run(prompt)
        return result.output.summary
