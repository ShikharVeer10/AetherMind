# AetherMind Document Extraction Agent

Extract structured data from PowerPoint (.pptx) files and export JSON suitable for downstream search, analysis, or summarization. Optional AI summaries can be enabled for slides and images.

## Features
- Extracts slide text, tables, images, positions, styling metadata, and basic flow relationships
- Exports a clean JSON schema for each document
- Optional slide summaries via Gemini (pydantic-ai), with a local rule-based fallback when the API is unavailable
- Optional image summaries via Ollama vision models

## Requirements
- Python 3.9+
- Dependencies in `requirements.txt`

## Installation
```bash
pip install -r requirements.txt
```

## Usage
```bash
python main.py
```

When prompted, provide a path to a `.pptx` file. The JSON output is written to:
```
output/extracted_json/<document_name>.json
```

## Configuration
Enable or disable summaries using environment variables:

- `ENABLE_SUMMARIES` (default: `false`)
- `ENABLE_IMAGE_SUMMARIES` (default: `false`)

Examples:
```bash
set ENABLE_SUMMARIES=true
set ENABLE_IMAGE_SUMMARIES=true
python main.py
```

### AI Providers
- Slide summaries use `pydantic-ai` with `google:gemini-2.0-flash`. Configure your Google GenAI credentials as required by the SDK.
- Image summaries use Ollama. Set:
  - `OLLAMA_HOST` (default: `http://localhost:11434`)
  - `OLLAMA_VISION_MODEL` (default: `llava`)

## Project Structure
```
app/
  agents/                 # AI summarization agents
  extractors/             # PPTX parsing and extraction
  models/                 # Pydantic data models
  services/               # Orchestration and export logic
  output/extracted_json/  # Generated JSON outputs
  main.py                 # CLI entry point
```

## Notes
- Only `.pptx` files are supported currently.
- Image bytes are removed from output JSON by default for size and privacy.
- Element positions are exported in points.
