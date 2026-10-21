# Screenshots to add to the Review 3 presentation

The current Review 3 deck uses clearly typeset excerpts from actual program output so every result is readable. To personalize it with genuine evidence from your Mac/VS Code, capture these screenshots from the same code version you will submit.

1. **VS Code project tree** — show the COSTRA folder and modules (`main.py`, `lexer.py`, `parser.py`, `semantic.py`, `ir.py`, `optimizer.py`, `executor.py`, `test_costra.py`). Keep any tokens, credentials or personal paths out of view.
2. **Demo: lexer, parser/AST, and semantic success** — run `python3 main.py --demo` and scroll so token count, the AST section, and the successful semantic check are readable. Use full-screen terminal or widen the terminal panel.
3. **Demo: relational IR and selected plan** — same run; capture the logical operators and the estimated cost plus selected plan. Include the note that the costs are model units, not milliseconds, if visible.
4. **Demo: execution result + SQLite plan** — same run; show the three department rows and the separately labelled SQLite `EXPLAIN QUERY PLAN` section.
5. **Semantic-error example** — run `python3 main.py --error-demo`; capture the unknown-column rejection and the message that SQL was not executed.
6. **Tests** — run `python3 -m unittest -v`; capture the final `Ran 52 tests` and `OK` lines (capture a second image if the final lines don't fit in one view).
7. **Benchmark summary (optional)** — run `python3 benchmark.py` and capture the four-query median summary. Avoid presenting a single timing as a performance guarantee.

Upload the original PNG/JPG files here, preferably at 16:9 or with readable terminal text. Do not crop out the command or relevant result. I'll place them on the matching slides and keep code/output summaries elsewhere for readability.
