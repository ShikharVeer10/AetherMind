"""
Task-specific extraction agents with explicit system prompts.
Each agent owns a single step in the extraction order.
"""

from typing import Optional

from models.document_model import (
    DiagramUnderstandingModel,
    FlowchartModel,
    HeaderFooterModel,
    LayoutStructureModel,
    RelationshipModel,
    SlideContextModel,
    SlideModel,
    TextPointModel,
    VisualInventoryModel,
)
from services.context_builder import ContextBuilder
from services.diagram_understanding_service import DiagramUnderstandingService
from services.flowchart_service import FlowchartService
from services.header_footer_service import HeaderFooterService
from services.layout_analysis_service import LayoutAnalysisService
from services.position_mapping_service import PositionMappingService
from services.relationship_service import RelationshipService
from services.table_service import TableService
from services.text_extraction_service import TextExtractionService
from services.visual_inventory_service import VisualInventoryService


class TextExtractionAgent:
    system_prompt = "Extract verbatim text points without paraphrasing."

    def __init__(self):
        self.service = TextExtractionService()

    def run(self, slide_model: SlideModel) -> list[TextPointModel]:
        return self.service.extract(slide_model.elements)


class HeaderFooterAgent:
    system_prompt = "Extract header, footer, slide number, and date placeholders."

    def __init__(self):
        self.service = HeaderFooterService()

    def run(self, raw_slide) -> HeaderFooterModel:
        return self.service.extract(raw_slide)


class VisualInventoryAgent:
    system_prompt = "Count all visual elements on the slide."

    def __init__(self):
        self.service = VisualInventoryService()

    def run(self, slide_model: SlideModel) -> VisualInventoryModel:
        return self.service.count(slide_model.elements)


class LayoutStructureAgent:
    system_prompt = "Classify layout regions and overall layout type."

    def __init__(self):
        self.service = LayoutAnalysisService()

    def run(
        self, slide_model: SlideModel, flowchart: Optional[FlowchartModel] = None
    ) -> LayoutStructureModel:
        return self.service.analyse(
            slide_model.elements,
            flowchart or FlowchartModel(),
        )


class PositionMappingAgent:
    system_prompt = "Map positions for every element on the slide."

    def __init__(self):
        self.service = PositionMappingService()

    def run(self, slide_model: SlideModel):
        return self.service.build(slide_model.elements)


class RelationshipMappingAgent:
    system_prompt = "Detect spatial and connector relationships between elements."

    def __init__(self):
        self.service = RelationshipService()

    def run(self, slide_model: SlideModel) -> list[RelationshipModel]:
        return self.service.detect(slide_model.elements)


class FlowchartAnalysisAgent:
    system_prompt = "Identify flowcharts and reconstruct box-arrow structure."

    def __init__(self):
        self.service = FlowchartService()

    def run(
        self,
        slide_model: SlideModel,
        relationships: list[RelationshipModel],
    ) -> FlowchartModel:
        return self.service.analyse(slide_model.elements, relationships)


class DiagramUnderstandingAgent:
    system_prompt = "Summarize diagram structure using nodes and relationships."

    def __init__(self):
        self.service = DiagramUnderstandingService()

    def run(
        self,
        slide_model: SlideModel,
        relationships: list[RelationshipModel],
        flowchart: FlowchartModel,
    ) -> DiagramUnderstandingModel:
        return self.service.analyse(slide_model.elements, relationships, flowchart)


class TableExtractionAgent:
    system_prompt = "Extract tables and convert to markdown format."

    def __init__(self):
        self.service = TableService()

    def run(self, slide_model: SlideModel) -> list[str]:
        markdowns = []
        for element in slide_model.elements:
            if element.element_type == "table":
                table_data = element.metadata.get("table_data", [])
                if table_data:
                    md = self.service.to_markdown(table_data)
                    if md:
                        markdowns.append(md)
                        element.table_markdown = md
        return markdowns


class ContextAssemblyAgent:
    system_prompt = "Build a structured context block for the slide."

    def __init__(self):
        self.builder = ContextBuilder()

    def run(
        self,
        title: str | None,
        header_footer: HeaderFooterModel,
        inventory: VisualInventoryModel,
        layout: LayoutStructureModel,
        flowchart: FlowchartModel,
        text_points: list[TextPointModel],
        position_mapping,
        relationships: list[RelationshipModel],
        diagram_understanding: DiagramUnderstandingModel,
    ) -> SlideContextModel:
        return self.builder.build(
            title=title,
            header_footer=header_footer,
            inventory=inventory,
            layout=layout,
            flowchart=flowchart,
            text_points=text_points,
            position_mapping=position_mapping,
            relationships=relationships,
            diagram_understanding=diagram_understanding,
        )
