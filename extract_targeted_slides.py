"""
Targeted extraction script for NMSU report slides.
Runs the full high-fidelity extraction pipeline on specific pages.
"""

import asyncio
import os
import sys
from pathlib import Path
from services.extraction_service import ExtractionService

# Specified pages from the user request
# Page 24 to 32 and Page 35 to 43
TARGET_PAGES = list(range(24, 33)) + list(range(35, 44))

async def run_targeted_extraction():
    pdf_path = r"C:\Users\shikh\Downloads\NMSU-Recommendations-Report-Final.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    print(f"Starting targeted high-fidelity extraction for {len(TARGET_PAGES)} slides...")
    
    # Initialize service with all enrichment layers enabled
    service = ExtractionService(
        document_path=pdf_path,
        enable_summaries=True,
        enable_image_summaries=True
    )

    # Perform extraction ONLY for target pages
    document_model = await service.extract_document(target_pages=TARGET_PAGES)
    
    print(f"Successfully extracted {document_model.total_slides} high-fidelity slides.")

    # Export to JSON and text summary
    json_path = service.export_to_json(extracted_document=document_model)
    print(f"Targeted high-fidelity extraction saved to: {json_path}")

if __name__ == "__main__":
    asyncio.run(run_targeted_extraction())
