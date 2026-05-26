from pathlib import Path
from typing import Optional
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE  # Classify the shape
from pptx.dml.color import RGBColor
from models.document_model import DocumentModel
from models.document_model import DocumentElementModel
from models.document_model import SlideModel
from models.document_model import PositionModel
from models.document_model import StyleModel


# Extract structured information from ppt presentation
class PPTExtractor:
    def __init__(self, pptx_file_path: str):
        self.pptx_file_path = Path(pptx_file_path)
        self.presentation = Presentation(pptx_file_path)

    def extract_document(self) -> DocumentModel:
        extracted_slides = []

        for slide_index, slide in enumerate(self.presentation.slides):
            extracted_slide = self.extract_slide(
                slide=slide, slide_number=slide_index + 1
            )
            extracted_slides.append(extracted_slide)

        document_model = DocumentModel(
            document_name=Path(self.pptx_file_path).name,
            document_type="ppt",
            total_slides=len(extracted_slides),
            slides=extracted_slides,
        )
        return document_model

    def extract_slide(self, slide, slide_number: int) -> SlideModel:
        extracted_elements = []
        slide_title: Optional[str] = None
        for index, shape in enumerate(slide.shapes):
            extracted_element = self.extract_shape(
                shape=shape, slide_number=slide_number, shape_index=index
            )
            if extracted_element is not None:
                extracted_elements.append(extracted_element)
                if slide_title is None and extracted_element.text:
                    slide_title = extracted_element.text

        slide_model = SlideModel(
            slide_number=slide_number, title=slide_title, elements=extracted_elements
        )
        return slide_model

    def extract_shape(
        self, shape, slide_number: int, shape_index: int
    ) -> Optional[DocumentElementModel]:
        extracted_text = None
        if shape.has_text_frame:
            extracted_text = shape.text_frame.text.strip()
            if extracted_text == "":
                extracted_text = None

        # Determine dimensions
        position_model = PositionModel(
            x=float(shape.left),
            y=float(shape.top),
            width=float(shape.width),
            height=float(shape.height),
        )

        style_model = self.extract_text_style(shape=shape)

        element = DocumentElementModel(
            element_id=f"slide_{slide_number}_shape_{shape_index}",
            element_type=self.get_shape_type(shape),
            text=extracted_text,
            position=position_model,
            style=style_model,
            shape_type=str(shape.shape_type),
            metadata=self.extract_shape_metadata(shape),
        )
        return element

    def get_shape_type(self, shape) -> str:
        if shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            return "text_box"
        if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            shape_name = shape.name.lower()
            if "arrow" in shape_name:
                return "arrow"
            if "rectangle" in shape_name or "box" in shape_name:
                return "shape"
            return "shape"

        connector_type = getattr(MSO_SHAPE_TYPE, "CONNECTOR", None)
        if connector_type is not None and shape.shape_type == connector_type:
            return "connector"
        if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            return "table"
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return "image"

        return "unknown"

    def extract_table_data(self, shape) -> list:
        extracted_rows = []
        if not shape.has_table:
            return extracted_rows
        table = shape.table

        for row in table.rows:
            extracted_cells = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                extracted_cells.append(cell_text)
            extracted_rows.append(extracted_cells)

        return extracted_rows

    def extract_shape_metadata(self, shape) -> dict:
        metadata = {}
        shape_type = self.get_shape_type(shape)
        if shape_type == "table":
            metadata["table_data"] = self.extract_table_data(shape)
        if shape_type == "image":
            try:
                metadata["__image_bytes"] = shape.image.blob
            except Exception:
                metadata["__image_bytes"] = None
        if shape.has_text_frame:
            metadata["bullet_hierarchy"] = self.extract_bullet_hierarchy(shape)
        return metadata

    def extract_bullet_hierarchy(self, shape) -> list:
        bullet_items = []
        if not shape.has_text_frame:
            return bullet_items
        text_frame = shape.text_frame
        for paragraph in text_frame.paragraphs:
            level = paragraph.level
            text = paragraph.text.strip()
            if text:
                bullet_items.append({"level": level, "text": text})
        return bullet_items

    # Extracts font and style information from a shape
    def extract_text_style(self, shape) -> StyleModel:
        font_size: Optional[float] = None
        font_name: Optional[str] = None
        is_bold = False
        is_italic = False
        text_color = None
        background_color = None

        try:
            # Check for
            if shape.has_text_frame:
                paragraphs = shape.text_frame.paragraphs
                if paragraphs and paragraphs[0].runs:
                    first_run = paragraphs[0].runs[0]
                    font = first_run.font

                    if font.size:
                        font_size = float(font.size.pt)
                    if font.name:
                        font_name = font.name
                    if font.bold:
                        is_bold = True
                    if font.italic:
                        is_italic = True
                    if font.color and font.color.rgb:
                        text_color = self.convert_rgb_to_hex(font.color.rgb)

        except Exception:
            pass

        try:
            if shape.fill and shape.fill.fore_color and shape.fill.fore_color.rgb:
                background_color = self.convert_rgb_to_hex(shape.fill.fore_color.rgb)

        except Exception:
            pass

        style_model = StyleModel(
            font_size=font_size,
            font_name=font_name,
            bold=is_bold,
            italic=is_italic,
            text_color=text_color,
            background_color=background_color,
        )

        return style_model

    # Sorting elements from top to bottom or right to left
    def sort_elements_by_reading_order(self, slide):
        sorted_elements = sorted(
            slide.elements, key=lambda element: (element.position.y, element.position.x)
        )
        return sorted_elements

    @staticmethod
    def convert_rgb_to_hex(rgb_color: RGBColor) -> str:
        return "#{:02x}{:02x}{:02x}".format(rgb_color[0], rgb_color[1], rgb_color[2])
