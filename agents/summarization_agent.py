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
                "presentation slide interpretation. Your task is to generate an extremely "
                "precise, detailed, and comprehensive slide summary. This summary must be of "
                "reconstruction-grade fidelity: when a downstream LLM is given this summary and the "
                "slide's structural JSON, it must be able to recreate the original slide as an identical "
                "image with maximum visual and content accuracy.\n\n"
                "CRITICAL RULES:\n"
                "1. First sentence of 'Plain English Summary': Begin with a single, clear sentence summarizing "
                "   the main message/purpose of the slide (suitable for slide purpose extraction).\n"
                "2. Synthesize all information — visual structure, element positions (using exact % coords), "
                "   typography hierarchy, colors, flowchart paths, images, and text content — into an "
                "   original, highly precise explanation. Do NOT repeat exact statements or copy verbatim text "
                "   outside the reconstruction blueprint.\n"
                "3. Always specify the design style, background styling, spacing, and grid/alignment patterns.\n"
                "4. If a flowchart or process diagram exists, map the step-by-step flow with element IDs, arrow "
                "   directions (e.g. Element_A -> Element_B), and connector styling (e.g., arrow type, label).\n"
                "5. Detail each element's exact position (left%, top%, width%, height%), typography (font name, "
                "   font size, color hex, bold/italic), and background fill colors.\n"
                "6. For images, provide highly detailed descriptions suitable for image generation prompts.\n\n"
                "OUTPUT FORMAT (use these exact headings):\n"
                "### Semantic Flow\n"
                "Provide a high-level explanation of the conceptual transformation or semantic flow. "
                "Detail the overall transition (e.g., low-level environment representation → high-level reasoning).\n\n"
                "### Step-by-step meaning\n"
                "Detail the execution or logical flow step-by-step. Map the narrative flow, decision branches, "
                "action sequences, or sequential logic represented by the visual elements.\n\n"
                "### Conceptual Layers\n"
                "Identify key abstract layers or concepts (e.g., State Abstraction, Temporal Abstraction) and "
                "explain them with clear examples from the slide elements.\n\n"
                "### Visual Design Details\n"
                "Provide the complete layout, design, styling, and visual blueprint details. You MUST organize this section using the following exact subheadings:\n"
                "Colour scheme:\n"
                "<detailed hex colors, backgrounds, platforms, paths, text and shapes colors>\n"
                "Shapes:\n"
                "<description of all shapes: rounded rectangles, diamonds, circles, etc.>\n"
                "Structure:\n"
                "<overall slide layout structure, layout patterns, spatial columns/groups, alignments, grids>\n"
                "Connectors:\n"
                "<connective paths, line thickness, arrow types, diagonal/straight connectors, labels>\n"
                "Typography:\n"
                "<fonts, sizes, weights, and colors for headers/body texts>\n"
                "Spacing & Alignment:\n"
                "<relative spacing, margins, alignment patterns, canvas ratio>\n"
                "Element-Level Details:\n"
                "<list of every element ID with its exact coordinates (left%, top%, width%, height%), type, precise content, background fill color, border, and typography>\n"
                "Image Descriptions:\n"
                "<detailed scene/object prompts for any images or icons suitable for image generation>\n\n"
                "### Plain English Summary\n"
                "A clear, concise 2-4 sentence summary of what the slide teaches. It should explain the core narrative in simple terms (e.g., how the agent simplifies a complex environment, how facts are abstracted, etc.)."
            ),
        )
    return _slide_summary_agent


class SummarizationAgent:
    system_prompt = (
        "Generate an extremely precise, detailed reconstruction-grade slide summary covering "
        "semantic flow, step-by-step meaning, conceptual layers, visual design details (including coordinates, typography, and color palette), "
        "and a plain English summary."
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

        # Collect rich Step 12 visual details
        visual_details = []
        if getattr(slide, "image_reconstruction", None) and slide.image_reconstruction:
            ir = slide.image_reconstruction
            if ir.layout_description:
                visual_details.append(f"Layout Description: {ir.layout_description}")
            if ir.color_palette:
                visual_details.append(f"Color Palette: {', '.join(ir.color_palette)}")
            if ir.object_location:
                visual_details.append("Object Locations:\n" + "\n".join(f"  - {loc}" for loc in ir.object_location))
            if ir.connector_layout:
                visual_details.append("Connector Layout:\n" + "\n".join(f"  - {conn}" for conn in ir.connector_layout))
            if ir.object_inventory:
                visual_details.append("Object Inventory:\n" + "\n".join(f"  - {obj}" for obj in ir.object_inventory))
            if ir.visual_hierarchy:
                visual_details.append("Visual Hierarchy:\n" + "\n".join(f"  - {h}" for h in ir.visual_hierarchy))
            if ir.layout_regions:
                visual_details.append(f"Layout Regions: {', '.join(ir.layout_regions)}")
            if ir.design_style:
                visual_details.append(f"Design Style: {ir.design_style}")
            if ir.recreation_prompt:
                visual_details.append(f"Initial Recreation Prompt:\n{ir.recreation_prompt}")

        if getattr(slide, "image_understanding", None) and slide.image_understanding:
            iu = slide.image_understanding
            if iu.scene_description:
                visual_details.append(f"Scene Description: {iu.scene_description}")
            if iu.semantic_meaning:
                visual_details.append(f"Semantic Meaning: {iu.semantic_meaning}")
            if iu.llm_recreation_prompt:
                visual_details.append(f"Image Reconstruction Prompt: {iu.llm_recreation_prompt}")

        if getattr(slide, "semantic_flow", None) and slide.semantic_flow:
            sf = slide.semantic_flow
            if sf.overall_flow:
                visual_details.append(f"Overall Flow: {sf.overall_flow}")
            if sf.step_by_step_explanation:
                visual_details.append("Step-by-Step Flow Explanation:\n" + "\n".join(f"  - {step}" for step in sf.step_by_step_explanation))
            if sf.visual_design_details:
                visual_details.append("Semantic Visual Design Details:\n" + "\n".join(f"  - {detail}" for detail in sf.visual_design_details))

        visual_details_text = "\n\n".join(visual_details) if visual_details else "(no rich visual details available)"

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

--- Rich Visual & Reconstruction Analysis ---
{visual_details_text}

Generate an extremely precise, reconstruction-grade slide summary using the following format:

### Semantic Flow
Provide a high-level explanation of the conceptual transformation or semantic flow. Detail the overall transition (e.g., low-level environment representation → high-level reasoning).

### Step-by-step meaning
Detail the execution or logical flow step-by-step. Map the narrative flow, decision branches, action sequences, or sequential logic represented by the visual elements.

### Conceptual Layers
Identify key abstract layers or concepts (e.g., State Abstraction, Temporal Abstraction) and explain them with clear examples from the slide elements.

### Visual Design Details
Colour scheme:
- <detailed hex colors, backgrounds, platforms, paths, text and shapes colors>
Shapes:
- <description of all shapes: rounded rectangles, diamonds, circles, etc.>
Structure:
- <overall slide layout structure, layout patterns, spatial columns/groups, alignments, grids>
Connectors:
- <connective paths, line thickness, arrow types, diagonal/straight connectors, labels>
Typography:
- <fonts, sizes, weights, and colors for headers/body texts>
Spacing & Alignment:
- <relative spacing, margins, alignment patterns, canvas ratio>
Element-Level Details:
- <list of every element ID with its exact coordinates (left%, top%, width%, height%), type, precise content, background fill color, border, and typography>
Image Descriptions:
- <detailed scene/object prompts for any images or icons suitable for image generation>

### Plain English Summary
A clear, concise 2-4 sentence summary of what the slide teaches. It should explain the core narrative in simple terms (e.g., how the agent simplifies a complex environment, how facts are abstracted, etc.).
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

        # Extract colors and fonts from slide
        colors = set()
        title_font = "default title typography"
        body_font = "default body typography"
        element_details = []

        # Estimate canvas boundaries dynamically (EMU default or based on elements)
        width = 12192000.0
        height = 6858000.0
        if getattr(slide, "elements", None):
            for e in slide.elements:
                if e.position:
                    width = max(width, e.position.x + e.position.width)
                    height = max(height, e.position.y + e.position.height)

            for e in sorted(slide.elements, key=lambda x: (x.position.y, x.position.x) if x.position else (0, 0)):
                if e.style:
                    if e.style.background_color:
                        colors.add(e.style.background_color)
                    if e.style.text_color:
                        colors.add(e.style.text_color)
                
                # Check for fonts
                if e.text and e.style:
                    if e.style.bold or (e.style.font_size and e.style.font_size >= 18):
                        parts = []
                        if e.style.font_name:
                            parts.append(f"font: {e.style.font_name}")
                        if e.style.font_size:
                            parts.append(f"size: {e.style.font_size}pt")
                        if e.style.bold:
                            parts.append("bold")
                        if e.style.text_color:
                            parts.append(f"color: {e.style.text_color}")
                        if parts:
                            title_font = ", ".join(parts)
                    else:
                        parts = []
                        if e.style.font_name:
                            parts.append(f"font: {e.style.font_name}")
                        if e.style.font_size:
                            parts.append(f"size: {e.style.font_size}pt")
                        if e.style.text_color:
                            parts.append(f"color: {e.style.text_color}")
                        if parts:
                            body_font = ", ".join(parts)

                # Format element coordinates
                if e.position:
                    left_pct = (e.position.x / width) * 100 if width else 0
                    top_pct = (e.position.y / height) * 100 if height else 0
                    w_pct = (e.position.width / width) * 100 if width else 0
                    h_pct = (e.position.height / height) * 100 if height else 0
                    pos_str = f"left: {left_pct:.1f}%, top: {top_pct:.1f}%, width: {w_pct:.1f}%, height: {h_pct:.1f}%"
                else:
                    pos_str = "default coordinates"

                elem_text = e.text.strip().replace('\n', ' ') if e.text else "(no text)"
                elem_bg = e.style.background_color if e.style and e.style.background_color else "transparent"
                elem_fg = e.style.text_color if e.style and e.style.text_color else "default"
                
                details_line = f"- Element '{e.element_id}' ({e.element_type}): Positioned at {pos_str}. Text: '{elem_text}'. Background Fill: {elem_bg}. Text Color: {elem_fg}."
                element_details.append(details_line)

        colors_list = sorted(list(colors))

        # Build structured sections
        fallback = "### Semantic Flow\n"
        fallback += f"The slide titled '{title}' represents a semantic flow in a {layout_desc} layout.\n"
        if getattr(slide, "semantic_flow", None) and slide.semantic_flow and slide.semantic_flow.overall_flow:
            fallback += f"{slide.semantic_flow.overall_flow}\n"

        fallback += "\n### Step-by-step meaning\n"
        has_step_detail = False
        if getattr(slide, "flowchart", None) and slide.flowchart.is_flowchart:
            fallback += f"Flowchart sequence details: {slide.flowchart.box_count} box(es) and {slide.flowchart.arrow_count} arrow(s).\n"
            if getattr(slide.flowchart, "reading_order", None):
                fallback += "Execution sequence: " + " → ".join(slide.flowchart.reading_order) + "\n"
            has_step_detail = True
        
        if getattr(slide, "relationships", None) and slide.relationships:
            fallback += "Step-by-step element linkages:\n"
            for rel in slide.relationships:
                label_str = f" (labeled '{rel.label}')" if rel.label else ""
                fallback += f"- Connector: {rel.source_element_id} → {rel.target_element_id} [{rel.relationship_type}]{label_str}\n"
            has_step_detail = True

        if not has_step_detail:
            fallback += "No specific process flow or logic mapping detected.\n"

        fallback += "\n### Conceptual Layers\n"
        fallback += f"- Primary Concept: Architecture overview of '{title}'\n"
        if text_lines:
            for line in text_lines[:5]:
                fallback += f"- Concept Detail: {line.strip()}\n"

        fallback += "\n### Visual Design Details\n"
        
        # Color scheme
        fallback += "Colour scheme:\n"
        if colors_list:
            fallback += f"- Colors used: {', '.join(colors_list)}\n"
        else:
            fallback += "- Colors: default (inherited)\n"
        if getattr(slide, "image_reconstruction", None) and slide.image_reconstruction.color_palette:
            fallback += f"- Color Palette from visual analysis: {', '.join(slide.image_reconstruction.color_palette)}\n"
            
        # Shapes
        fallback += "Shapes:\n"
        shapes_used = []
        if box_count:
            shapes_used.append("rounded rectangles for concepts" if "flowchart" in layout_desc.lower() else "rectangular text boxes")
        if arrow_count:
            shapes_used.append("straight/directional connector arrows")
        if shapes_used:
            for s in shapes_used:
                fallback += f"- {s}\n"
        else:
            fallback += "- No distinct shapes detected\n"
            
        # Structure
        fallback += "Structure:\n"
        fallback += f"- Layout type: {layout_desc}\n"
        fallback += "- Standard slide configuration\n"
        if getattr(slide, "image_reconstruction", None) and slide.image_reconstruction.layout_description:
            fallback += f"- Visual layout analysis: {slide.image_reconstruction.layout_description}\n"
            
        # Connectors
        fallback += "Connectors:\n"
        if getattr(slide, "relationships", None) and slide.relationships:
            for rel in slide.relationships:
                label_str = f" (label: '{rel.label}')" if rel.label else ""
                fallback += f"- Arrow: {rel.source_element_id} → {rel.target_element_id} [{rel.relationship_type}]{label_str}\n"
        else:
            fallback += "- No connectors detected\n"
            
        # Typography
        fallback += "Typography:\n"
        fallback += f"- Title Font/Style: {title_font}\n"
        fallback += f"- Body Font/Style: {body_font}\n"
        
        # Spacing & Alignment
        fallback += "Spacing & Alignment:\n"
        fallback += "- Spacing: moderate\n"
        fallback += "- Alignments: standard grid, canvas aspect ratio 16:9\n"
        
        # Element-Level Details
        fallback += "Element-Level Details:\n"
        if element_details:
            for ed in element_details:
                fallback += f"  {ed}\n"
        else:
            fallback += "  - (no elements detected)\n"
            
        # Image Descriptions
        fallback += "Image Descriptions:\n"
        if image_summaries:
            fallback += f"  - {image_summaries.replace('\n', ' | ')}\n"
        else:
            fallback += "  - No images present\n"

        fallback += "\n### Plain English Summary\n"
        fallback += f"This slide titled '{title}' explains key concepts on this topic.\n"
        if text_lines:
            fallback += "Instead of focusing on environment coordinates directly, it highlights key facts:\n"
            for line in text_lines[:3]:
                fallback += f"- {line.strip()}\n"
        if hf_info:
            fallback += f"\nHeader/Footer Details: {hf_info.replace('\n', ' | ')}"

        return fallback
