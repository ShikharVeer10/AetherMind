from typing import List, Optional
from pathlib import Path
import fitz
from models.document_model import (
    DocumentModel,
    DocumentElementModel,
    SlideModel,
    PositionModel,
    StyleModel,
    ParagraphModel,
    RunModel,
)
from services.table_service import TableService

class PDFExtractor:
    def __init__(self, pdf_file_path: str):
        self.pdf_file_path = Path(pdf_file_path)
        self.doc = fitz.open(pdf_file_path)
        self.table_service = TableService()

    def extract_document(self) -> DocumentModel:
        extracted_slides = []
        for page_index, page in enumerate(self.doc):
            extracted_slide = self.extract_page(
                page=page, page_number=page_index + 1
            )
            extracted_slides.append(extracted_slide)

        return DocumentModel(
            document_name=self.pdf_file_path.name,
            document_type="pdf",
            total_slides=len(extracted_slides),
            slides=extracted_slides,
            presentation_metadata={
                "pdf_version": self.doc.metadata.get("format", "PDF"),
                "author": self.doc.metadata.get("author", ""),
                "title": self.doc.metadata.get("title", ""),
                "subject": self.doc.metadata.get("subject", ""),
                "created": self.doc.metadata.get("creationDate", ""),
                "modified": self.doc.metadata.get("modDate", ""),
            },
        )

    def extract_page(self, page, page_number: int) -> SlideModel:
        scale = 12700.0
        page_height_points = page.rect.height

        extracted_elements = []
        z_order = 1

        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        slide_title = self._deduce_title(
        blocks,
        page_height_points
    )

        for block_idx, block in enumerate(blocks):

            if block.get("type") != 0:
                continue

            lines = block.get("lines", [])

            if not lines:
                continue

            paragraphs = []
            block_text_parts = []

            for line in lines:

                line_spans = line.get("spans", [])

                if not line_spans:
                    continue

                line_text = "".join(
                    span.get("text", "")
                    for span in line_spans
                ).strip()

                if not line_text:
                    continue

                runs = []

                for span in line_spans:

                    span_text = span.get("text", "")

                    if not span_text:
                        continue

                    font_name = span.get("font", "")
                    font_size = span.get("size")
                    flags = span.get("flags", 0)

                    is_bold = (
                        bool(flags & 16)
                        or "bold" in font_name.lower()
                    )

                    is_italic = (
                        bool(flags & 2)
                        or "italic" in font_name.lower()
                        or "oblique" in font_name.lower()
                    )

                    color_int = span.get("color")

                    runs.append(
                        RunModel(
                            text=span_text,
                            bold=is_bold,
                            italic=is_italic,
                            font_size=font_size,
                            font_name=font_name,
                        font_color=self._get_color_hex(color_int),
                    )
                )

            paragraphs.append(
                ParagraphModel(
                    level=0,
                    text=line_text,
                    runs=runs,
                )
            )

            block_text_parts.append(line_text)

            if not block_text_parts:
                continue

        full_text = "\n".join(block_text_parts)

        bx0, by0, bx1, by1 = block["bbox"]

        position = PositionModel(
            x=bx0 * scale,
            y=by0 * scale,
            width=(bx1 - bx0) * scale,
            height=(by1 - by0) * scale,
        )

        style = None

        if lines and lines[0].get("spans"):

            first_span = lines[0]["spans"][0]

            font_name = first_span.get("font", "")
            flags = first_span.get("flags", 0)

            is_bold = (
                bool(flags & 16)
                or "bold" in font_name.lower()
            )

            is_italic = (
                bool(flags & 2)
                or "italic" in font_name.lower()
                or "oblique" in font_name.lower()
            )

            style = StyleModel(
                font_size=first_span.get("size"),
                font_name=font_name,
                bold=is_bold,
                italic=is_italic,
                text_color=self._get_color_hex(
                    first_span.get("color")
                ),
                background_color=None,
            )

        element_id = f"slide_{page_number}_shape_{block_idx + 1}"

        elem = DocumentElementModel(
            element_id=element_id,
            element_type="text_box",
            text=full_text,
            paragraphs=paragraphs,
            position=position,
            style=style,
            shape_type="rect",
            metadata={
                "name": f"Text Block {block_idx + 1}",
                "visible": True,
                "is_placeholder": False,
                "z_order": z_order,
            },
        )

        extracted_elements.append(elem)
        z_order += 1

        return SlideModel(
        slide_number=page_number,
        title=slide_title,
        elements=extracted_elements,
        background_color="#ffffff",
    )