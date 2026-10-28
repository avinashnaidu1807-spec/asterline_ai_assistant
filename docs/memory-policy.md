# Asterline AI Research Assistant — Persistent Memory Policy

## 1. Purpose & Guiding Principles

The Asterline Research Assistant maintains persistent memory across sessions to personalize employee workflows without compromising safety or data integrity.

This policy establishes five non-negotiable principles:
1. **Per-User Isolation:** No user's memories may ever be viewed, queried, modified, or inferred by any other user.
2. **Documentary Non-Authoritativeness:** Stored memories and prior AI outputs are *never* treated as authoritative company truth. Company documentation in `corpus.jsonl` remains the sole ground truth.
3. **Sensitive Data Protection:** Credentials, secrets, tokens, passwords, and sensitive PII are strictly barred from persistent storage.
4. **User Agency & Verifiability:** Users retain complete authority to inspect, update, correct, and delete any memory stored about them.
5. **Traceable Provenance:** Memory updates and corrections preserve audit trails and backward pointers to the original records they modify.

---

## 2. Memory Taxonomy

All persisted memories are classified into one of five structured categories:

| Category | Description | Typical Retention | Example |
| :--- | :--- | :--- | :--- |
| `preferences` | User formatting, detail depth, or interaction style preferences. | Indefinite until modified | "Prefers concise bulleted summaries for technical overviews." |
| `user_context` | Role, team, technical skills, or regional work context. | Indefinite | "Staff infrastructure engineer specializing in distributed query engines." |
| `active_projects` | Ongoing initiatives, epics, or tasks currently being researched. | Active sprint / project duration | "Investigating warehouse export deduplication for Snowflake integration." |
| `decisions` | Explicit choices or architectural conclusions agreed during chat. | Project lifecycle | "Decided to adopt monotonic scheduler clocking to prevent INC-2026-03 recurrence." |
| `conversation_summaries` | Condensed semantic recap of multi-turn research sessions. | 90 days rolling | "Discussed Launch tier ingestion limits (300 rps) vs Team tier (1500 rps)." |

---

## 3. Storage Policies & Screening

Before any memory is written to the database, it must pass through the `should_store()` policy pipeline:

### 3.1 Sensitive Data Screening
The system executes regular expression screening across all candidate text:
* API keys (`sk-[A-Za-z0-9-_]{20,}`)
* Bearer authentication tokens (`Bearer [A-Za-z0-9\-._~+/]+=*`)
* Passwords and credentials (`(?i)(password|secret|api_key|token|credential)\s*[:=]\s*\S+`)
* Private cryptographic keys (`(?i)private[_\s]?key`)
* Credit card numbers and payment tokens

If any sensitive pattern matches, `should_store()` immediately returns `(False, "Content contains sensitive data")` and the write is rejected.

### 3.2 AI Documentation Non-Authoritativeness Screening
User memories must capture *user context*, not company documentation. If content starts with or contains documentary assertion markers:
* `"according to the documentation"`
* `"based on the evidence"`
* `"sources indicate"`
* `"as stated in"`

The content is rejected from memory persistence to prevent AI hallucinations from calcifying into permanent memory.

### 3.3 Redundancy Screening
Candidate memories are compared against existing active memories in the same category using word-level Jaccard similarity. If similarity $\ge 0.75$, the write is rejected as redundant.

---

## 4. Updates, Corrections & Provenance Chains

When a user provides updated or contradictory personal context (e.g. "Actually, my primary timezone is now US Eastern EST time"):
1. **Detection:** The `detect_correction()` heuristic recognizes correction cues (`actually`, `correction:`, `to clarify`, `wrong`, `changed to`, `is now`).
2. **Matching:** It identifies the corresponding existing active memory with the highest keyword overlap ($\ge 0.35$).
3. **Status Transition:** The old memory's status is updated from `active` to `corrected`.
4. **Provenance Tracking:** The new memory is created with `status="active"` and a provenance pointer `provenance="correction_of:<old_memory_id>"`.
5. **Auditability:** The complete history remains auditable in the database while only active memories are injected into future conversational context.

---

## 5. Deletion & Forget Requests

The system supports both natural language forget requests and UI-driven management:

### Natural Language Forget
* User prompts like *"Please forget about my staging credentials"* or *"Don't remember my home address"* are parsed by `detect_forget_request()`.
* The Memory Management Agent converts these requests into declarative `DELETE` operations matching the subject keywords.
* Matching memories are marked as `status="forgotten"` or purged.

### UI-Driven Control
* **Edit/Correct Modal:** Users can manually edit any memory in the frontend Memory Manager page (`/memory`).
* **Forget Button:** Single-click deletion for individual memories.
* **Forget All Modal:** Allows complete erasure of all memories belonging to the active user with explicit confirmation.

---

## 6. Zero Cross-User Leakage Guarantee

To prevent cross-tenant data contamination:
* Every database query in `repository.py` strictly binds the current `user_id`:
  ```sql
  SELECT * FROM memories WHERE user_id = :user_id AND status = 'active'
  ```
* Any attempt by User B to access, update, or delete a memory with UUID belonging to User A fails with `Memory not found or not owned by user`.
* Cross-user isolation is enforced by automated tests in `test_memory.py` and `test_edge_cases.py` (Case I).

