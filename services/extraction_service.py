# Extraction service for a powerpoint presentation
import json
from typing import Optional
from pathlib import Path
from extractors.ppt_extractor import PPTExtractor


class ExtractionService:
    def __init__(
        self,
        document_path: str,
        enable_summaries: bool = False,
        enable_image_summaries: bool = False,
    ):
        self.document_path = document_path
        self.document_extension = Path(document_path).suffix.lower()
        self.enable_summaries = enable_summaries
        self.enable_image_summaries = enable_image_summaries
        self.summarization_agent = None
        self.image_summarization_agent = None
        self._summary_error_types = ()
        if self.enable_summaries:
            try:
                from pydantic_ai import exceptions as pydantic_ai_exceptions
            except ImportError:
                self.summarization_agent = None
            else:
                self._summary_error_types = (
                    pydantic_ai_exceptions.UserError,
                    pydantic_ai_exceptions.ModelHTTPError,
                )
                try:
                    from agents.summarization_agent import SummarizationAgent

                    self.summarization_agent = SummarizationAgent()
                except pydantic_ai_exceptions.UserError:
                    self.summarization_agent = None
        if self.enable_image_summaries:
            from agents.image_summarization_agent import ImageSummaryAgent

            self.image_summarization_agent = ImageSummaryAgent()

    async def extract_document(self):
        if self.document_extension == ".pptx":
            extractor = PPTExtractor(self.document_path)
            document_model = extractor.extract_document()
            if self.enable_summaries:
                for slide in document_model.slides:
                    slide.slide_summary = await self._summarize_slide(slide)
                document_model.document_summary = self._build_document_summary(
                    document_model
                )
            if self.enable_image_summaries and self.image_summarization_agent:
                await self._summarize_images(document_model)
            return document_model
        else:
            raise ValueError(f"Unsupported document type: {self.document_extension}")

    # Provide a method to load the json file
    def export_to_json(
        self, extracted_document, output_directory: str = "output/extracted_json"
    ):
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        document_name = Path(self.document_path).stem
        json_output_file = output_path / f"{document_name}.json"
        output_payload = self._format_output(extracted_document)
        with open(json_output_file, "w", encoding="utf-8") as json_file:
            json.dump(output_payload, json_file, indent=4, ensure_ascii=False)
        return json_output_file

    def _format_output(self, extracted_document):
        slides_payload = []
        for slide in extracted_document.slides:
            elements_payload = []
            for element in slide.elements:
                style = None
                if element.style:
                    style = {
                        "font_size": element.style.font_size,
                        "bold": element.style.bold,
                        "italic": element.style.italic,
                        "color": element.style.text_color,
                        "background_color": element.style.background_color,
                    }

                elements_payload.append(
                    {
                        "id": element.element_id,
                        "type": element.element_type,
                        "text": element.text,
                        "position": {
                            "x": element.position.x,
                            "y": element.position.y,
                            "width": element.position.width,
                            "height": element.position.height,
                        },
                        "style": style,
                        "metadata": self._sanitize_metadata(element.metadata),
                    }
                )

            relationships_payload = []
            for relationship in slide.relationships:
                source_element = next(
                    (
                        element
                        for element in slide.elements
                        if element.element_id == relationship.source_element_id
                    ),
                    None,
                )
                target_element = next(
                    (
                        element
                        for element in slide.elements
                        if element.element_id == relationship.target_element_id
                    ),
                    None,
                )
                source_label = (
                    source_element.text.strip()
                    if source_element and source_element.text
                    else None
                )
                target_label = (
                    target_element.text.strip()
                    if target_element and target_element.text
                    else None
                )
                relationships_payload.append(
                    {
                        "type": relationship.relationship_type,
                        "from": source_label or relationship.source_element_id,
                        "to": target_label or relationship.target_element_id,
                    }
                )

            slides_payload.append(
                {
                    "slide_number": slide.slide_number,
                    "title": slide.title,
                    "elements": elements_payload,
                    "relationships": relationships_payload,
                    "summary": slide.slide_summary,
                }
            )

        return {
            "document_type": extracted_document.document_type,
            "slides": slides_payload,
            "summary": extracted_document.document_summary,
        }

    async def _summarize_slide(self, slide) -> Optional[str]:
        if self.summarization_agent:
            try:
                return await self.summarization_agent.summarize_slide(slide)
            except self._summary_error_types:
                return self._fallback_slide_summary(slide)
        return self._fallback_slide_summary(slide)

    @staticmethod
    def _fallback_slide_summary(slide) -> Optional[str]:
        title = slide.title.strip() if slide.title else None
        lines = []
        if title:
            lines.append(title)
        for element in slide.elements:
            if not element.text:
                continue
            for raw_line in element.text.splitlines():
                cleaned = raw_line.strip()
                if not cleaned or cleaned in lines:
                    continue
                lines.append(ExtractionService._truncate_text(cleaned, 120))
                if len(lines) >= 4:
                    break
            if len(lines) >= 4:
                break
        if not lines:
            return None
        if title and lines[0] == title:
            details = lines[1:4]
            if details:
                summary = f"{title}: " + "; ".join(details)
            else:
                summary = title
        else:
            summary = "; ".join(lines[:3])
        return ExtractionService._truncate_text(summary, 300)

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        trimmed = text[: limit - 3].rstrip()
        return f"{trimmed}..."

    async def _summarize_images(self, document_model):
        for slide in document_model.slides:
            image_summaries = []
            for element in slide.elements:
                if element.element_type != "image":
                    continue
                image_bytes = element.metadata.get("__image_bytes")
                if not image_bytes:
                    continue
                try:
                    summary = await self.image_summarization_agent.summarize_image(
                        image_bytes
                    )
                except Exception:
                    summary = None
                if summary:
                    element.metadata["image_summary"] = summary
                    image_summaries.append(summary)

            if image_summaries:
                joined_summary = " ".join(image_summaries)
                if slide.slide_summary:
                    slide.slide_summary = (
                        f"{slide.slide_summary}\nImage summary: {joined_summary}"
                    )
                else:
                    slide.slide_summary = f"Image summary: {joined_summary}"

    @staticmethod
    def _build_document_summary(document_model) -> Optional[str]:
        slide_summaries = [
            slide.slide_summary for slide in document_model.slides if slide.slide_summary
        ]
        if slide_summaries:
            return " ".join(slide_summaries)
        slide_titles = [slide.title for slide in document_model.slides if slide.title]
        if slide_titles:
            return "Slides cover: " + "; ".join(slide_titles)
        return None

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        if not metadata:
            return {}
        sanitized = {}
        for key, value in metadata.items():
            if key.startswith("__"):
                continue
            sanitized[key] = value
        return sanitized
