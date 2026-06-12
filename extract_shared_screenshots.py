import os
import json
import base64
from pathlib import Path
from typing import List
from services.chart_understanding_service import ChartUnderstandingService
from models.document_model import DocumentElementModel, PositionModel

def extract_screenshots():
    # Setup paths
    screenshot_dir = Path(r"C:\Users\shikh\Pictures\Screenshots")
    output_dir = Path(r"C:\Users\shikh\AetherMind\output\screenshot_extractions")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize service
    chart_service = ChartUnderstandingService()
    
    # Files to process
    target_files = [f"Screenshot ({i}).png" for i in range(13, 24)]
    
    results = []
    
    for filename in target_files:
        file_path = screenshot_dir / filename
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue
            
        print(f"Processing {filename}...")
        
        with open(file_path, "rb") as f:
            image_bytes = f.read()
            
        # Mock DocumentElementModel
        element = DocumentElementModel(
            element_id=filename.replace(" ", "_").replace("(", "").replace(")", ""),
            element_type="image",
            position=PositionModel(x=0, y=0, width=1000000, height=1000000), # dummy
            metadata={
                "__image_bytes": image_bytes,
                "detected_chart_type": "stacked_bar_chart", # hint based on observation
                "name": filename
            }
        )
        
        try:
            # The service returns a ChartUnderstandingModel
            chart_info = chart_service.extract_understanding(element)
            
            # Save individual JSON
            output_file = output_dir / f"{element.element_id}.json"
            with open(output_file, "w", encoding="utf-8") as out:
                json.dump(chart_info.model_dump(), out, indent=2)
            
            print(f"  Success! Saved to {output_file}")
            results.append({
                "screenshot": filename,
                "output_file": str(output_file)
            })
            
        except Exception as e:
            print(f"  Failed to process {filename}: {e}")
            
    # Save summary
    with open(output_dir / "summary.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    extract_screenshots()
