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

from services.semantic_region_detection_service import SemanticRegionDetectionService

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
        self.semantic_region_service = SemanticRegionDetectionService()

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

        print("    [Orchestrator] Step 0: Semantic regions and layout graph...")
        slide_model.semantic_regions = self.semantic_region_service.detect_regions(slide_model)
        slide_model.layout_graph = self.semantic_region_service.build_layout_graph(slide_model.elements, slide_model.semantic_regions)

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

        # 10.5) Visual Object Classification
        print("    [Orchestrator] Step 10.5: Visual Object Classification...")
        from services.visual_object_classifier_service import VisualObjectClassifierService
        visual_classifier = VisualObjectClassifierService()
        visual_classifier.classify_elements(slide_model.elements)

        # 10.6) Chart Detection and Understanding
        print("    [Orchestrator] Step 10.6: Chart Detection and Understanding...")
        from services.chart_detection_service import ChartDetectionService
        from services.chart_understanding_service import ChartUnderstandingService
        from services.chart_reconstruction_service import ChartReconstructionService
        
        chart_detector = ChartDetectionService()
        chart_detector.detect_charts(slide_model.elements)
        
        chart_service = ChartUnderstandingService()
        chart_reconstructor = ChartReconstructionService()
        
        slide_model.chart_understandings = []
        for element in slide_model.elements:
            vclass = element.metadata.get("visual_class", {})
            if isinstance(vclass, dict) and vclass.get("classification") == "chart":
                element.element_type = "chart" # Ensure it's treated as a chart
                chart_info = chart_service.extract_understanding(element)
                element.chart_understanding = chart_info
                slide_model.chart_understandings.append(chart_info)
                element.metadata["chart_reconstruction"] = chart_reconstructor.build_reconstruction_data(chart_info)

        # 11) Table extraction (markdown)
        print("    [Orchestrator] Step 11: Table extraction and semantics...")
        table_markdowns = self.table_agent.run(slide_model)
        
        from services.semantic_table_service import SemanticTableService
        from services.advanced_table_intelligence_service import AdvancedTableIntelligenceService
        table_sem_service = SemanticTableService()
        advanced_table_service = AdvancedTableIntelligenceService()

        for element in slide_model.elements:
            if element.element_type == "table":
                vclass = element.metadata.get("visual_class", {})
                if isinstance(vclass, dict) and vclass.get("classification") != "table":
                    # If classified as something else, skip table analysis
                    continue
                element.table_semantics = table_sem_service.analyze_table_semantics(element)
                element.table_reconstruction = advanced_table_service.analyze_table(element)

        # 11.5) Universal Structural Understanding
        print("    [Orchestrator] Step 11.5: Universal Structural Understanding...")
        from services.structural_understanding_service import UniversalStructuralUnderstandingService
        struct_service = UniversalStructuralUnderstandingService()
        slide_model = struct_service.analyze_slide(slide_model)

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
        from services.semantic_region_detection_service import SemanticRegionDetectionService

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
            # Transfer LLM-derived semantics to SlideModel (Universal Structural Understanding)
            slide_model.business_message = slide_model.semantic_flow.overall_flow
            slide_model.communication_intent = slide_model.semantic_flow.slide_intent
            slide_model.reading_order = slide_model.semantic_flow.reading_order
            
            # HIGH ACCURACY OVERRIDE: If LLM identified a specific archetype, trust it over heuristics
            if slide_model.semantic_flow.slide_archetype:
                from models.document_model import SlideArchetypeModel
                slide_model.slide_archetype = SlideArchetypeModel(
                    slide_archetype=slide_model.semantic_flow.slide_archetype,
                    confidence=0.95  # LLM reasoning is high confidence
                )

            # Map framework-specific data from LLM reasoning
            if slide_model.semantic_flow.capability_map_data:
                from models.document_model import CapabilityMapModel
                slide_model.capability_map = CapabilityMapModel(**slide_model.semantic_flow.capability_map_data)
            
            if slide_model.semantic_flow.governance_data:
                from models.document_model import GovernanceFrameworkModel
                slide_model.governance_framework = GovernanceFrameworkModel(**slide_model.semantic_flow.governance_data)
                
            if slide_model.semantic_flow.process_flow_data:
                from models.document_model import ProcessFlowModel
                slide_model.process_flow = ProcessFlowModel(**slide_model.semantic_flow.process_flow_data)
                
            if slide_model.semantic_flow.dashboard_data:
                from models.document_model import DashboardModel
                slide_model.dashboard = DashboardModel(**slide_model.semantic_flow.dashboard_data)

            # Table Intelligence Refinement
            if slide_model.semantic_flow.table_intelligence:
                for llm_table in slide_model.semantic_flow.table_intelligence:
                    tid = llm_table.get("table_id")
                    for element in slide_model.elements:
                        if element.element_id == tid and element.table_reconstruction:
                            # Update with LLM-derived structural insights (merged cells, etc.)
                            if "merged_cells" in llm_table:
                                element.table_reconstruction.merged_cells = llm_table["merged_cells"]
                            if "nested_headers" in llm_table:
                                element.table_reconstruction.hierarchy = llm_table["nested_headers"]

            if slide_model.semantic_flow.visual_hierarchy:
                from models.document_model import VisualHierarchyModel
                vh = slide_model.semantic_flow.visual_hierarchy
                slide_model.visual_hierarchy = VisualHierarchyModel(
                    primary_focus=[vh.get("primary_focus")] if vh.get("primary_focus") else [],
                    secondary_focus=[vh.get("secondary_focus")] if vh.get("secondary_focus") else [],
                    tertiary_focus=[vh.get("tertiary_focus")] if vh.get("tertiary_focus") else []
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
        
        # Ensure top-level fields are populated if they weren't by semantic_flow
        if not slide_model.business_message:
            slide_model.business_message = recon_context.business_message
        if not slide_model.communication_intent:
            slide_model.communication_intent = recon_context.communication_intent
        if not slide_model.functional_equivalence_requirements:
            slide_model.functional_equivalence_requirements = recon_context.functional_equivalence_requirements
        if not slide_model.reading_order:
            slide_model.reading_order = recon_context.reading_order

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
