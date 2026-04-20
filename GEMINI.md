# LLM Knowledge Base (LKB) - Technical Specification

## Core Principles
1. **Files as API:** All state is stored in local Markdown files or JSON state files.
2. **LLM as Compiler:** The LLM is the primary "writer" of the wiki, not a human.
3. **Whole-File Ingest:** No chunking. Leveraging 1M+ context windows for high-fidelity synthesis.
4. **Visual Weaving:** Agentic placement of extracted figures and tables into the knowledge graph.

## Tech Stack
- **Orchestration:** Python 3.11+, PydanticAI.
- **LLM:** Gemini 2.5 Flash (Primary).
- **Processing:** `pdftext` (Text), `PyMuPDF` (Images), `Trafilatura` (Web).
- **Database:** LanceDB (Local Vector Store).
- **Frontend:** Obsidian.

## Data Flow
1. **Ingest:** `processor.py` standardizes input, extracts text, and rips images into `attachments/`.
2. **Compile:** `agent.py` uses templates to generate structured Markdown with metadata and embedded visuals.
3. **Organize:** `lkb.py` maps source directories to `wiki/` subfolders using deterministic naming.
4. **Index:** `search_engine.py` builds the vector index for downstream Q&A.
5. **Audit:** `health_checker.py` performs LLM-driven gap analysis.

## Project Structure
- `wiki/`: The knowledge output (Obsidian Vault).
- `raw/`: Source documents.
- `attachments/`: Extracted figures and images.
- `templates/`: Decoupled LLM prompts and article blueprints.
- `tools/`: Independent CLI utilities.
