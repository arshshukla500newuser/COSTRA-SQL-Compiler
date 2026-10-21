# COSTRA — Full Test Cases for Review Presentation

**Purpose:** ready-to-use SQL inputs, expected outcomes, error tests and optimizer checks for a professor demonstration. These cases were checked against the current local project and its deterministic in-memory sample database.

## How to run each input

1. Open the project folder in VS Code.
2. Run `python3 main.py`.
3. Choose option `4` (custom SQL). Paste one SQL query on the `SQL>` prompt as a single line.
4. For the full demo, choose option `3`; for cost calculation, choose option `5`; for the deliberate unknown-column error, choose option `7`.

You can also run a query directly from the terminal: `python3 main.py --query "SELECT name FROM Employee LIMIT 3;"`. The command-line query option returns a nonzero status for rejected input; that is expected for negative tests.

## Best cases to show live

1. **TC02** — custom input to show parse → semantic analysis → cost estimate → output.
2. **TC08** — join and alias resolution.
3. **TC07** — grouping and `HAVING`.
4. **TC21** — full Review 3 demo: 98 tokens, AST, semantic pass, relational IR, six candidate plan estimates, three result rows and SQLite query plan.
5. **TC22** — unknown-column semantic rejection.
6. **TC35 / menu option 5** — worked cost formula and plan selection.

## Test cases

### TC01 — Basic SELECT + LIMIT (Valid query)

**Input SQL**
```sql
SELECT name, salary FROM Employee LIMIT 3;
```

**Expected result**
PASS; 3 rows: Arjun | 85000; Neha | 72000; Riya | 48000.

**What it demonstrates:** Shows lexer, parser, semantic analysis, planning and execution on a simple query.

### TC02 — WHERE filter + descending order (Valid query)

**Input SQL**
```sql
SELECT name, salary FROM Employee WHERE salary > 80000 ORDER BY salary DESC;
```

**Expected result**
PASS; Ishita | 91000; Arjun | 85000. Estimated path uses an index for the salary predicate.

**What it demonstrates:** Good short custom-input demo.

### TC03 — ORDER BY + LIMIT (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee ORDER BY salary DESC LIMIT 3;
```

**Expected result**
PASS; Ishita; Arjun; Aman.

**What it demonstrates:** Shows ordering and row limiting.

### TC04 — DISTINCT values (Valid query)

**Input SQL**
```sql
SELECT DISTINCT dept_id FROM Employee ORDER BY dept_id;
```

**Expected result**
PASS; department IDs 1, 2, 3, 4.

**What it demonstrates:** Shows duplicate elimination.

### TC05 — Scalar aggregate (Valid query)

**Input SQL**
```sql
SELECT COUNT(*) AS employee_count FROM Employee;
```

**Expected result**
PASS; employee_count = 8.

**What it demonstrates:** Shows aggregate function handling.

### TC06 — GROUP BY counts (Valid query)

**Input SQL**
```sql
SELECT dept_id, COUNT(*) AS n FROM Employee GROUP BY dept_id ORDER BY dept_id;
```

**Expected result**
PASS; (1, 3), (2, 2), (3, 2), (4, 1).

**What it demonstrates:** Good aggregation example.

### TC07 — GROUP BY + HAVING + AVG (Valid query)

**Input SQL**
```sql
SELECT dept_id, AVG(salary) AS avg_salary FROM Employee GROUP BY dept_id HAVING AVG(salary) > 70000 ORDER BY avg_salary DESC;
```

**Expected result**
PASS; dept 4 = 91000.0; dept 1 = 78333.3333 (approximately).

**What it demonstrates:** Demonstrates aggregate filtering after grouping.

### TC08 — INNER JOIN (Valid query)

**Input SQL**
```sql
SELECT e.name, d.name AS department FROM Employee e JOIN Department d ON e.dept_id = d.id ORDER BY e.id LIMIT 4;
```

**Expected result**
PASS; Arjun | Engineering; Neha | Engineering; Riya | HR; Kabir | Sales.

**What it demonstrates:** Shows alias resolution and join handling.

### TC09 — IN predicate (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE dept_id IN (1, 4) ORDER BY name;
```

**Expected result**
PASS; Aman; Arjun; Ishita; Neha.

**What it demonstrates:** Demonstrates IN list parsing/execution.

### TC10 — BETWEEN predicate (Valid query)

**Input SQL**
```sql
SELECT name, salary FROM Employee WHERE salary BETWEEN 60000 AND 80000 ORDER BY salary;
```

**Expected result**
PASS; Kabir | 65000; Priya | 69000; Neha | 72000; Aman | 78000.

**What it demonstrates:** Shows range filtering.

### TC11 — LIKE pattern (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE name LIKE 'A%' ORDER BY name;
```

**Expected result**
PASS; Aman; Arjun.

**What it demonstrates:** Shows string pattern matching.

### TC12 — IS NOT NULL (Valid query)

**Input SQL**
```sql
SELECT name FROM Project WHERE manager_id IS NOT NULL ORDER BY name;
```

**Expected result**
PASS; AI Platform; Analytics; CRM; ERP; Mobile App.

**What it demonstrates:** Shows null predicate support.

### TC13 — Empty result / IS NULL (Valid query)

**Input SQL**
```sql
SELECT name FROM Project WHERE manager_id IS NULL;
```

**Expected result**
PASS; 0 rows returned (the seeded projects all have manager IDs).

**What it demonstrates:** Useful no-results edge case; zero rows is not an error.

### TC14 — Arithmetic expression (Valid query)

**Input SQL**
```sql
SELECT name, salary + 1000 AS adjusted_salary FROM Employee WHERE id = 1;
```

**Expected result**
PASS; Arjun | 86000.

**What it demonstrates:** Shows expression parsing and SQL execution.

### TC15 — LEFT JOIN (Valid query)

**Input SQL**
```sql
SELECT e.name, d.name AS department FROM Employee e LEFT JOIN Department d ON e.dept_id = d.id ORDER BY e.id LIMIT 3;
```

**Expected result**
PASS; Arjun | Engineering; Neha | Engineering; Aman | Engineering.

**What it demonstrates:** Shows outer-join syntax; optimizer preserves its order.

### TC16 — COUNT(DISTINCT ...) (Valid query)

**Input SQL**
```sql
SELECT COUNT(DISTINCT dept_id) AS departments FROM Employee;
```

**Expected result**
PASS; departments = 4.

**What it demonstrates:** Shows aggregate DISTINCT.

### TC17 — NOT IN (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE dept_id NOT IN (1, 2) ORDER BY name;
```

**Expected result**
PASS; Ishita; Kabir; Rahul.

**What it demonstrates:** Negative membership condition.

### TC18 — NOT BETWEEN (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE salary NOT BETWEEN 60000 AND 80000 ORDER BY name;
```

**Expected result**
PASS; Arjun; Ishita; Rahul; Riya.

**What it demonstrates:** Negative range predicate.

### TC19 — NOT LIKE (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE name NOT LIKE 'A%' ORDER BY name;
```

**Expected result**
PASS; Ishita; Kabir; Neha; Priya; Rahul; Riya.

**What it demonstrates:** Negative string-pattern predicate.

### TC20 — AND/OR precedence (Valid query)

**Input SQL**
```sql
SELECT name FROM Employee WHERE dept_id = 1 OR dept_id = 2 AND salary > 70000 ORDER BY name;
```

**Expected result**
PASS; Aman; Arjun; Neha. AND binds more tightly than OR.

**What it demonstrates:** Useful parser precedence explanation.

### TC21 — Full compiler/optimizer demo (Valid query)

**Input SQL**
```sql
SELECT d.name AS department, COUNT(e.id) AS employee_count, AVG(e.salary) AS average_salary FROM Employee e JOIN Department d ON e.dept_id = d.id JOIN Assignment a ON e.id = a.employee_id JOIN Project p ON a.project_id = p.id WHERE e.salary > 60000 AND p.budget > 100000 GROUP BY d.name HAVING AVG(e.salary) > 65000 ORDER BY AVG(e.salary) DESC LIMIT 5;
```

**Expected result**
PASS; Finance | 1 | 91000.0; Engineering | 5 | 79600.0; HR | 1 | 69000.0. 3 rows. 6 candidate plans; lowest estimate 115222.63 model units (Plan 1 and Plan 2 tie).

**What it demonstrates:** Best end-to-end demonstration of all implemented stages.

### TC22 — Unknown column (Expected semantic rejection)

**Input SQL**
```sql
SELECT e.unknown_column FROM Employee e;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Unknown column: e.unknown_column. No SQL is executed.

**What it demonstrates:** Menu option 7 demonstrates an unknown-column rejection.

### TC23 — Unknown table (Expected semantic rejection)

**Input SQL**
```sql
SELECT name FROM Staff;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Unknown table: Staff; Unknown column: name.

**What it demonstrates:** Shows schema-aware name validation.

### TC24 — Unknown alias (Expected semantic rejection)

**Input SQL**
```sql
SELECT x.name FROM Employee e;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Unknown table or alias: x.

**What it demonstrates:** Shows alias checking.

### TC25 — Ambiguous unqualified column (Expected semantic rejection)

**Input SQL**
```sql
SELECT id FROM Employee e JOIN Department d ON e.dept_id = d.id;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Ambiguous column: id (matches e.id, d.id).

**What it demonstrates:** Shows ambiguity detection.

### TC26 — Missing projection (Expected syntax rejection)

**Input SQL**
```sql
SELECT FROM Employee;
```

**Expected result**
REJECT at SYNTAX ANALYSIS: unexpected FROM at line 1, column 8.

**What it demonstrates:** Shows syntax error location.

### TC27 — Illegal character (Expected lexical rejection)

**Input SQL**
```sql
SELECT @ FROM Employee;
```

**Expected result**
REJECT at LEXICAL ANALYSIS: unexpected character '@' at line 1, column 8.

**What it demonstrates:** Shows lexical error handling.

### TC28 — Aggregate inside WHERE (Expected semantic rejection)

**Input SQL**
```sql
SELECT e.name FROM Employee e WHERE AVG(e.salary) > 50000;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Aggregate function AVG is not allowed in this clause.

**What it demonstrates:** Shows clause-specific semantic validation.

### TC29 — Invalid GROUP BY projection (Expected semantic rejection)

**Input SQL**
```sql
SELECT e.name, COUNT(*) FROM Employee e GROUP BY e.dept_id;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Selected column e.name must appear in GROUP BY or be aggregated.

**What it demonstrates:** Shows grouping rule validation.

### TC30 — Non-integer LIMIT (Expected syntax rejection)

**Input SQL**
```sql
SELECT name FROM Employee LIMIT 2.5;
```

**Expected result**
REJECT at SYNTAX ANALYSIS: LIMIT must be a non-negative integer.

**What it demonstrates:** Shows boundary/type constraint for LIMIT.

### TC31 — Empty IN list (Expected syntax rejection)

**Input SQL**
```sql
SELECT name FROM Employee WHERE id IN ();
```

**Expected result**
REJECT at SYNTAX ANALYSIS: invalid empty IN list.

**What it demonstrates:** Shows malformed predicate rejection.

### TC32 — Unsupported function (Expected semantic rejection)

**Input SQL**
```sql
SELECT explode(e.salary) FROM Employee e;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: Unsupported function: EXPLODE.

**What it demonstrates:** Shows supported-function validation.

### TC33 — AVG on text column (Expected semantic rejection)

**Input SQL**
```sql
SELECT AVG(e.name) FROM Employee e;
```

**Expected result**
REJECT at SEMANTIC ANALYSIS: AVG requires a numeric column.

**What it demonstrates:** Shows basic aggregate argument-type checking.

### TC34 — Multiple statements (Expected syntax rejection)

**Input SQL**
```sql
SELECT name FROM Employee; SELECT name FROM Department;
```

**Expected result**
REJECT at SYNTAX ANALYSIS: multiple statements are not supported.

**What it demonstrates:** Confirms one input must be one supported SELECT.

### TC35 — Cost calculation / access-path choice

**Command:** `python3 main.py --cost-demo` or choose menu option `5`.

**Worked input SQL:**
```sql
SELECT e.name FROM Employee e WHERE e.salary > 60000;
```

**Expected calculation using the current synthetic model:** Employee input estimate N = 10,000; selectivity = 0.72; estimated output ≈ 7,200 rows. Full scan + predicate = 10,000 + (0.20 × 10,000) = 12,000. Index scan = 2 × log2(10,000) + (0.60 × 7,200) = 4,346.58. The index scan has the lower estimate.

**Full multi-join candidate comparison:** Plans 1 and 2 each have estimated cost 115,222.63; Plans 3 and 4 each 121,702.63; Plans 5 and 6 each 123,862.63 model units. The program returns the first minimum candidate when there is a tie.

**Important:** model units are not milliseconds. The selected COSTRA estimate is not injected into SQLite; SQLite independently chooses its execution plan.

### TC36 — Review-wise presentation commands

| Goal | Input/command | Expected demonstration |
|---|---|---|
| Review 1 design | `python3 main.py --review1-demo` or menu option 1 | Problem, objectives, scope and architecture summary |
| Review 2 implementation | `python3 main.py --review2-demo` or menu option 2 | Lexer, parser/AST, semantic checks, IR and sample execution |
| Review 3 full pipeline | `python3 main.py --demo` or menu option 3 | Full multi-join compile/plan/execute flow |
| User-provided SQL | Menu option 4; then paste TC02 | Executes the custom SELECT |
| Cost calculation | `python3 main.py --cost-demo` or menu option 5 | Worked full-scan/index estimate and plan comparison |
| Review milestone summary | `python3 main.py --progress-demo` or menu option 6 | Review 1 → Review 2 → Review 3 |
| Error demonstration | `python3 main.py --error-demo` or menu option 7 | Unknown-column rejection before execution |

## Automated verification

The current regression suite contains **52 automated tests** spanning lexer errors and tokenization, parsing and clause handling, semantic validation, optimizer selection, SQLite integration, and command-line demonstration modes. Run it using:
```bash
python3 -m unittest -v
```
The latest checked run completed with 52 tests passing. Run the suite again on the machine used for submission and keep the fresh terminal output as evidence.

## Seeded sample data note

The executable SQLite example uses a small deterministic in-memory fixture (8 employees, 4 departments, 5 projects and 8 assignments). The optimizer’s 10,000 Employee / 1,200 Project / 30,000 Assignment figures are separate synthetic planning statistics, not counts gathered from the execution fixture.
