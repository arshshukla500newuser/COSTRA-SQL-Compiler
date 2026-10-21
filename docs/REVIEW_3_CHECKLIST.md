# Review 3 - Submission Checklist

## Working project
- [ ] Run `python3 main.py --demo` on the machine used for the review.
- [ ] Demonstrate the multi-join query end to end.
- [ ] Show valid and invalid input cases without a traceback.
- [ ] Explain lexer, parser/AST, semantic analysis, relational IR, optimizer, cost model and executor.
- [ ] Explain how synthetic estimates differ from measured time and SQLite's own plan.

## Code and quality
- [ ] `python3 -m unittest -v` passes from a clean checkout (52 tests in the latest checked run).
- [ ] `python3 benchmark.py` regenerates JSON and CSV.
- [ ] No secrets, virtual environments, bytecode caches or temporary exports in the repository.
- [ ] Main modules have clear responsibility and readable names.

## Evidence and documentation
- [ ] Test plan and test results match the latest source.
- [ ] Keep terminal/output screenshots that are genuine and captured from the current version.
- [ ] Final report covers all required chapters and limitations.
- [ ] User guide has exact setup and commands.
- [ ] Final presentation and report links open.

## Submission
- [ ] Confirm the official Review 3 date and slot from the faculty date sheet.
- [ ] Commit the final version to GitHub after reviewing the staged diff.
- [ ] Keep a clean local ZIP/backup of the submitted repository.
