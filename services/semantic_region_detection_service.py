import re
from typing import Any, Dict, List, Optional
from models.document_model import SemanticRegionModel, SlideModel, PositionModel, DocumentElementModel

class SemanticRegionDetectionService:
    def detect_regions(self, slide: SlideModel) -> List[SemanticRegionModel]:
        semantic_regions = []
        width = 12192000.0
        height = 6858000.0
        
        # Estimate layout boundaries dynamically
        for e in slide.elements:
            if e.position:
                width = max(width, e.position.x + e.position.width)
                height = max(height, e.position.y + e.position.height)

        # 1. Callout Boxes & Highlighted Regions
        for element in slide.elements:
            if element.element_type in ("shape", "text_box", "placeholder"):
                text = (element.text or "").strip()
                if not text:
                    continue
                
                has_bg = False
                has_border = False
                if element.style:
                    if element.style.background_color and element.style.background_color.lower() not in ("#ffffff", "#000000", "none"):
                        has_bg = True
                    if element.style.text_color and element.style.text_color.lower() not in ("#ffffff", "#000000"):
                        pass
                if element.metadata.get("border_color"):
                    has_border = True
                
                shape_type_str = str(element.shape_type).lower()
                is_callout_shape = "callout" in shape_type_str or "balloon" in shape_type_str
                
                if is_callout_shape or (has_bg and has_border) or (has_bg and len(text) < 150):
                    role = "callout_box" if is_callout_shape else "highlighted_region"
                    purpose = f"Highlights key information: '{text[:60]}...'"
                    semantic_regions.append(SemanticRegionModel(
                        name=f"{role}_{element.element_id}",
                        semantic_role=role,
                        purpose=purpose,
                        position=element.position,
                        contents=[text]
                    ))

        # 2. Sidebars (Width < 35% of slide, Height > 40% of slide, positioned on extreme left/right)
        for element in slide.elements:
            if element.position:
                el_w = element.position.width / width
                el_h = element.position.height / height
                el_x = element.position.x / width
                
                if el_w < 0.35 and el_h > 0.4 and (el_x < 0.25 or el_x > 0.65):
                    text = (element.text or "").strip()
                    if text:
                        semantic_regions.append(SemanticRegionModel(
                            name=f"sidebar_{element.element_id}",
                            semantic_role="sidebar",
                            purpose=f"Provides supplementary sidebar content: '{text[:60]}...'",
                            position=element.position,
                            contents=[text]
                        ))

        # 3. Findings, Recommendations, and Executive Summary Panels
        for element in slide.elements:
            text = (element.text or "").strip()
            if not text:
                continue
                
            text_lower = text.lower()
            role = None
            purpose = ""
            
            if "finding" in text_lower or "result" in text_lower or "observation" in text_lower or "metrics" in text_lower:
                role = "findings_panel"
                purpose = "Presents data observations or findings"
            elif "recommend" in text_lower or "next step" in text_lower or "proposal" in text_lower or "should" in text_lower or "action item" in text_lower:
                role = "recommendation_panel"
                purpose = "Outlines recommendations or action items"
            elif "executive summary" in text_lower or "key takeaway" in text_lower or "summary" in text_lower or "overview" in text_lower:
                role = "executive_summary_panel"
                purpose = "Summarizes core slide content"
                
            if role:
                already_captured = False
                for r in semantic_regions:
                    if r.name == f"{role}_{element.element_id}":
                        already_captured = True
                        break
                if not already_captured:
                    semantic_regions.append(SemanticRegionModel(
                        name=f"{role}_{element.element_id}",
                        semantic_role=role,
                        purpose=purpose,
                        position=element.position,
                        contents=[text]
                    ))
                    
        return semantic_regions
