"""
Orchestrates the end-to-end extraction of a .pptx document.

Delegates per-slide enrichment to AgentOrchestrator, which runs
multiple extraction agents in parallel phases.
"""

import json
from pathlib import Path
from extractors.ppt_extractor import PPTExtractor
from agents.agent_orchestrator import AgentOrchestrator


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
        if self.document_extension != ".pptx":
            raise ValueError(
                f"Unsupported document type: {self.document_extension}"
            )

        extractor = PPTExtractor(self.document_path)
        document_model = extractor.extract_document()

        orchestrator = AgentOrchestrator(
            summarization_agent=self.summarization_agent,
            image_summarization_agent=self.image_summarization_agent,
        )

        raw_slides = list(extractor.presentation.slides)

        for slide_model, raw_slide in zip(
            document_model.slides, raw_slides
        ):
            slide_model.slide_summary = self._build_fallback_summary(
                slide_model
            )
            await orchestrator.process_slide(
                slide_model=slide_model,
                raw_slide=raw_slide,
            )

        return document_model

    def export_to_json(
        self,
        extracted_document,
        output_directory: str = "output/extracted_json",
    ):
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        document_name = Path(self.document_path).stem
        json_output_file = output_path / f"{document_name}.json"

        output_payload = self._format_output(extracted_document)
        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=4, ensure_ascii=False)

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
                        "font_name": element.style.font_name,
                        "bold": element.style.bold,
                        "italic": element.style.italic,
                        "color": element.style.text_color,
                        "background_color": element.style.background_color,
                    }

                paragraphs = [
                    {
                        "level": p.level,
                        "text": p.text,
                        "runs": [
                            {
                                "text": r.text,
                                "bold": r.bold,
                                "italic": r.italic,
                                "font_size": r.font_size,
                                "font_name": r.font_name,
                                "font_color": r.font_color,
                            }
                            for r in p.runs
                        ],
                    }
                    for p in element.paragraphs
                ]

                elements_payload.append(
                    {
                        "id": element.element_id,
                        "type": element.element_type,
                        "text": element.text,
                        "paragraphs": paragraphs,
                        "position": {
                            "x": element.position.x,
                            "y": element.position.y,
                            "width": element.position.width,
                            "height": element.position.height,
                        },
                        "style": style,
                        "table_markdown": element.table_markdown,
                        "metadata": self._sanitize_metadata(element.metadata),
                    }
                )

            relationships_payload = [
                {
                    "type": r.relationship_type,
                    "source": r.source_element_id,
                    "target": r.target_element_id,
                    "label": r.label,
                    "confidence": r.confidence,
                }
                for r in slide.relationships
            ]

            hf = None
            if slide.header_footer:
                hf = {
                    "header": slide.header_footer.header_text,
                    "footer": slide.header_footer.footer_text,
                    "slide_number": slide.header_footer.slide_number_text,
                    "date": slide.header_footer.date_text,
                }

            inv = None
            if slide.visual_inventory:
                inv = slide.visual_inventory.model_dump()

            layout = None
            if slide.layout_structure:
                layout = {
                    "type": slide.layout_structure.layout_type,
                    "regions": [
                        {
                            "name": r.name,
                            "element_ids": r.element_ids,
                        }
                        for r in slide.layout_structure.regions
                    ],
                }

            flowchart = None
            if slide.flowchart and slide.flowchart.is_flowchart:
                flowchart = {
                    "box_count": slide.flowchart.box_count,
                    "arrow_count": slide.flowchart.arrow_count,
                    "boxes": slide.flowchart.boxes,
                    "arrows": slide.flowchart.arrows,
                    "relationships": [
                        {
                            "type": r.relationship_type,
                            "source": r.source_element_id,
                            "target": r.target_element_id,
                            "label": r.label,
                            "confidence": r.confidence,
                        }
                        for r in slide.flowchart.relationships
                    ],
                    "reading_order": slide.flowchart.reading_order,
                }

            context = None
            if slide.context:
                context = slide.context.model_dump()

            text_points = [
                {
                    "element_id": p.element_id,
                    "level": p.level,
                    "text": p.text,
                }
                for p in slide.text_points
            ]

            position_mapping = [
                {
                    "element_id": p.element_id,
                    "element_type": p.element_type,
                    "x": p.x,
                    "y": p.y,
                    "width": p.width,
                    "height": p.height,
                }
                for p in slide.position_mapping
            ]

            diagram_understanding = None
            if slide.diagram_understanding:
                diagram_understanding = slide.diagram_understanding.model_dump()

            slides_payload.append(
                {
                    "slide_number": slide.slide_number,
                    "title": slide.title,
                    "header_footer": hf,
                    "visual_inventory": inv,
                    "layout": layout,
                    "elements": elements_payload,
                    "relationships": relationships_payload,
                    "flowchart": flowchart,
                    "context": context,
                    "text_points": text_points,
                    "position_mapping": position_mapping,
                    "diagram_understanding": diagram_understanding,
                    "table_markdowns": slide.table_markdowns,
                    "summary": slide.slide_summary,
                }
            )

        return {
            "document_type": "ppt",
            "document_name": extracted_document.document_name,
            "total_slides": extracted_document.total_slides,
            "slides": slides_payload,
        }

    @staticmethod
    def _build_fallback_summary(slide) -> str:
        title = (slide.title or "").strip()
        text_fragments = []

        for element in slide.elements:
            if element.text:
                cleaned = " ".join(element.text.split())
                if cleaned:
                    text_fragments.append(cleaned)

        if text_fragments:
            unique = []
            for frag in text_fragments:
                if frag not in unique:
                    unique.append(frag)
            body = "; ".join(unique[:3])
            if title and title not in body:
                return f"{title}. Key points: {body}."
            return f"Key points: {body}."

        if title:
            return f"{title}."

        return f"Slide {slide.slide_number} contains no extracted text."

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        if not metadata:
            return {}
        return {
            k: v for k, v in metadata.items()
            if not k.startswith("__")
        }
