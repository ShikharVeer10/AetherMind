import asyncio
from pathlib import Path
from services.extraction_service import ExtractionService

async def main():
    service = ExtractionService(
        document_path=r'deloitte_it_strategic_review_2014.pdf',
        enable_summaries=False,
        enable_image_summaries=False
    )
    doc = await service.extract_document()
    json_path = service.export_to_json(doc)
    print(f'DONE: {json_path}')

if __name__ == "__main__":
    asyncio.run(main())
