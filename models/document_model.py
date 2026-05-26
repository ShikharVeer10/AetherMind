from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


# Store the position and dimensions of the element
class PositionModel(BaseModel):
    x: float
    y: float
    width: float
    height: float


class StyleModel(BaseModel):
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    bold: bool = False
    italic: bool = False
    text_color: Optional[str] = None
    background_color: Optional[str] = None


# Represents the relation between 2 elements
class RelationshipModel(BaseModel):
    relationship_type: str
    source_element_id: str
    target_element_id: str


# Represents a single element in the document
class DocumentElementModel(BaseModel):
    element_id: str
    element_type: str
    text: Optional[str]
    position: PositionModel
    style: Optional[StyleModel] = None
    shape_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Represents one slide/page in a document
class SlideModel(BaseModel):
    slide_number: int
    title: Optional[str] = None
    elements: List[DocumentElementModel] = Field(default_factory=list)
    slide_summary: Optional[str] = None


# Represents the entire document
class DocumentModel(BaseModel):
    document_name: str
    document_type: str
    total_slides: int
    slides: List[SlideModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
