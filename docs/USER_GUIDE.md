# COSTRA User Guide

## 1. Requirements

- Python 3.9 or newer.
- No external Python packages are required for runtime.
- Open the project root in VS Code or use a terminal.

## 2. Start the integrated Review 1 → Review 2 → Review 3 workflow

Run:

```bash
python3 main.py
```

1. Choose **1 — Start complete Review 1 → Review 2 → Review 3 workflow**.
2. Choose **1** for the built-in multi-join demo query or **2** to enter your own SQL.
3. Enter the custom query once. A one-line query can end with `;`; multi-line SQL is also accepted.
4. COSTRA shows Review 1's problem, objectives, scope and architecture.
5. The same selected SQL then flows through Review 2 (lexer, parser/AST, semantic validation and relational IR) and Review 3 (candidate-plan cost estimates, best estimated plan, SQLite execution results, SQLite EXPLAIN plan and timings).
6. A final summary reports success or the stage that failed. If compilation fails, optimization and execution are skipped.

The interactive menu intentionally does not offer separate Review 1, Review 2 and Review 3 options. This creates one continuous demonstration using a single SQL input.

## 3. Custom SQL example

Choose option 1 in the main menu, then option 2 for custom SQL. Enter:

```sql
SELECT name, salary FROM Employee WHERE salary > 80000;
```

The parser supports the SQL subset documented in `README.md`; it is not a full SQL implementation.

## 4. Direct commands

Use a direct command when you want one walkthrough without opening the menu:

```bash
python3 main.py --review1-demo
python3 main.py --review2-demo
python3 main.py --progress-demo
python3 main.py --cost-demo
python3 main.py --demo
python3 main.py --error-demo
python3 main.py --query "SELECT name FROM Employee LIMIT 2;"
```

## 5. How to explain cost output

- `estimated rows` are calculated from synthetic row counts, distinct counts, ranges and selectivity assumptions.
- `estimated cost` is a relative model quantity; it is **not milliseconds**.
- COSTRA compares access paths and join-method estimates, generates candidate join orders, and selects the lowest-cost candidate among those generated.
- The full demo has six candidates. Plans 1 and 2 tie at **115,222.63 model units**; the implementation returns the first candidate at the minimum cost.
- SQLite independently plans and executes the normalized SQL. COSTRA does not inject its chosen physical tree into SQLite.

## 6. Run tests and benchmark

```bash
python3 -m unittest -v
python3 benchmark.py
```

The current regression suite contains 52 tests. The benchmark is a local timing tool over a tiny seeded in-memory SQLite fixture and should not be presented as proof that COSTRA is faster than SQLite.

## 7. Error handling

COSTRA stops when lexical, syntax or semantic validation fails. Example errors include an illegal character, invalid SQL syntax, unknown table, unknown alias, unknown column, ambiguous unqualified column, unsupported function or invalid grouping. A query that fails these stages is not executed.
