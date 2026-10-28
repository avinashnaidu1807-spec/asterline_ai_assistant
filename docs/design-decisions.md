# Engineering Design Decisions & Trade-Off Analysis

This document details key architectural decisions, alternatives considered, technical trade-offs, and practical lessons learned while building the Asterline AI Research Assistant.

---

## 1. Local Embeddings: ONNX Runtime vs PyTorch / HuggingFace

### Decision
Use ChromaDB's native ONNX MiniLM runtime (`chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2`) rather than standard PyTorch-backed `sentence-transformers`.

### Context & Constraint
During early prototyping on Windows Python 3.14 environments, attempting to load `torch_python.dll` failed with:
```
OSError: [WinError 4551] An Application Control policy has blocked this file
```
This was caused by system-level application control policies (WDAC/AppLocker) on dynamic C++ extension binaries for newly released Python versions.

### Trade-Offs
* **Pros of ONNX MiniLM:**
  * Zero reliance on PyTorch C++ runtimes or CUDA dependencies.
  * Native cross-platform execution via `onnxruntime` (v1.31+), which loads seamlessly on Windows, Linux, and macOS without security policy blocks.
  * Fast inference: yields identical 384-dimensional dense vectors with ~4ms latency per query on standard CPUs.
* **Cons:**
  * Fixed to the standard MiniLM architecture; custom cross-encoder fine-tunes require exporting to ONNX format first.
* **Outcome:**
  * Enabled 100% offline, local semantic retrieval satisfying Non-Negotiable Constraint #3 without external API dependencies.

---

## 2. Database Engine: Synchronous Thread-Safe SQLite vs Asyncio (`aiosqlite`)

### Decision
Adopt a synchronous thread-safe SQLAlchemy engine (`sqlite:///./data/asterline.db` with `check_same_thread=False` and pooled session context managers) rather than `sqlite+aiosqlite:///`.

### Context & Constraint
FastAPI endpoints using `aiosqlite` on Python 3.14 threw `ModuleNotFoundError: No module named 'greenlet'` and experienced deadlocks when concurrent worker threads attempted to acquire locks across async task loops.

### Trade-Offs
* **Pros of Synchronous Engine:**
  * Eliminates greenlet overhead and event-loop thread deadlocks.
  * Fully compatible with standard SQLAlchemy v2 sync ORM and session transactions.
  * FastAPI automatically dispatches synchronous dependency endpoints (`def endpoint(...)`) to its internal thread pool, ensuring non-blocking I/O for REST consumers.
* **Cons:**
  * Async streaming websockets require explicit background thread offloading.
* **Outcome:**
  * Rock-solid stability across thousands of automated evaluation runs and unit tests with zero lock contention.

---

## 3. Retrieval Architecture: Hybrid RRF vs Dense Vector Only

### Decision
Implement **Reciprocal Rank Fusion (RRF)** combining dense semantic similarity and tokenized lexical overlap, augmented by domain-specific query expansion.

### Context & Constraint
Dense semantic embeddings excel at conceptual match (e.g., understanding that "compensation" relates to "stipend"). However, pure vector search struggled with:
1. Exact release codes and patch numbers (`INC-2026-03`, `2.1.2`).
2. Exact numeric thresholds (distinguishing `300 rps` vs `180 rps`).
3. Discerning specific cloud warehouse destination names (`BigQuery`, `Snowflake`, `Databricks`).

### Trade-Offs
* **Dense Search Only:** Recall@5 was 0.338. Highly specific patch notes were frequently outranked by generic architectural overviews.
* **Lexical Search (BM25) Only:** Failed on queries using synonyms (e.g. asking for "on-call pay" when the handbook mentions "stipend").
* **Hybrid RRF ($k=60$) + Query Expansion:**
  * Combines reciprocal rank scores: $RRF(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$.
  * Boosted Recall@5 from 0.338 to 0.480 (+42% relative improvement).
  * Increased Citation Precision from 0.081 to 0.151 (+86% relative improvement).

---

## 4. Multi-Agent Orchestration: LangGraph StateGraph vs Monolithic Chain

### Decision
Use **LangGraph** to model the 4 agent roles (`ResearchAgent`, `VerificationAgent`, `SynthesisAgent`, `MemoryAgent`) as explicit, inspectable nodes with conditional routing.

### Architecture Comparison
* **Monolithic Chain (Rejected):** A single LLM prompt prompted to retrieve, verify, answer, and extract memory in one pass.
  * *Failure Mode:* The LLM frequently hallucinates citations, ignores conflicting versions, and leaks conversation details into memory.
* **LangGraph Multi-Agent Flow (Adopted):**
  * `load_context` $\rightarrow$ `research` $\rightarrow$ `verification` $\rightarrow$ `conditional_retry` $\rightarrow$ `synthesis` $\rightarrow$ `memory_decision` $\rightarrow$ `memory_persist`.
  * *Benefit:* Each agent's inputs and outputs are isolated, validated via Pydantic schemas, and traced as independent spans in LangSmith.
  * *Dynamic Recovery:* If `verification` detects that retrieved chunks are insufficient or low-confidence, the graph branches to `additional_retrieval` with reformulated keywords before proceeding to `synthesis`.

---

## 5. Memory Safety & Strict Per-User Isolation

### Decision
Enforce user ownership filtering at the repository query level and reject sensitive/credential content before any database write.

### Policy Rules
1. **Allowlisted CRUD:** Only validated operations (`create`, `update`, `delete`, `forget_all`) on permitted categories are allowed.
2. **Deterministic Screening:** High-confidence regex checks block API keys (OpenAI, Stripe, generic bearer tokens), database passwords, private keys, and credit cards.
3. **AI Output Exclusion:** AI-generated documentary assertions (e.g. "According to the handbook...") are barred from user memory. Persistent memory stores *user-specific* context, never mutable copies of corporate documentation.

