from services.semantic_table_service import SemanticTableService
from services.flexible_table_detector import FlexibleTableDetector
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
from services.layout_structure_service import LayoutStructureService
from services.table_service import TableService

class PDFExtractor:
    def __init__(self, pdf_file_path: str):
        self.pdf_file_path = Path(pdf_file_path)
        self.doc = fitz.open(pdf_file_path)
        self.table_service = TableService()
        self.layout_service = LayoutStructureService()
        self.flexible_table_detector = FlexibleTableDetector()
        self.semantic_table_service = SemanticTableService()

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
    def extract_table_as_list(self, table):

        table_data = []

        extracted = table.extract()

        for row in extracted:
            cleaned_row = []
            for cell in row:
                cleaned_row.append(
                    str(cell).strip()
                    if cell is not None
                    else ""
                )
            table_data.append(cleaned_row)
        return table_data

    def extract_page(self, page, page_number: int) -> SlideModel:
        scale = 12700.0
        page_height_points = page.rect.height

        extracted_elements = []
        detected_tables = []
        z_order = 1

        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        print("\nPAGE:", page_number)
        
        try:
            tables = page.find_tables()
            print("TABLES FOUND:", len(tables.tables))
        except Exception as e:
            print("TABLE DETECTION ERROR:", e)
            tables = None
        
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

                line_text = "".join(span.get("text", "") for span in line_spans).strip()
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

                    is_bold = bool(flags & 16) or "bold" in font_name.lower()
                    is_italic = bool(flags & 2) or "italic" in font_name.lower() or "oblique" in font_name.lower()

                    color_int = span.get("color")
                    runs.append(RunModel(
                        text=span_text,
                        bold=is_bold,
                        italic=is_italic,
                        font_size=font_size,
                        font_name=font_name,
                        font_color=self._get_color_hex(color_int),
                    ))

                paragraphs.append(ParagraphModel(
                    level=0,
                    text=line_text,
                    runs=runs,
                ))
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
                is_bold = (bool(flags & 16) or "bold" in font_name.lower())
                is_italic = (bool(flags & 2) or "italic" in font_name.lower() or "oblique" in font_name.lower())

                style = StyleModel(
                    font_size=first_span.get("size"),
                    font_name=font_name,
                    bold=is_bold,
                    italic=is_italic,
                    text_color=self._get_color_hex(first_span.get("color")),
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

        # Process native tables if found
        if tables:
            for table_idx, table in enumerate(tables.tables):
                raw_table_content = self.extract_table_as_list(table)
                if not raw_table_content:
                    continue

                table_markdown = self.table_service.to_markdown(raw_table_content)
                table_structure = self.table_service.analyze_structure(raw_table_content)
                table_semantic_interpretation = self.table_service.generate_semantic_context(raw_table_content)
                table_render_model = self.table_service.build_render_model(raw_table_content, table_structure)
                
                table_element = DocumentElementModel(
                    element_id=f"slide_{page_number}_table_{table_idx}",
                    element_type="table",
                    text=table_markdown,
                    paragraphs=[],
                    position=PositionModel(
                        x=table.bbox[0] * scale,
                        y=table.bbox[1] * scale,
                        width=(table.bbox[2] - table.bbox[0]) * scale,
                        height=(table.bbox[3] - table.bbox[1]) * scale,
                    ),
                    table_markdown=table_markdown,
                    raw_table_content=raw_table_content,
                    table_structure=table_structure,
                    table_render_model=table_render_model,
                    table_semantic_interpretation=table_semantic_interpretation,
                    metadata={"z_order": z_order}
                )
                extracted_elements.append(table_element)
                detected_tables.append({
                    "rows": len(raw_table_content),
                    "columns": max(len(r) for r in raw_table_content) if raw_table_content else 0,
                    "content": raw_table_content
                })
                z_order += 1

        # Flexible table detection fallback for text blocks
        visual_tables = self.flexible_table_detector.detect_visual_tables(extracted_elements)
        for visual_table in visual_tables:
            detected_tables.append({
                "table_type": visual_table.get("table_type", "visual_table"),
                "rows": len(visual_table.get("rows", [])),
                "content": visual_table.get("rows", [])
            })

        return SlideModel(
            slide_number=page_number,
            title=slide_title,
            elements=extracted_elements,
            background_color="#ffffff",
            detected_tables=detected_tables,
        )




    def _deduce_title(self,blocks: List[dict],page_height: float) -> Optional[str]:
        candidates = []

        for block in blocks:

            if block.get("type") != 0:
                continue

            bbox = block.get("bbox", (0, 0, 0, 0))
            y0 = bbox[1]

        # Ignore bottom 25% of page
            if y0 > page_height * 0.75:
                continue

            block_max_font = 0.0
            block_text = ""

            for line in block.get("lines", []):

                for span in line.get("spans", []):

                    block_max_font = max(
                    block_max_font,
                    span.get("size", 0.0)
                    )

                    block_text += span.get(
                    "text",
                    ""
                    )

            block_text = block_text.strip()

            if not block_text:
                continue

            candidates.append(
                {
                    "text": block_text,
                    "max_font": block_max_font,
                    "y0": y0,
                    "x0": bbox[0],
                }
            )

        if not candidates:
            return None

        global_max_font = max(
        candidate["max_font"]
        for candidate in candidates
        )
        font_threshold = global_max_font * 0.7
        title_candidates = [
            candidate
            for candidate in candidates
            if candidate["max_font"] >= font_threshold
        ]
        title_candidates.sort(
            key=lambda candidate: (
                candidate["y0"],
                candidate["x0"],
            )
        )
        if title_candidates:
            return (
                title_candidates[0]["text"]
                .replace("\n", " ")
                .strip()
            )
        return None

    def _get_color_hex(self,color_int: Optional[int]) -> Optional[str]:
        if color_int is None:
            return None
        try:
            r = (color_int >> 16) & 255
            g = (color_int >> 8) & 255
            b = color_int & 255
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return None