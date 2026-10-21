# Open COSTRA in VS Code (Mac)

1. Extract the `COSTRA_SQL_Compiler_VSCode.zip` file. It creates a folder named `COSTRA-SQL-Compiler-Phase3`.
2. Open that folder in VS Code using **File → Open Folder…**.
3. Recommended: open `COSTRA-SQL-Compiler-Phase3.code-workspace` inside the folder if you want the saved workspace settings.
4. Open **Terminal → New Terminal** and run `python3 main.py`.
5. If your professor asks for a particular demo, choose the corresponding numbered menu option.

No third-party Python packages are required; the project uses Python's standard library and SQLite.

## VS Code run shortcuts

Open **Terminal → Run Task…** (or the command palette and search for “Tasks: Run Task”) and choose one of:

- `COSTRA: Interactive Professor Menu`
- `COSTRA: Full Review 3 Demo`
- `COSTRA: Cost Calculation and Best Plan`
- `COSTRA: Review 1 to Review 3 Progress`
- `COSTRA: Semantic Error Demo`
- `COSTRA: Run All Tests`
- `COSTRA: Run Custom SQL (prompt)`

The tasks use `python3` and run from the project root. For debugging, open **Run and Debug** and select a COSTRA configuration; the Python extension is required for the debugger.
