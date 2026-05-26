import asyncio
import os
from pathlib import Path
from services.extraction_service import ExtractionService
def main():
    print("Enterprise Document Extraction Agent")

    document_path=input("Document Path:").strip()
    if document_path.startswith("\"") and document_path.endswith("\""):
        document_path = document_path[1:-1].strip()
    if not document_path:
        raise ValueError("Path cannot be empty")
    document_path_object=Path(document_path)
    if not document_path_object.exists():
        raise FileNotFoundError("Document not found")
    enable_summaries = os.getenv("ENABLE_SUMMARIES", "false").lower() in {"1", "true"}
    enable_image_summaries = (
        os.getenv("ENABLE_IMAGE_SUMMARIES", "false").lower() in {"1", "true"}
    )
    extraction_service=ExtractionService(
        document_path=document_path,
        enable_summaries=enable_summaries,
        enable_image_summaries=enable_image_summaries,
    )
    print("Document Extraction")
    extracted_document=asyncio.run(extraction_service.extract_document())
    print("Document Extraction Completed")

    json_path=extraction_service.export_to_json(extracted_document=extracted_document)

    print(f"Extracted document saved to: {json_path}")

if __name__=="__main__":
    main()