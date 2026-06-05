"""Quick test to verify the pipeline runs without validation errors."""
import asyncio
import os
import sys

# Use the test pptx
DOCUMENT_PATH = r"C:\Users\shikh\OneDrive\Documents\Desktop\EAID Offerings Abriged for Client 2026 (1).pdf"

if not os.path.exists(DOCUMENT_PATH):
    print(f"ERROR: File not found: {DOCUMENT_PATH}")
    sys.exit(1)

from services.extraction_service import ExtractionService

extraction_service = ExtractionService(
    document_path=DOCUMENT_PATH,
    enable_summaries=True,
    enable_image_summaries=True,
)

print("Starting extraction...")
try:
    extracted_document = asyncio.run(extraction_service.extract_document())
    print(f"\nExtraction completed successfully!")
    print(f"Total slides: {extracted_document.total_slides}")
    for slide in extracted_document.slides:
        print(f"  Slide {slide.slide_number}: {slide.title or '(no title)'} - {len(slide.elements)} elements")
        if slide.layout_structure:
            print(f"    Layout: {slide.layout_structure.layout_type}, Regions: {[r.name for r in slide.layout_structure.regions]}")

    json_path = extraction_service.export_to_json(extracted_document=extracted_document)
    print(f"\nJSON exported to: {json_path}")
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
