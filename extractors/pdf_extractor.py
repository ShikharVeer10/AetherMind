from pathlib import Path
from typing import List, Optional
import fitz  # PyMuPDF
from models.document_model import (
    DocumentModel,
    DocumentElementModel,
    SlideModel,
    PositionModel,
    StyleModel,
    ParagraphModel,
    RunModel,
)


class PDFExtractor:
    def __init__(self, pdf_file_path: str):
        self.pdf_file_path = Path(pdf_file_path)
        self.doc = fitz.open(pdf_file_path)

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
        # Scale PDF points to PowerPoint EMU (1 pt = 12700 EMU)
        scale = 12700.0
        page_width_points = page.rect.width
        page_height_points = page.rect.height

        extracted_elements = []
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        # Deduce page title
        slide_title = self._deduce_title(blocks, page_height_points)

        # 1. Add full-page image element at the bottom (Z-order 0)
        # This renders the visual slide so our vision-based agents can summarize/interpret it.
        try:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
        except Exception:
            img_bytes = None

        if img_bytes:
            full_page_element = DocumentElementModel(
                element_id=f"slide_{page_number}_full_page_image",
                element_type="image",
                text=None,
                paragraphs=[],
                position=PositionModel(
                    x=0.0,
                    y=0.0,
                    width=page_width_points * scale,
                    height=page_height_points * scale,
                ),
                style=None,
                shape_type="rect",
                metadata={
                    "name": f"Full Slide {page_number} Image",
                    "__image_bytes": img_bytes,
                    "visible": True,
                    "is_placeholder": False,
                    "z_order": 0,
                }
            )
            extracted_elements.append(full_page_element)

        # 2. Extract text blocks and map to slide elements
        z_order = 1
        for block_idx, block in enumerate(blocks):
            if block.get("type") != 0:  # Skip image blocks (we already have full-slide visual context)
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
            
            # Position conversion
            bx0, by0, bx1, by1 = block["bbox"]
            position = PositionModel(
                x=bx0 * scale,
                y=by0 * scale,
                width=(bx1 - bx0) * scale,
                height=(by1 - by0) * scale,
            )

            # Style model from first span
            style = None
            if lines and lines[0].get("spans"):
                first_span = lines[0]["spans"][0]
                font_name = first_span.get("font", "")
                flags = first_span.get("flags", 0)
                is_bold = bool(flags & 16) or "bold" in font_name.lower()
                is_italic = bool(flags & 2) or "italic" in font_name.lower() or "oblique" in font_name.lower()
                style = StyleModel(
                    font_size=first_span.get("size"),
                    font_name=font_name,
                    bold=is_bold,
                    italic=is_italic,
                    text_color=self._get_color_hex(first_span.get("color")),
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
            background_color="#ffffff",  # Default PDF page background
        )

    def _get_color_hex(self, color_int: Optional[int]) -> Optional[str]:
        if color_int is None:
            return None
        try:
            r = (color_int >> 16) & 255
            g = (color_int >> 8) & 255
            b = color_int & 255
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return None

    def _deduce_title(self, blocks: List[dict], page_height: float) -> Optional[str]:
        candidates = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            
            bbox = block.get("bbox", (0, 0, 0, 0))
            y0 = bbox[1]
            
            # Skip blocks in the bottom 25% of the page (almost certainly not a title)
            if y0 > page_height * 0.75:
                continue
                
            block_max_font = 0.0
            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_max_font = max(block_max_font, span.get("size", 0.0))
                    block_text += span.get("text", "")
            
            block_text = block_text.strip()
            if not block_text:
                continue
                
            candidates.append({
                "text": block_text,
                "max_font": block_max_font,
                "y0": y0,
                "x0": bbox[0]
            })
            
        if not candidates:
            return None
            
        # Find global max font size
        global_max_font = max(c["max_font"] for c in candidates)
        
        # Filter candidates: must be within 30% of the max font size on the page
        font_threshold = global_max_font * 0.7
        title_candidates = [c for c in candidates if c["max_font"] >= font_threshold]
        
        # Sort title candidates: primarily by y0 (top to bottom), secondarily by x0 (left to right)
        title_candidates.sort(key=lambda c: (c["y0"], c["x0"]))
        
        if title_candidates:
            # Clean and return the topmost candidate
            return title_candidates[0]["text"].replace("\n", " ").strip()
            
        return None
