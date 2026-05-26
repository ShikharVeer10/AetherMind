# Extraction service for a powerpoint presentation
import json
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
        if self.enable_summaries:
            from agents.summarization_agent import SummarizationAgent

            self.summarization_agent = SummarizationAgent()
        if self.enable_image_summaries:
            from agents.image_summarization_agent import ImageSummaryAgent

            self.image_summarization_agent = ImageSummaryAgent()

    async def extract_document(self):
        if self.document_extension == ".pptx":
            extractor = PPTExtractor(self.document_path)
            document_model = extractor.extract_document()
            if self.enable_summaries and self.summarization_agent:
                for slide in document_model.slides:
                    try:
                        slide.slide_summary = (
                            await self.summarization_agent.summarize_slide(slide)
                        )
                    except Exception:
                        slide.slide_summary = None
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

            slides_payload.append(
                {
                    "slide_number": slide.slide_number,
                    "title": slide.title,
                    "elements": elements_payload,
                    "relationships": [],
                    "summary": slide.slide_summary,
                }
            )

        return {
            "document_type": "ppt",
            "document_name": extracted_document.document_name,
            "slides": slides_payload,
        }

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
    def _sanitize_metadata(metadata: dict) -> dict:
        if not metadata:
            return {}
        sanitized = {}
        for key, value in metadata.items():
            if key.startswith("__"):
                continue
            sanitized[key] = value
        return sanitized
