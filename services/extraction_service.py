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
        if suffix == ".pptx":
            return suffix
        name = Path(document_path).name.lower().rstrip(".,;")
        if name.endswith(".pptx"):
            return ".pptx"
        return suffix

    async def extract_document(self):
        if self.document_extension != ".pptx":
            raise ValueError(
                f"Unsupported document type: {self.document_extension}"
            )

        extractor = PPTExtractor(self.document_path)
        document_model = extractor.extract_document()

        orchestrator = AgentOrchestrator(
            summarization_agent=self.summarization_agent,
            image_summarization_agent=self.image_summarization_agent,
            presentation_metadata=document_model.presentation_metadata,
        )

        raw_slides = list(extractor.presentation.slides)

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

        return document_model

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
            json.dump(output_payload, f, indent=4, ensure_ascii=False)

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
                        "image_summary": element.metadata.get("image_summary"),
                        "metadata": self._sanitize_metadata(element.metadata),
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
                    "llm_reconstruction_payload": self._build_llm_reconstruction_payload(
                        slide
                    ),
                    "table_markdowns": slide.table_markdowns,
                    "summary": slide.slide_summary,
                }
            )


        return {
            "document_type": "ppt",
            "document_name": extracted_document.document_name,
            "total_slides": extracted_document.total_slides,
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
                "table_markdown": element.table_markdown,
                "image_description": image_summary,
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
            text = content["text"] or content["image_description"] or content["table_markdown"] or ""
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
