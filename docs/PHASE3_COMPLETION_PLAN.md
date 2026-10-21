# COSTRA: Review 2 to Final Review Completion Plan

The official Compiler Design Lab instruction manual requires Phase 3 to complete remaining functionality, integrate all modules, test valid/invalid/boundary/error/complex inputs, provide meaningful errors, evaluate performance where applicable, and prepare the final report, presentation and user instructions.

The manual does not specify the student's exact scheduled review dates. These were proposed work targets beginning 14 October 2026, not official faculty deadlines. Recheck the faculty date sheet before treating any target as a submission deadline.

| Target | Work block | Definition of done |
|---|---|---|
| 14-15 Oct | Review 2 audit | Module inventory, baseline run, current issues and target test cases recorded. |
| 16-18 Oct | Integration and code hardening | Parser, semantics, IR, optimizer and executor work through the same end-to-end pipeline; useful errors; regression tests. |
| 19-20 Oct | Validation | Positive, negative, boundary and complex SQL tests pass and their outputs are saved. |
| 21 Oct | Evidence and performance | Test output, example results, SQLite's plan, and repeatable local end-to-end timing report saved with limits clearly described. |
| 22-23 Oct | Documentation | README, module descriptions, architecture, final report, test plan and user guide are ready. |
| 24-25 Oct | Final presentation and repository review | Demo order rehearsed, final presentation updated, repo cleaned, checklist completed. |
| On the official Review 3 date | Submission buffer | Confirm date/time against the actual date sheet, rerun tests on the demo machine, and submit all deliverables. |

## Required deliverables from the instruction manual

- Complete working project and complete source code
- Test cases and results
- Screenshots/output evidence
- Final project report
- Presentation
- User instructions

## Release gate

Do not label the project final until `python3 -m unittest -v` passes, `python3 main.py` completes its demo, the benchmark artifacts are regenerated from the current source, the final report matches the shipped code, and the Review 3 date is checked against the faculty date sheet.
