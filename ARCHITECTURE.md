# LKB Architecture & Data Flow

This document provides a detailed technical overview of the LLM Knowledge Base (LKB) system, illustrating how raw data is transformed into an agentically maintained information graph.

---

## 🏗 System Architecture

The LKB follows a "Knowledge Compiler" pattern, treating information as a compiled asset.

```mermaid
graph TD
    subgraph Sources
        A[raw/]
        B[Research Dirs]
        C[synthesized/]
    end

    subgraph Processors
        D[pdftext / PyMuPDF]
        E[Trafilatura]
    end

    subgraph Core_Agent [LKB Backend]
        F[lkb.py - CLI/Orchestrator]
        G[agent.py - Knowledge Engineer]
        H[models.py - Multi-Model Bridge]
    end

    subgraph Storage
        I[wiki/ - Model-Specific Subfolders]
        J[.lkb_state.json - Sync Progress]
        K[LanceDB - Search Index]
    end

    subgraph Frontend
        L[Obsidian IDE]
    end

    Sources -->|Sync| F
    F -->|Raw Files| D & E
    D & E -->|Extracted Text + Images| G
    G -->|Instructions & Blueprints| Templates
    G -->|Compiled Markdown| I
    I -->|Index| K
    I -->|Graph View| L
    K -->|Query| F
    F -->|Synthesized Answer| C
```

---

## 🔄 Data Flow: Stage-by-Stage

### 1. Synchronize (`sync`)
The **Sync** stage is the primary "Compilation" pass.
1.  **Crawl:** The system scans all directories defined in `config.yaml`.
2.  **Filter:** It checks `.lkb_state_<model>.json` and skips files already processed.
3.  **Extract:**
    *   **Text:** `pdftext` (visual-aware) or `fitz` (fallback).
    *   **Images:** `PyMuPDF` rips figures/tables into `attachments/<paper_name>/`.
4.  **Compile:** The LLM receives the text, paper metadata, and a list of available images.
5.  **Weave:** The LLM generates a structured `.md` file, agentically inserting `![[image]]` tags and `[[Related Concepts]]`.
6.  **Organize:** Files are saved to `wiki/<model>/<topic>/<filename>.md` using deterministic source-based naming.

### 2. Index (`index`)
The **Index** stage prepares the knowledge for high-speed retrieval.
1.  **Recursive Scan:** Iterates through every `.md` file in the current model's wiki.
2.  **Tabularize:** Loads title, content, and file paths into a `pandas` DataFrame.
3.  **LanceDB Ingest:** Overwrites the local `wiki_articles` table in the model-specific LanceDB instance.
4.  **Search Prep:** (Future V4) Generates vector embeddings for semantic similarity.

### 3. Query (`query`)
The **Query** stage enables the "Researcher" persona.
1.  **Search:** Performs a hybrid search (Keyword + Filter) across the LanceDB index.
2.  **Context Construction:** Retrieves the top-K most relevant compiled articles.
3.  **Synthesis:** The LLM answers the user's question based *strictly* on the retrieved wiki context.
4.  **Self-Synthesis Loop:** High-value answers are automatically written to the `synthesized/` directory as new articles, which are then picked up by the next `sync` pass to further interconnect the graph.

### 4. Health Check (`health`)
The **Health** stage is an LLM-driven audit.
1.  **Link Analysis:** Identifies "Broken Links" (concepts mentioned but not existing as files) and "Orphans."
2.  **Gap Detection:** The LLM analyzes existing topics and suggests 3-5 new research directions to fill knowledge voids.

### 5. Clean (`clean`)
The **Clean** stage ensures vault integrity.
1.  **Pattern Match:** Removes files with "Extraction Error" or "Missing Content" in the filename.
2.  **Size Gate:** Purges files < 200 characters (typically result from parsing failures).

---

## 🧠 Core Design Principles

1.  **Files as API:** No proprietary database locks. Your data is always readable Markdown.
2.  **Model-Agnostic Isolation:** Separate wikis and states for Gemini vs. Ollama allow for objective performance comparison.
3.  **Deterministic Naming:** Prevents duplicate articles when switching models or re-processing.
4.  **Quality Gate:** Two-stage logic prevents "polite" LLM errors from polluting the Obsidian graph.
