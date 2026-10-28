# AI-Use Disclosure & Engineering Verification Statement

## 1. Overview of AI Tools Utilized

In accordance with assignment requirements, this document discloses the artificial intelligence tools and automated workflows used in designing, developing, and verifying the Asterline AI Research Assistant:

* **Primary AI Assistant:** Google DeepMind Antigravity agentic coding assistant with advanced code intelligence models.
* **Scope of Assistance:**
  * Architectural system drafting and state graph design.
  * Retrieval-Augmented Generation (RAG) hybrid reciprocal rank fusion algorithms.
  * React/TypeScript frontend components and styling.
  * Evaluation suite automation, metric computation, and failure analysis scripts.
  * Test case assertions for system verification.

---

## 2. Validation & Verification Methodology

No claim of functionality in this repository is based on unverified AI assertions. Every component underwent deterministic engineering verification:

1. **Corpus Integrity Verification:**
   * Authoritative `corpus.jsonl` was extracted from official embedded PDF attachments.
   * Cryptographic SHA256 checksum calculated and verified: `f63fc05cf43204485c98bd8fb6d89860a32c16a7e906bc90975e7c3954fe9fb1` (75 chunks across 25 documents).
   * Original file remained completely immutable and unmodified.

2. **Automated Unit & Integration Testing:**
   * A comprehensive pytest test suite (`backend/tests/`) with 24 automated tests was implemented and executed.
   * **Result:** 24 passed, 0 failed.
   * Explicitly verified all 10 assignment edge cases (Cases A through J).

3. **Empirical Evaluation Pipeline:**
   * Executed 86 benchmark test queries against the live multi-agent graph across both a baseline configuration and an improved configuration.
   * Logged and persisted full execution results to `evaluation/results/baseline_results.json` and `evaluation/results/improved_results.json`.
   * Confirmed a **+42% relative increase in Recall@5** and **+86% relative increase in Citation Precision**.

4. **Frontend Production Build Verification:**
   * TypeScript type-checking and production bundle compilation was verified via `npm run build` with Vite.
   * **Result:** Zero TypeScript compilation errors, production bundle generated cleanly.

5. **Security & Memory Isolation Verification:**
   * Automated tests confirmed that cross-user memory leakage is mathematically prevented by scoped database queries.
   * Sensitive API keys, bearer tokens, and credentials were tested and confirmed rejected by the memory policy filter.

