# COSTRA Review 3 Demo Script

**Target duration:** about 5–7 minutes. Keep the terminal open at the project root.

## 1. Start the integrated workflow

```bash
python3 main.py
```

Choose **1** to start the complete workflow, then choose **1** for the built-in multi-join query or **2** to enter your own SQL once. COSTRA then presents Review 1 design, Review 2 compilation and Review 3 optimization/costing/execution in sequence using that same query. No separate review menu options are needed.

## 2. Recommended route through the demo

1. Explain the problem, objectives, SQL scope and architecture during Review 1.
2. Show the chosen SQL once, followed by tokens, AST, semantic validation and relational IR during Review 2.
3. Show candidate estimated costs, the minimum-cost plan and the selected plan tree during Review 3.
4. Show normalized SQL, SQLite result rows, SQLite's independent `EXPLAIN QUERY PLAN`, and stage timings.
5. Finish with the final summary. If asked, run the semantic error demonstration or tests separately:

```bash
python3 main.py --error-demo
python3 -m unittest -v
```

## 3. One-line explanation of each stage

- **Lexer:** characters become tokens.
- **Parser/AST:** tokens are checked against the SQL grammar and represented as a syntax tree.
- **Semantic analysis:** tables, aliases, columns and supported aggregate/grouping rules are validated.
- **Relational IR:** the query is represented as logical scan, join, filter, aggregate, sort and projection operators.
- **Cost estimation:** synthetic statistics estimate rows and relative costs for candidate access paths, join methods and join orders.
- **Selection:** the candidate with the lowest estimated total is selected; Plans 1 and 2 tie at 115,222.63 model units for the full demo.
- **SQLite execution:** the normalized SQL is passed to SQLite, which independently chooses its real plan and returns rows.

## 4. Cost explanation to say aloud

“COSTRA estimates the work of access paths and join algorithms using estimated row counts. It compares candidate plans and chooses the minimum estimated total from the candidates it generated. These cost values are model units, not milliseconds, and SQLite independently chooses the actual execution plan.”

For the Employee salary-filter example: with 10,000 estimated input rows and 7,200 estimated output rows, full scan plus predicate costs `10,000 + 0.20 × 10,000 = 12,000.00`. The index estimate costs `2 × log2(10,000) + 0.60 × 7,200 = 4,346.58`. Under the model, the index path is lower-cost.

## 5. Short fallback commands

```bash
python3 main.py --review1-demo
python3 main.py --review2-demo
python3 main.py --progress-demo
python3 main.py --cost-demo
python3 main.py --demo
python3 main.py --error-demo
python3 -m unittest -v
```

## 6. Do not overclaim

COSTRA uses synthetic statistics and a simplified relative cost model. Its chosen estimated plan is not injected into SQLite. Explain that boundary openly if asked.
