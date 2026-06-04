import asyncio
import os
from models.document_model import SlideModel, VisualInventoryModel
from agents.slide_interpretation_agent import SlideInterpretationAgent

async def main():
    # Force empty API keys so it falls back to local Ollama
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GOOGLE_API_KEY"] = ""
    os.environ["GROQ_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""

    slide = SlideModel(
        slide_number=1,
        title="Environment Abstraction"
    )
    slide.visual_inventory = VisualInventoryModel(
        text_box_count=4,
        shape_count=1,
        arrow_count=2,
        total_elements=7
    )
    
    agent = SlideInterpretationAgent()
    result = await agent.interpret_slide(slide, image_summaries="Diagram describing has key.")
    print("Ollama Result:")
    if result:
        print("Model:", type(result))
        print("image_generation_prompt:", result.image_generation_prompt)
        print("overall_flow:", result.overall_flow)
    else:
        print("No result generated.")

asyncio.run(main())
