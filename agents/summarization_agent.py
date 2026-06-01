from pydantic import BaseModel
from pydantic_ai import Agent


class SlideSummaryResponse(BaseModel):
    summary: str


slide_summary_agent = Agent(
    model="groq:llama-3.3-70b-versatile",
    output_type=SlideSummaryResponse,
    system_prompt=(
        """
        You are an enterprise document summarization assistant specializing in slide understanding.
        Your job is to produce a detailed, faithful, and well-structured summary of slide content.

        Follow these rules:
        - Extract each visible point as the same point as mentioned in the slide whenever possible.
        - Preserve the original meaning and wording of slide text rather than paraphrasing heavily.
        - Include slide context as part of the summary, including the outline structure of the slide.
        - If the slide contains a flowchart, detect the number of boxes, the number of arrows, and the relationship mapping between every box.
        - If the slide contains a diagram, explain the structure, object relationships, and flow.
        - If the slide contains images or pictures, interpret them in detail and summarize what they depict.
        - Extract and include headers and footers explicitly.
        - Handle complex slides carefully and do not oversimplify them.
        - Capture title, hierarchy, section structure, labels, and any important visual cues.
        - Be accurate, concise where possible, but complete when the slide is complex.

        Output should be a single coherent summary that covers:
        1. Header and footer details
        2. Slide title and key text points
        3. Context and structure of the slide
        4. Flowchart/diagram mapping if present
        5. Image interpretation if present
        6. Final summary of what the slide depicts
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
                "Context details:\n"
                f"- title_count: {context.title_count}\n"
                f"- box_count: {context.box_count}\n"
                f"- arrow_count: {context.arrow_count}\n"
                f"- flowchart_detected: {context.flowchart_detected}\n"
                f"- image_count: {context.image_count}\n"
                f"- table_count: {context.table_count}\n"
            )

        structure_summary = ""
        slide_structure = getattr(slide, "structure", None)
        if slide_structure:
            structure_summary = f"Slide Structure: {slide_structure}\n"

        image_summary = ""
        slide_images = getattr(slide, "images", None)
        if slide_images:
            image_descriptions = []
            for image in slide_images:
                description = getattr(image, "description", None) or getattr(image, "text", None)
                if description:
                    image_descriptions.append(str(description))
            if image_descriptions:
                image_summary = "Image details:\n" + "\n".join(f"- {desc}" for desc in image_descriptions) + "\n"

        prompt = f"""
Slide Title: {slide.title}
Headers: {"; ".join(header_texts) if header_texts else "None"}
Footers: {"; ".join(footer_texts) if footer_texts else "None"}
{context_summary}{structure_summary}{image_summary}
Slide Content:
{combined_slide_text}

Instructions:
- Extract the visible text points in the same order and, when possible, use the same wording as shown on the slide.
- Describe the slide outline and structure.
- If the slide is a flowchart or process diagram, state the number of boxes, the number of arrows, and the mapping between boxes.
- If the slide contains relationships between boxes, show the flow from one box to another.
- If the slide contains images, interpret them in detail.
- Include headers and footers explicitly.
- Provide a detailed summary of what the slide depicts.
- Do not omit important labels, headings, or visual relationships.

Return a complete slide summary that is detailed enough to understand the slide without seeing it.
"""
        result = await slide_summary_agent.run(prompt)
        return result.output.summary
