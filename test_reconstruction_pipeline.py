import json
from models.document_model import (
    SlideModel, DocumentElementModel, PositionModel, StyleModel,
    RelationshipModel, FlowchartModel, LayoutStructureModel, RegionModel,
    TextPointModel, ImageReconstructionModel, ImageUnderstandingModel,
    DocumentModel
)
from services.table_service import TableService
from services.chart_understanding_service import ChartUnderstandingService
from services.semantic_region_detection_service import SemanticRegionDetectionService
from services.document_structure_service import DocumentStructureService
from services.extraction_service import ExtractionService

def test_pipeline():
    print("Testing Reconstruction Services...")

    # 1. Test Table structure analysis
    table_service = TableService()
    mock_table_data = [
        ["Product", "Q1 Revenue", "Q2 Revenue", "Total"],
        ["Product A", "$10,000", "$12,000", "$22,000"],
        ["Product B", "$15,000", "$18,000", "$33,000"],
        ["Subtotal", "$25,000", "$30,000", "$55,000"],
        ["Total", "$25,000", "$30,000", "$55,000"]
    ]
    struct = table_service.analyze_structure(mock_table_data)
    assert struct["is_financial_table"] == True, "Failed financial table check"
    assert struct["has_subtotals"] == True, "Failed subtotals check"
    assert struct["has_totals"] == True, "Failed totals check"
    print("Table Service Analysis: PASSED")

    # 2. Test mock slide with table, chart, and regions
    slide = SlideModel(slide_number=1, title="Q2 Financial Analysis & Recommendations")
    
    # Add table element
    table_el = DocumentElementModel(
        element_id="table_1",
        element_type="table",
        position=PositionModel(x=1000000, y=2000000, width=5000000, height=3000000),
        metadata={"table_data": mock_table_data}
    )
    table_el.raw_table_content = mock_table_data
    table_el.table_structure = struct
    table_el.table_semantic_interpretation = table_service.generate_interpretation(mock_table_data)
    
    # Add chart element with mock PPTX metadata
    chart_el = DocumentElementModel(
        element_id="chart_1",
        element_type="chart",
        position=PositionModel(x=7000000, y=2000000, width=4000000, height=3000000),
        metadata={"chart_data": {
            "title": "Revenue Growth Trend",
            "chart_type": "line",
            "series": [{"name": "Sales", "values": [10, 15, 25, 40]}],
            "categories": ["Jan", "Feb", "Mar", "Apr"]
        }}
    )
    chart_service = ChartUnderstandingService()
    chart_el.chart_understanding = chart_service.analyze_chart_element(chart_el, slide)
    assert chart_el.chart_understanding.chart_type == "line_chart"
    assert "upward trend" in chart_el.chart_understanding.trends[0]
    
    # Add title and recommendation text elements
    title_el = DocumentElementModel(
        element_id="title_el",
        element_type="text_box",
        position=PositionModel(x=0, y=0, width=12192000, height=1000000),
        text="Q2 Financial Findings & Key Observations"
    )
    rec_el = DocumentElementModel(
        element_id="rec_el",
        element_type="text_box",
        position=PositionModel(x=0, y=5000000, width=12192000, height=1000000),
        text="Recommendation: We must increase marketing budget next quarter"
    )
    
    # Add elements to slide
    slide.elements = [title_el, rec_el, table_el, chart_el]
    slide.chart_understandings = [chart_el.chart_understanding]
    
    # 3. Test Semantic Region Detection
    region_detector = SemanticRegionDetectionService()
    slide.semantic_regions = region_detector.detect_regions(slide)
    
    has_findings = any(r.semantic_role == "findings_panel" for r in slide.semantic_regions)
    has_recommendations = any(r.semantic_role == "recommendation_panel" for r in slide.semantic_regions)
    assert has_findings == True, "Failed to detect findings panel"
    assert has_recommendations == True, "Failed to detect recommendation panel"
    print("Semantic Region Detection: PASSED")

    # 4. Test Document Structure Service
    doc = DocumentModel(
        document_name="TestReport.pptx",
        document_type="pptx",
        total_slides=1,
        slides=[slide]
    )
    
    doc_structure_service = DocumentStructureService()
    doc.document_structure = doc_structure_service.analyze_document(doc)
    assert doc.document_structure["document_role"] == "Financial Audit Report"
    print("Document Structure Analysis: PASSED")

    # 5. Test JSON Serialization Compatibility
    # Mocking ExtractionService export serialization
    extractor_service = ExtractionService(document_path="TestReport.pptx")
    serialized = extractor_service._format_output(doc)
    
    # Assert new fields are present
    assert serialized["document_structure"] is not None
    assert serialized["slides"][0]["chart_understandings"] != []
    assert serialized["slides"][0]["semantic_regions"] != []
    
    table_payload = next(e for e in serialized["slides"][0]["elements"] if e["type"] == "table")
    assert table_payload["raw_table_content"] == mock_table_data
    
    # Verify valid json dump
    json_str = json.dumps(serialized, indent=2)
    assert len(json_str) > 0
    print("Serialization & Backward Compatibility Verification: PASSED")

if __name__ == "__main__":
    test_pipeline()
