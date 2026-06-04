from models.document_model import SemanticSlideDescriptionModel, SlideModel

class SemanticSlideService:
    def analyze_slide(self,slide: SlideModel) -> SemanticSlideDescriptionModel:
        title = slide.title or ""
        semantic_flow = (slide.semantic_flow.overall_flow if slide.semantic_flow else "")
        summary = (
            slide.semantic_flow.plain_english_summary
            if slide.semantic_flow and slide.semantic_flow.plain_english_summary
            else (slide.slide_summary if slide.slide_summary else "")
        )
        image_prompt = (
            slide.semantic_flow.image_generation_prompt
            if slide.semantic_flow and slide.semantic_flow.image_generation_prompt
            else self._build_image_prompt(slide)
        )
        return SemanticSlideDescriptionModel(
            semantic_flow=semantic_flow,
            step_by_step_meaning=[
                step
                for step in (
                    slide.semantic_flow.step_by_step_explanation
                    if slide.semantic_flow
                    else []
                )
            ],
            conceptual_layers=[layer for layer in (slide.semantic_flow.conceptual_layers if slide.semantic_flow else [])],
            visual_design_details=[
                detail
                for detail in (
                    slide.semantic_flow.visual_design_details
                    if slide.semantic_flow
                    else []
                )
            ],
            plain_english_summary=summary,
            image_generation_prompt=image_prompt
        )
    def _build_image_prompt(self, slide: SlideModel) -> str:
        prompt_parts = []
        if slide.title:
            prompt_parts.append(f"Slide title: {slide.title}")
        if slide.image_understanding:
            if slide.image_understanding.scene_description:
                prompt_parts.append(slide.image_understanding.scene_description)
            if slide.image_understanding.semantic_meaning:
                prompt_parts.append(slide.image_understanding.semantic_meaning)
        if slide.layout_structure:
            prompt_parts.append(f"Layout: {slide.layout_structure.layout_type}")
        return "\n".join(prompt_parts)