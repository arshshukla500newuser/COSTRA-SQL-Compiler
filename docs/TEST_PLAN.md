# COSTRA Test Plan and Results

## Test approach

COSTRA uses Python's standard-library `unittest` so the suite can run on a clean Python installation without adding dependencies. Test groups cover the lexer, parser, semantic validation, estimated optimization, and SQLite-backed end-to-end execution.

| Area | Covered behavior |
|---|---|
| Lexer | Token classes, case-insensitive keywords, line/column locations, comments, escaped quotes, unexpected characters |
| Parser | SELECT clauses, joins, aliases, AST shape, operator precedence, arithmetic, aggregate calls, DISTINCT, NULL/IN/BETWEEN/LIKE, invalid LIMIT and malformed statements |
| Semantics | Unknown table/alias/column, duplicate aliases, ambiguous columns, invalid aggregate placement, unsupported functions, type and GROUP BY checks, ORDER BY output aliases |
| Optimizer | Minimum-cost selection, multiple inner-join orders, index-path estimate, scalar aggregation, DISTINCT node, outer-join order preservation |
| Execution | Deterministic demo results, literal handling, LEFT JOIN, SQLite EXPLAIN output, lexical/syntax/semantic fail-fast behavior |

## Expected positive checks

- The demo query completes and returns rows with `department`, `employee_count` and `average_salary` columns.
- A simple salary filter returns a sorted result from SQLite.
- `COUNT(*)`, grouping, `DISTINCT`, `IN`, `BETWEEN`, `LIKE` and `IS NULL` statements are parsed and validated where they match the supported subset.
- COSTRA returns the minimum cost among candidates generated for a given query.

## Expected negative checks

- Lexical errors include line and column.
- Syntax errors name the unexpected token or expected grammar item.
- Semantic errors include unknown table/alias/column, ambiguous unqualified columns, aggregate usage in `WHERE`, unsupported function names, incompatible `SUM`/`AVG` input types, and invalid grouped projections.
- The pipeline does not execute statements that fail lexical, syntax or semantic validation.

## Latest recorded result

Regenerate with `python3 -m unittest -v` from the repository root. The shipped test output is saved in `reports/test_results.txt`. The latest verified run on 20 October 2026 reports **52 tests passed**; the exact output is stored in `reports/test_results.txt`.

## Interpretation limits

The sample database is small; the synthetic optimizer statistics are intentionally not calibrated against it. Test success validates supported examples and error paths, not compliance with the entire SQL language standard. Runtime benchmarks are local evidence only.
