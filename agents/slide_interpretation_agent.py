import json
import os
from typing import Optional
from pydantic_ai import Agent
from models.document_model import SemanticFlowModel


_slide_interpretation_agent = None

def _get_slide_interpretation_agent() -> Agent:
    global _slide_interpretation_agent
    if _slide_interpretation_agent is None:
        _slide_interpretation_agent = Agent(
            model="google:gemini-2.0-flash",
            output_type=SemanticFlowModel,
            system_prompt=(
                "You are an expert presentation analyst, diagram reasoning specialist, and visual design educator.\n"
                "Your task is to analyze a slide's textual and visual representation and construct a detailed "
                "SemanticFlowModel capturing its core meaning, step-by-step logic, abstract concepts, visual design, "
                "summaries, and recreation blueprint.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. overall_flow: Provide a high-level explanation of the conceptual transformation or semantic flow. "
                "Explain the transition (e.g. low-level representation -> high-level reasoning).\n"
                "2. step_by_step_explanation: Detail the execution or logical flow step-by-step.\n"
                "3. conceptual_layers: Identify key abstract layers (e.g. State Abstraction, Temporal Abstraction) and "
                "explain them with clear examples from the slide.\n"
                "4. visual_design_details: Analyze the visual structure: color palette (e.g. teal/green platforms, yellow "
                "key), shape choices (e.g. rounded rectangles), alignment (e.g. left vs right), and connectives.\n"
                "5. plain_english_summary: Write a clear, 2-4 sentence summary of what the slide teaches.\n"
                "6. decision_points: List binary or logical decisions (e.g., 'Agent has key?').\n"
                "7. cause_effect_chain: List causal linkages and dependencies.\n"
                "8. image_generation_prompt: Provide an extremely detailed layout reconstruction blueprint. "
                "Specify layout, objects, relative coordinates, colors, and connectors so that another model can reconstruct "
                "the slide visual structure identically."
            ),
        )
    return _slide_interpretation_agent


class SlideInterpretationAgent:
    """
    AI Agent that analyzes a slide's structural context and image summaries,
    generating a SemanticFlowModel.
    """

    async def interpret_slide(
        self,
        slide,
        image_summaries: str = "",
    ) -> Optional[SemanticFlowModel]:
        """
        Run the semantic flow analysis on a slide using the best available LLM.
        """
        # Gather text points
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

        # Gather header/footer info
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

        # Build context outline
        context_outline = ""
        if getattr(slide, "context", None) and getattr(slide.context, "outline", None):
            context_outline = slide.context.outline
        elif getattr(slide, "layout_structure", None):
            layout_type = slide.layout_structure.layout_type
            context_outline = f"Layout Type: {layout_type}."

        # Construct Prompt
        prompt = f"""\
Slide {slide.slide_number}
Title: {slide.title or '(none)'}

--- Header / Footer ---
{hf_info or '(no header/footer detected)'}

--- Extracted Text ---
{slide_text}

--- Slide Structure & Layout Context ---
{context_outline or '(no layout context)'}

--- Image Summaries ---
{image_summaries or '(no image summaries)'}

Perform a deep semantic and visual layout analysis of this slide. Fill out the SemanticFlowModel completely.
"""

        # Check API keys
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if gemini_key:
            try:
                agent = _get_slide_interpretation_agent()
                result = await agent.run(prompt)
                return result.output
            except Exception as e:
                print(f"[SlideInterpretationAgent] Gemini analysis failed: {e}")

        # Fallback to Groq
        if groq_key:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                
                # Request JSON output
                json_prompt = (
                    f"{prompt}\n\n"
                    "CRITICAL: Return your response ONLY as a raw JSON object matching this schema. "
                    "Do NOT wrap in markdown code blocks like ```json. Do NOT include any extra text.\n"
                    "Schema:\n"
                    "{\n"
                    '  "overall_flow": "string",\n'
                    '  "step_by_step_explanation": ["string"],\n'
                    '  "conceptual_layers": ["string"],\n'
                    '  "visual_design_details": ["string"],\n'
                    '  "plain_english_summary": "string",\n'
                    '  "decision_points": ["string"],\n'
                    '  "cause_effect_chain": ["string"],\n'
                    '  "image_generation_prompt": "string"\n'
                    "}"
                )

                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": json_prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                
                res_text = response.choices[0].message.content
                if res_text:
                    parsed = json.loads(res_text.strip())
                    return SemanticFlowModel(**parsed)
            except Exception as e:
                print(f"[SlideInterpretationAgent] Groq analysis failed: {e}")

        # Fallback to OpenAI
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                
                json_prompt = (
                    f"{prompt}\n\n"
                    "CRITICAL: Return your response ONLY as a raw JSON object matching this schema. "
                    "Do NOT wrap in markdown code blocks. Do NOT include any extra text.\n"
                    "Schema:\n"
                    "{\n"
                    '  "overall_flow": "string",\n'
                    '  "step_by_step_explanation": ["string"],\n'
                    '  "conceptual_layers": ["string"],\n'
                    '  "visual_design_details": ["string"],\n'
                    '  "plain_english_summary": "string",\n'
                    '  "decision_points": ["string"],\n'
                    '  "cause_effect_chain": ["string"],\n'
                    '  "image_generation_prompt": "string"\n'
                    "}"
                )

                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": json_prompt}],
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"}
                )
                
                res_text = response.choices[0].message.content
                if res_text:
                    parsed = json.loads(res_text.strip())
                    return SemanticFlowModel(**parsed)
            except Exception as e:
                print(f"[SlideInterpretationAgent] OpenAI analysis failed: {e}")

        # If all LLM APIs fail, return None so calling service can use programmatic fallback
        print("[SlideInterpretationAgent] No LLM API succeeded. Falling back to programmatic analysis.")
        return None
