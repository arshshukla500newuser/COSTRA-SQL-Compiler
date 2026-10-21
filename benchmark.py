"""Repeatable, local end-to-end timing sampler for COSTRA's supported SQL examples."""
from __future__ import annotations
import csv
import json
import platform
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from executor import Executor
from main import DEMO_SQL, run_query

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
RUNS = 30
WARMUP_RUNS = 3
QUERIES = {
    "multi_join_aggregation": DEMO_SQL,
    "indexed_salary_filter": "SELECT name, salary FROM Employee WHERE salary > 80000 ORDER BY salary DESC LIMIT 3;",
    "grouped_department_counts": "SELECT d.name AS department, COUNT(e.id) AS total_employees FROM Employee e JOIN Department d ON e.dept_id = d.id GROUP BY d.name ORDER BY total_employees DESC;",
    "distinct_departments": "SELECT DISTINCT dept_id FROM Employee ORDER BY dept_id;",
}


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def mean(values):
    return sum(values) / len(values) if values else None


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    index = round((len(ordered) - 1) * pct)
    return ordered[index]


def benchmark_query(name, sql, executor):
    for _ in range(WARMUP_RUNS):
        warmup = run_query(sql, executor)
        if not warmup.compilation.success or not warmup.executed:
            raise RuntimeError(f"Warm-up failed for {name}: {warmup.compilation.errors or warmup.execution_error}")

    samples_ms = []
    last_result = None
    component_samples = {}
    result_signature = None
    for _ in range(RUNS):
        start = time.perf_counter()
        result = run_query(sql, executor)
        elapsed = (time.perf_counter() - start) * 1000
        if not result.compilation.success or not result.executed:
            raise RuntimeError(f"Benchmark failed for {name}: {result.compilation.errors or result.execution_error}")
        signature = (tuple(result.headers), tuple(result.rows))
        if result_signature is not None and signature != result_signature:
            raise RuntimeError(f"Non-repeatable result encountered for {name}")
        result_signature = signature
        samples_ms.append(elapsed)
        for stage, value in result.timings_ms.items():
            component_samples.setdefault(stage, []).append(value)
        last_result = result

    return {
        "query_name": name,
        "runs": RUNS,
        "warmup_runs": WARMUP_RUNS,
        "rows_returned": len(last_result.rows),
        "candidate_plans": len(last_result.compilation.candidates),
        "selected_estimated_cost_model_units": round(last_result.compilation.best_plan.cost, 4),
        "elapsed_ms": {
            "min": round(min(samples_ms), 4),
            "median": round(median(samples_ms), 4),
            "mean": round(mean(samples_ms), 4),
            "p95": round(percentile(samples_ms, 0.95), 4),
            "max": round(max(samples_ms), 4),
        },
        "stage_median_ms": {stage: round(median(values), 4) for stage, values in component_samples.items()},
        "result_is_repeatable": True,
        "interpretation": "Local end-to-end timing on a tiny in-memory fixture; not a general performance guarantee.",
    }


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = {
        "project": "COSTRA - Cost-Based SQL Compiler & Query Optimizer",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "sqlite_version": sqlite3.sqlite_version,
        "environment": "current local runtime; measurements vary by machine and load",
        "note": "COSTRA's estimated cost values are synthetic model units and are not elapsed milliseconds. SQLite executes normalized SQL independently.",
        "benchmarks": [],
    }
    with Executor() as executor:
        for name, sql in QUERIES.items():
            record = benchmark_query(name, sql, executor)
            record["sql"] = " ".join(sql.split())
            output["benchmarks"].append(record)

    json_path = REPORTS / "benchmark_results.json"
    csv_path = REPORTS / "benchmark_results.csv"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "query_name", "runs", "warmup_runs", "rows_returned", "candidate_plans",
            "selected_estimated_cost_model_units", "min_ms", "median_ms", "mean_ms", "p95_ms", "max_ms",
            "result_is_repeatable",
        ])
        writer.writeheader()
        for item in output["benchmarks"]:
            writer.writerow({
                "query_name": item["query_name"], "runs": item["runs"], "warmup_runs": item["warmup_runs"],
                "rows_returned": item["rows_returned"], "candidate_plans": item["candidate_plans"],
                "selected_estimated_cost_model_units": item["selected_estimated_cost_model_units"],
                "min_ms": item["elapsed_ms"]["min"], "median_ms": item["elapsed_ms"]["median"],
                "mean_ms": item["elapsed_ms"]["mean"], "p95_ms": item["elapsed_ms"]["p95"],
                "max_ms": item["elapsed_ms"]["max"], "result_is_repeatable": item["result_is_repeatable"],
            })
    print(f"Wrote {json_path.relative_to(ROOT)}")
    print(f"Wrote {csv_path.relative_to(ROOT)}")
    for item in output["benchmarks"]:
        print(f"{item['query_name']}: median {item['elapsed_ms']['median']:.4f} ms, "
              f"{item['rows_returned']} rows, estimated cost "
              f"{item['selected_estimated_cost_model_units']:.2f} model units")


if __name__ == "__main__":
    main()
