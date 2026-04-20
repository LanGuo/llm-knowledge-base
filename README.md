# LLM Knowledge Base (LKB)

> "A large fraction of my recent token throughput is going less into manipulating code, and more into manipulating knowledge." — [Andrej Karpathy](https://x.com/karpathy/status/2039805659525644595).

LKB is an agentically maintained personal knowledge system. It treats knowledge as a "compiled" asset, moving away from static notes toward an LLM-managed information graph.

## 🛠 Operational Workflow

To maintain your knowledge base, follow this sequence:

1. **`python lkb.py sync`**: The **Compiler**. Scans tracked directories, converts files to text, extracts images, and uses the LLM to write structured `.md` articles into topic-specific subfolders in `wiki/`.
2. **`python lkb.py index`**: The **Librarian**. Builds a local LanceDB vector index of all compiled articles for fast searching.
3. **`python lkb.py query "..."`**: The **Researcher**. Performs hybrid search across your wiki to answer complex research questions. **High-value answers are automatically saved to `synthesized/` to enhance the graph.**
4. **`python lkb.py health`**: The **Auditor**. Scans for broken links, orphans, and suggests new research directions based on "knowledge gaps."
5. **`python lkb.py clean`**: The **Purge**. Removes empty or error-based junk files from the wiki independently of the sync process.
6. **`python lkb.py resync`**: The **Refresher**. Clears state and re-processes all sources.

---

## 🧠 Technical Architecture & Design Decisions

### 1. The Self-Synthesis Loop
LKB is designed to "grow" autonomously. When you use the `query` command to ask a complex question, the system retrieves context, synthesizes an answer, and writes that answer back into the `synthesized/` directory as a new Markdown article. This new article is then indexed and linked during the next `sync` pass, creating a compounding cycle of knowledge.

### 1. Hybrid Client Strategy
The system utilizes a dual-path orchestration layer to ensure maximum reliability across cloud and local providers:
- **Cloud (Gemini/OpenAI):** Uses `pydantic-ai` for high-level agentic orchestration.
- **Local (Ollama):** Uses the **official `ollama` Python library**. This bypasses strict OpenAI-SDK validation errors (like the `finish_reason: null` bug) and enables native JSON Schema constraints.

### 2. Native JSON Mode (Ollama)
For local models, we utilize Ollama's `format` parameter. By passing the Pydantic schema directly to the serving engine, we enable **Grammar-Based Sampling**. This physically prevents the model from generating invalid characters, ensuring 100% schema compliance even on small 7B models.

### 3. Visual Artifact Ingest & Weaving
- **Image Extraction:** Utilizes `PyMuPDF` to rip figures and images from PDFs. These are stored in `attachments/`.
- **Graph & Image Weaving:** The LLM is provided with a list of available visual artifacts. It contextually "weaves" them into the article using Obsidian's `![[filename]]` syntax and agentically identifies `related_concepts` to create clickable graph edges (`[[Concept]]`).

### 4. Long-Context Strategy
- **Whole-File Ingest:** Leverages Gemini's **1M+ token window** or Ollama's **64k+ context window** (configured via `num_ctx`). LKB avoids RAG-style chunking, allowing the model to synthesize the entire methodology of a paper at once.

### 5. Template-Driven Intelligence
All LLM behavior is decoupled from the Python backend and managed via the `templates/` directory (`compiler_instructions.txt`, `article_structure.md`, etc.).

---

## 📂 Project Structure
- `wiki/`: The "Compiled" output. Organized by model and topic.
- `templates/`: LLM system prompts and Markdown blueprints.
- `sources/`: Tracked directories (configurable in `config.yaml`).
- `attachments/`: Media and figures extracted from research papers.
- `tools/`: Standalone scripts for health checks and search.
