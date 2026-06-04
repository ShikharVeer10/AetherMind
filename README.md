# AetherMind Document Extraction Agent

AetherMind is an enterprise-grade document extraction agent designed to parse PowerPoint (`.pptx`) presentations and convert them into structured, high-fidelity JSON representations. Beyond simple text parsing, AetherMind maps the visual, spatial, design, and semantic properties of every slide, producing reconstruction-grade blueprints that downstream LLMs can use to recreate slide visuals near-identically.

---

## 🚀 Key Features

- ** verbatims & Hierarchy**: Extracts all text elements exactly as written, preserving paragraph hierarchy, bullet levels, and reading order (top-to-bottom, left-to-right).
- **🎨 Precise Style Extraction**: Captures background fills (solid, gradient, hex colors), text alignment, fonts, weights, sizes, and borders.
- **📊 Table & Data Parsing**: Detects tables and automatically formats cell data into GitHub-Flavored Markdown (GFM) tables, handling variable lengths and row alignments.
- **📂 Group Shape Recursion**: Recursively traverses complex PowerPoint groups to extract nested text, shapes, diagrams, and image content.
- **🧠 Multi-Agent Orchestration**: Coordinates specialized extraction agents (Layout, Flowchart, Diagram, Position, Relationships, Table, and Text) in structured pipeline phases.
- **🖼️ Deep Image & Diagram Understanding**: 
  - Uses local or cloud Vision LLMs (Ollama/Gemini/Groq/OpenAI) to extract detailed component breakdowns, transcribing text in images, and generating Mermaid.js diagram code representations.
  - Falls back to precomputed hashes for lightning-fast lookups, or local BLIP transformers, or structured layout-based fallbacks.
- **🗺️ Spatial & Relational Mapping**: Detects containment, connector arrows, end-to-end flowchart loops, proximity clusters, and topological reading orders.
- **🏗️ Slide Reconstruction Context**: Compiles exhaustive visual layout coordinates (in EMUs and percentages), visual hierarchy focuses, attention flows, and semantic flow descriptions.

---

## 🛠️ Requirements & Installation

- **Python**: 3.9+
- **Major Libraries**: `python-pptx`, `pydantic`, `pydantic-ai`, `google-genai`, `requests`, `transformers`, `torch`, `Pillow`.

### Installation

Clone the repository and install the dependencies into a virtual environment:

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install requirements
pip install -r requirements.txt
```

---

## 💻 Usage

Run the main extraction agent CLI:

```bash
python main.py
```

When prompted, input the path to your target PowerPoint (`.pptx`) file.

### Programmatic Flow

You can also orchestrate the extraction pipeline programmatically:

```python
import asyncio
from services.extraction_service import ExtractionService

async def main():
    service = ExtractionService(
        document_path="path/to/presentation.pptx",
        enable_summaries=True,
        enable_image_summaries=True
    )
    extracted_doc = await service.extract_document()
    json_path = service.export_to_json(extracted_doc)
    print(f"Extraction successful: {json_path}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration & Environment Variables

Fine-tune AI interpretation and fallback thresholds using the following environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENABLE_SUMMARIES` | `true` | Enables AI slide summaries and semantic flow blueprints. |
| `ENABLE_IMAGE_SUMMARIES` | `true` | Enables local/cloud vision summarization of slide images. |
| `GEMINI_API_KEY` | None | API key for `google:gemini-2.0-flash` (Primary Slide & Image LLM). |
| `GROQ_API_KEY` | None | Fallback API key for Llama-3.3-70b-versatile and Llama-3.2-11b Vision. |
| `OPENAI_API_KEY` | None | Fallback API key for GPT-4o-mini Slide & Image models. |
| `OLLAMA_HOST` | `http://localhost:11434` | Target URL for a local running Ollama instance. |
| `OLLAMA_VISION_MODEL` | `moondream` | Model used for local Ollama image interpretation. |

---

## 📂 Project Structure

```
AetherMind/
├── agents/                      # Dedicated multi-agent extraction pipeline
│   ├── agent_orchestrator.py    # Pipeline manager coordinates agent phases
│   ├── extraction_agents.py     # Task-specific agents (Text, Layout, Position, etc.)
│   ├── slide_interpretation.py  # LLM slide semantics interpreter
│   └── image_summarization.py   # Cloud/local vision image interpreter
├── extractors/                  # Core parsing layer
│   └── ppt_extractor.py         # python-pptx wrapper for shapes, styles, and group traversal
├── models/                      # Pydantic schema representations
│   └── document_model.py        # Structural, visual, spatial & reconstruction schemas
├── services/                    # Business and analysis services
│   ├── context_builder.py       # Assembles multi-agent metrics into structured context
│   ├── diagram_understanding.py  # Reasoner for nodes, edges, flows, and branch logic
│   ├── flowchart_service.py     # Topological box-and-arrow flow resolver
│   ├── header_footer_service.py # Resolves slide layout/master templates and coordinates
│   ├── image_reconstruction.py  # Compiles image styling rules & illustration styles
│   ├── image_understanding.py   # Deduces semantic designs and prompt boundaries
│   ├── layout_analysis.py       # Layout classifier (two-column, single-column, flowchart...)
│   └── slide_reconstruction.py  # Visual EMU percentage layouts and reconstruction prompts
├── output/                      # Target export directory
│   └── extracted_json/          # JSON data schemas and human-readable TXT summaries
├── main.py                      # Interactive CLI entry point
└── requirements.txt             # Project library dependencies
```

---

## 📊 Extracted Outputs

AetherMind generates two files for each parsed document inside `output/extracted_json/`:

### 1. Unified JSON Schema (`<document_name>.json`)
An exhaustive document tree including:
- **Slide Dimensions & aspect ratio** (EMUs, 16:9, 4:3, etc.).
- **Verbatim Text Elements** with paragraph-level runs, sizing, font, and alignments.
- **Connector and Proximity Networks** linking related visual shapes.
- **Topological Reading Order** showing logical attention sequences.
- **Diagram Node Maps** with branch logic (`If Yes -> Open Door`).
- **Complete Visual Reconstruction Prompts** containing detailed layout, geometry, border, styling, color, and rendering instructions.

### 2. Formatted Markdown Summary (`<document_name>_summary.txt`)
A clean, human-readable summary of every slide following the structured formatting template:
- **Semantic Flow**: Conceptual mapping or progression sequences.
- **Step-by-step meaning**: Narrative breakdown of flow logic.
- **Conceptual Layers**: Abstract definitions and slide-based examples.
- **Visual Design Details**: Extracted color schemes, layout structures, and connector paths.
- **Plain English Summary**: 3–5 paragraphs explaining what the slide teaches.
- **Image Generation Prompt**: Visual blueprints for direct reproduction.

---

## 🔒 Notes & Guidelines

- **Image Blobs**: To keep JSON outputs clean, raw image bytes (`__image_bytes`) are parsed for internal vision model processing but are stripped from the final exported JSON files.
- **Local Fallbacks**: If API keys are missing and no local Ollama server is running, the agent automatically falls back to rule-based analyzers (`SemanticFlowService`, `VisualInventoryService`, etc.) ensuring the pipeline never fails.
