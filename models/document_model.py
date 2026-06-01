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
    
class HeaderModel(BaseModel):
    text:str
    element_id:str
    position:Optional[PositionModel]=None

class FooterModel(BaseModel):
    text:str
    element_id:str
    is_page_number:bool=False
    position:Optional[PositionModel]=None
    
class ContextModel(BaseModel):
    title_count:int=0
    box_count:int=0
    text_box_count:int=0
    shape_count:int=0
    arrow_count:int=0
    image_count:int=0
    table_count:int=0
    flowchart_detected:bool=False
    diagram_detected:bool=False
    timeline_detected:bool=False
    
#FlowModel: Stores flow chart level information
class FlowModel(BaseModel):
    flow_detected:bool=False
    flow_type:Optional[str]=None
    start_node:Optional[str]=None
    end_node:Optional[str]=None
    node_count:int=0
    connector_count:int=0
    relationship_count:int=0

#Representing extracted objects like shape,arrow,etc
class DocumentElementModel(BaseModel):
    element_id:str
    element_type:str
    text:Optional[str]=None
    position:PositionModel
    style:Optional[StyleModel]=None
    shape_type:Optional[str]=None
    metadata:Dict[str,Any]=Field(default_factory=dict)

class SectionModel(BaseModel):
    section_name: str
    element_ids: List[str] = Field(default_factory=list)
    bounding_box: Optional[PositionModel] = None

#To support Slide models
class SlideModel(BaseModel):
    slide_number: int
    title: Optional[str] = None
    slide_type: Optional[str] = None
    headers:List[HeaderModel]=Field(default_factory=list)
    footers:List[FooterModel]=Field(default_factory=list)
    context:Optional[ContextModel]=None
    elements: List[DocumentElementModel] = Field(default_factory=list)
    sections: List[SectionModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    flow_information: Optional[FlowModel] = None
    slide_summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
# Represents the entire document
class DocumentModel(BaseModel):
    document_name: str
    document_type: str
    total_slides: int
    slides: List[SlideModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


