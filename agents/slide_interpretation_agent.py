import json
import os
from typing import Optional

import requests
from pydantic_ai import Agent

from models.document_model import SemanticFlowModel

_slide_interpretation_agent = None

_RECONSTRUCTION_SYSTEM_PROMPT = (
    "You are an expert presentation analyst, diagram reasoning specialist, and visual reconstruction architect.\n"
    "Your task is NOT to summarize — it is to produce a reconstruction blueprint so another AI can recreate "
    "this slide with matching meaning, flow, diagram structure, layout, and visual intent.\n\n"
    "OUTPUT STYLE EXAMPLE (match this depth and structure):\n"
    "overall_flow: 'The slide shows a transformation from low-level environment representation → high-level reasoning'\n"
    "step_by_step_explanation: [\n"
    "  'The agent exists in a complex environment (game screen with ladders, obstacles, key, and exit).',\n"
    "  'Instead of modelling every pixel or movement, the system abstracts the environment into a state variable: Whether the agent has the key or not.',\n"
    "  'This creates a binary decision node: Agent has key?',\n"
    "  'If No → take a higher-level action: Get key',\n"
    "  'If Yes → take another higher-level action: Open the door'\n"
    "]\n"
    "conceptual_layers: [\n"
    "  'State Abstraction: Reduces complex environment into meaningful variables. Example: Instead of tracking position, ladders, obstacles → track only: Does the agent have the key?',\n"
    "  'Temporal Abstraction: Converts primitive actions into macro-actions. Example: Get key = sequence of movements; Open the door = sequence of actions near the door'\n"
    "]\n"
    "visual_design_details: [\n"
    "  'Colour scheme: Dark/black background, teal/green platforms and ladders, yellow/gold key, light green action boxes, light blue decision node',\n"
    "  'Shapes: Rounded rectangles for abstract concepts, straight connectors for decision logic',\n"
    "  'Structure: Left → Concrete world; Right → Abstract decision-making pipeline',\n"
    "  'Connectors: Diagonal connector links game to abstraction layer; arrows indicate logical flow'\n"
    "]\n"
    "plain_english_summary: Multi-paragraph (3-5 paragraphs) educational explanation preserving all key terms and flow logic.\n\n"
    "CRITICAL EXTRACTION RULES — NEVER VIOLATE:\n"
    "- Do NOT summarize away diagram structure.\n"
    "- Do NOT reduce diagrams to node counts or edge counts.\n"
    "- Do NOT replace visible text with generic descriptions.\n"
    "- Do NOT collapse flow logic into vague summaries.\n"
    "- ALWAYS preserve exact visible text, decision branches, yes/no labels, connector labels, "
    "flow direction, hierarchy, object relationships, and relative positioning.\n\n"
    "FIELD INSTRUCTIONS:\n"
    "1. overall_flow: One sentence describing the conceptual transformation or semantic progression (use exact slide labels).\n"
    "2. step_by_step_explanation: Narrative steps explaining meaning — NOT element IDs. Include decision branches with exact text.\n"
    "3. conceptual_layers: Named layers with definitions and concrete examples from the slide.\n"
    "4. visual_design_details: Colour scheme, shapes, spatial structure, connectors — specific and visual.\n"
    "5. plain_english_summary: 3-5 paragraphs explaining what the slide teaches in plain language.\n"
    "6. decision_points: Every decision node with EXACT question text.\n"
    "7. cause_effect_chain: Causal links using exact element text and branch labels.\n"
    "8. image_generation_prompt: PRIMARY reconstruction field — a complete visual blueprint with sections:\n"
    "   === LAYOUT === (left/right/top/bottom/center with contents and proportions)\n"
    "   === OBJECTS === (every visible object with exact text, type, placement)\n"
    "   === DIAGRAM STRUCTURE === (decisions, branches, flow, exact text, mermaid if applicable)\n"
    "   === VISUAL HIERARCHY === (importance, grouping, emphasis)\n"
    "   === SPATIAL RELATIONSHIPS === (placement, connectors, arrow directions)\n"
    "   === VISUAL DESIGN === (colors, shapes, styling)\n"
    "   === RENDERING INSTRUCTIONS === (how to recreate near-identically)\n"
    "If the original slide disappeared, image_generation_prompt alone must be enough for another model "
    "to generate a visually and semantically near-identical slide."
)

_JSON_SCHEMA_HINT = (
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


def _get_slide_interpretation_agent() -> Agent:
    global _slide_interpretation_agent
    if _slide_interpretation_agent is None:
        _slide_interpretation_agent = Agent(
            model="google:gemini-2.0-flash",
            output_type=SemanticFlowModel,
            system_prompt=_RECONSTRUCTION_SYSTEM_PROMPT,
        )
    return _slide_interpretation_agent


def _element_label_lookup(slide) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for element in slide.elements:
        label = (element.text or "").strip().replace("\n", " ")
        if not label and element.paragraphs:
            label = " ".join(
                p.text.strip() for p in element.paragraphs if p.text
            ).strip()
        lookup[element.element_id] = label or f"[{element.element_id}]"
    return lookup


def _build_reconstruction_context(slide) -> str:
    """Assemble structural extraction data for the interpretation prompt."""
    sections: list[str] = []
    labels = _element_label_lookup(slide)

    if getattr(slide, "diagram_understanding", None):
        du = slide.diagram_understanding
        if du.flow_description:
            sections.append(f"--- Diagram Flow Description ---\n{du.flow_description}")
        if du.summary:
            sections.append(f"--- Diagram Understanding ---\n{du.summary}")
        if du.nodes:
            node_lines = []
            for node in du.nodes:
                text = node.get("text") or labels.get(node.get("element_id", ""), "")
                node_lines.append(
                    f"  - [{node.get('type', 'unknown')}] "
                    f"{labels.get(node.get('element_id', ''), node.get('element_id', ''))}"
                    f"{f': {text}' if text and text != labels.get(node.get('element_id', ''), '') else ''}"
                )
            sections.append("--- Diagram Nodes ---\n" + "\n".join(node_lines))
        if du.edges:
            edge_lines = []
            for edge in du.edges:
                src = labels.get(edge.get("source", ""), edge.get("source", ""))
                tgt = labels.get(edge.get("target", ""), edge.get("target", ""))
                line = f'  - "{src}" → "{tgt}" ({edge.get("type", "unknown")})'
                if edge.get("label"):
                    line += f' [label: {edge["label"]}]'
                edge_lines.append(line)
            sections.append("--- Diagram Edges ---\n" + "\n".join(edge_lines))

    if getattr(slide, "flowchart", None) and slide.flowchart.is_flowchart:
        fc = slide.flowchart
        fc_lines = [
            f"Flowchart: {fc.box_count} box(es), {fc.arrow_count} arrow(s)"
        ]
        for box in fc.boxes:
            text = (box.get("text") or labels.get(box.get("element_id", ""), "")).strip()
            fc_lines.append(f"  Box: {text or box.get('element_id', '')}")
        for rel in fc.relationships:
            src = labels.get(rel.source_element_id, rel.source_element_id)
            tgt = labels.get(rel.target_element_id, rel.target_element_id)
            line = f'  Flow: "{src}" → "{tgt}"'
            if rel.label:
                line += f' [{rel.label}]'
            fc_lines.append(line)
        if fc.reading_order:
            order_labels = [
                labels.get(eid, eid) for eid in fc.reading_order
            ]
            fc_lines.append("  Reading order: " + " → ".join(order_labels))
        sections.append("--- Flowchart Structure ---\n" + "\n".join(fc_lines))

    if getattr(slide, "layout_structure", None):
        layout = slide.layout_structure
        layout_lines = [f"Layout type: {layout.layout_type}"]
        for region in layout.regions or []:
            layout_lines.append(f"  Region '{region.name}': {len(region.element_ids)} element(s)")
        sections.append("--- Layout Regions ---\n" + "\n".join(layout_lines))

    if getattr(slide, "relationships", None):
        connector_rels = [
            r for r in slide.relationships
            if r.relationship_type == "connector"
        ]
        if connector_rels:
            rel_lines = []
            for rel in connector_rels:
                src = labels.get(rel.source_element_id, rel.source_element_id)
                tgt = labels.get(rel.target_element_id, rel.target_element_id)
                line = f'  "{src}" → "{tgt}"'
                if rel.label:
                    line += f' [connector label: {rel.label}]'
                rel_lines.append(line)
            sections.append("--- Connector Relationships ---\n" + "\n".join(rel_lines))

    # Element-level visual details
    elem_lines = []
    for element in slide.elements:
        if element.element_type in {"arrow", "connector"}:
            continue
        label = labels.get(element.element_id, element.element_id)
        parts = [f"  - [{element.element_type}] \"{label}\""]
        if hasattr(element, "style") and element.style:
            if element.style.background_color:
                parts.append(f"    fill: {element.style.background_color}")
            if element.style.text_color:
                parts.append(f"    text colour: {element.style.text_color}")
            if element.style.font_name:
                size = f" {element.style.font_size}pt" if element.style.font_size else ""
                parts.append(f"    font: {element.style.font_name}{size}")
            if element.style.bold:
                parts.append("    bold: yes")
        if hasattr(element, "shape_type") and element.shape_type:
            parts.append(f"    shape: {element.shape_type}")
        if hasattr(element, "position") and element.position:
            left_pct = round(100 * element.position.x / 12192000, 1)
            top_pct = round(100 * element.position.y / 6858000, 1)
            w_pct = round(100 * element.position.width / 12192000, 1)
            h_pct = round(100 * element.position.height / 6858000, 1)
            parts.append(f"    position: left {left_pct}%, top {top_pct}%, width {w_pct}%, height {h_pct}%")
        elem_lines.append("\n".join(parts))
    if elem_lines:
        sections.append(
            "--- Element Visual Details (position, style, shape) ---\n"
            + "\n".join(elem_lines)
        )

    return "\n\n".join(sections)


class SlideInterpretationAgent:
    """
    AI Agent that analyzes a slide's structural context and image summaries,
    generating a SemanticFlowModel reconstruction blueprint.
    """

    async def interpret_slide(
        self,
        slide,
        image_summaries: str = "",
    ) -> Optional[SemanticFlowModel]:
        """
        Run the semantic flow analysis on a slide using the best available LLM.
        Falls back to rule-based SemanticFlowService when no LLM succeeds.
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

        hf_info = ""
        if getattr(slide, "header_footer", None):
            hf = slide.header_footer
            hf_parts = []
            if hf.header_text:
                hf_parts.append(f'Header: "{hf.header_text}"')
            if hf.footer_text:
                hf_parts.append(f'Footer: "{hf.footer_text}"')
            if hf.slide_number_text:
                hf_parts.append(f"Slide Number: {hf.slide_number_text}")
            if hf.date_text:
                hf_parts.append(f"Date: {hf.date_text}")
            if hf_parts:
                hf_info = "\n".join(hf_parts)

        context_outline = ""
        if getattr(slide, "context", None) and getattr(slide.context, "outline", None):
            context_outline = slide.context.outline
        elif getattr(slide, "layout_structure", None):
            layout_type = slide.layout_structure.layout_type
            context_outline = f"Layout Type: {layout_type}."

        reconstruction_context = _build_reconstruction_context(slide)

        prompt = f"""\
Slide {slide.slide_number}
Title: {slide.title or '(none)'}
{hf_info or '(no header/footer detected)'}
{slide_text}
{context_outline or '(no layout context)'}
{reconstruction_context or '(no structural extraction data)'}
{image_summaries or '(no image summaries)'}

Produce a reconstruction-oriented SemanticFlowModel. Do not summarize away structure.
The image_generation_prompt must be detailed enough for another model to recreate this slide.
"""

        enable_summaries = os.getenv("ENABLE_SUMMARIES", "true").lower() in {"1", "true"}
        if not enable_summaries:
            print("[SlideInterpretationAgent] ENABLE_SUMMARIES is false. Bypassing LLM and using rule-based SemanticFlowService.")
            from services.semantic_flow_service import SemanticFlowService
            return SemanticFlowService().analyze_slide(slide, image_summaries=image_summaries)

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

        if groq_key:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)

                json_prompt = (
                    f"{prompt}\n\n"
                    "CRITICAL: Return your response ONLY as a raw JSON object matching this schema. "
                    "Do NOT wrap in markdown code blocks. Do NOT include any extra text.\n"
                    f"Schema:\n{_JSON_SCHEMA_HINT}"
                )

                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": _RECONSTRUCTION_SYSTEM_PROMPT},
                        {"role": "user", "content": json_prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"},
                )

                res_text = response.choices[0].message.content
                if res_text:
                    parsed = json.loads(res_text.strip())
                    return SemanticFlowModel(**parsed)
            except Exception as e:
                print(f"[SlideInterpretationAgent] Groq analysis failed: {e}")

        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)

                json_prompt = (
                    f"{prompt}\n\n"
                    "CRITICAL: Return your response ONLY as a raw JSON object matching this schema. "
                    "Do NOT wrap in markdown code blocks. Do NOT include any extra text.\n"
                    f"Schema:\n{_JSON_SCHEMA_HINT}"
                )

                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": _RECONSTRUCTION_SYSTEM_PROMPT},
                        {"role": "user", "content": json_prompt}
                    ],
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                )

                res_text = response.choices[0].message.content
                if res_text:
                    parsed = json.loads(res_text.strip())
                    return SemanticFlowModel(**parsed)
            except Exception as e:
                print(f"[SlideInterpretationAgent] OpenAI analysis failed: {e}")

        # Fallback to Ollama
        skip_ollama = os.getenv("SKIP_OLLAMA", "false").lower() in {"1", "true"}
        if not skip_ollama:
            ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            try:
                resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    target_model = "llama3.2"
                    if "llama3.2:latest" in models or "llama3.2" in models:
                        target_model = "llama3.2"
                    elif models:
                        target_model = models[0]

                    json_prompt = (
                        f"{prompt}\n\n"
                        "CRITICAL: Return your response ONLY as a raw JSON object matching this schema. "
                        "Do NOT wrap in markdown code blocks. Do NOT include any extra text.\n"
                        f"Schema:\n{_JSON_SCHEMA_HINT}"
                    )

                payload = {
                    "model": target_model,
                    "prompt": json_prompt,
                    "system": _RECONSTRUCTION_SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                }
                print(f"[SlideInterpretationAgent] Using local Ollama model: {target_model}...")
                response = requests.post(
                    f"{ollama_host}/api/generate",
                    json=payload,
                    timeout=15,
                )
                if response.status_code == 200:
                    res_text = response.json().get("response", "").strip()
                    if res_text:
                        parsed = json.loads(res_text)
                        return SemanticFlowModel(**parsed)
            except Exception as e:
                print(f"[SlideInterpretationAgent] Ollama analysis failed: {e}")

        print("[SlideInterpretationAgent] No LLM API succeeded. Using rule-based SemanticFlowService.")
        from services.semantic_flow_service import SemanticFlowService

        return SemanticFlowService().analyze_slide(slide, image_summaries=image_summaries)
