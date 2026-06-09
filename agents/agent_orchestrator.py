"""
Multi-agent orchestrator that runs extraction tasks in the required order.
Each task is owned by a dedicated agent with an explicit system prompt.
"""

from typing import Optional
from models.document_model import FlowchartModel

from models.document_model import (
    HeaderFooterModel,
    SlideModel,
    VisualInventoryModel,
)

from agents.extraction_agents import (
    ContextAssemblyAgent,
    DiagramUnderstandingAgent,
    FlowchartAnalysisAgent,
    HeaderFooterAgent,
    LayoutStructureAgent,
    PositionMappingAgent,
    RelationshipMappingAgent,
    TextExtractionAgent,
    VisualInventoryAgent,
)
from agents.table_extraction_agent import TableExtractionAgent

class AgentOrchestrator:
    """
    Coordinates multiple extraction services/agents for a single slide.

    Usage:
        orchestrator = AgentOrchestrator(
            summarization_agent=...,
            image_agent=...,
        )
        enriched_slide = await orchestrator.process_slide(slide, raw_slide)
    """

    def __init__(
        self,
        summarization_agent=None,
        image_summarization_agent=None,
        presentation_metadata=None,
    ):
        self.summarization_agent = summarization_agent
        self.image_summarization_agent = image_summarization_agent
        self.presentation_metadata = presentation_metadata or {}
        self.last_slide_title = None

        self.text_agent = TextExtractionAgent()
        self.header_footer_agent = HeaderFooterAgent()
        self.inventory_agent = VisualInventoryAgent()
        self.layout_agent = LayoutStructureAgent()
        self.position_agent = PositionMappingAgent()
        self.relationship_agent = RelationshipMappingAgent()
        self.flowchart_agent = FlowchartAnalysisAgent()
        self.diagram_agent = DiagramUnderstandingAgent()
        self.table_agent = TableExtractionAgent()
        self.context_agent = ContextAssemblyAgent()

    async def process_slide(
        self, slide_model: SlideModel, raw_slide
    ) -> SlideModel:
        """
        Run all extraction phases on a single slide and return the
        enriched SlideModel.

        Parameters:
            slide_model:  The SlideModel already populated with elements
                          by PPTExtractor.
            raw_slide:    The raw python-pptx slide object (needed for
                          header/footer placeholder access).
        """
        if slide_model.title:
            self.last_slide_title = slide_model.title

        # 1) Exact text extraction (verbatim)
        print("    [Orchestrator] Step 1: Text extraction...")
        slide_model.text_points = self.text_agent.run(slide_model)

        # 2) Header/footer extraction
        print("    [Orchestrator] Step 2: Header/footer...")
        header_footer = self.header_footer_agent.run(raw_slide)

        # 3) Visual inventory counts
        print("    [Orchestrator] Step 3: Visual inventory...")
        visual_inventory = self.inventory_agent.run(slide_model)

        # 4) Layout structure identification
        print("    [Orchestrator] Step 4: Layout structure...")
        layout = self.layout_agent.run(slide_model)

        # 5) Position mapping
        print("    [Orchestrator] Step 5: Position mapping...")
        position_mapping = self.position_agent.run(slide_model)

        # 6) Relationship mapping
        print("    [Orchestrator] Step 6: Relationship mapping...")
        relationships = self.relationship_agent.run(slide_model) or []
        slide_model.relationships = relationships

        # 7) Flowchart analysis
        print("    [Orchestrator] Step 7: Flowchart analysis skipped")


        flowchart = FlowchartModel(
            is_flowchart=False,
            box_count=0,
            arrow_count=0,
            decision_node_count=0,
            start_nodes=[],
            end_nodes=[],
            flow_type="none",
            boxes=[],
            arrows=[],
            relationships=[],
            relationship_mapping=[],
            reading_order=[],
            reading_order_labels=[],
            process_summary=None,
        )

       

        # 9) Image understanding and depiction
        print("    [Orchestrator] Step 9: Image summaries...")
        image_summary_text = await self._run_image_summaries(slide_model)

        print("    [Orchestrator] Step 8: Diagram understanding...")
        diagram_understanding= self.diagram_agent.run(
            slide_model,
            relationships,
            flowchart
        )

        # 10) Slide context
        print("    [Orchestrator] Step 10: Slide context...")

        context = self.context_agent.run(
            title=slide_model.title,
            header_footer=header_footer or HeaderFooterModel(),
            inventory=visual_inventory or VisualInventoryModel(),
            layout=layout,
            flowchart=flowchart,
            text_points=slide_model.text_points,
            position_mapping=position_mapping,
            relationships=relationships or [],
            diagram_understanding=diagram_understanding
        )

        # 11) Table extraction (markdown)
        print("    [Orchestrator] Step 11: Table extraction...")
        table_markdowns = self.table_agent.run(slide_model)

        # Final assembly
        print("    [Orchestrator] Final assembly...")
        slide_model.header_footer = header_footer or HeaderFooterModel()
        slide_model.visual_inventory = visual_inventory or VisualInventoryModel()
        slide_model.layout_structure = layout
        slide_model.context = context
        slide_model.table_markdowns = table_markdowns or []
        slide_model.position_mapping = position_mapping
        slide_model.diagram_understanding = diagram_understanding
        slide_model.flowchart = flowchart

        # 12) Semantic flow, image understanding, and reconstruction
        print("    [Orchestrator] Step 12: Semantic services...")
        from services.image_understanding_service import ImageUnderstandingService
        from services.imagereconstruction_service import ImageReconstructionService
        from services.semantic_slide_service import SemanticSlideService
        from services.chart_understanding_service import ChartUnderstandingService
        from services.semantic_region_detection_service import SemanticRegionDetectionService

        # Run Chart Understanding Service
        chart_service = ChartUnderstandingService()
        slide_model.chart_understandings = []
        for element in slide_model.elements:
            if element.element_type == "chart" or (element.element_type == "image" and any(k in (element.metadata.get("image_summary") or "").lower() for k in ("chart", "graph", "dashboard", "kpi"))):
                chart_info = chart_service.analyze_chart_element(element, slide_model)
                element.chart_understanding = chart_info
                slide_model.chart_understandings.append(chart_info)

        img_und_service = ImageUnderstandingService()
        slide_model.image_understanding = img_und_service.analyze_slide(slide_model)

        img_rec_service = ImageReconstructionService()
        slide_model.image_reconstruction = img_rec_service.analyze_slide(slide_model)

        # Run Semantic Region Detection Service
        sem_region_service = SemanticRegionDetectionService()
        slide_model.semantic_regions = sem_region_service.detect_regions(slide_model)

        print("    [Orchestrator] Step 12.1: Slide interpretation (semantic flow)...")
        from agents.slide_interpretation_agent import SlideInterpretationAgent
        from services.semantic_flow_service import SemanticFlowService

        try:
            interpretation_agent = SlideInterpretationAgent()
            slide_model.semantic_flow = await interpretation_agent.interpret_slide(
                slide_model,
                image_summaries=image_summary_text or "",
            )
        except Exception as e:
            print(f"    [Orchestrator] Slide interpretation failed: {e}")
            slide_model.semantic_flow = SemanticFlowService().analyze_slide(
                slide_model,
                image_summaries=image_summary_text or "",
            )

        if slide_model.semantic_flow:
            slide_model.slide_summary = SemanticFlowService().format_structured_output(
                slide_model.semantic_flow
            )

        # 12.5) Slide summary (fallback if semantic flow did not produce structured output)
        print("    [Orchestrator] Step 12.5: Slide summary generation...")
        if not slide_model.slide_summary:
            slide_summary = await self._run_slide_summary(
                slide_model, context.outline, image_summary_text or ""
            )
            if slide_summary:
                slide_model.slide_summary = slide_summary

        sem_slide_service = SemanticSlideService()
        slide_model.semantic_slide_description = sem_slide_service.analyze_slide(slide_model)

        # 13) Slide Reconstruction Context
        print("    [Orchestrator] Step 13: Slide reconstruction context...")

        from services.slide_reconstruction_service import SlideReconstructionService
        recon_service = SlideReconstructionService()    
        recon_context = recon_service.build_context(slide_model,presentation_metadata=self.presentation_metadata)
        slide_model.slide_reconstruction_context = recon_context
        return slide_model

    async def _run_image_summaries(self, slide_model: SlideModel) -> Optional[str]:
        if not self.image_summarization_agent:
            return ""

        # Extract all text from slide to use as context
        text_lines = []
        if getattr(slide_model, "text_points", None):
            for p in slide_model.text_points:
                if getattr(p, "text", None):
                    text_lines.append(p.text)
        
        slide_text = "\n".join(text_lines) if text_lines else None
        slide_title = getattr(slide_model, "title", None) or self.last_slide_title

        summaries = []
        for element in slide_model.elements:
            if element.element_type != "image":
                continue
            image_bytes = element.metadata.get("__image_bytes")
            if not image_bytes:
                continue
            try:
                desc = await self.image_summarization_agent.summarize_image(
                    image_bytes,
                    slide_title=slide_title,
                    slide_text=slide_text,
                )
            except Exception:
                desc = None
            if desc:
                element.metadata["image_summary"] = desc
                summaries.append(desc)

        return "\n\n".join(summaries)


    async def _run_slide_summary(self,slide_model: SlideModel,context_outline: str,image_summaries: str,) -> Optional[str]:
        if not self.summarization_agent:
            return None
        try:
            return await self.summarization_agent.summarize_slide(
                slide_model,
                context_outline=context_outline,
                image_summaries=image_summaries,
            )
        except Exception:
            return None
