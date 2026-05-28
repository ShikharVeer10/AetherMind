# Extraction service for a powerpoint presentation
import json
from pathlib import Path
from typing import Optional
from extractors.ppt_extractor import PPTExtractor


class ExtractionService:
    def __init__(
        self,
        document_path: str,
        enable_summaries: bool = False,
        enable_image_summaries: bool = False,
    ):
        self.document_path = document_path
        self.document_extension = Path(document_path).suffix.lower()
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

    async def extract_document(self):
        if self.document_extension == ".pptx":
            extractor = PPTExtractor(self.document_path)
            document_model = extractor.extract_document()
            if self.enable_summaries and self.summarization_agent:
                for slide in document_model.slides:
                    slide.slide_summary = await self.summarization_agent.summarize_slide(
                        slide
                    )
            if self.enable_image_summaries and self.image_summarization_agent:
                await self._summarize_images(document_model)
            return document_model
        else:
            raise ValueError(f"Unsupported document type: {self.document_extension}")

    # Provide a method to load the json file
    def export_to_json(
        self, extracted_document, output_directory: str = "output/extracted_json"
    ):
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        document_name = Path(self.document_path).stem
        json_output_file = output_path / f"{document_name}.json"
        output_payload = self._format_output(extracted_document)
        with open(json_output_file, "w", encoding="utf-8") as json_file:
            json.dump(output_payload, json_file, indent=4, ensure_ascii=False)
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
                        "bold": element.style.bold,
                        "italic": element.style.italic,
                        "color": element.style.text_color,
                        "background_color": element.style.background_color,
                    }

                elements_payload.append(
                    {
                        "id": element.element_id,
                        "type": element.element_type,
                        "text": element.text,
                        "position": {
                            "x": element.position.x,
                            "y": element.position.y,
                            "width": element.position.width,
                            "height": element.position.height,
                        },
                        "style": style,
                        "metadata": self._sanitize_metadata(element.metadata),
                    }
                )

            relationships_payload = self._build_slide_relationships(slide)
            slide_summary = slide.slide_summary or self._build_slide_summary(slide)
            slides_payload.append(
                {
                    "slide_number": slide.slide_number,
                    "title": slide.title,
                    "elements": elements_payload,
                    "relationships": relationships_payload,
                    "summary": slide_summary,
                }
            )

        document_summary = self._build_document_summary(
            extracted_document=extracted_document, slides_payload=slides_payload
        )

        return {
            "document_type": "ppt",
            "document_name": extracted_document.document_name,
            "document_summary": document_summary,
            "slides": slides_payload,
        }

    async def _summarize_images(self, document_model):
        for slide in document_model.slides:
            image_summaries = []
            for element in slide.elements:
                if element.element_type != "image":
                    continue
                image_bytes = element.metadata.get("__image_bytes")
                if not image_bytes:
                    continue
                try:
                    summary = await self.image_summarization_agent.summarize_image(
                        image_bytes
                    )
                except Exception:
                    summary = None
                if summary:
                    element.metadata["image_summary"] = summary
                    image_summaries.append(summary)

            if image_summaries:
                joined_summary = " ".join(image_summaries)
                if slide.slide_summary:
                    slide.slide_summary = (
                        f"{slide.slide_summary}\nImage summary: {joined_summary}"
                    )
                else:
                    slide.slide_summary = f"Image summary: {joined_summary}"

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        if not metadata:
            return {}
        sanitized = {}
        for key, value in metadata.items():
            if key.startswith("__"):
                continue
            sanitized[key] = value
        return sanitized

    def _build_slide_relationships(self, slide) -> list:
        relationships = []
        relationships.extend(self._build_flow_relationships(slide))
        relationships.extend(self._build_bullet_relationships(slide))
        if not relationships:
            relationships.extend(self._build_reading_order_relationships(slide))
        return relationships

    def _build_flow_relationships(self, slide) -> list:
        relationships = []
        text_candidates = [
            element
            for element in slide.elements
            if element.text
            and element.element_type not in {"connector", "arrow"}
        ]
        connector_candidates = [
            element
            for element in slide.elements
            if element.element_type in {"connector", "arrow"}
        ]
        if not text_candidates or not connector_candidates:
            return relationships

        for connector in connector_candidates:
            connector_center = self._element_center(connector)
            is_horizontal = connector.position.width >= connector.position.height
            if is_horizontal:
                left = self._find_nearest(
                    text_candidates,
                    connector_center,
                    predicate=lambda candidate: self._element_center(candidate)["x"]
                    < connector_center["x"],
                )
                right = self._find_nearest(
                    text_candidates,
                    connector_center,
                    predicate=lambda candidate: self._element_center(candidate)["x"]
                    > connector_center["x"],
                )
                direction = "left_to_right"
            else:
                left = self._find_nearest(
                    text_candidates,
                    connector_center,
                    predicate=lambda candidate: self._element_center(candidate)["y"]
                    < connector_center["y"],
                )
                right = self._find_nearest(
                    text_candidates,
                    connector_center,
                    predicate=lambda candidate: self._element_center(candidate)["y"]
                    > connector_center["y"],
                )
                direction = "top_to_bottom"

            if left and right:
                relationships.append(
                    {
                        "type": "flow",
                        "from": self._element_label(left),
                        "to": self._element_label(right),
                        "from_element_id": left.element_id,
                        "to_element_id": right.element_id,
                        "direction": direction,
                    }
                )
        return relationships

    def _build_bullet_relationships(self, slide) -> list:
        relationships = []
        for element in slide.elements:
            bullet_items = element.metadata.get("bullet_hierarchy") or []
            if len(bullet_items) < 2:
                continue
            previous_text = None
            for item in bullet_items:
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                if previous_text:
                    relationships.append(
                        {
                            "type": "sequence",
                            "from": previous_text,
                            "to": text,
                            "container_element_id": element.element_id,
                        }
                    )
                previous_text = text
            stack = []
            for item in bullet_items:
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                level = int(item.get("level", 0))
                while stack and stack[-1]["level"] >= level:
                    stack.pop()
                if stack:
                    parent = stack[-1]
                    relationships.append(
                        {
                            "type": "hierarchy",
                            "from": parent["text"],
                            "to": text,
                            "container_element_id": element.element_id,
                            "from_level": parent["level"],
                            "to_level": level,
                        }
                    )
                stack.append({"level": level, "text": text})
        return relationships

    def _build_reading_order_relationships(self, slide) -> list:
        candidates = [element for element in slide.elements if element.text]
        if len(candidates) < 2:
            return []
        sorted_elements = sorted(
            candidates, key=lambda element: (element.position.y, element.position.x)
        )
        relationships = []
        for index in range(len(sorted_elements) - 1):
            current_element = sorted_elements[index]
            next_element = sorted_elements[index + 1]
            relationships.append(
                {
                    "type": "reading_order",
                    "from": self._element_label(current_element),
                    "to": self._element_label(next_element),
                    "from_element_id": current_element.element_id,
                    "to_element_id": next_element.element_id,
                    "direction": "top_to_bottom",
                }
            )
        return relationships

    def _build_slide_summary(self, slide) -> str:
        title = (slide.title or "").strip()
        summary_parts = []
        if title:
            summary_parts.append(f"{title}.")
        key_points = self._collect_key_points(slide)
        if key_points:
            summary_parts.append(f"Key points: {'; '.join(key_points)}.")
        if not summary_parts:
            return "Slide contains no extractable text."
        return " ".join(summary_parts)

    def _collect_key_points(self, slide) -> list:
        key_points = []
        seen = set()
        for element in slide.elements:
            for bullet in element.metadata.get("bullet_hierarchy", []) or []:
                text = (bullet.get("text") or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                key_points.append(text)
                if len(key_points) >= 3:
                    return key_points
        if key_points:
            return key_points
        for element in slide.elements:
            if not element.text:
                continue
            text = self._truncate_text(element.text)
            if text and text not in seen and text != (slide.title or ""):
                seen.add(text)
                key_points.append(text)
            if len(key_points) >= 2:
                break
        return key_points

    def _build_document_summary(self, extracted_document, slides_payload) -> str:
        titles = [
            (slide.title or "").strip()
            for slide in extracted_document.slides
            if (slide.title or "").strip()
        ]
        if titles:
            title_sample = "; ".join(titles[:5])
            return f"Slides cover: {title_sample}."
        summaries = [
            slide_payload.get("summary")
            for slide_payload in slides_payload
            if slide_payload.get("summary")
        ]
        if summaries:
            return " ".join(summaries[:3])
        return "Document contains no extractable text."

    @staticmethod
    def _element_center(element) -> dict:
        return {
            "x": element.position.x + (element.position.width / 2),
            "y": element.position.y + (element.position.height / 2),
        }

    @staticmethod
    def _distance_squared(a: dict, b: dict) -> float:
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        return (dx * dx) + (dy * dy)

    def _find_nearest(self, candidates, origin: dict, predicate) -> Optional[object]:
        best_candidate = None
        best_distance = None
        for candidate in candidates:
            if not predicate(candidate):
                continue
            distance = self._distance_squared(origin, self._element_center(candidate))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_candidate = candidate
        return best_candidate

    @staticmethod
    def _element_label(element) -> str:
        if element.text:
            cleaned = " ".join(element.text.split())
            if cleaned:
                return cleaned[:120]
        return element.element_id

    @staticmethod
    def _truncate_text(text: str, limit: int = 120) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}..."
