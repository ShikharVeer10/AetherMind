"""
AI agent that generates a concise summary of what a slide *depicts*.

Now receives the full slide context (visual inventory, layout, relationships,
flowchart info) so the summary is aware of the slide's structure, not just
its text.
"""

import os
from pydantic import BaseModel
from pydantic_ai import Agent


class SlideSummaryResponse(BaseModel):
    summary: str


_slide_summary_agent = None


def _get_slide_summary_agent() -> Agent:
    global _slide_summary_agent
    if _slide_summary_agent is None:
        _slide_summary_agent = Agent(
            model="google:gemini-2.0-flash",
            output_type=SlideSummaryResponse,
            system_prompt=(
                "You are an expert enterprise document analysis assistant specialized in "
                "presentation slide interpretation. Your task is to generate a comprehensive, "
                "well-structured summary that explains what the slide DEPICTS, illustrates, "
                "and communicates — based on its visual layout, element counts, relationships, "
                "flowcharts, diagrams, tables, images, and text content.\n\n"
                "CRITICAL RULES:\n"
                "1. Do NOT copy exact sentences, statements, or bullet points from the slide text verbatim.\n"
                "2. Synthesize all information — visual structure, element relationships, flowchart paths, "
                "   image descriptions, and text — into an original explanation.\n"
                "3. Always include specific counts (e.g., '6 boxes', '3 arrows') from the visual inventory.\n"
                "4. If a flowchart or process diagram exists, map the step-by-step flow with arrow directions.\n"
                "5. If images exist, incorporate the image descriptions into the interpretation.\n"
                "6. Mention the header and footer text if provided.\n"
                "7. Describe the spatial layout (single_column, two_column, flowchart, diagram, etc.).\n\n"
                "OUTPUT FORMAT (use these exact headings):\n"
                "### Visual Element Counts\n"
                "State the exact count of each element type on this slide.\n\n"
                "### Flow Mapping\n"
                "If a flowchart/process exists: map each step as Step N → Step N+1 with descriptions.\n"
                "If no flow: write 'No flowchart or process flow detected.'\n\n"
                "### Key Content\n"
                "- Main message/purpose of the slide\n"
                "- Key data, statistics, or figures\n"
                "- Decisions, conclusions, or action items\n\n"
                "### Interpretation\n"
                "Holistic explanation of what this slide communicates, including its visual layout, "
                "diagrams/images, and the overall narrative or teaching intent."
            ),
        )
    return _slide_summary_agent


class SummarizationAgent:
    system_prompt = (
        "Generate a comprehensive, structured slide summary covering: visual element counts, "
        "flow/process mapping, key content extraction, and holistic interpretation. "
        "Use original phrasing — never copy slide text verbatim. "
        "Include header/footer text, image descriptions, and spatial layout details."
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

        # Gather header/footer info for context
        hf_info = ""
        if getattr(slide, "header_footer", None):
            hf = slide.header_footer
            hf_parts = []
            if hf.header_text:
                hf_parts.append(f"Header: \"{hf.header_text}\"")
            if hf.footer_text:
                hf_parts.append(f"Footer: \"{hf.footer_text}\"")
            if hf.slide_number_text:
                hf_parts.append(f"Slide Number: {hf.slide_number_text}")
            if hf.date_text:
                hf_parts.append(f"Date: {hf.date_text}")
            if hf_parts:
                hf_info = "\n".join(hf_parts)

        # Check if API key is available.
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        prompt = f"""\
Slide {slide.slide_number}
Title: {slide.title or '(none)'}

--- Header / Footer ---
{hf_info or '(no header/footer detected)'}

--- Extracted Text (verbatim, one bullet per line) ---
{slide_text}

--- Slide Context (visual inventory, layout, flowchart, relationships, diagram analysis) ---
{context_outline or '(no context available)'}

--- Image Descriptions ---
{image_summaries or '(no images)'}

Generate a comprehensive, well-structured summary of what this slide depicts using the following format.
CRITICAL: Do NOT repeat exact statements or copy-paste verbatim sentences from the extracted text. Use original phrasing.

### Visual Element Counts
State the exact number of boxes, arrows, shapes, images, tables, connectors, and other visual elements on this slide, using the counts from the Slide Context.

### Flow Mapping
If this slide contains a flowchart, process diagram, or any sequential flow:
- Map the flow step-by-step: Step 1: [label] → Step 2: [label] → ...
- Describe connections and their directions.
- State the total number of boxes and arrows in the flow.
If no flow is present, write "No flowchart or process flow detected."

### Key Content
- The main message or purpose of the slide
- Key data, statistics, or figures mentioned
- Any decisions, conclusions, or action items

### Interpretation
Explain what this slide is trying to communicate, explain, or illustrate as a whole, including its visual layout, diagrams/images, header/footer context, and the relationship mapping between elements.
"""

        if gemini_key:
            try:
                agent = _get_slide_summary_agent()
                result = await agent.run(prompt)
                return result.output.summary
            except Exception as e:
                print(f"[SummarizationAgent] Gemini summary generation failed: {e}")

        # Fallback to Groq if key is available
        if groq_key:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                )
                if response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[SummarizationAgent] Groq summary generation failed: {e}")

        # Fallback to OpenAI if key is available
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model="gpt-4o-mini",
                )
                if response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[SummarizationAgent] OpenAI summary generation failed: {e}")

        # Programmatic fallback if all else fails
        print("[SummarizationAgent] No LLM API succeeded. Generating programmatic fallback.")
        return self._build_fallback(slide, text_lines, image_summaries, hf_info)


    @staticmethod
    def _build_fallback(
        slide, text_lines: list[str], image_summaries: str, hf_info: str
    ) -> str:
        """Programmatic fallback when no AI API key is available."""
        title = slide.title or "(none)"
        elements_desc = []

        # Count elements from visual inventory or raw elements
        box_count = 0
        arrow_count = 0
        icon_count = 0
        image_count = 0
        table_count = 0
        if getattr(slide, "visual_inventory", None):
            inv = slide.visual_inventory
            box_count = getattr(inv, "text_box_count", 0) + getattr(inv, "shape_count", 0)
            arrow_count = getattr(inv, "arrow_count", 0) + getattr(inv, "connector_count", 0)
            icon_count = getattr(inv, "icon_count", 0)
            image_count = getattr(inv, "image_count", 0)
            table_count = getattr(inv, "table_count", 0)
        elif getattr(slide, "elements", None):
            for e in slide.elements:
                if e.element_type in {"shape", "text_box", "placeholder"}:
                    box_count += 1
                elif e.element_type in {"arrow", "connector"}:
                    arrow_count += 1
                elif e.element_type == "image":
                    image_count += 1
                elif e.element_type == "table":
                    table_count += 1

        if box_count:
            elements_desc.append(f"{box_count} box(es)")
        if arrow_count:
            elements_desc.append(f"{arrow_count} arrow(s)/connector(s)")
        if image_count:
            elements_desc.append(f"{image_count} image(s)")
        if table_count:
            elements_desc.append(f"{table_count} table(s)")

        layout_desc = "standard"
        if getattr(slide, "layout_structure", None):
            layout_desc = slide.layout_structure.layout_type

        # Build structured sections
        fallback = "### Visual Element Counts\n"
        if elements_desc:
            fallback += f"Visual elements detected: {', '.join(elements_desc)}.\n"
        else:
            fallback += "No specific visual elements detected.\n"

        fallback += "\n### Flow Mapping\n"
        if getattr(slide, "flowchart", None) and slide.flowchart.is_flowchart:
            fallback += f"Flowchart detected with {slide.flowchart.box_count} box(es) and {slide.flowchart.arrow_count} arrow(s).\n"
            if getattr(slide.flowchart, "reading_order", None):
                fallback += "Step-by-step sequence: " + " → ".join(slide.flowchart.reading_order) + "\n"
        else:
            fallback += "No flowchart or process flow detected.\n"

        fallback += "\n### Key Content\n"
        if text_lines:
            fallback += "Extracted key points:\n"
            for line in text_lines[:8]:
                fallback += f"- {line.strip()}\n"
        else:
            fallback += "No text content detected.\n"

        fallback += "\n### Interpretation\n"
        fallback += f"This slide titled '{title}' is structured as a {layout_desc} layout."
        if elements_desc:
            fallback += f" It visually presents {', '.join(elements_desc)} to communicate its core concept."
        if hf_info:
            fallback += f"\n\nHeader/Footer: {hf_info}"
        if image_summaries:
            fallback += f"\n\nImage Analysis:\n{image_summaries}"
        return fallback
