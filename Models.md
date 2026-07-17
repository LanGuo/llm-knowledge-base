# LLM Model Comparison: Technical Specifications & Test Results

This document records the technical facts and observed performance of the models evaluated for the LKB system.

---

## 📊 Technical Comparison Matrix

| Model | Provider | Context Window | Native Tool-Calling | Native JSON Mode | Test Result (LKB Sync) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gemini 2.5 Flash** | Google API | 1,000,000 | Yes (Full) | Yes | **Success.** High reliability; handled 70+ files effortlessly. |
| **OLMo-3 7B Think** | Ollama | 65,536 | No (per Ollama) | **Yes (Robust)** | **Success.** High-fidelity extraction via reasoning step + JSON mode. |
| **Gemma4:e4b** | Ollama | 128,000 | Yes (Partial) | **Yes (Robust)** | **Inconsistent.** Prone to timeouts on long-context tasks. |
| **Gemma3:12b** | Ollama | 32,768 | No (per Ollama) | **Yes (Robust)** | **Success.** Works via JSON mode despite lack of tool-use metadata. |

---

## 🔍 Key Technical Findings

### 1. Native JSON Mode vs. Tool-Calling
*   **Tool-Calling (Previous Approach):** Requires a specialized "Metadata Handshake." If the model's Ollama template lacks tool logic, the API rejects the request.
*   **Native JSON Mode (Current Approach):** Bypasses the tool handshake by using the **official Ollama Python library** instead of the generic OpenAI SDK. By passing the Pydantic schema directly to Ollama's `format` parameter, we utilize **Grammar-Based Sampling** to force valid output while avoiding strict OpenAI-SDK validation errors (like the `finish_reason: null` bug). This is the **most robust** way to get structured data from local models.

### 2. Context & Reasoning Overhead
*   **Reasoning Models (Think):** Models like OLMo-3 7B Think perform an internal reasoning step before outputting JSON. This significantly improves graph weaving and metadata accuracy but increases processing time.
*   **Timeout Solution:** Local models require a more generous timeout (**20 minutes**) when processing large research papers under strict JSON constraints.

### 3. File Naming & Deduplication
*   **Design Decision:** We use **Source-Based Filenaming** (e.g., `paper_name.md`) instead of LLM-generated titles. This ensures that switching between models (e.g., comparing Gemini and OLMo outputs) results in clean overwrites rather than duplicate files.

---

## 🛠 Lessons Learned
*   **The "Harness" is the Key:** Local model capability is often limited by the serving harness template rather than the model weights. JSON Mode provides a universal bridge for structured output.
*   **Privacy/Performance Trade-off:** Local models offer 100% privacy and zero API costs but require significant hardware time for long-context reasoning compared to cloud-based Flash models.

---

## 🐛 Known Issue: Gemma4:e4b "Gatsby" Hallucination

During a 119-paper bulk sync (AwesomeOPD corpus, 2026-07-15/16), `gemma4:e4b` produced a completely unrelated, fully-formed summary of **F. Scott Fitzgerald's *The Great Gatsby*** for 3 of 119 papers (2.5%), instead of summarizing the actual paper text it was given. This was not a crash or a malformed-JSON failure — the model returned syntactically valid JSON matching the `WikiArticle` schema, populated with confident, internally-consistent (but entirely wrong) content.

### Affected papers
| arXiv ID | Actual paper | Extracted text |
| :--- | :--- | :--- |
| 2602.12222 | *Towards On-Policy SFT: Distribution Discriminant Theory and its Applications in LLM Training* (Zhang, Liu, et al.) | 106,738 chars, clean |
| 2603.19220 | *Nemotron-Cascade 2: Post-Training LLMs with Cascade RL and Multi-Domain On-Policy Distillation* (Yang, Liu, Chen, et al., NVIDIA) | 181,155 chars, clean |
| 2604.00626 | *A Survey of On-Policy Distillation for Large Language Models* (Song & Zheng, Tencent) | 411,015 chars, clean |

### Input (excerpt, 2602.12222)
```
Towards On-Policy SFT: Distribution Discriminant Theory
and its Applications in LLM Training
Miaosen Zhang * 1 2 Yishan Liu * 1 3 Shuxia Lin 1 Xu Yang 1 Qi Dai 2 Chong Luo 2
Weihao Jiang 3 Peng Hou 3 Anxiang Zeng 3 Xin Geng 1 Baining Guo 1 2
Abstract
Supervised fine-tuning (SFT) is computationally
efficient but often yields inferior generalization
compared to reinforcement learning (RL). ...
```

### Output (gemma4:e4b, 2602.12222 — after full daemon restart, clean state)
```json
{
  "title": "The Great Gatsby",
  "authors": ["F. Scott Fitzgerald"],
  "affiliation": null,
  "date_published": "1925",
  "journal_or_conference": null,
  "summary": "A story of the American Dream, illusion, and decay, set in the wealthy summer enclave of Long Island. Narrated by Nick Carraway, it follows his neighbor, Jay Gatsby, a mysterious millionaire who throws extravagant parties hoping to recapture a lost love—Daisy Buchanan. The novel explores themes of class disparity, nostalgia, moral corruption, and the impossibility of repeating the past.",
  "tags": ["American Literature", "Jazz Age", "Tragedy", "Social Commentary", "Romance"]
}
```

For 2604.00626 the model went further, hallucinating an author list of the novel's *characters* (`Nick Carraway, Jay Gatsby, Daisy Buchanan, Tom Buchanan, Jordan Baker`) and a `Related Concepts` list (`The American Dream (and its corruption)`, `Old Money vs. New Money`, ...) — fully in the shape the pipeline expects, just about the wrong document entirely.

### What it wasn't
Each of these was ruled out before concluding it's a model-level failure mode:
- **Not a PDF-extraction bug** — text was cleanly extracted (title, authors, abstract all present and readable) for all 3 papers.
- **Not concurrency/cross-request contamination** — reprocessing the same paper alone (`sync_parallelism`/`OLLAMA_NUM_PARALLEL` effectively 1, no other in-flight requests) reproduced the exact same failure.
- **Not stale server-side cache** — fully restarting the Ollama daemon (killing `llama-server` and `ollama serve`, clearing all in-memory state/checkpoints) and retrying still reproduced Gatsby for the same input, in the first two attempts. *(Correction below: a third fresh-restart attempt broke this pattern — see "Follow-up" section. The failure is not actually deterministic; two data points made it look that way.)*
- **Not a prompt injection in the source PDF** — the extracted text contains no mention of "Gatsby," "Fitzgerald," or any instruction-override phrasing (`ignore previous`, `disregard`, `you are now`, etc.). The one hit for "system prompt" was the paper legitimately describing its own self-distillation baseline methodology.

### Working theory
~~The failure is deterministic given the exact input (same paper → same wrong output, across a full server restart)~~ — **this turned out to be wrong, see "Follow-up" below; only two data points supported it.** What still holds: this points to something in how local models handle long/dense input under **grammar-constrained JSON decoding** (`format=<schema>` via the Ollama Python client). *The Great Gatsby* is an extremely common "summarize this document" example text in LLM instruction-tuning and evaluation corpora (public domain, frequently used in tutorials/benchmarks for summarization tasks). The leading hypothesis is that when the constrained sampler struggles to stay grounded in a long, dense, technical input, the model falls back to a strongly memorized completion pattern associated with "document summarization" prompts in general, rather than actually failing loudly.

### Update: this is not a `gemma4:e4b`-specific bug
Switching model wasn't a clean fix. Re-running the identical prompts against **`gemma3:12b`** corrected **2602.12222** on the first try (correct title/authors/summary), but produced *different*, still-wrong, hallucinated content for the other two:
- **2603.19220** ("Nemotron-Cascade 2...") → titled **"Grading of Model Proof"**, a fabricated summary of grading a geometry/coordinate proof. Nothing in the source resembles this.
- **2604.00626** ("A Survey of On-Policy Distillation...") → titled **"On-Policy Distillation Across Modalities"**, topically plausible (same general subject area) but not the actual paper — this document is 411,015 chars ≈ **~103K tokens**, which exceeds the pipeline's hardcoded `num_ctx=65536` (`agent.py::_compile_ollama`), so genuine context truncation is a likely direct cause here specifically.

Escalating further to **`gemma4:31b`** (largest local model available, 21GB) with a bumped `num_ctx` (up to 200K) made things worse, not better: on **2603.19220** (only 45K tokens — comfortably within *any* of these models' context windows) it entered a runaway generation loop, decoding **29,000+ tokens** (vs. the normal 1,000–3,000 for a `WikiArticle`) before being killed manually; decode speed also degraded from ~6.7 tok/s to ~1.9 tok/s as the ballooning context slowed each step. This was not "a very thorough answer" — it never produced a valid stop condition.

So across 3 local models (8B, 12B, 31B) tested on these 2 remaining papers, **bigger model ≠ more reliable** here. `gemma3:12b`'s output for 2604.00626 is our best available result (on-topic, schema-valid, just not verified against the true title) but 2603.19220 has no correct compiled article as of this writing — the actual paper (Nemotron-Cascade 2) is only available via its raw PDF in `raw/distillation/`.

### Working theory (revised)
Not a single-model quirk — this looks like a general failure mode of small-to-mid local models under **grammar-constrained JSON decoding** on long, dense technical documents: when the constrained sampler can't stay grounded, it falls back to *some* strongly memorized completion pattern rather than failing loudly. Which pattern it falls back to (Gatsby, a geometry proof grading rubric, a plausible-sounding but fabricated paper) appears to vary by model and possibly by exact input length/content — none of it is directly traceable to the source document.

### Resolution
Switching to **`gemini-2.5-flash`** (cloud, via the existing `pydantic-ai` path in `agent.py`) correctly identified and summarized both remaining papers on the first try — including the full 17-author list for Nemotron-Cascade 2 (NVIDIA) and the correct authors/affiliation/date for the Tencent survey (2604.00626), the one that had exceeded the local pipeline's `num_ctx=65536` cap. All 119/119 articles are now correctly compiled. Net takeaway: for documents that push against a local model's practical context/reasoning limits, cloud fallback is more reliable than escalating local model size — 8B → 12B → 31B *didn't* monotonically improve results (31B was worse, entering a runaway generation loop), while a single cloud call resolved both remaining cases cleanly.

### Follow-up: length is the real signal, and it's stochastic not deterministic
After the KB was complete, went back and checked what actually distinguished these 3 papers from the other 116 that compiled fine on the first try. Ran every paper's page count and character length through the same extractor and ranked all 119:

| Paper | Pages | Chars | Rank by length (of 119) |
| :--- | :--- | :--- | :--- |
| 2604.00626 | 89 | 411,015 | **#1 (longest in the whole corpus)** |
| 2603.19220 | 63 | 181,155 | **#2 (second-longest)** |
| 2602.12222 | 40 | 106,738 | #13 (top 11%) |

Corpus median: 68,677 chars / 21 pages. **All three failures are above the median, and two of them are literally the single longest and second-longest documents out of 119** — not a subtle correlation.

Checked and ruled out author count as a confound: 2604.00626 (the #1 longest and most failure-prone) has only **2** authors — the fewest of the three — while 2603.19220 has 17 and 2602.12222 has 11. No consistent pattern; length correlates, author count doesn't.

**Then re-ran a third fresh-Ollama-restart test on all three with `gemma4:e4b`, one at a time, to directly answer "does a clean restart fix it":**
- **2602.12222** (rank #13) → **correct this time** ("Towards On-Policy SFT..."), after failing twice previously.
- **2603.19220** (rank #2) → still wrong, but a *third distinct* hallucination: **"The Art of the Impossible: A Guide to Creative Problem Solving"** — not Gatsby, not the geometry-proof story from the `gemma3:12b` run either.
- **2604.00626** (rank #1) → Gatsby again.

This directly overturns the earlier "deterministic given the exact input" claim (which was based on only two data points, both Gatsby). It's **stochastic**: the two most extreme-length documents fail consistently across independent attempts, the moderately-long one is more of a coin flip, and *which* fake document gets hallucinated varies each time — it isn't "this input always triggers Gatsby specifically," it's "under length/context stress the model confidently generates some plausible-sounding fake document, and which one comes out is close to random."

### Takeaway for future syncs
This class of failure — syntactically valid, schema-compliant, but *semantically unrelated* output — silently passes the pipeline's existing quality gate (`clean_wiki`'s "Extraction Error" / "Missing Content" filename check), since the model never signals a problem, and it is **not reliably fixed by retrying or switching models** — each attempt can produce a *different* wrong answer, and even a plain retry of the same model/input isn't guaranteed to repeat the same failure. Mitigations that actually help:
1. Spot-check compiled articles' `source:`/title fields after a bulk sync (`grep -h "^source:" *.md | sort | uniq -c`) to catch duplicate/repeated titles.
2. For any flagged article, diff the compiled title against the source filename/known paper list — don't assume a differently-wrong retry means "fixed," and don't assume a same-model retry that succeeds means the underlying risk is gone.
3. **Document length is the strongest predictor found so far** — papers in the top few percent by length (here: >~100K+ chars) are meaningfully more likely to trigger this, independent of author count or any other checked factor. Documents near or over `num_ctx` (~65K tokens here) are an even harder risk factor and should either be chunked or run with a model/context configuration that actually fits the full text.
4. Treat "raw PDF in `raw/distillation/`" as the ground-truth fallback for any paper whose compiled article can't be trusted — full text is preserved regardless of compilation outcome.
