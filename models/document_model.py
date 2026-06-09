from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class RunModel(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    font_color: Optional[str] = None


class ParagraphModel(BaseModel):
    level: int = 0
    text: str
    alignment: Optional[str] = None
    runs: List[RunModel] = Field(default_factory=list)


class RelationshipModel(BaseModel):
    relationship_type: str
    source_element_id: str
    target_element_id: str
    label: Optional[str] = None
    confidence: float = 1.0
    semantic_relation:Optional[str]=None
    direction:Optional[str]=None


class TextPointModel(BaseModel):
    element_id: str
    level: int = 0
    text: str


class PositionMapModel(BaseModel):
    element_id: str
    element_type: str
    x: float
    y: float
    width: float
    height: float


class DiagramUnderstandingModel(BaseModel):
    is_diagram: bool = False
    diagram_type: str = "none"
    node_count: int = 0
    edge_count: int = 0
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    flow_description: str = ""
    summary: str = ""


class ChartUnderstandingModel(BaseModel):
    chart_type: str = "none"
    title: Optional[str] = None
    measures: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    trends: List[str] = Field(default_factory=list)
    anomalies: List[str] = Field(default_factory=list)
    comparisons: List[str] = Field(default_factory=list)
    raw_chart_data: Optional[Dict[str, Any]] = None


class SemanticRegionModel(BaseModel):
    name: str
    semantic_role: str
    purpose: str
    position: PositionModel
    contents: List[str] = Field(default_factory=list)


class DocumentElementModel(BaseModel):
    element_id: str
    element_type: str
    text: Optional[str] = None
    paragraphs: List[ParagraphModel] = Field(default_factory=list)
    position: PositionModel
    style: Optional[StyleModel] = None
    shape_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    table_markdown: Optional[str] = None
    raw_table_content: Optional[List[List[str]]] = None
    table_structure: Optional[Dict[str, Any]] = None
    table_visual_metadata: Optional[dict] = None
    table_render_model: Optional[dict] = None
    table_semantic_interpretation: Optional[Dict[str, Any]] = None
    chart_understanding: Optional[ChartUnderstandingModel] = None
    table_title: Optional[str] = None
    table_purpose: Optional[str] = None
    table_insights: List[str] = Field(default_factory=list)
    table_geometry: dict = Field(default_factory=dict)
    table_styles: dict = Field(default_factory=dict)
    table_merged_cells: list = Field(default_factory=list)

class HeaderFooterModel(BaseModel):
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    slide_number_text: Optional[str] = None
    date_text: Optional[str] = None
    confidentiality_label: Optional[str] = None
    header_type: Optional[str] = None
    footer_type: Optional[str] = None


class VisualInventoryModel(BaseModel):
    text_box_count: int
    shape_count: int
    arrow_count: int
    connector_count: int
    image_count: int
    table_count: int
    group_count: int
    chart_count: int
    placeholder_count: int
    unknown_count: int
    total_elements: int

    # NEW
    title_count: int = 0
    header_count: int = 0
    footer_count: int = 0
    figure_count: int = 0
    icon_count: int = 0

    slide_type: str | None = None


class RegionModel(BaseModel):
    name: str
    x_start: float = 0
    y_start: float = 0
    x_end: float = 0
    y_end: float = 0
    element_ids: List[str] = Field(default_factory=list)


class LayoutRegionModel(BaseModel):
    name: str
    element_ids: List[str] = Field(default_factory=list)


class LayoutStructureModel(BaseModel):
    layout_type: str = ""
    regions: List[RegionModel] = Field(default_factory=list)


class FlowchartModel(BaseModel):
    is_flowchart: bool = False
    box_count: int = 0
    arrow_count: int = 0
    decision_node_count: int = 0
    start_nodes: List[str] = Field(default_factory=list)
    end_nodes: List[str] = Field(default_factory=list)
    flow_type: Optional[str] = None
    boxes: List[Dict[str, Any]] = Field(default_factory=list)
    arrows: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    relationship_mapping: List[Dict[str, Any]] = Field(default_factory=list)
    reading_order: List[str] = Field(default_factory=list)
    reading_order_labels: List[str] = Field(default_factory=list)
    process_summary: Optional[str] = None

class VisualDesignModel(BaseModel):
    color_scheme: List[str] = Field(default_factory=list)
    shapes: List[str] = Field(default_factory=list)
    connector_types: List[str] = Field(default_factory=list)
    layout_pattern: Optional[str] = None
    spatial_structure: Optional[str] = None
    background_style: Optional[str] = None
    layout_style: Optional[str] = None
    primary_shapes: List[str] = Field(default_factory=list)

class ImageUnderstandingModel(BaseModel):
    scene_description: str = ""
    objects_detected: List[str] = Field(default_factory=list)
    actions_detected: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    semantic_meaning: str = ""
    visual_design: Optional[VisualDesignModel] = None
    image_type: str = ""
    dominant_colors: List[str] = Field(default_factory=list)
    visual_elements: List[str] = Field(default_factory=list)
    llm_recreation_prompt: str = ""
    slide_intent: Optional[str] = None
    visual_regions: List[Dict[str, Any]] = Field(default_factory=list)
    illustration_inventory: List[Dict[str, Any]] = Field(default_factory=list)
    relationship_mapping: List[Dict[str, Any]] = Field(default_factory=list)
    design_hierarchy: Optional[Dict[str, Any]] = None
    reading_order: List[str] = Field(default_factory=list)

class SemanticFlowModel(BaseModel):
    overall_flow: str = ""
    step_by_step_explanation: List[str] = Field(default_factory=list)
    conceptual_layers: List[str] = Field(default_factory=list)
    visual_design_details: List[str] = Field(default_factory=list)
    plain_english_summary: str = ""
    decision_points: List[str] = Field(default_factory=list)
    cause_effect_chain: List[str] = Field(default_factory=list)
    image_generation_prompt: str = ""
    slide_intent: Optional[str] = None
    content_hierarchy: Optional[Dict[str, Any]] = None
    visual_hierarchy: Optional[Dict[str, Any]] = None
    semantic_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    layout_regions: List[Dict[str, Any]] = Field(default_factory=list)
    visual_grouping: List[Dict[str, Any]] = Field(default_factory=list)
    storytelling_structure: Optional[str] = None
    reading_order: List[str] = Field(default_factory=list)

class SlideReconstructionContextModel(BaseModel):
    title: str = ""
    slide_type: str = ""
    purpose: str = ""
    domain: str = ""
    theme: str = ""
    design_style: str = ""
    mood: str = ""
    complexity: str = ""
    category: str = ""
    background_type: str = ""
    primary_color: str = ""
    secondary_color: str = ""
    gradient_direction: str = ""
    texture: str = ""
    patterns: str = ""
    effects: str = ""
    title_typography: str = ""
    body_typography: str = ""
    typography_color_palette: List[str] = Field(default_factory=list)
    layout_type: str = ""
    canvas_ratio: str = "16:9"
    regions: List[str] = Field(default_factory=list)
    reading_order: List[str] = Field(default_factory=list)
    alignment: str = ""
    spacing: str = ""
    primary_focus: str = ""
    secondary_focus: str = ""
    tertiary_elements: str = ""
    attention_flow: str = ""
    visual_elements: List[Dict[str, Any]] = Field(default_factory=list)
    image_reconstructions: List[Dict[str, Any]] = Field(default_factory=list)
    element_relationships: List[str] = Field(default_factory=list)
    reconstruction_prompt: str = ""

class SlideContextModel(BaseModel):
    header_footer: Optional[HeaderFooterModel] = None
    title: Optional[str] = None
    visual_inventory: Optional[VisualInventoryModel] = None
    layout_structure: Optional[LayoutStructureModel] = None
    flowchart: Optional[FlowchartModel] = None
    text_points: List[TextPointModel] = Field(default_factory=list)
    position_mapping: List[PositionMapModel] = Field(default_factory=list)
    relationship_mapping: List[RelationshipModel] = Field(default_factory=list)
    diagram_understanding: Optional[DiagramUnderstandingModel] = None
    outline: str = ""
    image_understanding:Optional[ImageUnderstandingModel]=None
    semantic_flow:Optional[SemanticFlowModel]=None
    exact_text_dump: List[Dict[str, Any]] = Field(default_factory=list)
    table_contexts: List[Dict[str, Any]] = Field(default_factory=list)
    image_depictions: List[str] = Field(default_factory=list)
    slide_structure_summary: Optional[str] = None




class ImageReconstructionModel(BaseModel):
    layout_description: str = ""
    color_palette: List[str] = Field(default_factory=list)
    object_location: List[str] = Field(default_factory=list)
    connector_layout: List[str] = Field(default_factory=list)
    recreation_prompt: str = ""
    object_inventory: List[str] = Field(default_factory=list)
    visual_hierarchy: List[str] = Field(default_factory=list)
    layout_regions: List[str] = Field(default_factory=list)
    design_style: str = ""

class SemanticSlideDescriptionModel(BaseModel):
    semantic_flow: str = ""
    step_by_step_meaning: List[str] = Field(default_factory=list)
    conceptual_layers: List[str] = Field(default_factory=list)
    visual_design_details: List[str] = Field(default_factory=list)
    plain_english_summary: str = ""
    image_generation_prompt:str=""
    visual_inventory_summary: str | None = None
    relationship_summary: str | None = None
    image_depiction_summary: Optional[str]
    slide_archetype: str | None = None
    flowchart_summary: str | None = None

class SlideModel(BaseModel):
    slide_number: int
    title: Optional[str] = None
    background_color: Optional[str] = None
    layout_regions: list = []
    elements: List[DocumentElementModel] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    header_footer: Optional[HeaderFooterModel] = None
    visual_inventory: Optional[VisualInventoryModel] = None
    semantic_slide_description: Optional[SemanticSlideDescriptionModel] = None
    layout_structure: Optional[LayoutStructureModel] = None
    flowchart: Optional[FlowchartModel] = None
    diagram_understanding: Optional[DiagramUnderstandingModel] = None
    image_understanding: Optional[ImageUnderstandingModel] = None
    context: Optional[SlideContextModel] = None
    semantic_flow: Optional[SemanticFlowModel] = None
    table_markdowns: List[str] = Field(default_factory=list)
    slide_summary: Optional[str] = None
    text_points: List[TextPointModel] = Field(default_factory=list)
    position_mapping: List[PositionMapModel] = Field(default_factory=list)
    image_reconstruction: Optional[ImageReconstructionModel] = None
    slide_reconstruction_context: Optional[SlideReconstructionContextModel] = None
    chart_understandings: List[ChartUnderstandingModel] = Field(default_factory=list)
    semantic_regions: List[SemanticRegionModel] = Field(default_factory=list)
    detected_tables: Optional[list] = []

    

class DocumentStructureModel(BaseModel):
    presentation_type: str = "unknown"
    slide_sequence: List[str] = Field(default_factory=list)
    total_sections: int = 0
    section_breaks: List[int] = Field(default_factory=list)
    executive_summary_slides: List[int] = Field(default_factory=list)
    methodology_slides: List[int] = Field(default_factory=list)
    findings_slides: List[int] = Field(default_factory=list)
    recommendation_slides: List[int] = Field(default_factory=list)
    appendix_slides: List[int] = Field(default_factory=list)
    narrative_flow: str = ""
    document_summary: str = ""
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    

class DocumentModel(BaseModel):
    document_name: str
    document_type: str
    total_slides: int
    slides: List[SlideModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    presentation_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Top-level presentation metadata: author, slide dimensions, theme, etc.",
    )
    document_structure: Optional[Dict[str, Any]] = None

