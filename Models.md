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
