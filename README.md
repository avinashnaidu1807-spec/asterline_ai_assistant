# Asterline AI Research Assistant

> **Enterprise Multi-Agent Research Assistant with Local Hybrid Retrieval, Persistent Per-User Memory Isolation, and LangSmith Observability.** Built for Asterline Labs.

[![Python Tests](https://img.shields.io/badge/pytest-24%20passed-brightgreen)](#automated-testing)
[![Frontend Build](https://img.shields.io/badge/Vite%20%2B%20TypeScript-passing-brightgreen)](#frontend)
[![Corpus Chunks](https://img.shields.io/badge/Corpus%20Integrity-75%20chunks%20%2F%2025%20docs-blue)](#authoritative-knowledge-base)
[![Paid Services](https://img.shields.io/badge/Paid%20Services-None%20Required-success)](#zero-cost-local-execution)

---

## 1. Quick Start: Single-Command Launch

Launch the full application (FastAPI backend + Vite React frontend + SQLite + ChromaDB) with a single command:

### On Windows (PowerShell):
```powershell
.\start.ps1
```

### On Linux / macOS:
```bash
chmod +x start.sh
./start.sh
```

Once started:
* **Web Application:** [http://localhost:5173](http://localhost:5173)
* **Interactive API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **System Health Endpoint:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 2. Key Capabilities & Architectural Highlights

1. **Authoritative Knowledge Base (Immutable):**
   * Pre-indexed with all 75 chunks across 25 documents from the authentic `corpus.jsonl` (SHA256: `f63fc05cf43204485c98bd8fb6d89860a32c16a7e906bc90975e7c3954fe9fb1`).
   * The original corpus is preserved unchanged.

2. **100% Free / Local Execution:**
   * **Dense Embeddings:** Local ONNX runtime using `all-MiniLM-L6-v2` (384 dimensions) with ~4ms CPU inference. No PyTorch binary blocks or GPU needed.
   * **Vector Store:** Embedded ChromaDB database persisted locally in `./data/chroma_db`.
   * **Generation Mode:** Built-in deterministic grounded synthesis engine out of the box with zero paid API keys required. Optional support for OpenAI (`gpt-4o-mini`) and Ollama local models (`llama3.2:3b`).

3. **Genuine 4-Agent LangGraph System:**
   * **Research Agent:** Performs Reciprocal Rank Fusion (RRF) between semantic search and lexical term matching with domain query expansion.
   * **Verification & Conflict Resolution Agent:** Analyzes evidence specificity, version applicability, and explicit temporal supersession (not just newest document).
   * **Memory Management Agent:** Screens candidate user preferences and facts, rejects sensitive credentials and transient AI outputs, and manages corrections and forget operations.
   * **Synthesis Agent:** Produces grounded markdown answers citing exact `chunk_id`s, titles, and versions, highlighting missing documentation or ambiguities.

4. **Persistent Per-User Memory Isolation:**
   * Persistent SQLite database (`./data/asterline.db`) storing users, conversations, messages, and memories.
   * **Strict Isolation:** Every query enforces user ownership filtering. User A's memories are mathematically isolated from User B.
   * **Correction Chains & Provenance:** Updating a preference sets prior memories to `corrected` and preserves backward audit pointers.
   * **User Agency:** Full support for inspecting, adding, editing, and single-click / natural language "forget" requests.

5. **LangSmith Tracing & Observability:**
   * Full tracing for agent execution steps, input queries, retrieved chunks, verification reasoning, and memory writes.
   * Designated sharing recipient: **`radialpulse@nxtwave.co.in`**.

---

## 3. System Architecture

```
User Browser (React + Vite + TypeScript)
  │
  ▼ [HTTP REST]
FastAPI Gateway (Port 8000)
  │
  ├─► [LangGraph Multi-Agent Orchestration]
  │     1. Load Context Node (SQLite active memories + conversation history)
  │     2. Research Agent (Hybrid ONNX dense + lexical search)
  │     3. Verification Agent (Supersession & conflict resolution)
  │     4. [Conditional Retry] Additional Retrieval Node
  │     5. Synthesis Agent (Grounded answer generation + documentary citations)
  │     6. Memory Decision Agent (Safety screening & candidate extraction)
  │     7. Memory Persist Node (Transactional SQLite write with user scoping)
  │
  ├─► [Persistent Storage]
  │     • ChromaDB: 75 authoritative corpus chunks (local cosine index)
  │     • SQLite: Multi-user relational schema with foreign key constraints
  │
  └─► [LangSmith Observability]
        • Automated RunTree traces exported to project 'asterline-research-assistant'
```

---

## 4. Manual Setup & Configuration

### Prerequisites
* Python 3.10+ (tested on Python 3.11, 3.12, 3.14)
* Node.js 18+ and npm

### Backend Setup
```bash
cd asterline-research-assistant/backend

# Create .env from template
copy .env.example .env     # On Windows
# cp .env.example .env     # On Linux/macOS

# Install backend dependencies
pip install -r requirements.txt

# Verify setup
python ../scripts/check_setup.py

# Launch backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```bash
cd asterline-research-assistant/frontend

# Install dependencies
npm install

# Build production bundle (or run dev server)
npm run build
npm run dev -- --port 5173
```

---

## 5. LangSmith Tracing Setup & Project Sharing

To enable real-time observability in your LangSmith dashboard:

1. Open your `.env` file (in `backend/` or workspace root).
2. Configure your LangSmith credentials:
   ```env
   LANGSMITH_API_KEY=lsv2_pt_your_langsmith_api_key_here
   LANGSMITH_PROJECT=asterline-research-assistant
   LANGCHAIN_TRACING_V2=true
   ```
3. Start the application. All agent workflow runs will stream live traces to LangSmith.
4. **Project Sharing Instructions:**
   * Navigate to [smith.langchain.com](https://smith.langchain.com).
   * Open the project: `asterline-research-assistant`.
   * Click **Settings** (gear icon) $\rightarrow$ **Members** / **Sharing**.
   * Add **`radialpulse@nxtwave.co.in`** with Viewer or Collaborator access.

---

## 6. Automated Testing & Evaluation

### Run Automated Unit & Edge-Case Tests (24/24 Passing)
```bash
cd asterline-research-assistant/backend
python -m pytest tests/ -v
```

This suite verifies:
* **ChromaDB Integrity:** 75 chunks indexed across 25 documents.
* **Agent Isolation:** Independent unit tests for Research, Verification, Synthesis, and Memory agents.
* **Memory Safety & Isolation:** Zero cross-user leakage, credential screening, and correction flows.
* **Edge Cases A through J:**
  * **Case A:** On-call stipend ($175 weekday / $250 weekend superseding outdated $140).
  * **Case B:** Cold disaster recovery RTO (60 days vs 20 days).
  * **Case C:** Launch tier ingestion limits (300 rps sustained / 450 rps burst vs 180 rps).
  * **Case D:** Patch 2.1.2 warehouse deduplication cleanup.
  * **Case E:** March 2026 incident delayed alerts due to queue backlog/drift (not lost).
  * **Case F:** Abstention / lack of coverage for unannounced APAC region.
  * **Case G:** Distinct retention tiers (14-day explorer, 90-day searchable, 540-day archive).
  * **Case H:** Enterprise custom negotiated pricing.
  * **Case I:** Strict user memory isolation.
  * **Case J:** Sensitive API key, bearer token, and password rejection.

### Run Automated Evaluation Benchmark (86 Test Cases)
```bash
python asterline-research-assistant/evaluation/run_evaluation.py --baseline
```

Results are saved to `evaluation/results/` and demonstrate a **+42% relative improvement in Recall@5** and **+86% improvement in Citation Precision** over the baseline.

---

## 7. Project Documentation Directory

| Document | Description |
| :--- | :--- |
| [`docs/architecture.md`](docs/architecture.md) | In-depth architectural design, agent state lifecycles, and Mermaid diagrams. |
| [`docs/design-decisions.md`](docs/design-decisions.md) | Technical trade-off analysis (ONNX vs PyTorch, sync SQLite vs aiosqlite, RRF). |
| [`docs/memory-policy.md`](docs/memory-policy.md) | Persistent memory taxonomy, write policies, safety screening, and isolation guarantees. |
| [`docs/failure-analysis.md`](docs/failure-analysis.md) | Baseline vs improved benchmark results, failure root causes, and measured gains. |
| [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) | AI-use disclosure statement and verification methodology. |

---

## 8. Synthetic Seed Users

Three synthetic users are pre-configured in SQLite:
* `alice_chen` (Alice Chen) — Platform Infrastructure Engineer
* `bob_kumar` (Bob Kumar) — Data Pipeline & Warehouse Engineer
* `carol_reyes` (Carol Reyes) — Operations & Incident Manager

Switch between users in the top-left sidebar to observe how each user's memories, conversation history, and context remain strictly isolated.

