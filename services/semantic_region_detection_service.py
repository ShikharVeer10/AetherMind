from typing import List, Any, Dict
from models.document_model import (
    SlideModel, 
    DocumentElementModel, 
    SemanticRegionModel, 
    PositionModel,
    LayoutGraphModel
)

class SemanticRegionDetectionService:
    def detect_regions(self, slide: SlideModel) -> List[SemanticRegionModel]:
        elements = slide.elements
        if not elements:
            return []

        regions = []
        regions.extend(self._detect_structural_regions(elements))
        regions.extend(self._detect_visual_panels(elements))
        return regions
    def build_layout_graph(self, elements: List[DocumentElementModel], regions: List[SemanticRegionModel]) -> LayoutGraphModel:
        nodes = []
        edges = []
        for e in elements:
            nodes.append({
                "id": e.element_id,
                "type": e.element_type,
                "label": e.text[:50] if e.text else e.element_type
            })
        for r in regions:
            nodes.append({
                "id": f"region_{r.name}",
                "type": "region",
                "label": r.name
            })
        for r in regions:
            for e_id in r.contents:
                edges.append({
                    "source": f"region_{r.name}",
                    "target": e_id,
                    "relation": "contains"
                })
        sorted_elements = sorted(elements, key=lambda x: (x.position.y, x.position.x))
        for i in range(len(sorted_elements) - 1):
            edges.append({
                "source": sorted_elements[i].element_id,
                "target": sorted_elements[i+1].element_id,
                "relation": "precedes_in_reading_order"
            })
            
        return LayoutGraphModel(nodes=nodes, edges=edges)

    def _detect_structural_regions(self, elements: List[DocumentElementModel]) -> List[SemanticRegionModel]:
        regions = []
        title_elements = [e for e in elements if "title" in str(e.metadata.get("name", "")).lower()]
        if title_elements:
            regions.append(SemanticRegionModel(
                name="Title Region",
                semantic_role="header",
                purpose="Defines slide topic",
                position=title_elements[0].position,
                contents=[e.element_id for e in title_elements]
            ))
        return regions
    def _detect_visual_panels(self, elements: List[DocumentElementModel]) -> List[SemanticRegionModel]:
        if not elements:
            return []
        sorted_x = sorted(elements, key=lambda e: e.position.x)
        gaps = []
        for i in range(len(sorted_x) - 1):
            gap = sorted_x[i+1].position.x - (sorted_x[i].position.x + sorted_x[i].position.width)
            if gap > 500000: # Approx 0.5 inches
                gaps.append(i)
                
        regions = []
        if len(gaps) == 1:
            # 2-panel layout
            left_elems = sorted_x[:gaps[0]+1]
            right_elems = sorted_x[gaps[0]+1:]
            
            if left_elems:
                regions.append(self._create_region_from_elements("Left Panel", left_elems))
            if right_elems:
                regions.append(self._create_region_from_elements("Right Panel", right_elems))
                
        return regions

    def _create_region_from_elements(self, name: str, elements: List[DocumentElementModel]) -> SemanticRegionModel:
        min_x = min(e.position.x for e in elements)
        min_y = min(e.position.y for e in elements)
        max_x = max(e.position.x + e.position.width for e in elements)
        max_y = max(e.position.y + e.position.height for e in elements)
        
        return SemanticRegionModel(
            name=name,
            semantic_role="content_panel",
            purpose="Groups related content vertically",
            position=PositionModel(x=min_x, y=min_y, width=max_x-min_x, height=max_y-min_y),
            contents=[e.element_id for e in elements]
        )
