# COSTRA — Phase 3 Release Manifest

**Project:** COSTRA — Cost-Based SQL Compiler & Query Optimizer  
**Student:** Arsh Shukla · 24BDS0113 · VIT Vellore  
**Prepared:** 20 October 2026

## Verified commands

```bash
python3 -m compileall -q .
python3 -m unittest -v
python3 main.py --demo
python3 main.py --error-demo
python3 main.py --review1-demo
python3 main.py --review2-demo
python3 main.py --cost-demo
python3 main.py --progress-demo
python3 main.py --query "SELECT name FROM Employee LIMIT 2;"
python3 benchmark.py
```

- Compile check: passed.
- Regression suite: **52 tests passed** (`reports/test_results.txt`).
- Full main demo: returned **3 rows** (`reports/demo_output.txt`).
- Cost example and six candidate costs: `reports/cost_demo_output.txt`.
- Review-wise summary: `reports/review_progress_output.txt`.
- Unknown-column demonstration: rejected during semantic validation before execution (`reports/semantic_error_output.txt`).
- Custom-query example: `reports/custom_query_output.txt`.
- Benchmark: four query shapes, three warm-up and 30 measured repetitions each; JSON/CSV saved under `reports/`.

## Interactive menu

`python3 main.py` opens an eight-option switch-style menu:

1. Review 1 design summary
2. Review 2 core-module walkthrough
3. Review 3 full pipeline demo
4. Custom SQL input
5. Cost calculation and lowest-cost candidate
6. Review 1 → Review 2 → Review 3 progress
7. Semantic-error demonstration
8. Exit

## Included deliverables

- Python source modules and regression tests.
- Updated switch-style interactive menu and direct CLI shortcuts.
- README, changelog, user guide, demo script and release manifest.
- Final project report source and PDF.
- **32-slide** Review 3 PowerPoint and PDF export in the selected brown/terracotta theme.
- Updated presenter guide, architecture diagram, test plan, final-review checklist and screenshot checklist.
- Demo output, error output, cost-calculation output, review-progress output, test log and benchmark evidence.

## Scope and limitation note

COSTRA uses synthetic statistics and a relative educational cost model. The selected estimated plan is not passed into SQLite. SQLite independently plans and executes the normalized SQL. The implementation is a tested educational SQL subset, not a production optimizer or a full SQL-standard implementation.

## Repository publication status

This release is prepared locally. A GitHub remote push is **not** claimed; publishing it requires an authenticated GitHub session or a manual commit from the student's machine.
