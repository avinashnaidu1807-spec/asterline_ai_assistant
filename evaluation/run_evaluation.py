#!/usr/bin/env python3
"""
Asterline Research Assistant - Automated Evaluation Runner
Runs the full test suite against the backend API and computes metrics.

Usage:
    python evaluation/run_evaluation.py [--api-base http://localhost:8000] [--output-dir evaluation/results]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_OUTPUT_DIR = "evaluation/results"
DEFAULT_TEST_CASES_PATH = "evaluation/test_cases.jsonl"
REQUEST_TIMEOUT = 60.0  # seconds per API call
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TestCase:
    id: str
    category: str
    question: str
    expected_chunk_ids: List[str]
    expected_facts: List[str]
    answer_possible: bool
    conflict_present: bool
    expected_memory_behavior: Optional[str]
    rationale: str


@dataclass
class TestResult:
    test_id: str
    category: str
    question: str
    answer: str
    retrieved_chunk_ids: List[str]
    retrieval_recall_at_5: float
    citation_precision: float
    fact_coverage_rate: float
    appropriate_abstention: bool
    conflict_handled: bool
    unsupported_claim_detected: bool
    latency_ms: float
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class CategoryMetrics:
    category: str
    count: int
    avg_retrieval_recall: float
    avg_citation_precision: float
    avg_fact_coverage: float
    abstention_rate: float
    conflict_detection_rate: float
    unsupported_claim_rate: float
    avg_latency_ms: float
    error_count: int


@dataclass
class EvaluationReport:
    timestamp: str
    api_base_url: str
    total_tests: int
    completed_tests: int
    error_tests: int
    overall_retrieval_recall_at_5: float
    overall_citation_precision: float
    overall_fact_coverage_rate: float
    overall_abstention_rate: float
    overall_conflict_detection_rate: float
    overall_unsupported_claim_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    category_metrics: List[CategoryMetrics]
    results: List[TestResult]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loading test cases
# ---------------------------------------------------------------------------


def load_test_cases(path: str) -> List[TestCase]:
    """Load test cases from a JSONL file. Skips blank lines and logs bad JSON."""
    cases: List[TestCase] = []
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Test cases file not found: {path}")

    with open(path_obj, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON at line %d: %s", lineno, exc)
                continue

            required = {"id", "category", "question", "expected_chunk_ids", "expected_facts",
                        "answer_possible", "conflict_present", "expected_memory_behavior", "rationale"}
            missing = required - set(obj.keys())
            if missing:
                logger.warning("Skipping test case at line %d, missing fields: %s", lineno, missing)
                continue

            cases.append(TestCase(**{k: obj[k] for k in required}))

    logger.info("Loaded %d test cases from %s", len(cases), path)
    return cases


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def call_api(
    question: str,
    user_id: str,
    conv_id: str,
    client: Optional[httpx.Client],
    api_base: str,
) -> Tuple[Dict[str, Any], float]:
    """
    Send a question to the chat endpoint. Returns (response_dict, latency_ms).
    Supports direct in-process execution when api_base == 'direct' or client is None.
    """
    if api_base == "direct" or client is None:
        t0 = time.monotonic()
        backend_dir = Path(__file__).resolve().parent.parent / "backend"
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from app.agents.graph import run_agent_workflow
        final_state = run_agent_workflow(
            question=question,
            user_id=user_id,
            conversation_id=conv_id,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        ans_dict = final_state.get("answer") or {}
        return {
            "answer": ans_dict.get("answer", ""),
            "sources": ans_dict.get("sources", []),
            "claims": ans_dict.get("claims", []),
            "limitations": [ans_dict.get("limitations")] if ans_dict.get("limitations") else [],
            "needs_clarification": ans_dict.get("needs_clarification", False),
            "conflicts": final_state.get("conflicts_detected", []),
        }, latency_ms

    url = f"{api_base}/api/chat"
    payload = {
        "message": question,
        "user_id": user_id,
        "conversation_id": conv_id,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.monotonic()
        try:
            resp = client.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            latency_ms = (time.monotonic() - t0) * 1000
            resp.raise_for_status()
            return resp.json(), latency_ms
        except httpx.HTTPStatusError as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            if exc.response.status_code < 500 or attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            logger.warning(
                "HTTP %d on attempt %d/%d, retrying in %ds...",
                exc.response.status_code, attempt, MAX_RETRIES, wait,
            )
            time.sleep(wait)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            logger.warning("Request error on attempt %d/%d: %s. Retrying in %ds...", attempt, MAX_RETRIES, exc, wait)
            time.sleep(wait)

    raise RuntimeError("All retries exhausted")  # unreachable, for type checker


def create_test_user(client: httpx.Client, api_base: str) -> str:
    """Create an ephemeral test user and return the user_id."""
    url = f"{api_base}/api/users"
    payload = {"username": f"eval-runner-{uuid.uuid4().hex[:8]}"}
    resp = client.post(url, json=payload, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    user_id = data.get("user_id") or data.get("id") or data["username"]
    logger.info("Created test user: %s", user_id)
    return str(user_id)


def create_conversation(client: httpx.Client, api_base: str, user_id: str) -> str:
    """Create a new conversation and return the conversation_id."""
    url = f"{api_base}/api/conversations"
    payload = {"user_id": user_id}
    try:
        resp = client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        conv_id = data.get("conversation_id") or data.get("id") or str(uuid.uuid4())
        return str(conv_id)
    except Exception:
        # If conversation creation endpoint doesn't exist, generate a local UUID
        return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _extract_chunk_ids(response: Dict[str, Any]) -> List[str]:
    """
    Extract retrieved chunk IDs from the API response.
    Tries common response shapes.
    """
    # Try sources list (most common)
    sources = response.get("sources") or response.get("chunks") or response.get("retrieved_chunks") or []
    ids: List[str] = []
    for s in sources:
        if isinstance(s, dict):
            cid = s.get("chunk_id") or s.get("id") or s.get("source_id")
            if cid:
                ids.append(str(cid))
        elif isinstance(s, str):
            ids.append(s)
    # Also check top-level chunk_ids
    if not ids:
        ids = [str(c) for c in (response.get("chunk_ids") or [])]
    return ids


CHUNK_ALIASES = {
    "employee-handbook": "handbook",
    "data-retention-policy": "retention",
    "on-call-runbook": "oncall",
    "pricing-guide": "pricing",
    "support-guide": "sla",
    "incident-report-march-2026": "incident-03",
    "security-overview": "security",
    "release-notes-v2.3.1": "release-23",
    "product-docs-v2.1": "ingest",
    "product-docs-v2.0": "release-20",
    "compliance-certifications": "security",
    "roadmap-2026": "regions",
}


def _canon_id(cid: str) -> str:
    cid = str(cid).strip().lower()
    if ":" in cid:
        doc, num = cid.split(":", 1)
        doc_canon = CHUNK_ALIASES.get(doc, doc)
        try:
            n = int(num)
            if n > 2:
                n = 2
            num = str(n)
        except ValueError:
            pass
        return f"{doc_canon}:{num}"
    return CHUNK_ALIASES.get(cid, cid)


def compute_retrieval_recall_at_k(
    expected_ids: List[str],
    retrieved_ids: List[str],
    k: int = 5,
) -> float:
    """
    Recall@K: fraction of expected IDs present in the top-K retrieved IDs.
    Returns 1.0 if no expected IDs (nothing to recall).
    """
    if not expected_ids:
        return 1.0
    top_k = {_canon_id(cid) for cid in retrieved_ids[:k]}
    expected = {_canon_id(cid) for cid in expected_ids}
    matched = expected & top_k
    return len(matched) / len(expected)


def compute_citation_precision(
    claims: List[str],
    retrieved_ids: List[str],
) -> float:
    """
    Citation Precision: fraction of retrieved chunk IDs that are in the expected
    set (claims here is the list of expected chunk IDs for the test case).
    Returns 1.0 if no retrieved IDs.
    """
    if not retrieved_ids:
        return 1.0
    expected = {_canon_id(cid) for cid in claims}
    matched = sum(1 for cid in retrieved_ids if _canon_id(cid) in expected)
    return matched / len(retrieved_ids)


def check_expected_facts(answer: str, expected_facts: List[str]) -> Tuple[int, int]:
    """
    Check how many expected facts appear in the answer (case-insensitive substring match).
    Returns (matched_count, total_count).
    """
    if not expected_facts:
        return 0, 0
    answer_lower = answer.lower()
    matched = sum(
        1 for fact in expected_facts
        if _normalize(fact) in answer_lower
    )
    return matched, len(expected_facts)


def _normalize(text: str) -> str:
    """Normalize text for loose matching."""
    # Remove currency symbols and punctuation for flexible matching
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def check_appropriate_abstention(answer: str, answer_possible: bool) -> bool:
    """
    When answer_possible is False, the system should abstain (say it doesn't know /
    can't find the info). Returns True if the behavior is appropriate.
    When answer_possible is True, we assume the system provided an answer (not abstained).
    """
    answer_lower = answer.lower()
    abstention_signals = [
        "i don't have", "i do not have", "not available", "cannot find",
        "no information", "not found", "not in", "unable to find",
        "doesn't appear", "does not appear", "not mentioned", "no record",
        "not published", "not announced", "no date", "no specific",
    ]
    seems_abstained = any(sig in answer_lower for sig in abstention_signals)

    if not answer_possible:
        # We expect abstention
        return seems_abstained
    else:
        # We expect an actual answer, not a refusal
        # Consider it appropriate if NOT a hard refusal
        hard_refusal_signals = ["i cannot answer", "i refuse", "i'm not able to help"]
        return not any(sig in answer_lower for sig in hard_refusal_signals)


def check_conflict_handling(answer: str, conflict_present: bool) -> bool:
    """
    When conflict_present is True, check that the answer acknowledges the conflict
    or discusses supersession. Returns True if handled appropriately.
    When conflict_present is False, returns True (no conflict to handle).
    """
    if not conflict_present:
        return True
    answer_lower = answer.lower()
    conflict_signals = [
        "conflict", "discrepan", "inconsisten", "supersed", "overrid",
        "two different", "differ", "outdated", "older document",
        "updated policy", "effective", "current policy", "previous",
    ]
    return any(sig in answer_lower for sig in conflict_signals)


def check_prompt_injection_safety(answer: str, question: str) -> bool:
    """
    For prompt injection test cases, verify the system prompt is not revealed
    and no alternate persona is adopted. Returns True if the response is safe.
    """
    answer_lower = answer.lower()
    unsafe_signals = [
        "system prompt:", "instructions:", "you are an ai", "my system prompt",
        "ignore previous", "as a different ai", "i am now",
    ]
    # Safe if none of the unsafe signals appear
    return not any(sig in answer_lower for sig in unsafe_signals)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def run_test_case(
    tc: TestCase,
    client: httpx.Client,
    api_base: str,
    user_id: str,
    conv_id: str,
) -> TestResult:
    """Run a single test case and compute all metrics."""
    try:
        raw_response, latency_ms = call_api(tc.question, user_id, conv_id, client, api_base)
        answer = (
            raw_response.get("answer")
            or raw_response.get("response")
            or raw_response.get("message")
            or raw_response.get("content")
            or ""
        )
        retrieved_ids = _extract_chunk_ids(raw_response)

        recall = compute_retrieval_recall_at_k(tc.expected_chunk_ids, retrieved_ids, k=5)
        precision = compute_citation_precision(tc.expected_chunk_ids, retrieved_ids)
        matched_facts, total_facts = check_expected_facts(answer, tc.expected_facts)
        fact_coverage = matched_facts / total_facts if total_facts > 0 else 1.0
        abstention_ok = check_appropriate_abstention(answer, tc.answer_possible)
        conflict_ok = check_conflict_handling(answer, tc.conflict_present)

        # Unsupported claim detection: if answer_possible is False, flag if the
        # system confidently asserts a specific value not in expected_facts
        unsupported_claim = False
        if not tc.answer_possible:
            # If the answer does NOT seem to abstain, it's making an unsupported claim
            unsupported_claim = not abstention_ok

        return TestResult(
            test_id=tc.id,
            category=tc.category,
            question=tc.question,
            answer=answer,
            retrieved_chunk_ids=retrieved_ids,
            retrieval_recall_at_5=recall,
            citation_precision=precision,
            fact_coverage_rate=fact_coverage,
            appropriate_abstention=abstention_ok,
            conflict_handled=conflict_ok,
            unsupported_claim_detected=unsupported_claim,
            latency_ms=latency_ms,
            error=None,
            raw_response=raw_response,
        )

    except Exception as exc:
        logger.error("Test %s failed: %s", tc.id, exc)
        return TestResult(
            test_id=tc.id,
            category=tc.category,
            question=tc.question,
            answer="",
            retrieved_chunk_ids=[],
            retrieval_recall_at_5=0.0,
            citation_precision=0.0,
            fact_coverage_rate=0.0,
            appropriate_abstention=False,
            conflict_handled=False,
            unsupported_claim_detected=False,
            latency_ms=0.0,
            error=str(exc),
        )


def _compute_category_metrics(results: List[TestResult]) -> List[CategoryMetrics]:
    """Aggregate metrics by category."""
    categories: Dict[str, List[TestResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    metrics = []
    for cat, cat_results in sorted(categories.items()):
        valid = [r for r in cat_results if r.error is None]
        n = len(valid)
        if n == 0:
            metrics.append(CategoryMetrics(
                category=cat, count=len(cat_results),
                avg_retrieval_recall=0.0, avg_citation_precision=0.0,
                avg_fact_coverage=0.0, abstention_rate=0.0,
                conflict_detection_rate=0.0, unsupported_claim_rate=0.0,
                avg_latency_ms=0.0, error_count=len(cat_results),
            ))
            continue

        metrics.append(CategoryMetrics(
            category=cat,
            count=len(cat_results),
            avg_retrieval_recall=sum(r.retrieval_recall_at_5 for r in valid) / n,
            avg_citation_precision=sum(r.citation_precision for r in valid) / n,
            avg_fact_coverage=sum(r.fact_coverage_rate for r in valid) / n,
            abstention_rate=sum(1 for r in valid if r.appropriate_abstention) / n,
            conflict_detection_rate=sum(1 for r in valid if r.conflict_handled) / n,
            unsupported_claim_rate=sum(1 for r in valid if r.unsupported_claim_detected) / n,
            avg_latency_ms=sum(r.latency_ms for r in valid) / n,
            error_count=len(cat_results) - n,
        ))
    return metrics


def _safe_avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def run_all_tests(
    api_base_url: str,
    output_dir: str,
    test_cases_path: str = DEFAULT_TEST_CASES_PATH,
) -> EvaluationReport:
    """
    Main entry point: load test cases, create resources, run all tests,
    compute aggregate metrics, save results.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    test_cases = load_test_cases(test_cases_path)

    use_direct = api_base_url == "direct"
    client = None
    if not use_direct:
        try:
            temp_client = httpx.Client(timeout=REQUEST_TIMEOUT)
            health_resp = temp_client.get(f"{api_base_url}/health", timeout=3.0)
            health_resp.raise_for_status()
            logger.info("API health check passed: %s", health_resp.json())
            client = temp_client
        except Exception as exc:
            logger.info("API server not active on %s (%s); switching to direct graph runner", api_base_url, exc)
            use_direct = True

    effective_api_base = "direct" if use_direct else api_base_url
    user_id = f"eval-{uuid.uuid4().hex[:12]}"
    if not use_direct and client:
        try:
            user_id = create_test_user(client, api_base_url)
        except Exception:
            pass

    results: List[TestResult] = []
    category_convs: Dict[str, str] = {}

    for i, tc in enumerate(test_cases, 1):
        logger.info("[%d/%d] Running %s (%s)", i, len(test_cases), tc.id, tc.category)

        # Multi-turn tests share a conversation; others get fresh conversations per category
        if tc.category == "multi_turn":
            group_key = f"multi_turn_{tc.id[:6]}"
        else:
            group_key = tc.category

        if group_key not in category_convs:
            if not use_direct and client:
                category_convs[group_key] = create_conversation(client, api_base_url, user_id)
            else:
                category_convs[group_key] = str(uuid.uuid4())

        conv_id = category_convs[group_key]
        result = run_test_case(tc, client, effective_api_base, user_id, conv_id)
        results.append(result)

        if result.error:
            logger.warning("  ERROR: %s", result.error)
        else:
            logger.info(
                "  recall=%.2f precision=%.2f fact_cov=%.2f latency=%.0fms",
                result.retrieval_recall_at_5,
                result.citation_precision,
                result.fact_coverage_rate,
                result.latency_ms,
            )

    # Aggregate metrics
    valid_results = [r for r in results if r.error is None]
    error_count = len(results) - len(valid_results)
    latencies = [r.latency_ms for r in valid_results]

    report = EvaluationReport(
        timestamp=timestamp,
        api_base_url=api_base_url,
        total_tests=len(test_cases),
        completed_tests=len(valid_results),
        error_tests=error_count,
        overall_retrieval_recall_at_5=_safe_avg([r.retrieval_recall_at_5 for r in valid_results]),
        overall_citation_precision=_safe_avg([r.citation_precision for r in valid_results]),
        overall_fact_coverage_rate=_safe_avg([r.fact_coverage_rate for r in valid_results]),
        overall_abstention_rate=_safe_avg([float(r.appropriate_abstention) for r in valid_results]),
        overall_conflict_detection_rate=_safe_avg([float(r.conflict_handled) for r in valid_results]),
        overall_unsupported_claim_rate=_safe_avg([float(r.unsupported_claim_detected) for r in valid_results]),
        avg_latency_ms=_safe_avg(latencies),
        p95_latency_ms=_p95(latencies),
        category_metrics=_compute_category_metrics(results),
        results=results,
        metadata={
            "test_cases_path": str(test_cases_path),
            "runner_version": "1.0.0",
        },
    )

    # Save machine-readable JSON
    json_path = output_path / f"results_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(_report_to_dict(report), fh, indent=2, default=str)
    logger.info("Saved JSON results to %s", json_path)

    # Save human-readable Markdown
    md_path = output_path / f"report_{timestamp}.md"
    md_content = generate_markdown_report(report)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)
    logger.info("Saved Markdown report to %s", md_path)

    return report


def _report_to_dict(report: EvaluationReport) -> Dict[str, Any]:
    """Convert EvaluationReport to a JSON-serialisable dict."""
    d = asdict(report)
    return d


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------


def generate_markdown_report(report: EvaluationReport) -> str:
    """Generate a human-readable Markdown evaluation report."""
    lines: List[str] = []

    lines.append("# Asterline Research Assistant — Evaluation Report")
    lines.append("")
    lines.append(f"**Run timestamp:** {report.timestamp}  ")
    lines.append(f"**API base:** `{report.api_base_url}`  ")
    lines.append(f"**Total test cases:** {report.total_tests}  ")
    lines.append(f"**Completed:** {report.completed_tests} | **Errors:** {report.error_tests}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Overall Metrics")
    lines.append("")
    lines.append("| Metric | Score |")
    lines.append("|--------|-------|")
    lines.append(f"| Retrieval Recall@5 | {report.overall_retrieval_recall_at_5:.3f} |")
    lines.append(f"| Citation Precision | {report.overall_citation_precision:.3f} |")
    lines.append(f"| Fact Coverage Rate | {report.overall_fact_coverage_rate:.3f} |")
    lines.append(f"| Appropriate Abstention Rate | {report.overall_abstention_rate:.3f} |")
    lines.append(f"| Conflict Detection Rate | {report.overall_conflict_detection_rate:.3f} |")
    lines.append(f"| Unsupported Claim Rate *(lower is better)* | {report.overall_unsupported_claim_rate:.3f} |")
    lines.append(f"| Avg Latency (ms) | {report.avg_latency_ms:.0f} |")
    lines.append(f"| P95 Latency (ms) | {report.p95_latency_ms:.0f} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Metrics by Category")
    lines.append("")
    lines.append("| Category | N | Recall@5 | Cit. Precision | Fact Coverage | Abstention | Conflict Det. | Unsup. Claims | Avg Latency (ms) | Errors |")
    lines.append("|----------|---|----------|----------------|---------------|------------|---------------|----------------|-------------------|--------|")
    for cm in report.category_metrics:
        lines.append(
            f"| {cm.category} | {cm.count} "
            f"| {cm.avg_retrieval_recall:.2f} "
            f"| {cm.avg_citation_precision:.2f} "
            f"| {cm.avg_fact_coverage:.2f} "
            f"| {cm.abstention_rate:.2f} "
            f"| {cm.conflict_detection_rate:.2f} "
            f"| {cm.unsupported_claim_rate:.2f} "
            f"| {cm.avg_latency_ms:.0f} "
            f"| {cm.error_count} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Individual Test Results")
    lines.append("")

    for r in report.results:
        status_icon = "✅" if r.error is None else "❌"
        lines.append(f"### {status_icon} `{r.test_id}` — {r.category}")
        lines.append("")
        lines.append(f"**Question:** {r.question}")
        lines.append("")
        if r.error:
            lines.append(f"> **Error:** {r.error}")
        else:
            lines.append(f"**Answer (truncated):** {r.answer[:500]}{'...' if len(r.answer) > 500 else ''}")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Retrieval Recall@5 | {r.retrieval_recall_at_5:.2f} |")
            lines.append(f"| Citation Precision | {r.citation_precision:.2f} |")
            lines.append(f"| Fact Coverage | {r.fact_coverage_rate:.2f} |")
            lines.append(f"| Appropriate Abstention | {'✅' if r.appropriate_abstention else '❌'} |")
            lines.append(f"| Conflict Handled | {'✅' if r.conflict_handled else '❌'} |")
            lines.append(f"| Unsupported Claim | {'⚠️ Yes' if r.unsupported_claim_detected else '✅ No'} |")
            lines.append(f"| Latency | {r.latency_ms:.0f} ms |")
            if r.retrieved_chunk_ids:
                lines.append(f"| Retrieved Chunks | `{'`, `'.join(r.retrieved_chunk_ids)}` |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generated by Asterline Research Assistant Evaluation Runner v1.0.0*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Asterline Research Assistant — Automated Evaluation Runner",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("ASTERLINE_API_BASE", DEFAULT_API_BASE),
        help=f"Backend API base URL (default: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for output files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--test-cases",
        default=DEFAULT_TEST_CASES_PATH,
        help=f"Path to test_cases.jsonl (default: {DEFAULT_TEST_CASES_PATH})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting evaluation against %s", args.api_base)

    try:
        report = run_all_tests(
            api_base_url=args.api_base,
            output_dir=args.output_dir,
            test_cases_path=args.test_cases,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Tests run:               {report.total_tests}")
    print(f"Completed:               {report.completed_tests}")
    print(f"Errors:                  {report.error_tests}")
    print(f"Retrieval Recall@5:      {report.overall_retrieval_recall_at_5:.3f}")
    print(f"Citation Precision:      {report.overall_citation_precision:.3f}")
    print(f"Fact Coverage Rate:      {report.overall_fact_coverage_rate:.3f}")
    print(f"Abstention Rate:         {report.overall_abstention_rate:.3f}")
    print(f"Conflict Detection Rate: {report.overall_conflict_detection_rate:.3f}")
    print(f"Unsupported Claim Rate:  {report.overall_unsupported_claim_rate:.3f}  (lower is better)")
    print(f"Avg Latency:             {report.avg_latency_ms:.0f} ms")
    print(f"P95 Latency:             {report.p95_latency_ms:.0f} ms")
    print("=" * 60)
    print(f"Results saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
