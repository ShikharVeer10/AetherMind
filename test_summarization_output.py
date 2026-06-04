from models.document_model import (
    SlideModel, DocumentElementModel, PositionModel, StyleModel,
    RelationshipModel, FlowchartModel, LayoutStructureModel, RegionModel,
    TextPointModel, ImageReconstructionModel
)
from agents.summarization_agent import SummarizationAgent

# Create a mock slide matching the user's scenario
slide = SlideModel(slide_number=1, title="Environment Abstraction")

# Set up visual inventory
from models.document_model import VisualInventoryModel
slide.visual_inventory = VisualInventoryModel(
    text_box_count=4,
    shape_count=1,
    arrow_count=2,
    total_elements=7
)

# Set up elements
slide.elements = [
    DocumentElementModel(
        element_id="Game_Area",
        element_type="image",
        position=PositionModel(x=0, y=0, width=5000000, height=5000000),
        style=StyleModel(background_color="#000000", text_color="#FFFFFF"),
        text="Concrete World (Game screen with ladders, obstacles, key, and exit)"
    ),
    DocumentElementModel(
        element_id="Decision_Node",
        element_type="shape",
        position=PositionModel(x=6000000, y=2000000, width=3000000, height=1000000),
        style=StyleModel(background_color="#ADD8E6", text_color="#000000", bold=True, font_size=18, font_name="Arial"),
        text="Agent has key?"
    ),
    DocumentElementModel(
        element_id="Action_No",
        element_type="shape",
        position=PositionModel(x=10000000, y=1000000, width=2000000, height=800000),
        style=StyleModel(background_color="#90EE90", text_color="#000000", font_size=14, font_name="Arial"),
        text="Get key"
    ),
    DocumentElementModel(
        element_id="Action_Yes",
        element_type="shape",
        position=PositionModel(x=10000000, y=3000000, width=2000000, height=800000),
        style=StyleModel(background_color="#90EE90", text_color="#000000", font_size=14, font_name="Arial"),
        text="Open the door"
    )
]

# Set up relationships
slide.relationships = [
    RelationshipModel(relationship_type="decision_no", source_element_id="Decision_Node", target_element_id="Action_No", label="No"),
    RelationshipModel(relationship_type="decision_yes", source_element_id="Decision_Node", target_element_id="Action_Yes", label="Yes")
]

# Set up layout structure
slide.layout_structure = LayoutStructureModel(
    layout_type="flowchart",
    regions=[
        RegionModel(name="left", element_ids=["Game_Area"]),
        RegionModel(name="right", element_ids=["Decision_Node", "Action_No", "Action_Yes"])
    ]
)

# Set up image reconstruction palette and styling details
slide.image_reconstruction = ImageReconstructionModel(
    layout_description="Concrete game area on the left, abstract decision flowchart on the right",
    color_palette=["#000000", "#ADD8E6", "#90EE90", "#FFD700"],
    object_location=["Game_Area at left, flowchart elements at right"],
    connector_layout=["Straight arrows from Decision_Node to Action_No and Action_Yes"]
)

# Set up text points
slide.text_points = [
    TextPointModel(element_id="Game_Area", level=0, text="Concrete World (Game screen with ladders, obstacles, key, and exit)"),
    TextPointModel(element_id="Decision_Node", level=0, text="Agent has key?"),
    TextPointModel(element_id="Action_No", level=1, text="If No -> take higher-level action: Get key"),
    TextPointModel(element_id="Action_Yes", level=1, text="If Yes -> take another higher-level action: Open the door")
]

# Call programmatic fallback
agent = SummarizationAgent()
result = agent._build_fallback(
    slide=slide,
    text_lines=["  [L0] Agent has key?", "  [L1] Get key", "  [L1] Open the door"],
    image_summaries="Game screen depicting agent, platforms, key, and exit door",
    hf_info="Slide 1 | Part 1"
)

print("=" * 60)
print("GENERATED SUMMARY PREVIEW:")
print("=" * 60)
print(result)
print("=" * 60)
