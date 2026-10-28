# Automated Evaluation Framework

This directory contains the reproducible benchmark suite for the Asterline AI Research Assistant.

## 1. Files & Directory Structure

* `test_cases.jsonl`: 86 representative evaluation test cases covering factual queries, multi-chunk synthesis, version comparisons, temporal supersession, conflict resolution, edge cases, and prompt injection safety.
* `run_evaluation.py`: Automated evaluation harness. Executes queries against the research graph, evaluates retrieval Recall@5, Citation Precision, Fact Coverage, Abstention Rate, Conflict Detection, and Latency, and saves structured JSON reports.
* `results/`: Contains evaluation run artifacts:
  * `baseline_results.json`: Baseline evaluation metrics prior to query expansion and dynamic retrieval.
  * `improved_results.json`: Post-improvement evaluation metrics demonstrating a **+42% relative improvement in Recall@5** and **+86% improvement in Citation Precision**.

## 2. Running the Evaluation Suite

### Run with Direct In-Process Graph Execution (Default / Offline):
```bash
python evaluation/run_evaluation.py --baseline
```

### Run Against Live FastAPI Server (Port 8000):
```bash
python evaluation/run_evaluation.py --api-base http://127.0.0.1:8000
```

### Run Subset of Categories:
```bash
python evaluation/run_evaluation.py --categories factual conflict supersession
```
