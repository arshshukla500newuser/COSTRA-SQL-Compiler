# COSTRA — Project File Index

## Core source code
- `main.py` — interactive 8-option menu and CLI entry point.
- `compiler.py` — orchestrates lexical, syntax, semantic and optimization stages.
- `lexer.py` — SQL tokenization.
- `parser.py` — recursive-descent parser.
- `ast_nodes.py` — SQL AST structures.
- `semantic.py` — table, alias, column, aggregate and grouping validation.
- `schema.py` — schema and synthetic statistics/index metadata.
- `statistics.py` — selectivity estimates.
- `ir.py` — relational logical plan.
- `optimizer.py` — access-path, join algorithm and candidate-plan cost estimates.
- `executor.py` — SQLite-backed sample execution and SQLite EXPLAIN output.
- `test_costra.py` — 52 automated unit/integration/CLI regression tests.
- `benchmark.py` — repeatable local benchmark runner.
- `requirements.txt` — no third-party runtime requirements.

## Interactive menu (`python3 main.py`)
1. Review 1 — problem definition, objectives, scope, design.
2. Review 2 — core compiler stages and sample execution.
3. Review 3 — complete end-to-end demonstration.
4. Enter a custom SELECT query.
5. Cost formula, worked example and minimum-cost candidate choice.
6. Review 1 → Review 2 → Review 3 progress.
7. Semantic-error demonstration.
8. Exit.

## Useful direct commands
- `python3 main.py --demo`
- `python3 main.py --review1-demo`
- `python3 main.py --review2-demo`
- `python3 main.py --cost-demo`
- `python3 main.py --progress-demo`
- `python3 main.py --error-demo`
- `python3 -m unittest -v`
- `python3 benchmark.py`

## Documentation / evidence
- `README.md` — setup, scope, pipeline and limitations.
- `docs/USER_GUIDE.md` — how to operate the interactive menu.
- `docs/DEMO_SCRIPT.md` — recommended Review 3 presentation sequence.
- `docs/TEST_PLAN.md` — test coverage and run commands.
- `docs/FINAL_PROJECT_REPORT.md` — final report source.
- `docs/REVIEW3_PRESENTER_GUIDE.md` — oral explanation guide.
- `docs/REVIEW_3_CHECKLIST.md` — final-review checklist.
- `reports/demo_output.txt` — current full demo output.
- `reports/cost_demo_output.txt` — formulas and candidate costs.
- `reports/review_progress_output.txt` — milestone summary.
- `reports/test_results.txt` — fresh test output (52 tests).
- `presentation/COSTRA_Review3_Professor_Menu.pptx/.pdf` — updated deck.

## Presentation test cases

- `docs/FULL_TEST_CASES_FOR_PRESENTATION.md` - all copy-paste SQL inputs, expected outputs, negative cases, cost calculation and menu demo commands.
- `docs/FULL_TEST_CASES_FOR_PRESENTATION.pdf` - print-ready version of the same reference.
- `reports/test_cases_for_presentation.csv` - spreadsheet-friendly case list.
