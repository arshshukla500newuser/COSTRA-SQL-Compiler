# COSTRA Final Release Notes

**Release preparation date:** 15 October 2026

## Run commands

```bash
python3 -m compileall -q .
python3 main.py --demo
python3 main.py --error-demo
python3 -m unittest -v
python3 benchmark.py
```

## Current checked results

- `python3 -m compileall -q .`: passed.
- `python3 -m unittest -v`: 52 tests passed.
- `python3 main.py --demo`: completed and returned three rows.
- `python3 main.py --error-demo`: rejected an unknown column during semantic analysis before execution.
- `python3 benchmark.py`: regenerated JSON and CSV for four query shapes, with three warm-ups and 30 measured repetitions each.
- Review 3 presentation: 28 slides, centered on a worked SQL compilation example and real stage outputs.

## Important project boundary

The optimizer uses synthetic statistics and relative model-cost units. These are not elapsed milliseconds. SQLite independently plans and executes normalized SQL; COSTRA does not inject its chosen estimated plan into SQLite.

## Before submission

Run the commands again on the presentation machine. Confirm the official Review 3 schedule with faculty, capture current screenshots as described in `SCREENSHOTS_NEEDED.md`, and push the reviewed local changes to GitHub from an authenticated session.
