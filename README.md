# COSTRA - Cost-Based SQL Compiler & Query Optimizer

COSTRA is an educational Compiler Design project that makes the path from SQL text to a validated query representation and cost-estimated plan visible. It uses Python for the compiler/optimizer prototype and SQLite as a separate execution engine over a small deterministic sample database.

> **Important implementation boundary:** COSTRA estimates and compares candidate plans using synthetic statistics and a relative cost model. The selected COSTRA plan is shown for analysis; SQLite independently plans and executes the normalized SQL. COSTRA does not inject its selected physical plan into SQLite.

## Quick start

Requirements: Python 3.9 or newer. The project uses only the Python standard library.

Run the complete review demonstration without navigating the menu:

```bash
python3 main.py --demo
```

Other useful commands:

```bash
python3 main.py                 # interactive menu
python3 main.py --error-demo    # expected semantic rejection before execution
python3 main.py --query "SELECT name FROM Employee WHERE salary > 80000 LIMIT 2;"
```

Interactive workflow (`python3 main.py`):

1. Choose **Start complete Review 1 → Review 2 → Review 3 workflow**.
2. Choose the built-in multi-join demo query or enter your own SQL once (multi-line input is supported; finish with `;`).
3. COSTRA presents Review 1 design, then sends that same SQL through Review 2 compilation and Review 3 optimization/costing and SQLite execution.
4. The final summary reports the selected estimated plan, cost comparison, execution result, or the stage and reason for any error.

The interactive menu has only the integrated workflow and Exit; review stages are no longer separate menu choices. Direct mode flags remain available for debugging and focused checks.
Direct mode flags are also available: `--review1-demo`, `--review2-demo`, `--progress-demo`, `--cost-demo`, `--demo`, `--error-demo`, and `--query "SELECT ..."`.

Run the regression tests:

```bash
python3 -m unittest -v
```

Run the same commands used for the presentation:

```bash
./run_review3_demo.sh
./run_review3_error_demo.sh
```

Run the repeatable local benchmark:

```bash
python3 benchmark.py
```

The benchmark writes `reports/benchmark_results.json` and `reports/benchmark_results.csv`. The results are machine-local measurements and should not be interpreted as general performance guarantees.

## Processing pipeline

```text
SQL input
  -> Lexer / token stream
  -> Recursive-descent parser
  -> Abstract Syntax Tree (AST)
  -> Schema-aware semantic validation
  -> Logical relational IR
  -> Synthetic cardinality/selectivity estimation
  -> Candidate join-order and access-path generation
  -> Relative cost calculation and minimum-cost candidate selection
  -> Normalized SQL passed to SQLite
  -> Result rows + SQLite EXPLAIN QUERY PLAN + stage timings
```

## Current SQL subset

The parser supports a documented subset of `SELECT`:

- Projection expressions, aliases, `*`, qualified `table.*`, and `DISTINCT`.
- `FROM` with table names and aliases.
- `INNER JOIN`, `LEFT JOIN`, `RIGHT JOIN`, and `CROSS JOIN`.
- `WHERE` with parentheses, `NOT`, `AND`, `OR`, comparisons, arithmetic, `IS [NOT] NULL`, `[NOT] IN`, `[NOT] BETWEEN`, and `[NOT] LIKE`.
- `GROUP BY`, `HAVING`, `ORDER BY` with `ASC`/`DESC`, and non-negative integer `LIMIT`.
- `COUNT`, `SUM`, `AVG`, `MIN`, and `MAX`, including `COUNT(DISTINCT column)`.
- Integer, decimal/scientific-notation and quoted string literals, `NULL`, `TRUE`, `FALSE`, and `--` line comments.

This is not a full SQL implementation. Features such as subqueries, CTEs, window functions, `UNION`, quoted identifiers, `CASE`, `IS DISTINCT FROM`, and multi-statement scripts are outside the current scope.

## Modules

| File | Responsibility |
|---|---|
| `lexer.py` | Converts SQL characters into location-aware tokens and reports illegal characters. |
| `parser.py` | Recursive-descent parser with expression precedence and syntax diagnostics. |
| `ast_nodes.py` | AST dataclasses and safe formatting of supported expressions/queries. |
| `semantic.py` | Validates tables, aliases, columns, ambiguity, aggregate placement and basic grouping rules. |
| `schema.py` | Logical schema, synthetic row/distinct/range statistics, and modelled indexes. |
| `statistics.py` | Selectivity estimates for common predicates. |
| `ir.py` | Logical relational plan nodes and tree formatting. |
| `optimizer.py` | Access-path estimates, join-order alternatives, join-method costing, and selected candidate. |
| `compiler.py` | Runs lexer, parser, semantics and optimizer in order and captures stage timings/errors. |
| `executor.py` | Creates the in-memory SQLite fixture, executes normalized `SELECT` SQL, and returns SQLite's own query plan. |
| `main.py` | Interactive demonstration and readable pipeline output. |
| `test_costra.py` | Automated unit and integration regression tests. |
| `benchmark.py` | Repeatable local end-to-end timing runs with JSON/CSV output. |
| `docs/` | Final report, user guide, test plan, limitations, architecture and completion checklist. |

## How the optimizer works

1. Split simple `AND`-connected predicates and identify predicates that reference one table only.
2. Estimate filtered rows using hard-coded synthetic row counts, distinct counts, and numeric ranges.
3. Compare a table-scan estimate with an index-path estimate when a suitable modelled index and a simple searchable predicate are present.
4. For inner joins, enumerate candidate relation orders up to a configured cap. For each join step, estimate output cardinality and compare nested-loop, hash-join, and merge-join relative costs.
5. Preserve the written order when an outer or cross join makes arbitrary join reordering unsafe.
6. Add estimated aggregation, `HAVING`, distinct, sorting, limit and projection costs; return the six lowest-cost unique join-order candidates.

The cost numbers are **relative model units**, not milliseconds. The row counts and column distributions are synthetic. SQLite's `EXPLAIN QUERY PLAN` output is displayed separately as the plan SQLite actually selected for execution.

## Data used for the demo

The optimizer uses the synthetic statistics in `schema.py` (for example, 10,000 estimated employee rows and 30,000 assignment rows). The executor seeds a much smaller in-memory SQLite database with sample records so the demonstration stays fast and outputs are repeatable. Therefore, estimated cardinalities are not expected to match the sample execution row counts.

## Quality checks

- Test suite: `python3 -m unittest -v` (52 tests in the latest checked run)
- Test case inventory and latest observed results: `docs/TEST_PLAN.md` and `reports/test_results.txt`
- Final project report (source): `docs/FINAL_PROJECT_REPORT.md`
- Final project report (PDF): [reports/COSTRA_Final_Project_Report.pdf](reports/COSTRA_Final_Project_Report.pdf)
- Final review presentation (editable PowerPoint): [presentation/COSTRA_Final_Project_Review3_Demonstration.pptx](presentation/COSTRA_Final_Project_Review3_Demonstration.pptx)
- Final review presentation (PDF): [presentation/COSTRA_Final_Project_Review3_Demonstration.pdf](presentation/COSTRA_Final_Project_Review3_Demonstration.pdf)
- Step-by-step run instructions: `docs/USER_GUIDE.md`
- Personal screenshot capture requests: `docs/SCREENSHOTS_NEEDED.md`
- Review 3 demonstration script: `docs/DEMO_SCRIPT.md`
- Final-review checklist: `docs/REVIEW_3_CHECKLIST.md`
- Planned work from Review 2 to final review: `docs/PHASE3_COMPLETION_PLAN.md`

## Current limitations and responsible claims

- Candidate costs and cardinalities use an educational heuristic model, not live database statistics.
- Candidate plan output is analytical; it is not forced into SQLite's physical execution engine.
- Join-order enumeration is exhaustive only within the configured cap, not a dynamic-programming optimizer.
- The sample database is intentionally small and is not a production benchmark dataset.
- Type checking and SQL semantics cover the documented subset, not the full SQL standard.

These limitations are explicit so the implementation can be explained accurately during the final review.


---

## Review 1 + Review 2 + Review 3 deliverables

The combined review assets are stored in `docs/reviews/`:

- `COSTRA_Review_1_2_3_Report.pdf` — combined report covering design, implementation, optimization, validation, limitations, test queries and repository update steps.
- `COSTRA_Review_1_2_3_Presentation.pptx` — editable presentation for the combined review.

### Three demonstration queries

Run each query using the integrated menu (`python3 main.py`, then choose the complete workflow and enter a custom query). Exact costs and result rows depend on the current code and its configured fixture; capture the terminal output from the current branch for submission evidence.

**Test 1 — JOIN + WHERE + end-to-end candidate costs**

```sql
SELECT e.name, d.name
FROM Employee e
JOIN Department d ON e.dept_id = d.id
WHERE e.salary > 50000;
```

Shows tokenization, AST, semantic validation, relational IR, candidate-plan cost comparison, selection status and SQLite results. One captured run displayed two candidate plans tied at `10,030.58` relative model units and returned seven rows; this is a specific run, not a universal expected result.

**Test 2 — Multiple joins + aggregation**

```sql
SELECT
    d.name AS department,
    COUNT(e.id) AS employee_count,
    AVG(e.salary) AS average_salary
FROM Employee e
JOIN Department d ON e.dept_id = d.id
JOIN Assignment a ON e.id = a.employee_id
JOIN Project p ON a.project_id = p.id
WHERE e.salary > 60000
  AND p.budget > 100000
GROUP BY d.name
HAVING AVG(e.salary) > 65000
ORDER BY AVG(e.salary) DESC
LIMIT 5;
```

Shows multiple joins, aggregate functions, `GROUP BY`, `HAVING`, `ORDER BY` and `LIMIT`. Record actual output and costs from the current branch.

**Test 3 — Filter + possible index access + sorting + limit**

```sql
SELECT e.name, e.salary
FROM Employee e
WHERE e.salary > 80000
ORDER BY e.salary DESC
LIMIT 5;
```

Shows predicate handling, access-path costing where implemented, sorting and limiting. Record actual candidate plans and output from the current branch.

### Semantic-error demonstration

```sql
SELECT e.unknown_column
FROM Employee e;
```

Expected behavior: semantic analysis reports an unknown column and stops before candidate-plan generation and execution.

### Interpreting COSTRA's costs

COSTRA uses configured/synthetic statistics and relative cost units. These values are not milliseconds or measured runtime. COSTRA selects a candidate for educational plan analysis; SQLite independently chooses its own internal execution plan and runs the normalized SQL. The selected COSTRA plan is not injected into SQLite.

