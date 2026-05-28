from pathlib import Path
from typing import Optional
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER  # Classify the shape
from models.document_model import DocumentModel
from models.document_model import DocumentElementModel
from models.document_model import SlideModel
from models.document_model import PositionModel
from models.document_model import StyleModel


# Extract structured information from ppt presentation
EMU_PER_INCH = 914400
PIXELS_PER_INCH = 96
TITLE_PLACEHOLDER_TYPES = {
    placeholder
    for placeholder in (
        getattr(PP_PLACEHOLDER, "TITLE", None),
        getattr(PP_PLACEHOLDER, "CENTER_TITLE", None),
        getattr(PP_PLACEHOLDER, "SUBTITLE", None),
    )
    if placeholder is not None
}


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
            if slide_title is None:
                title_text = self.extract_title_text(shape)
                if title_text:
                    slide_title = title_text
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
            x=self.emu_to_pixels(shape.left),
            y=self.emu_to_pixels(shape.top),
            width=self.emu_to_pixels(shape.width),
            height=self.emu_to_pixels(shape.height),
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
        if shape.has_table:
            return "table"
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return "image"
        if getattr(shape, "is_connector", False):
            return "connector"
        if shape.shape_type == MSO_SHAPE_TYPE.LINE:
            return "connector"
        if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            auto_shape = getattr(shape, "auto_shape_type", None)
            auto_shape_name = ""
            if auto_shape is not None:
                auto_shape_label = getattr(auto_shape, "name", None)
                if auto_shape_label is None:
                    auto_shape_label = str(auto_shape)
                auto_shape_name = str(auto_shape_label).lower()
            elif shape.name:
                auto_shape_name = shape.name.lower()
            if "arrow" in auto_shape_name or "chevron" in auto_shape_name:
                return "arrow"
            return "shape"
        if shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            return "text_box"
        if shape.has_text_frame:
            return "text_box"
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            return "group"

        return "shape"

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
            table_data = self.extract_table_data(shape)
            metadata["table_data"] = table_data
            if table_data:
                metadata["table_rows"] = len(table_data)
                metadata["table_columns"] = max(len(row) for row in table_data)
        if shape_type == "image":
            image = getattr(shape, "image", None)
            metadata["__image_bytes"] = image.blob if image else None
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

        if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    font = run.font
                    if font.size and font_size is None:
                        font_size = float(font.size.pt)
                    if font.name and font_name is None:
                        font_name = font.name
                    if font.bold is True:
                        is_bold = True
                    if font.italic is True:
                        is_italic = True
                    if text_color is None:
                        text_color = self.extract_hex_color(font.color)

                paragraph_font = paragraph.font
                if paragraph_font.size and font_size is None:
                    font_size = float(paragraph_font.size.pt)
                if paragraph_font.name and font_name is None:
                    font_name = paragraph_font.name
                if paragraph_font.bold is True:
                    is_bold = True
                if paragraph_font.italic is True:
                    is_italic = True
                if text_color is None:
                    text_color = self.extract_hex_color(paragraph_font.color)

        fill = getattr(shape, "fill", None)
        if fill and fill.type == MSO_FILL.SOLID:
            background_color = self.extract_hex_color(fill.fore_color)

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
    def emu_to_pixels(emu: float) -> float:
        return round((float(emu) / EMU_PER_INCH) * PIXELS_PER_INCH, 2)

    def extract_title_text(self, shape) -> Optional[str]:
        if not getattr(shape, "is_placeholder", False):
            return None
        placeholder_type = getattr(shape.placeholder_format, "type", None)
        if placeholder_type not in TITLE_PLACEHOLDER_TYPES:
            return None
        if not shape.has_text_frame:
            return None
        title_text = shape.text_frame.text.strip()
        return title_text or None

    def extract_hex_color(self, color_format) -> Optional[str]:
        if not color_format:
            return None
        if color_format.type != MSO_COLOR_TYPE.RGB:
            return None
        if not color_format.rgb:
            return None
        return self.convert_rgb_to_hex(color_format.rgb)

    @staticmethod
    def convert_rgb_to_hex(rgb_color: RGBColor) -> str:
        return "#{:02x}{:02x}{:02x}".format(rgb_color[0], rgb_color[1], rgb_color[2])
