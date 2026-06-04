"""
Slide Reconstruction Agent.

LLM-backed agent that enriches the programmatically-assembled
SlideReconstructionContextModel with richer inferences for purpose,
domain, mood, category, and polished image reconstruction descriptions.

Falls back gracefully to the programmatic version when no LLM is available.
"""

import json
import os
from typing import Optional

from pydantic_ai import Agent

from models.document_model import SlideReconstructionContextModel


# ────────────────────────────────────────────
# Pydantic-AI agent (Gemini, lazy-initialized)
# ────────────────────────────────────────────

_reconstruction_agent: Optional[Agent] = None


def _get_reconstruction_agent() -> Agent:
    global _reconstruction_agent
    if _reconstruction_agent is None:
        _reconstruction_agent = Agent(
            model="google:gemini-2.0-flash",
            output_type=SlideReconstructionContextModel,
            system_prompt=(
                "You are an expert Presentation Reconstruction Model.\n"
                "You receive a JSON representation of a slide's reconstruction context — "
                "containing extracted metadata, visual style, background info, typography, "
                "layout, visual hierarchy, element inventory, image reconstruction cues, "
                "and relationships.\n\n"
                "Your task is to REFINE and ENRICH each field so that another model can "
                "recreate the original slide with maximum visual fidelity.\n\n"
                "CRITICAL RULES:\n"
                "1. Do NOT discard any existing data. Only improve, expand, or clarify fields.\n"
                "2. For 'purpose' and 'domain': infer from the slide's title, text content, "
                "   and visual structure. Be specific (e.g. 'machine learning pipeline overview' "
                "   not just 'technology').\n"
                "3. For 'mood': describe the visual feeling (e.g. 'clean, corporate, minimalist' "
                "   or 'vibrant, educational, diagram-heavy').\n"
                "4. For 'image_reconstructions': write detailed visual descriptions suitable for "
                "   an image generation model.\n"
                "5. For 'reconstruction_prompt': produce the FULL canonical reconstruction "
                "   template with all sections (SLIDE_METADATA through RECONSTRUCTION_INSTRUCTIONS).\n"
                "6. Keep all list fields as lists. Keep all string fields as strings.\n"
                "7. Return ONLY a valid JSON object matching the SlideReconstructionContextModel schema."
            ),
        )
    return _reconstruction_agent


class SlideReconstructionAgent:
    """
    AI agent that enriches a SlideReconstructionContextModel with LLM inference.
    Supports Gemini → Groq → OpenAI fallback chain.
    """

    async def enrich_context(
        self,
        context: SlideReconstructionContextModel,
    ) -> Optional[SlideReconstructionContextModel]:
        """
        Send the programmatic reconstruction context to an LLM for enrichment.
        Returns the enriched model, or None if all APIs fail.
        """
        # Serialize the context to JSON for the prompt
        context_json = context.model_dump_json(indent=2)

        prompt = (
            "Below is a JSON representation of a slide's reconstruction context.\n"
            "Refine and enrich every field to maximize reconstruction fidelity.\n"
            "Return your response as a COMPLETE JSON object matching the schema.\n\n"
            f"```json\n{context_json}\n```"
        )

        # --- Try Gemini (primary) ---
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            try:
                agent = _get_reconstruction_agent()
                result = await agent.run(prompt)
                return result.output
            except Exception as e:
                print(f"[SlideReconstructionAgent] Gemini enrichment failed: {e}")

        # --- Fallback: Groq ---
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                return self._call_groq(groq_key, prompt)
            except Exception as e:
                print(f"[SlideReconstructionAgent] Groq enrichment failed: {e}")

        # --- Fallback: OpenAI ---
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                return self._call_openai(openai_key, prompt)
            except Exception as e:
                print(f"[SlideReconstructionAgent] OpenAI enrichment failed: {e}")

        print("[SlideReconstructionAgent] No LLM API succeeded. Using programmatic context.")
        return None

    # ──────────────────────────────────────
    # Groq fallback
    # ──────────────────────────────────────

    @staticmethod
    def _call_groq(api_key: str, prompt: str) -> Optional[SlideReconstructionContextModel]:
        from groq import Groq

        client = Groq(api_key=api_key)
        json_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Return your response ONLY as a raw JSON object matching the "
            "SlideReconstructionContextModel schema. Do NOT wrap in markdown code blocks."
        )
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": json_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        res_text = response.choices[0].message.content
        if res_text:
            parsed = json.loads(res_text.strip())
            return SlideReconstructionContextModel(**parsed)
        return None

    # ──────────────────────────────────────
    # OpenAI fallback
    # ──────────────────────────────────────

    @staticmethod
    def _call_openai(api_key: str, prompt: str) -> Optional[SlideReconstructionContextModel]:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        json_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Return your response ONLY as a raw JSON object matching the "
            "SlideReconstructionContextModel schema. Do NOT wrap in markdown code blocks."
        )
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": json_prompt}],
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
        )
        res_text = response.choices[0].message.content
        if res_text:
            parsed = json.loads(res_text.strip())
            return SlideReconstructionContextModel(**parsed)
        return None
