# COSTRA Final Code Check and Test Steps

## Verification performed

- Python syntax check: `python -m py_compile *.py` — passed.
- Automated regression suite: `python -m unittest -v` — 52 tests passed.
- Integrated built-in demo: `python main.py` → choose `1` → choose `1` — completed all three review stages and SQLite returned 3 rows.
- Custom SQL smoke test: `python main.py --query "SELECT name FROM Department ORDER BY name LIMIT 3;"` — compilation and SQLite execution passed; 3 rows returned.
- Semantic-error demo: `python main.py --error-demo` — correctly reported the unknown column and stopped before execution.

These checks were run in the current packaging environment. Run them again on the presentation laptop before the review.

## Windows / VS Code setup

1. Extract the ZIP file.
2. Open the extracted `COSTRA-SQL-Compiler-Phase3` folder in VS Code (open the folder containing `main.py`).
3. Open **Terminal → New Terminal**.
4. Check Python is installed:

   ```powershell
   python --version
   ```

   Use Python 3.10+ if available. If `python` is not recognized, try `py --version` and replace `python` with `py` in the commands below.

5. No third-party packages are required; COSTRA uses the Python standard library.
6. Check syntax and run the complete automated test suite:

   ```powershell
   python -m py_compile *.py
   python -m unittest -v
   ```

   Expected: `Ran 52 tests` and `OK`.

## Manual test cases for the demonstration

| ID | Test | Steps / input | Expected result |
|---|---|---|---|
| TC-01 | Start integrated workflow | Run `python main.py`; choose `1`; choose `1` | Review 1, Review 2, Review 3, cost comparison, best estimated plan, SQLite results and final summary appear in one run. |
| TC-02 | Custom SQL | Run `python main.py`; choose `1`; choose `2`; enter `SELECT name FROM Department ORDER BY name LIMIT 3;`; submit a blank line to finish | The same query goes through the integrated workflow and returns up to 3 department names. |
| TC-03 | Grouping and aggregates | Use the built-in demo query | Output includes department, employee count and average salary; demo returns 3 rows in the packaged fixture. |
| TC-04 | Unknown column | Run `python main.py --error-demo` | A semantic diagnostic identifies `e.unknown_column`; query execution is skipped. |
| TC-05 | Invalid SQL syntax | Run `python main.py --query "SELECT FROM;"` | A syntax/compilation error is displayed and SQLite execution does not occur. A non-zero exit code is expected. |
| TC-06 | Exit menu | Run `python main.py`; choose `2` | COSTRA prints a goodbye message and exits. |

## Suggested presentation order

1. Start with `python main.py`.
2. Select `1` to start the integrated demonstration.
3. Select `1` for the built-in query (recommended for a predictable presentation) or `2` for a custom query.
4. Explain Review 1 as design and scope; Review 2 as lexing, parsing, semantic validation and IR; Review 3 as estimated-cost comparison and SQLite execution.
5. Point out that COSTRA's plan costs are **synthetic relative cost units**, not milliseconds. SQLite independently chooses its actual execution plan; COSTRA's selected estimated plan is not forced into SQLite.
6. Run the automated tests before the review, not during the timed presentation.

## Scope and honest limitations

The compiler supports a documented subset of SQL, not the complete SQL standard. The optimizer uses a simplified cost model and synthetic statistics. A successful test suite validates the implemented features and test cases, not every possible SQL query or workload.
