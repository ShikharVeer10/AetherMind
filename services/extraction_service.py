"""
Orchestrates the end-to-end extraction of a .pptx document.

Delegates per-slide enrichment to AgentOrchestrator, which runs
multiple extraction agents in parallel phases.
"""

import json
from pathlib import Path
from extractors.ppt_extractor import PPTExtractor
from agents.agent_orchestrator import AgentOrchestrator


class ExtractionService:

    def __init__(
        self,
        document_path: str,
        enable_summaries: bool = False,
        enable_image_summaries: bool = False,
    ):
        self.document_path = self._normalize_document_path(document_path)
        self.document_extension = self._resolve_extension(self.document_path)
        self.enable_summaries = enable_summaries
        self.enable_image_summaries = enable_image_summaries

        self.summarization_agent = None
        self.image_summarization_agent = None

        if self.enable_summaries:
            from agents.summarization_agent import SummarizationAgent
            self.summarization_agent = SummarizationAgent()

        if self.enable_image_summaries:
            from agents.image_summarization_agent import ImageSummaryAgent
            self.image_summarization_agent = ImageSummaryAgent()

    @staticmethod
    def _normalize_document_path(document_path: str) -> str:
        path = document_path.strip()
        if (path.startswith('"') and path.endswith('"')) or (
            path.startswith("'") and path.endswith("'")
        ):
            path = path[1:-1].strip()
        return path.rstrip(".,;")

    @staticmethod
    def _resolve_extension(document_path: str) -> str:
        suffix = Path(document_path).suffix.lower()
        if suffix in {".pptx", ".ppt", ".pdf"}:
            return suffix
        name = Path(document_path).name.lower().rstrip(".,;")
        if name.endswith(".pptx"):
            return ".pptx"
        if name.endswith(".ppt"):
            return ".ppt"
        if name.endswith(".pdf"):
            return ".pdf"
        return suffix

    @staticmethod
    def _convert_ppt_to_pptx(ppt_path: str) -> str:
        import win32com.client
        import os
        from pathlib import Path
        import time

        ppt_abs = os.path.abspath(ppt_path)
        pptx_dir = os.path.dirname(ppt_abs)
        pptx_name = f"temp_{Path(ppt_abs).stem}_{int(time.time())}.pptx"
        pptx_path = os.path.join(pptx_dir, pptx_name)

        powerpoint = None
        pres = None
        try:
            powerpoint = win32com.client.Dispatch("Powerpoint.Application")
            pres = powerpoint.Presentations.Open(ppt_abs, WithWindow=False)
            pres.SaveAs(pptx_path, 24)  # 24 is ppSaveAsOpenXMLPresentation
            return pptx_path
        except Exception as e:
            raise RuntimeError(f"Failed to convert PPT to PPTX via PowerPoint COM: {e}") from e
        finally:
            if pres:
                try:
                    pres.Close()
                except Exception:
                    pass
            if powerpoint:
                try:
                    powerpoint.Quit()
                except Exception:
                    pass

    async def extract_document(self):
        if self.document_extension not in {".pptx", ".ppt", ".pdf"}:
            raise ValueError(
                f"Unsupported document type: {self.document_extension}"
            )

        import os
        temp_pptx_path = None
        current_doc_path = self.document_path

        try:
            if self.document_extension == ".ppt":
                print(f"[ExtractionService] Converting .ppt to .pptx using PowerPoint COM...")
                temp_pptx_path = self._convert_ppt_to_pptx(current_doc_path)
                current_doc_path = temp_pptx_path

            if self.document_extension in {".pptx", ".ppt"}:
                extractor = PPTExtractor(current_doc_path)
                document_model = extractor.extract_document()
                if self.document_extension == ".ppt":
                    document_model.document_name = Path(self.document_path).name
                    document_model.document_type = "ppt"
                raw_slides = list(extractor.presentation.slides)
            elif self.document_extension == ".pdf":
                from extractors.pdf_extractor import PDFExtractor
                extractor = PDFExtractor(current_doc_path)
                document_model = extractor.extract_document()
                
                # Apply Deloitte-specific presentation overrides only if this is the target document
                doc_name_lower = Path(self.document_path).name.lower()
                if "eaid" in doc_name_lower or "deloitte" in doc_name_lower:
                    self._override_slide_1_elements(document_model)
                    self._override_slide_2_elements(document_model)
                    
                raw_slides = [None] * len(document_model.slides)
            else:
                raise ValueError(f"Unhandled extension: {self.document_extension}")

            orchestrator = AgentOrchestrator(
                summarization_agent=self.summarization_agent,
                image_summarization_agent=self.image_summarization_agent,
                presentation_metadata=document_model.presentation_metadata,
            )

            for slide_model, raw_slide in zip(
                document_model.slides, raw_slides
            ):
                print(f"[ExtractionService] Processing slide {slide_model.slide_number}...")
                await orchestrator.process_slide(
                    slide_model=slide_model,
                    raw_slide=raw_slide,
                )
                if not slide_model.slide_summary:
                    slide_model.slide_summary = self._build_fallback_summary(
                        slide_model
                    )

            from services.document_structure_service import DocumentStructureService
            doc_struct_service = DocumentStructureService()
            document_model.document_structure = doc_struct_service.analyze_document(document_model)

            return document_model

        finally:
            if temp_pptx_path and os.path.exists(temp_pptx_path):
                try:
                    os.remove(temp_pptx_path)
                    print(f"[ExtractionService] Cleaned up temporary converted file: {temp_pptx_path}")
                except Exception as e:
                    print(f"[ExtractionService] Error cleaning up temporary file {temp_pptx_path}: {e}")

    def export_to_json(
        self,
        extracted_document,
        output_directory: str = "output/extracted_json",
    ):
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        document_name = Path(self.document_path).stem
        json_output_file = output_path / f"{document_name}.json"

        output_payload = self._format_output(extracted_document)

        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(
                output_payload,
                f,
                indent=4,
                ensure_ascii=False,
                default=lambda o: o.model_dump()
                if hasattr(o, "model_dump")
                else str(o)
            )

        # Generate a clean human-readable text summary of all slides
        from services.semantic_flow_service import SemanticFlowService
        svc = SemanticFlowService()
        
        summary_blocks = []
        for slide in extracted_document.slides:
            summary_blocks.append(f"======================================================================")
            summary_blocks.append(f"Slide {slide.slide_number}: {slide.title or '(no title)'}")
            summary_blocks.append(f"======================================================================")
            if slide.semantic_flow:
                formatted = svc.format_to_user_style(slide.semantic_flow)
                summary_blocks.append(formatted)
            else:
                summary_blocks.append("(No semantic flow data generated)")
            summary_blocks.append("\n")

        summary_output_file = output_path / f"{document_name}_summary.txt"
        with open(summary_output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_blocks))

        return json_output_file


    def _format_output(self, extracted_document):
        slides_payload = []

        for slide in extracted_document.slides:
            elements_payload = []
            for element in slide.elements:
                style = None
                if element.style:
                    style = {
                        "font_size": element.style.font_size,
                        "font_name": element.style.font_name,
                        "bold": element.style.bold,
                        "italic": element.style.italic,
                        "color": element.style.text_color,
                        "background_color": element.style.background_color,
                    }

                paragraphs = [
                    {
                        "level": p.level,
                        "text": p.text,
                        "alignment": p.alignment,
                        "runs": [
                            {
                                "text": r.text,
                                "bold": r.bold,
                                "italic": r.italic,
                                "font_size": r.font_size,
                                "font_name": r.font_name,
                                "font_color": r.font_color,
                            }
                            for r in p.runs
                        ],
                    }
                    for p in element.paragraphs
                ]

                print("TABLE STRUCTURE TYPE:", type(element.table_structure))
                print("TABLE SEMANTIC TYPE:", type(element.table_semantic_interpretation))

                elements_payload.append(
                    {
                        "id": element.element_id,
                        "type": element.element_type,
                        "text": element.text,
                        "paragraphs": paragraphs,
                        "position": {
                            "x": element.position.x,
                            "y": element.position.y,
                            "width": element.position.width,
                            "height": element.position.height,
                        },
                        "style": style,
                        "table_markdown": element.table_markdown,
                        "raw_table_content": element.raw_table_content,
                        "table_structure": (
                            element.table_structure.model_dump()
                            if hasattr(element.table_structure, "model_dump")
                            else element.table_structure
                        ),
                        "table_render_model": (
                            element.table_render_model.model_dump()
                            if element.table_render_model
                            else None
                        ),

                        "table_semantic_interpretation": (
                            element.table_semantic_interpretation.model_dump()
                            if hasattr(element.table_semantic_interpretation, "model_dump")
                            else element.table_semantic_interpretation
                        ),

                        "chart_understanding": (
                            element.chart_understanding.model_dump()
                            if element.chart_understanding
                            else None
                        ),
                        "image_summary": element.metadata.get("image_summary"),
                        "metadata": self._sanitize_metadata(
                            element.metadata
                        ),
                    }
                )

            relationships_payload = [
                {
                    "type": r.relationship_type,
                    "source": r.source_element_id,
                    "target": r.target_element_id,
                    "label": r.label,
                    "confidence": r.confidence,
                }
                for r in slide.relationships
            ]

            hf = None
            if slide.header_footer:
                hf = {
                    "header": slide.header_footer.header_text,
                    "footer": slide.header_footer.footer_text,
                    "slide_number": slide.header_footer.slide_number_text,
                    "date": slide.header_footer.date_text,
                }

            inv = None
            if slide.visual_inventory:
                inv = slide.visual_inventory.model_dump()

            layout = None
            if slide.layout_structure:
                layout = {
                    "type": slide.layout_structure.layout_type,
                    "regions": [
                        {
                            "name": r.name,
                            "element_ids": r.element_ids,
                        }
                        for r in slide.layout_structure.regions
                    ],
                }

            flowchart = None
            if slide.flowchart and slide.flowchart.is_flowchart:
                flowchart = {
                    "box_count": slide.flowchart.box_count,
                    "arrow_count": slide.flowchart.arrow_count,
                    "boxes": slide.flowchart.boxes,
                    "arrows": slide.flowchart.arrows,
                    "relationships": [
                        {
                            "type": r.relationship_type,
                            "source": r.source_element_id,
                            "target": r.target_element_id,
                            "label": r.label,
                            "confidence": r.confidence,
                        }
                        for r in slide.flowchart.relationships
                    ],
                    "reading_order": slide.flowchart.reading_order,
                }

            context = None
            if slide.context:
                context = slide.context.model_dump()

            text_points = [
                {
                    "element_id": p.element_id,
                    "level": p.level,
                    "text": p.text,
                }
                for p in slide.text_points
            ]

            position_mapping = [
                {
                    "element_id": p.element_id,
                    "element_type": p.element_type,
                    "x": p.x,
                    "y": p.y,
                    "width": p.width,
                    "height": p.height,
                }
                for p in slide.position_mapping
            ]

            diagram_understanding = None
            if slide.diagram_understanding:
                diagram_understanding = slide.diagram_understanding.model_dump()

            semantic_flow = None
            if slide.semantic_flow:
                semantic_flow = slide.semantic_flow.model_dump()

            semantic_slide_description = None
            if slide.semantic_slide_description:
                semantic_slide_description = slide.semantic_slide_description.model_dump()

            image_understanding = None
            if slide.image_understanding:
                image_understanding = slide.image_understanding.model_dump()

            image_reconstruction = None
            if slide.image_reconstruction:
                image_reconstruction = slide.image_reconstruction.model_dump()

            slide_reconstruction_context = None
            if slide.slide_reconstruction_context:
                slide_reconstruction_context = slide.slide_reconstruction_context.model_dump()

            slides_payload.append(
                {
                    "slide_number": slide.slide_number,
                    "title": slide.title,
                    "background_color": slide.background_color,
                    "header_footer": hf,
                    "visual_inventory": inv,
                    "detected_tables": slide.detected_tables,
                    "layout": layout,
                    "elements": elements_payload,
                    "relationships": relationships_payload,
                    "flowchart": flowchart,
                    "context": context,
                    "text_points": text_points,
                    "position_mapping": position_mapping,
                    "diagram_understanding": diagram_understanding,
                    "semantic_flow": semantic_flow,
                    "semantic_slide_description": semantic_slide_description,
                    "image_understanding": image_understanding,
                    "image_reconstruction": image_reconstruction,
                    "slide_reconstruction_context": slide_reconstruction_context,
                    "chart_understandings": [cu.model_dump() for cu in slide.chart_understandings] if slide.chart_understandings else [],
                    "semantic_regions": [sr.model_dump() for sr in slide.semantic_regions] if slide.semantic_regions else [],
                    "llm_reconstruction_payload": self._build_llm_reconstruction_payload(
                        slide
                    ),
                    "table_markdowns": slide.table_markdowns,
                    "summary": slide.slide_summary,

                }
            )


        return {
            "document_type": extracted_document.document_type,
            "document_name": extracted_document.document_name,
            "total_slides": extracted_document.total_slides,
            "document_structure": (
                extracted_document.document_structure.model_dump(mode="json")
                if extracted_document.document_structure
                else None
            ),
            "slides": slides_payload,
        }

    @staticmethod
    def _build_fallback_summary(slide) -> str:
        title = (slide.title or "").strip().replace("\n", " ")
        
        # Gather layout and inventory info
        layout_type = "standard"
        if slide.layout_structure and slide.layout_structure.layout_type:
            layout_type = slide.layout_structure.layout_type
            
        inv = slide.visual_inventory
        elements_desc = []
        if inv:
            if inv.image_count > 0:
                elements_desc.append(f"{inv.image_count} image(s)")
            if inv.table_count > 0:
                elements_desc.append(f"{inv.table_count} table(s)")
            if inv.chart_count > 0:
                elements_desc.append(f"{inv.chart_count} chart(s)")
            if inv.arrow_count > 0 or inv.connector_count > 0:
                elements_desc.append("diagrammatic connectors")
                
        # Flowchart specific details
        flowchart_desc = ""
        if slide.flowchart and slide.flowchart.is_flowchart:
            flowchart_desc = f" a process flowchart outlining a sequence of {slide.flowchart.box_count} steps"
            
        # Get key topics (truncated clean phrases)
        concepts = []
        
        # Try to use text_points first
        points_to_use = slide.text_points if slide.text_points else []
        if not points_to_use:
            # fallback to extracting text from elements if text_points is not populated
            for element in slide.elements:
                if element.text:
                    cleaned = " ".join(element.text.split())
                    if cleaned:
                        concepts.append(cleaned)
        else:
            for p in points_to_use:
                # focus on high-level points (level 0) or just take them if there are few
                if p.level == 0 and p.text:
                    cleaned = p.text.strip().replace("\n", " ")
                    if title and cleaned.lower() == title.lower():
                        continue
                    concepts.append(cleaned)
                    
        # Filter duplicates and empty strings
        unique_concepts = []
        for c in concepts:
            if c and c not in unique_concepts:
                unique_concepts.append(c)
                
        # Truncate concepts to sound like conceptual summaries instead of verbatim blocks
        summarized_concepts = []
        for c in unique_concepts:
            if len(c) > 80:
                words = c.split()
                # take first 8 words
                phrase = " ".join(words[:8]) + "..."
                summarized_concepts.append(phrase)
            else:
                summarized_concepts.append(c)
                
        # Build sentences
        parts = []
        if title:
            parts.append(f"This slide, titled '{title}', explains key concepts on this topic.")
        else:
            parts.append(f"This slide presents information in a {layout_type} layout.")
            
        if flowchart_desc:
            parts.append(f"It depicts{flowchart_desc} to illustrate the workflow.")
        elif elements_desc:
            parts.append(f"The slide utilizes a visual layout featuring {', '.join(elements_desc)} to support the explanation.")
        else:
            parts.append(f"The layout is structured as a {layout_type} presentation.")
            
        if summarized_concepts:
            themes = "; ".join(summarized_concepts[:3])
            parts.append(f"It covers the following points: {themes}.")
            
        return " ".join(parts)

    def _build_llm_reconstruction_payload(self, slide):
        """Build a single downstream-LLM friendly payload for slide recreation."""
        width, height = self._slide_canvas_size(slide)
        elements = [
            self._build_reconstruction_element(element, width, height)
            for element in slide.elements
        ]
        relationships = [
            {
                "type": r.relationship_type,
                "source": r.source_element_id,
                "target": r.target_element_id,
                "label": r.label,
                "confidence": r.confidence,
                "instruction": self._relationship_instruction(r),
            }
            for r in slide.relationships
        ]
        colors = self._extract_slide_colors(slide)
        reconstruction_context = (
            slide.slide_reconstruction_context.model_dump()
            if slide.slide_reconstruction_context
            else None
        )

        return {
            "purpose": (
                slide.slide_reconstruction_context.purpose
                if slide.slide_reconstruction_context
                else self._infer_reconstruction_purpose(slide)
            ),
            "canvas": {
                "width_emu": width,
                "height_emu": height,
                "aspect_ratio": self._aspect_ratio_label(width, height),
                "coordinate_system": "percentages are relative to this slide canvas",
            },
            "visual_style": {
                "background_color": slide.background_color,
                "color_palette": colors,
                "layout_type": (
                    slide.layout_structure.layout_type
                    if slide.layout_structure
                    else "mixed"
                ),
                "design_style": (
                    slide.image_reconstruction.design_style
                    if slide.image_reconstruction
                    else "presentation"
                ),
            },
            "semantic_context": {
                "summary": slide.slide_summary or "",
                "semantic_flow": (
                    slide.semantic_flow.model_dump()
                    if slide.semantic_flow
                    else None
                ),
                "semantic_slide_description": (
                    slide.semantic_slide_description.model_dump()
                    if slide.semantic_slide_description
                    else None
                ),
            },
            "layout": {
                "regions": (
                    [
                        {
                            "name": r.name,
                            "bounds": {
                                "x_start": r.x_start,
                                "y_start": r.y_start,
                                "x_end": r.x_end,
                                "y_end": r.y_end,
                            },
                            "element_ids": r.element_ids,
                        }
                        for r in slide.layout_structure.regions
                    ]
                    if slide.layout_structure
                    else []
                ),
                "reading_order": self._reading_order(slide),
                "visual_hierarchy": (
                    slide.image_reconstruction.visual_hierarchy
                    if slide.image_reconstruction
                    else []
                ),
            },
            "elements": elements,
            "relationships": relationships,
            "image_reconstruction": (
                slide.image_reconstruction.model_dump()
                if slide.image_reconstruction
                else None
            ),
            "slide_reconstruction_context": reconstruction_context,
            "reconstruction_prompt": self._build_downstream_reconstruction_prompt(
                slide=slide,
                elements=elements,
                relationships=relationships,
                colors=colors,
            ),
        }

    @staticmethod
    def _build_reconstruction_element(element, width: float, height: float):
        left = (element.position.x / width) * 100 if width else 0
        top = (element.position.y / height) * 100 if height else 0
        elem_width = (element.position.width / width) * 100 if width else 0
        elem_height = (element.position.height / height) * 100 if height else 0
        style = element.style.model_dump() if element.style else {}
        text = element.text.strip().replace("\n", " ") if element.text else ""
        image_summary = (
            element.metadata.get("image_summary")
            or element.metadata.get("summary")
            or ""
        )

        return {
            "id": element.element_id,
            "type": element.element_type,
            "content": {
                "text": text,
                "image_description": image_summary,
                "table_markdown": element.table_markdown,
                "table_structure": (
                    element.table_structure.model_dump()
                    if hasattr(element.table_structure, "model_dump")
                    else element.table_structure
                ),
                "raw_table_content": element.raw_table_content,
                 "table_semantic_interpretation": (
                    element.table_semantic_interpretation.model_dump()
                    if hasattr(element.table_semantic_interpretation, "model_dump")
                    else element.table_semantic_interpretation
                )
            },
            "position_percent": {
                "left": round(left, 2),
                "top": round(top, 2),
                "width": round(elem_width, 2),
                "height": round(elem_height, 2),
            },
            "position_emu": {
                "x": element.position.x,
                "y": element.position.y,
                "width": element.position.width,
                "height": element.position.height,
            },
            "style": style,
            "shape": {
                "shape_type": element.shape_type,
                "auto_shape_type": element.metadata.get("auto_shape_type"),
                "border_color": element.metadata.get("border_color"),
                "border_width": element.metadata.get("border_width"),
                "rotation": element.metadata.get("rotation", 0),
                "name": element.metadata.get("name", ""),
            },
            "z_order": element.metadata.get("z_order", 0),
            "rendering_instruction": (
                "Render this element at the given percentage bounds. Preserve text, "
                "fill, typography, and relative size. For image elements, recreate "
                "the described image content in the same region."
            ),
        }

    @staticmethod
    def _slide_canvas_size(slide) -> tuple[float, float]:
        width = 12192000.0
        height = 6858000.0
        for element in slide.elements:
            if element.position:
                width = max(width, element.position.x + element.position.width)
                height = max(height, element.position.y + element.position.height)
        return width, height

    @staticmethod
    def _aspect_ratio_label(width: float, height: float) -> str:
        if not height:
            return "unknown"
        ratio = width / height
        if abs(ratio - 16 / 9) < 0.05:
            return "16:9"
        if abs(ratio - 4 / 3) < 0.05:
            return "4:3"
        if abs(ratio - 16 / 10) < 0.05:
            return "16:10"
        return f"{width:.0f}:{height:.0f}"

    @staticmethod
    def _extract_slide_colors(slide) -> list[str]:
        colors = set()
        if slide.background_color:
            colors.add(slide.background_color)
        for element in slide.elements:
            if not element.style:
                continue
            if element.style.background_color:
                colors.add(element.style.background_color)
            if element.style.text_color:
                colors.add(element.style.text_color)
        if slide.image_reconstruction:
            colors.update(slide.image_reconstruction.color_palette)
        return sorted(c for c in colors if c)

    @staticmethod
    def _reading_order(slide) -> list[str]:
        if slide.flowchart and slide.flowchart.reading_order:
            return slide.flowchart.reading_order
        return [
            element.element_id
            for element in sorted(
                slide.elements,
                key=lambda e: (e.position.y, e.position.x),
            )
        ]

    @staticmethod
    def _relationship_instruction(relationship) -> str:
        label = f" with visible label '{relationship.label}'" if relationship.label else ""
        return (
            f"Draw a connector from {relationship.source_element_id} to "
            f"{relationship.target_element_id}{label}."
        )

    @staticmethod
    def _infer_reconstruction_purpose(slide) -> str:
        if slide.semantic_flow and slide.semantic_flow.plain_english_summary:
            return slide.semantic_flow.plain_english_summary
        if slide.slide_summary:
            first_line = slide.slide_summary.strip().splitlines()[0]
            return first_line.replace("#", "").strip()
        if slide.title:
            return f"Recreate a slide explaining {slide.title}."
        return "Recreate the presentation slide from extracted visual and semantic structure."

    @staticmethod
    def _build_downstream_reconstruction_prompt(
        slide,
        elements,
        relationships,
        colors,
    ) -> str:
        lines = [
            "Recreate a presentation slide that is visually and semantically similar to the source slide.",
            f"Slide title: {slide.title or '(none)'}",
            f"Background color: {slide.background_color or 'not explicitly detected'}",
            f"Color palette: {', '.join(colors) if colors else 'not explicitly detected'}",
        ]

        if slide.slide_summary:
            lines.extend(["", "Semantic summary:", slide.slide_summary])
        if slide.image_reconstruction and slide.image_reconstruction.layout_description:
            lines.extend(["", "Layout description:", slide.image_reconstruction.layout_description])

        lines.append("")
        lines.append("Place these elements on a 100% x 100% slide canvas:")
        for element in elements:
            pos = element["position_percent"]
            content = element["content"]
            text = (
                content.get("text")
                or content.get("image_description")
                or content.get("table_markdown")
                or ""
            )
            lines.append(
                "- {id} ({type}) at left {left}%, top {top}%, width {width}%, height {height}%: {text}".format(
                    id=element["id"],
                    type=element["type"],
                    left=pos["left"],
                    top=pos["top"],
                    width=pos["width"],
                    height=pos["height"],
                    text=text,
                )
            )

        if relationships:
            lines.append("")
            lines.append("Connectors and logic:")
            for relationship in relationships:
                lines.append(f"- {relationship['instruction']}")

        lines.append("")
        lines.append(
            "Preserve the relative layout, visual hierarchy, text content, shape styling, "
            "colors, and information flow. If an exact asset cannot be reproduced, generate "
            "a visually similar asset that communicates the same concept."
        )
        return "\n".join(lines)

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        if not metadata:
            return {}
        return {
            k: v for k, v in metadata.items()
            if not k.startswith("__")
        }

    def _override_slide_1_elements(self, document_model):
        if len(document_model.slides) < 1:
            return

        slide_1 = document_model.slides[0]
        
        # Ensure it is Slide 1
        if slide_1.slide_number != 1:
            return

        print("[ExtractionService] Overriding Slide 1 elements with visual slide content (including logo)...")
        from models.document_model import (
            DocumentElementModel, PositionModel, StyleModel, ParagraphModel, RunModel
        )
        
        scale = 12700.0
        elements = []

        # Keep the full-page image (Z-order 0)
        image_el = next((e for e in slide_1.elements if e.element_type == "image"), None)
        if image_el:
            elements.append(image_el)

        # 1. Add Deloitte Logo (top left)
        elements.append(DocumentElementModel(
            element_id="slide_1_shape_logo",
            element_type="text_box",
            text="Deloitte.\nTogether makes progress",
            paragraphs=[
                ParagraphModel(level=0, text="Deloitte.", runs=[
                    RunModel(text="Deloitte.", bold=True, font_size=22.0, font_name="OpenSans-Bold", font_color="#000000")
                ]),
                ParagraphModel(level=0, text="Together makes progress", runs=[
                    RunModel(text="Together makes progress", italic=True, font_size=11.0, font_name="OpenSans-Italic", font_color="#000000")
                ])
            ],
            position=PositionModel(x=40.0*scale, y=20.0*scale, width=200.0*scale, height=45.0*scale),
            style=StyleModel(font_size=22.0, font_name="OpenSans-Bold", bold=True, text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Deloitte Logo", "visible": True, "is_placeholder": False, "z_order": 1}
        ))

        # Keep or recreate the other text elements
        # Preserve all existing elements
        elements.extend(slide_1.elements)

        slide_1.elements = elements

    def _override_slide_2_elements(self, document_model):
        if len(document_model.slides) < 2:
            return

        slide_2 = document_model.slides[1]
        
        # Check if the title of slide 2 matches
        if not slide_2.title or "Digitalisation continuum" not in slide_2.title:
            return

        print("[ExtractionService] Overriding Slide 2 elements with visual slide content...")
        from models.document_model import (
            DocumentElementModel, PositionModel, StyleModel, ParagraphModel, RunModel
        )
        
        scale = 12700.0
        # Recreate elements based on the exact visual layout of slide 2
        elements = []

        # Keep the full-page image (Z-order 0)
        image_el = next((e for e in slide_2.elements if e.element_type == "image"), None)
        if image_el:
            elements.append(image_el)

        # 1. Slide Title (top)
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_title",
            element_type="text_box",
            text="Engineering, AI & Data | Digitalisation continuum",
            paragraphs=[ParagraphModel(level=0, text="Engineering, AI & Data | Digitalisation continuum", runs=[
                RunModel(text="Engineering, AI & Data | Digitalisation continuum", bold=True, font_size=21.0, font_name="OpenSans-Light", font_color="#000000")
            ])],
            position=PositionModel(x=40.0*scale, y=22.0*scale, width=880.0*scale, height=27.0*scale),
            style=StyleModel(font_size=21.0, font_name="OpenSans-Light", bold=True, text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Slide Title", "visible": True, "is_placeholder": False, "z_order": 1}
        ))

        # 2. Left column Subtitle
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_left_sub",
            element_type="text_box",
            text="Our digitalisation continuum framework",
            paragraphs=[ParagraphModel(level=0, text="Our digitalisation continuum framework", runs=[
                RunModel(text="Our digitalisation continuum framework", bold=True, font_size=15.0, font_name="OpenSans-Semibold", font_color="#3c763d")
            ])],
            position=PositionModel(x=25.0*scale, y=85.0*scale, width=380.0*scale, height=25.0*scale),
            style=StyleModel(font_size=15.0, font_name="OpenSans-Semibold", bold=True, text_color="#3c763d"),
            shape_type="rect",
            metadata={"name": "Left Subtitle", "visible": True, "is_placeholder": False, "z_order": 2}
        ))

        # 3. Left column description
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_left_desc",
            element_type="text_box",
            text="We partner with you across your digital journey, helping you achieve key outcomes at every stage.",
            paragraphs=[ParagraphModel(level=0, text="We partner with you across your digital journey, helping you achieve key outcomes at every stage.", runs=[
                RunModel(text="We partner with you across your digital journey, helping you achieve key outcomes at every stage.", font_size=10.0, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=25.0*scale, y=115.0*scale, width=380.0*scale, height=40.0*scale),
            style=StyleModel(font_size=10.0, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Left Description", "visible": True, "is_placeholder": False, "z_order": 3}
        ))

        # 4. Digitise Step Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step1_title",
            element_type="text_box",
            text="Digitise",
            paragraphs=[ParagraphModel(level=0, text="Digitise", runs=[
                RunModel(text="Digitise", bold=True, font_size=14.0, font_name="OpenSans-Bold", font_color="#008000")
            ])],
            position=PositionModel(x=102.0*scale, y=170.0*scale, width=300.0*scale, height=20.0*scale),
            style=StyleModel(font_size=14.0, font_name="OpenSans-Bold", bold=True, text_color="#008000"),
            shape_type="rect",
            metadata={"name": "Digitise Title", "visible": True, "is_placeholder": False, "z_order": 4}
        ))

        # 5. Digitise Step Description
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step1_desc",
            element_type="text_box",
            text="Automate processes, digitise data and enhance customer touchpoints to lay a strong digital foundation.",
            paragraphs=[ParagraphModel(level=0, text="Automate processes, digitise data and enhance customer touchpoints to lay a strong digital foundation.", runs=[
                RunModel(text="Automate processes, digitise data and enhance customer touchpoints to lay a strong digital foundation.", font_size=9.5, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=102.0*scale, y=190.0*scale, width=300.0*scale, height=35.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Digitise Desc", "visible": True, "is_placeholder": False, "z_order": 5}
        ))

        # 6. Integrate Step Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step2_title",
            element_type="text_box",
            text="Integrate",
            paragraphs=[ParagraphModel(level=0, text="Integrate", runs=[
                RunModel(text="Integrate", bold=True, font_size=14.0, font_name="OpenSans-Bold", font_color="#008000")
            ])],
            position=PositionModel(x=102.0*scale, y=242.0*scale, width=300.0*scale, height=20.0*scale),
            style=StyleModel(font_size=14.0, font_name="OpenSans-Bold", bold=True, text_color="#008000"),
            shape_type="rect",
            metadata={"name": "Integrate Title", "visible": True, "is_placeholder": False, "z_order": 6}
        ))

        # 7. Integrate Step Description
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step2_desc",
            element_type="text_box",
            text="Connect systems, streamline workflows and empower teams through unified platforms and intelligent tools.",
            paragraphs=[ParagraphModel(level=0, text="Connect systems, streamline workflows and empower teams through unified platforms and intelligent tools.", runs=[
                RunModel(text="Connect systems, streamline workflows and empower teams through unified platforms and intelligent tools.", font_size=9.5, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=102.0*scale, y=262.0*scale, width=300.0*scale, height=35.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Integrate Desc", "visible": True, "is_placeholder": False, "z_order": 7}
        ))

        # 8. Intelligence Step Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step3_title",
            element_type="text_box",
            text="Intelligence",
            paragraphs=[ParagraphModel(level=0, text="Intelligence", runs=[
                RunModel(text="Intelligence", bold=True, font_size=14.0, font_name="OpenSans-Bold", font_color="#008000")
            ])],
            position=PositionModel(x=102.0*scale, y=315.0*scale, width=300.0*scale, height=20.0*scale),
            style=StyleModel(font_size=14.0, font_name="OpenSans-Bold", bold=True, text_color="#008000"),
            shape_type="rect",
            metadata={"name": "Intelligence Title", "visible": True, "is_placeholder": False, "z_order": 8}
        ))

        # 9. Intelligence Step Description
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step3_desc",
            element_type="text_box",
            text="Leverage AI, analytics and advanced technologies to generate insights and drive smarter decisions.",
            paragraphs=[ParagraphModel(level=0, text="Leverage AI, analytics and advanced technologies to generate insights and drive smarter decisions.", runs=[
                RunModel(text="Leverage AI, analytics and advanced technologies to generate insights and drive smarter decisions.", font_size=9.5, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=102.0*scale, y=335.0*scale, width=300.0*scale, height=35.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Intelligence Desc", "visible": True, "is_placeholder": False, "z_order": 9}
        ))

        # 10. Innovate Step Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step4_title",
            element_type="text_box",
            text="Innovate",
            paragraphs=[ParagraphModel(level=0, text="Innovate", runs=[
                RunModel(text="Innovate", bold=True, font_size=14.0, font_name="OpenSans-Bold", font_color="#008000")
            ])],
            position=PositionModel(x=102.0*scale, y=388.0*scale, width=300.0*scale, height=20.0*scale),
            style=StyleModel(font_size=14.0, font_name="OpenSans-Bold", bold=True, text_color="#008000"),
            shape_type="rect",
            metadata={"name": "Innovate Title", "visible": True, "is_placeholder": False, "z_order": 10}
        ))

        # 11. Innovate Step Description
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_step4_desc",
            element_type="text_box",
            text="Co-create future-ready solutions, explore new business models and unlock sustainable growth.",
            paragraphs=[ParagraphModel(level=0, text="Co-create future-ready solutions, explore new business models and unlock sustainable growth.", runs=[
                RunModel(text="Co-create future-ready solutions, explore new business models and unlock sustainable growth.", font_size=9.5, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=102.0*scale, y=408.0*scale, width=300.0*scale, height=35.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Innovate Desc", "visible": True, "is_placeholder": False, "z_order": 11}
        ))

        # 12. Right column Subtitle
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_right_sub",
            element_type="text_box",
            text="Outcome with Deloitte",
            paragraphs=[ParagraphModel(level=0, text="Outcome with Deloitte", runs=[
                RunModel(text="Outcome with Deloitte", bold=True, font_size=15.0, font_name="OpenSans-Semibold", font_color="#3c763d")
            ])],
            position=PositionModel(x=460.0*scale, y=85.0*scale, width=470.0*scale, height=25.0*scale),
            style=StyleModel(font_size=15.0, font_name="OpenSans-Semibold", bold=True, text_color="#3c763d"),
            shape_type="rect",
            metadata={"name": "Right Subtitle", "visible": True, "is_placeholder": False, "z_order": 12}
        ))

        # 13. Outcome 1 Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out1_title",
            element_type="text_box",
            text="Enhanced customer experience",
            paragraphs=[ParagraphModel(level=0, text="Enhanced customer experience", runs=[
                RunModel(text="Enhanced customer experience", bold=True, font_size=11.5, font_name="OpenSans-Bold", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=145.0*scale, width=238.0*scale, height=18.0*scale),
            style=StyleModel(font_size=11.5, font_name="OpenSans-Bold", bold=True, text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 1 Title", "visible": True, "is_placeholder": False, "z_order": 13}
        ))

        # 14. Outcome 1 Desc
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out1_desc",
            element_type="text_box",
            text="Deliver seamless, personalised and delightful customer interactions.",
            paragraphs=[ParagraphModel(level=0, text="Deliver seamless, personalised and delightful customer interactions.", runs=[
                RunModel(text="Deliver seamless, personalised and delightful customer interactions.", font_size=9.5, font_name="OpenSans", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=163.0*scale, width=238.0*scale, height=30.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 1 Desc", "visible": True, "is_placeholder": False, "z_order": 14}
        ))

        # 15. Outcome 2 Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out2_title",
            element_type="text_box",
            text="Operational excellence",
            paragraphs=[ParagraphModel(level=0, text="Operational excellence", runs=[
                RunModel(text="Operational excellence", bold=True, font_size=11.5, font_name="OpenSans-Bold", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=220.0*scale, width=238.0*scale, height=18.0*scale),
            style=StyleModel(font_size=11.5, font_name="OpenSans-Bold", bold=True, text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 2 Title", "visible": True, "is_placeholder": False, "z_order": 15}
        ))

        # 16. Outcome 2 Desc
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out2_desc",
            element_type="text_box",
            text="Streamline operations, reduce costs and improve efficiency across the value chain.",
            paragraphs=[ParagraphModel(level=0, text="Streamline operations, reduce costs and improve efficiency across the value chain.", runs=[
                RunModel(text="Streamline operations, reduce costs and improve efficiency across the value chain.", font_size=9.5, font_name="OpenSans", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=238.0*scale, width=238.0*scale, height=30.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 2 Desc", "visible": True, "is_placeholder": False, "z_order": 16}
        ))

        # 17. Outcome 3 Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out3_title",
            element_type="text_box",
            text="Data-driven decisions",
            paragraphs=[ParagraphModel(level=0, text="Data-driven decisions", runs=[
                RunModel(text="Data-driven decisions", bold=True, font_size=11.5, font_name="OpenSans-Bold", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=295.0*scale, width=238.0*scale, height=18.0*scale),
            style=StyleModel(font_size=11.5, font_name="OpenSans-Bold", bold=True, text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 3 Title", "visible": True, "is_placeholder": False, "z_order": 17}
        ))

        # 18. Outcome 3 Desc
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out3_desc",
            element_type="text_box",
            text="Harness data and AI to gain deeper insights and make confident, real-time decisions.",
            paragraphs=[ParagraphModel(level=0, text="Harness data and AI to gain deeper insights and make confident, real-time decisions.", runs=[
                RunModel(text="Harness data and AI to gain deeper insights and make confident, real-time decisions.", font_size=9.5, font_name="OpenSans", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=313.0*scale, width=238.0*scale, height=30.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 3 Desc", "visible": True, "is_placeholder": False, "z_order": 18}
        ))

        # 19. Outcome 4 Title
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out4_title",
            element_type="text_box",
            text="Sustainable growth",
            paragraphs=[ParagraphModel(level=0, text="Sustainable growth", runs=[
                RunModel(text="Sustainable growth", bold=True, font_size=11.5, font_name="OpenSans-Bold", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=370.0*scale, width=238.0*scale, height=18.0*scale),
            style=StyleModel(font_size=11.5, font_name="OpenSans-Bold", bold=True, text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 4 Title", "visible": True, "is_placeholder": False, "z_order": 19}
        ))

        # 20. Outcome 4 Desc
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_out4_desc",
            element_type="text_box",
            text="Build resilient, future-ready businesses that adapt and scale with confidence.",
            paragraphs=[ParagraphModel(level=0, text="Build resilient, future-ready businesses that adapt and scale with confidence.", runs=[
                RunModel(text="Build resilient, future-ready businesses that adapt and scale with confidence.", font_size=9.5, font_name="OpenSans", font_color="#ffffff")
            ])],
            position=PositionModel(x=696.0*scale, y=388.0*scale, width=238.0*scale, height=30.0*scale),
            style=StyleModel(font_size=9.5, font_name="OpenSans", text_color="#ffffff"),
            shape_type="rect",
            metadata={"name": "Outcome 4 Desc", "visible": True, "is_placeholder": False, "z_order": 20}
        ))

        # 21. Slide Footer (bottom)
        elements.append(DocumentElementModel(
            element_id="slide_2_shape_footer",
            element_type="text_box",
            text="Engineering + AI & Data Offerings \u00a9 2026 Deloitte Touche Tohmatsu India LLP.",
            paragraphs=[ParagraphModel(level=0, text="Engineering + AI & Data Offerings \u00a9 2026 Deloitte Touche Tohmatsu India LLP. 2", runs=[
                RunModel(text="Engineering + AI & Data Offerings \u00a9 2026 Deloitte Touche Tohmatsu India LLP.", font_size=8.5, font_name="OpenSans", font_color="#000000")
            ])],
            position=PositionModel(x=25.0*scale, y=510.0*scale, width=500.0*scale, height=15.0*scale),
            style=StyleModel(font_size=8.5, font_name="OpenSans", text_color="#000000"),
            shape_type="rect",
            metadata={"name": "Slide Footer", "visible": True, "is_placeholder": False, "z_order": 21}
        ))

        # Replace all slide elements
        slide_2.elements = elements

