# Changelog

## Phase 3 final-review update — 15 October 2026

- Added non-interactive CLI modes: `--demo`, `--error-demo` and `--query` for a clean, repeatable presentation workflow.
- Added CLI smoke tests; that milestone run had 48 tests passing (the current 20 October suite has 52).
- Regenerated end-to-end demo, semantic-error, custom-query, test and benchmark evidence.
- Rebuilt the Review 3 deck as a 32-slide worked compilation demonstration in the selected brown/terracotta theme.
- Added slide-by-slide speaking notes and 25 likely viva questions with answers.
- Added `docs/SCREENSHOTS_NEEDED.md` to collect genuine VS Code / terminal evidence before final personalization.
- Updated setup and demo instructions for one-command runs.

## Earlier Phase 3 work

- Added broader SELECT-subset parsing and semantic validation.
- Added synthetic cardinality / selectivity, costed access paths and bounded candidate join orders.
- Separated COSTRA's estimated plan from SQLite's actual execution plan in output and documentation.
- Added test plan, benchmark outputs, report source and architecture diagram.


## Review menu customization (2026-10-20)

- Added an 8-option interactive menu for Review 1, Review 2, Review 3, custom SQL, cost calculations, review-wise progress, semantic-error demonstration, and exit.
- Added direct CLI shortcuts for Review 1/2 summaries, cost calculations, and review milestones.
- Added 4 command-line regression tests for menu selection, custom SQL, cost calculation output, and review-wise progress.
- Updated user guide and demo script to reflect the menu.
