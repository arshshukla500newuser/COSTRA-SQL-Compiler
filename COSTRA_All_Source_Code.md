# COSTRA — All Runtime Source Code

This listing is generated from the current project files. It represents the runtime compiler/optimizer and its tests; presentation-authoring code is not part of the application.

---

## `main.py`

```python
"""Interactive COSTRA demo: parse, validate, estimate, then execute with SQLite."""
from __future__ import annotations
import argparse
import time
from dataclasses import dataclass, field
from typing import Optional
from compiler import CompilationResult, compile_sql
from executor import Executor, ExecutionError
from ast_nodes import ColumnRef, Literal, BinaryExpr, UnaryExpr, FunctionCall, IsNullExpr, InExpr, BetweenExpr
from optimizer import CostModel
from schema import STATS
from statistics import selectivity

DEMO_SQL = """
SELECT
    d.name AS department,
    COUNT(e.id) AS employee_count,
    AVG(e.salary) AS average_salary
FROM Employee e
JOIN Department d ON e.dept_id = d.id
JOIN Assignment a ON e.id = a.employee_id
JOIN Project p ON a.project_id = p.id
WHERE e.salary > 60000 AND p.budget > 100000
GROUP BY d.name
HAVING AVG(e.salary) > 65000
ORDER BY AVG(e.salary) DESC
LIMIT 5;
""".strip()


@dataclass
class QueryRunResult:
    compilation: CompilationResult
    executed: bool = False
    headers: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    executable_sql: Optional[str] = None
    sqlite_plan: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    execution_error: Optional[str] = None


def _expression_text(node, depth=0):
    indent = "  " * depth
    if isinstance(node, ColumnRef):
        return indent + "COLUMN " + ((node.table + ".") if node.table else "") + node.name
    if isinstance(node, Literal):
        return indent + f"LITERAL {node.value!r}"
    if isinstance(node, FunctionCall):
        rows = [indent + f"FUNCTION {node.name.upper()}" + (" DISTINCT" if node.distinct else "")]
        if node.argument != "*":
            rows.append(_expression_text(node.argument, depth + 1))
        else:
            rows.append("  " * (depth + 1) + "STAR")
        return "\n".join(rows)
    if isinstance(node, BinaryExpr):
        return "\n".join([indent + f"BINARY {node.operator}", _expression_text(node.left, depth + 1), _expression_text(node.right, depth + 1)])
    if isinstance(node, UnaryExpr):
        return "\n".join([indent + f"UNARY {node.operator}", _expression_text(node.operand, depth + 1)])
    if isinstance(node, IsNullExpr):
        return "\n".join([indent + f"IS {'NOT ' if node.negated else ''}NULL", _expression_text(node.expression, depth + 1)])
    if isinstance(node, InExpr):
        return "\n".join([indent + f"{'NOT ' if node.negated else ''}IN", _expression_text(node.expression, depth + 1)] + [_expression_text(v, depth + 1) for v in node.values])
    if isinstance(node, BetweenExpr):
        return "\n".join([indent + f"{'NOT ' if node.negated else ''}BETWEEN", _expression_text(node.expression, depth + 1), _expression_text(node.lower, depth + 1), _expression_text(node.upper, depth + 1)])
    return indent + repr(node)


def ast_summary(query):
    lines = ["SELECT" + (" DISTINCT" if query.distinct else "")]
    for item in query.columns:
        lines.append("  SELECT_ITEM" + (f" AS {item.alias}" if item.alias else ""))
        lines.append(_expression_text(item.expression, 2))
    lines.append(f"  FROM {query.table.name}" + (f" AS {query.table.alias}" if query.table.alias else ""))
    for join in query.joins:
        lines.append(f"  {join.join_type} JOIN {join.table.name}" + (f" AS {join.table.alias}" if join.table.alias else ""))
        lines.append("    ON\n" + _expression_text(join.condition, 3))
    if query.where is not None:
        lines.append("  WHERE\n" + _expression_text(query.where, 2))
    if query.group_by:
        lines.append("  GROUP BY")
        lines.extend(_expression_text(expr, 2) for expr in query.group_by)
    if query.having is not None:
        lines.append("  HAVING\n" + _expression_text(query.having, 2))
    if query.order_by:
        lines.append("  ORDER BY")
        lines.extend("    " + _expression_text(item.expression) + " " + item.direction for item in query.order_by)
    if query.limit is not None:
        lines.append(f"  LIMIT {query.limit}")
    return "\n".join(lines)


def run_query(sql: str, executor: Optional[Executor] = None) -> QueryRunResult:
    compilation = compile_sql(sql)
    output = QueryRunResult(compilation=compilation, timings_ms=dict(compilation.timings_ms))
    if not compilation.success or compilation.query is None:
        return output
    created_here = executor is None
    engine = executor or Executor()
    try:
        start = time.perf_counter()
        output.headers, output.rows, output.executable_sql = engine.execute(compilation.query)
        output.timings_ms["SQLite execution"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        output.sqlite_plan = engine.explain(compilation.query)
        output.timings_ms["SQLite EXPLAIN QUERY PLAN"] = (time.perf_counter() - start) * 1000
        output.executed = True
    except ExecutionError as exc:
        output.execution_error = str(exc)
    finally:
        if created_here:
            engine.close()
    return output


def _print_result(result: QueryRunResult):
    comp = result.compilation
    print("\n" + "=" * 78 + "\nCOSTRA — COST-BASED SQL COMPILER & QUERY OPTIMIZER\n" + "=" * 78)
    print("\nSQL INPUT\n" + "-" * 78 + "\n" + comp.sql.strip())
    print("\n1. LEXICAL ANALYSIS")
    print(f"Tokens recognised: {max(0, len(comp.tokens) - 1)}")
    print("Token stream: " + " ".join(token.kind for token in comp.tokens if token.kind != "EOF")[:800])
    if comp.failed_stage == "LEXICAL ANALYSIS":
        _print_errors(comp)
        return
    print("\n2. SYNTAX ANALYSIS + ABSTRACT SYNTAX TREE")
    if comp.query:
        print("Syntax: VALID")
        print(ast_summary(comp.query))
    if comp.failed_stage == "SYNTAX ANALYSIS":
        _print_errors(comp)
        return
    print("\n3. SEMANTIC ANALYSIS")
    if comp.errors and comp.failed_stage == "SEMANTIC ANALYSIS":
        _print_errors(comp)
        return
    print("Semantic checks passed. Table/alias map:")
    for alias, table in comp.aliases.items():
        print(f"  {alias} -> {table}")
    print("\n4. RELATIONAL INTERMEDIATE REPRESENTATION (LOGICAL PLAN)")
    print(comp.logical_plan.pretty(include_estimates=False) if comp.logical_plan else "Not generated")
    print("\n5. CANDIDATE PHYSICAL PLANS — SYNTHETIC ESTIMATES")
    for index, plan in enumerate(comp.candidates, start=1):
        print(f"Plan {index}: estimated cost {plan.cost:.2f} model units; estimated rows {plan.rows:.2f}")
    print("\n6. SELECTED ESTIMATED PLAN")
    if comp.best_plan:
        print(f"Lowest estimated cost: {comp.best_plan.cost:.2f} model units")
        print(comp.best_plan.pretty())
    print("Note: these relative cost estimates do not represent milliseconds and are not passed to SQLite.")
    if not result.executed:
        if result.execution_error:
            print("\n7. EXECUTION ERROR\n" + result.execution_error)
        return
    print("\n7. NORMALIZED SQL EXECUTED BY SQLITE\n" + (result.executable_sql or ""))
    print("\n8. EXECUTION RESULTS")
    print(" | ".join(result.headers))
    if result.headers:
        print("-" * min(100, max(24, len(" | ".join(result.headers)) + 4)))
    for row in result.rows:
        print(" | ".join("NULL" if value is None else str(value) for value in row))
    print(f"Rows returned: {len(result.rows)}")
    print("\n9. SQLITE'S OWN QUERY PLAN (SEPARATE FROM COSTRA'S ESTIMATE)")
    for line in result.sqlite_plan:
        print("  " + line)
    print("\n10. OBSERVED STAGE TIMINGS")
    for label, milliseconds in result.timings_ms.items():
        print(f"  {label:<34} {milliseconds:.3f} ms")
    print("Timings are a single local run on a tiny in-memory fixture; they are evidence, not a general benchmark.")


def _print_errors(compilation):
    print(f"\n{compilation.failed_stage or 'ERROR'} FAILED")
    for error in compilation.errors:
        print("  - " + error)
    print("No SQL was executed because this stage did not pass.")


def _print_review1_summary():
    print("\n" + "=" * 70)
    print("REVIEW 1 — PROBLEM DEFINITION & SYSTEM DESIGN")
    print("=" * 70)
    print("PROBLEM\n  SQL queries hide the internal steps that transform source text into a validated\n  query plan. COSTRA makes those steps visible for learning and demonstration.")
    print("\nOBJECTIVES\n  1. Tokenize a documented subset of SQL.\n  2. Parse tokens into an AST and validate table/alias/column references.\n  3. Build a relational logical plan.\n  4. Estimate alternative access paths and join orders.\n  5. Execute the normalized query separately through SQLite.")
    print("\nSCOPE\n  SELECT, joins, filters, grouping, HAVING, sorting, LIMIT, and supported\n  aggregate expressions. COSTRA is an educational SQL compiler/optimizer prototype,\n  not a full SQL implementation or a production database engine.")
    print("\nDESIGNED PIPELINE\n  SQL → Lexer → Parser/AST → Semantic Analysis → Relational IR\n      → Cardinality & Selectivity → Candidate Plans → Cost Comparison\n      → Normalized SQL → SQLite Results")
    print("\nREVIEW 1 OUTPUT\n  Problem statement, objectives, scope, architecture, methodology, and prototype plan.")


def _print_review2_pipeline():
    sql = "SELECT e.name, e.salary FROM Employee e WHERE e.salary > 80000 ORDER BY e.salary DESC LIMIT 3;"
    result = run_query(sql)
    comp = result.compilation
    print("\n" + "=" * 70)
    print("REVIEW 2 — CORE IMPLEMENTATION WALKTHROUGH")
    print("=" * 70)
    print("Representative SQL:\n  " + sql)
    print(f"\n1. LEXER: {max(0, len(comp.tokens) - 1)} tokens recognised.")
    print("   First tokens: " + " ".join(t.kind for t in comp.tokens if t.kind != "EOF")[:200])
    if not comp.success or comp.query is None:
        _print_errors(comp)
        return
    print("\n2. PARSER / AST: SQL syntax accepted.")
    print(ast_summary(comp.query))
    print("\n3. SEMANTIC ANALYSIS: all referenced names passed validation.")
    for alias, table in comp.aliases.items():
        print(f"   {alias} -> {table}")
    print("\n4. RELATIONAL IR: logical operators before choosing a physical implementation.")
    print(comp.logical_plan.pretty(include_estimates=False) if comp.logical_plan else "Not generated")
    print("\n5. EXECUTION CHECK: this prototype can then pass normalized SQL to SQLite.")
    if result.executed:
        print(" | ".join(result.headers))
        for row in result.rows:
            print(" | ".join("NULL" if value is None else str(value) for value in row))
        print(f"Rows returned: {len(result.rows)}")
    else:
        print(result.execution_error or "Execution did not complete.")
    print("\nREVIEW 2 OUTPUT\n  Working lexer, parser/AST, semantic validation, relational IR, plan estimates,\n  sample execution, and module-level evidence. The next milestone integrates and validates the whole system.")


def _print_review_progress():
    print("\n" + "=" * 70)
    print("COSTRA — REVIEW-WISE PROGRESS")
    print("=" * 70)
    print("REVIEW 1 | DESIGN\n  • Problem statement, motivation, objectives and supported SQL scope\n  • Architecture, methodology and compiler-stage mapping\n  • Output: approved plan for implementation")
    print("\nREVIEW 2 | CORE IMPLEMENTATION\n  • Lexer and parser/AST\n  • Semantic checks and relational IR\n  • Candidate-plan generation, synthetic cost estimates and SQLite-backed demo\n  • Output: working core modules and implementation evidence")
    print("\nREVIEW 3 | INTEGRATION & VALIDATION\n  • User-provided SQL through the full pipeline\n  • Worked cost formulas and lowest-cost candidate selection\n  • SQLite results and its separate EXPLAIN QUERY PLAN\n  • Error handling, regression tests, benchmark evidence and documentation\n  • Output: complete educational prototype and final submission package")
    print("\nIMPORTANT\n  The three reviews are milestones, not separate compilers. The final demo connects\n  the modules into one visible workflow. Cost values are model units, not milliseconds.")


def _print_cost_analysis():
    print("\n" + "=" * 70)
    print("COST CALCULATION & BEST ESTIMATED PLAN")
    print("=" * 70)
    sample_sql = "SELECT e.name FROM Employee e WHERE e.salary > 60000;"
    compiled = compile_sql(sample_sql)
    if not compiled.success or compiled.query is None:
        _print_errors(compiled)
        return
    employee_rows = float(STATS["Employee"]["rows"])
    fraction = selectivity(compiled.query.where, compiled.aliases)
    estimated_output = max(1.0, employee_rows * fraction)
    model = CostModel()
    full_scan_cost = model.full_scan(employee_rows) + model.predicate(employee_rows)
    index_cost = model.index_scan(employee_rows, estimated_output)
    print("WORKED ACCESS-PATH EXAMPLE")
    print("SQL: " + sample_sql)
    print(f"Synthetic Employee rows N = {employee_rows:,.0f}")
    print(f"Estimated selectivity = {fraction:.4f}  →  output rows ≈ {estimated_output:,.0f}")
    print("\nFull scan + predicate")
    print(f"  N + (0.20 × N) = {employee_rows:,.0f} + (0.20 × {employee_rows:,.0f}) = {full_scan_cost:,.2f}")
    print("\nIndex scan")
    print(f"  2 × log2(max(2, N)) + (0.60 × output_rows)")
    print(f"  2 × log2({employee_rows:,.0f}) + (0.60 × {estimated_output:,.0f}) = {index_cost:,.2f}")
    access_choice = "INDEX SCAN" if index_cost < full_scan_cost else "FULL TABLE SCAN"
    print(f"\nAccess-path decision: {access_choice} has the lower estimate.")

    print("\nFULL MULTI-JOIN QUERY — CANDIDATE PLAN COMPARISON")
    multi = compile_sql(DEMO_SQL)
    if not multi.success or multi.best_plan is None:
        _print_errors(multi)
        return
    for i, candidate in enumerate(multi.candidates, 1):
        print(f"  Plan {i}: {candidate.cost:,.2f} model units; rows ≈ {candidate.rows:.2f}")
    lowest = min(p.cost for p in multi.candidates)
    winners = [i for i, p in enumerate(multi.candidates, 1) if abs(p.cost - lowest) < 1e-9]
    winner_text = ", ".join(f"Plan {i}" for i in winners)
    print(f"\nLowest estimate: {lowest:,.2f} model units")
    print(f"Lowest-cost candidate(s): {winner_text}")
    print("Selection rule: choose the candidate with the minimum estimated total cost.")
    if len(winners) > 1:
        print("Tie note: the first minimum candidate in enumeration order is returned; the tied plan has the same estimated cost.")
    print("\nJOIN COST FORMULAS USED")
    print("  Nested loop = 0.15 × L × max(1, R)")
    print("  Hash join   = 1.10 × (L + R) + 0.25 × min(L, R)")
    print("  Merge join  = 0.80 × (L + R) + 0.45L log2(max(2,L)) + 0.45R log2(max(2,R))")
    print("\nThese are synthetic relative model units. They are not elapsed time and are not passed to SQLite.")


def _custom_query_prompt():
    print("\nEnter one supported SELECT statement on a single line.")
    print("Example: SELECT name, salary FROM Employee WHERE salary > 80000;")
    try:
        sql = input("SQL> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nReturning to menu.")
        return
    if not sql:
        print("No SQL entered. Returning to menu.")
        return
    _print_result(run_query(sql))


def interactive_menu():
    """Switch-style menu for professor-selected Review 1/2/3 demonstrations."""
    # A dictionary-based dispatch keeps the switch-like structure compatible with Python 3.9+.
    handlers = {
        "1": _print_review1_summary,
        "2": _print_review2_pipeline,
        "3": lambda: _print_result(run_query(DEMO_SQL)),
        "4": _custom_query_prompt,
        "5": _print_cost_analysis,
        "6": _print_review_progress,
        "7": lambda: _print_result(run_query("SELECT e.unknown_column FROM Employee e;")),
    }
    labels = {
        "1": "Review 1 — problem definition, objectives and design",
        "2": "Review 2 — core compiler stages and sample execution",
        "3": "Review 3 — complete end-to-end demonstration",
        "4": "Enter my own SELECT query",
        "5": "Show cost calculation and choose the lowest-cost plan",
        "6": "Compare Review 1 → Review 2 → Review 3 progress",
        "7": "Demonstrate semantic error handling",
        "8": "Exit",
    }
    while True:
        print("\n" + "=" * 68 + "\nCOSTRA — PROFESSOR-SELECTABLE DEMO MENU\n" + "=" * 68)
        for key, label in labels.items():
            print(f"{key}. {label}")
        try:
            choice = input("Choose a demo (1-8): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting COSTRA.")
            break
        if choice == "8":
            print("Goodbye.")
            break
        handler = handlers.get(choice)
        if handler is None:
            print("Invalid option. Please choose a number from 1 to 8.")
            continue
        handler()


def main(argv=None):
    """CLI entry point for both individual demo modes and the interactive menu."""
    parser = argparse.ArgumentParser(
        description="COSTRA: demonstrate SQL compilation, estimated cost selection and SQLite execution."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="run the complete multi-join demonstration and exit")
    mode.add_argument("--error-demo", action="store_true", help="show an unknown-column semantic error and exit")
    mode.add_argument("--review1-demo", action="store_true", help="show Review 1 design summary")
    mode.add_argument("--review2-demo", action="store_true", help="show Review 2 core implementation walkthrough")
    mode.add_argument("--cost-demo", action="store_true", help="show cost formulas, a worked calculation, and plan selection")
    mode.add_argument("--progress-demo", action="store_true", help="show Review 1/2/3 milestones")
    mode.add_argument("--query", metavar="SQL", help="compile and execute one SELECT query, then exit")
    args = parser.parse_args(argv)

    if args.demo:
        _print_result(run_query(DEMO_SQL))
        return 0
    if args.error_demo:
        _print_result(run_query("SELECT e.unknown_column FROM Employee e;"))
        # Semantic rejection is the expected outcome of this demonstration.
        return 0
    if args.review1_demo:
        _print_review1_summary()
        return 0
    if args.review2_demo:
        _print_review2_pipeline()
        return 0
    if args.cost_demo:
        _print_cost_analysis()
        return 0
    if args.progress_demo:
        _print_review_progress()
        return 0
    if args.query is not None:
        result = run_query(args.query)
        _print_result(result)
        return 0 if result.compilation.success and result.executed else 2

    interactive_menu()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## `compiler.py`

```python
"""Orchestrates COSTRA's lexical, syntax, semantic and optimization stages."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from time import perf_counter
from ast_nodes import SelectQuery, format_query
from ir import PlanNode
from lexer import Token, tokenize
from optimizer import optimize
from parser import parse_tokens
from semantic import SemanticAnalyzer


@dataclass
class CompilationResult:
    success: bool
    sql: str
    tokens: list[Token] = field(default_factory=list)
    query: Optional[SelectQuery] = None
    aliases: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    failed_stage: Optional[str] = None
    logical_plan: Optional[PlanNode] = None
    candidates: list[PlanNode] = field(default_factory=list)
    best_plan: Optional[PlanNode] = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    normalized_sql: Optional[str] = None


def compile_sql(sql: str) -> CompilationResult:
    """Run COSTRA's compile/optimization pipeline without executing the SQL."""
    result = CompilationResult(success=False, sql=sql)
    start = perf_counter()
    try:
        result.tokens = tokenize(sql)
        result.timings_ms["lexical analysis"] = (perf_counter() - start) * 1000
    except (ValueError, TypeError) as exc:
        result.failed_stage = "LEXICAL ANALYSIS"
        result.errors = [str(exc)]
        result.timings_ms["lexical analysis"] = (perf_counter() - start) * 1000
        return result

    start = perf_counter()
    try:
        result.query = parse_tokens(result.tokens)
        result.normalized_sql = format_query(result.query)
        result.timings_ms["syntax analysis + AST"] = (perf_counter() - start) * 1000
    except (SyntaxError, ValueError, IndexError) as exc:
        result.failed_stage = "SYNTAX ANALYSIS"
        result.errors = [str(exc)]
        result.timings_ms["syntax analysis + AST"] = (perf_counter() - start) * 1000
        return result

    start = perf_counter()
    result.errors, result.aliases = SemanticAnalyzer().analyze(result.query)
    result.timings_ms["semantic analysis"] = (perf_counter() - start) * 1000
    if result.errors:
        result.failed_stage = "SEMANTIC ANALYSIS"
        return result

    start = perf_counter()
    try:
        result.logical_plan, result.candidates, result.best_plan = optimize(result.query)
        result.timings_ms["cost estimation + plan search"] = (perf_counter() - start) * 1000
    except (ValueError, KeyError, TypeError) as exc:
        result.failed_stage = "OPTIMIZATION"
        result.errors = [str(exc)]
        result.timings_ms["cost estimation + plan search"] = (perf_counter() - start) * 1000
        return result

    result.success = True
    return result
```

---

## `lexer.py`

```python
"""Lexer for the SQL subset supported by COSTRA."""
from __future__ import annotations
from dataclasses import dataclass
import re

KEYWORDS = {
    "SELECT", "DISTINCT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
    "ON", "AND", "OR", "NOT", "GROUP", "BY", "HAVING", "ORDER", "ASC", "DESC", "LIMIT",
    "AS", "COUNT", "SUM", "AVG", "MIN", "MAX", "IS", "NULL", "LIKE", "IN", "BETWEEN",
    "TRUE", "FALSE", "CROSS",
}

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


TOKEN_SPEC = [
    ("COMMENT", r"--[^\n]*"),
    ("NUMBER", r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"),
    ("STRING", r"'(?:''|[^'])*'"),
    ("OPERATOR", r"!=|<>|<=|>=|=|<|>|\+|-|\*|/|%"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SEMICOLON", r";"),
    ("IDENTIFIER", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP", r"[ \t\r\n]+"),
    ("MISMATCH", r"."),
]
MASTER = re.compile("|".join(f"(?P<{kind}>{pattern})" for kind, pattern in TOKEN_SPEC))


def tokenize(sql: str) -> list[Token]:
    if not isinstance(sql, str):
        raise TypeError("SQL input must be a string")
    tokens: list[Token] = []
    line = 1
    line_start = 0
    for match in MASTER.finditer(sql):
        kind = match.lastgroup or "MISMATCH"
        value = match.group()
        column = match.start() - line_start + 1
        if kind in ("COMMENT", "SKIP"):
            newline_count = value.count("\n")
            if newline_count:
                line += newline_count
                line_start = match.start() + value.rfind("\n") + 1
            continue
        if kind == "IDENTIFIER" and value.upper() in KEYWORDS:
            kind = value.upper()
        if kind == "MISMATCH":
            raise ValueError(
                f"Lexical error at line {line}, column {column}: unexpected character {value!r}"
            )
        tokens.append(Token(kind, value, line, column))
    tokens.append(Token("EOF", "", line, len(sql.rsplit("\n", 1)[-1]) + 1))
    return tokens
```

---

## `parser.py`

```python
"""Recursive-descent parser for COSTRA's documented SELECT grammar."""
from __future__ import annotations
from typing import Optional
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr, Literal,
    JoinClause, OrderItem, SelectItem, SelectQuery, TableRef, UnaryExpr,
)
from lexer import Token, tokenize

AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def current(self) -> Token:
        return self.tokens[self.index]

    def match(self, *kinds: str) -> Optional[Token]:
        if self.current().kind in kinds:
            token = self.current()
            self.index += 1
            return token
        return None

    def expect(self, kind: str) -> Token:
        token = self.current()
        if token.kind != kind:
            raise SyntaxError(
                f"Syntax error at line {token.line}, column {token.column}: "
                f"expected {kind}, found {token.kind} ({token.value!r})"
            )
        self.index += 1
        return token

    def identifier(self) -> str:
        return self.expect("IDENTIFIER").value

    def parse(self) -> SelectQuery:
        query = self.select_statement()
        self.match("SEMICOLON")
        self.expect("EOF")
        return query

    def select_statement(self) -> SelectQuery:
        self.expect("SELECT")
        distinct = bool(self.match("DISTINCT"))
        columns = self.select_list()
        self.expect("FROM")
        table = self.table_ref()
        joins = []
        while self.current().kind in ("JOIN", "INNER", "LEFT", "RIGHT", "CROSS"):
            joins.append(self.join_clause())
        where = self.expression() if self.match("WHERE") else None
        group_by = []
        if self.match("GROUP"):
            self.expect("BY")
            group_by = self.expression_list()
        having = self.expression() if self.match("HAVING") else None
        order_by = []
        if self.match("ORDER"):
            self.expect("BY")
            order_by = self.order_list()
        limit = None
        if self.match("LIMIT"):
            token = self.expect("NUMBER")
            # LIMIT is deliberately restricted to a non-negative integer.
            if not token.value.isdigit():
                raise SyntaxError(
                    f"LIMIT must be a non-negative integer at line {token.line}, column {token.column}"
                )
            limit = int(token.value)
        return SelectQuery(columns, table, joins, where, group_by, having, order_by, limit, distinct)

    def select_list(self) -> list[SelectItem]:
        items = []
        while True:
            expression = self.expression()
            alias = None
            if self.match("AS"):
                alias = self.identifier()
            elif self.current().kind == "IDENTIFIER":
                alias = self.identifier()
            items.append(SelectItem(expression, alias))
            if not self.match("COMMA"):
                return items

    def table_ref(self) -> TableRef:
        name = self.identifier()
        alias = None
        if self.match("AS"):
            alias = self.identifier()
        elif self.current().kind == "IDENTIFIER":
            alias = self.identifier()
        return TableRef(name, alias)

    def join_clause(self):
        join_type = "INNER"
        if self.match("INNER"):
            self.expect("JOIN")
        elif self.match("LEFT"):
            join_type = "LEFT"
            self.match("OUTER")
            self.expect("JOIN")
        elif self.match("RIGHT"):
            join_type = "RIGHT"
            self.match("OUTER")
            self.expect("JOIN")
        elif self.match("CROSS"):
            join_type = "CROSS"
            self.expect("JOIN")
            table = self.table_ref()
            return JoinClause(table, Literal(True), join_type)
        else:
            self.expect("JOIN")
        table = self.table_ref()
        self.expect("ON")
        return JoinClause(table, self.expression(), join_type)

    def expression_list(self):
        values = [self.expression()]
        while self.match("COMMA"):
            values.append(self.expression())
        return values

    def order_list(self):
        items = []
        while True:
            expr = self.expression()
            direction = "DESC" if self.match("DESC") else "ASC"
            if direction == "ASC":
                self.match("ASC")
            items.append(OrderItem(expr, direction))
            if not self.match("COMMA"):
                return items

    # Precedence, low to high: OR, AND, NOT, comparison, +/-, */%, unary, primary.
    def expression(self):
        return self.or_expression()

    def or_expression(self):
        node = self.and_expression()
        while self.match("OR"):
            node = BinaryExpr(node, "OR", self.and_expression())
        return node

    def and_expression(self):
        node = self.not_expression()
        while self.match("AND"):
            node = BinaryExpr(node, "AND", self.not_expression())
        return node

    def not_expression(self):
        if self.match("NOT"):
            return UnaryExpr("NOT", self.not_expression())
        return self.comparison()

    def comparison(self):
        node = self.additive()
        if self.current().kind == "OPERATOR" and self.current().value in {
            "=", "!=", "<>", "<", "<=", ">", ">="
        }:
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, "<>" if op == "!=" else op, self.additive())
            return node
        if self.match("IS"):
            negated = bool(self.match("NOT"))
            self.expect("NULL")
            return IsNullExpr(node, negated)
        negated = False
        if self.current().kind == "NOT" and self.index + 1 < len(self.tokens) and self.tokens[self.index + 1].kind in ("IN", "BETWEEN", "LIKE"):
            self.index += 1
            negated = True
        if self.match("IN"):
            self.expect("LPAREN")
            values = []
            if self.current().kind != "RPAREN":
                values = self.expression_list()
            self.expect("RPAREN")
            if not values:
                raise SyntaxError("IN lists must contain at least one value")
            return InExpr(node, tuple(values), negated)
        if self.match("BETWEEN"):
            lower = self.additive()
            self.expect("AND")
            upper = self.additive()
            return BetweenExpr(node, lower, upper, negated)
        if self.match("LIKE"):
            right = self.additive()
            like = BinaryExpr(node, "LIKE", right)
            return UnaryExpr("NOT", like) if negated else like
        if negated:
            token = self.current()
            raise SyntaxError(f"Expected IN, BETWEEN, or LIKE after NOT at line {token.line}, column {token.column}")
        return node

    def additive(self):
        node = self.multiplicative()
        while self.current().kind == "OPERATOR" and self.current().value in ("+", "-"):
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, op, self.multiplicative())
        return node

    def multiplicative(self):
        node = self.unary()
        while self.current().kind == "OPERATOR" and self.current().value in ("*", "/", "%"):
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, op, self.unary())
        return node

    def unary(self):
        if self.current().kind == "OPERATOR" and self.current().value in ("+", "-"):
            op = self.current().value
            self.index += 1
            return UnaryExpr(op, self.unary())
        return self.primary()

    def primary(self):
        token = self.current()
        if self.match("LPAREN"):
            expr = self.expression()
            self.expect("RPAREN")
            return expr
        if token.kind == "NUMBER":
            self.index += 1
            try:
                value = float(token.value) if any(c in token.value.lower() for c in (".", "e")) else int(token.value)
            except ValueError as exc:
                raise SyntaxError(f"Invalid numeric literal {token.value!r}") from exc
            return Literal(value)
        if token.kind == "STRING":
            self.index += 1
            return Literal(token.value[1:-1].replace("''", "'"))
        if self.match("NULL"):
            return Literal(None)
        if self.match("TRUE"):
            return Literal(True)
        if self.match("FALSE"):
            return Literal(False)
        if token.kind == "OPERATOR" and token.value == "*":
            self.index += 1
            return ColumnRef("*")
        if token.kind == "IDENTIFIER" or token.kind in AGGREGATES:
            self.index += 1
            name = token.value
            if self.match("LPAREN"):
                distinct = bool(self.match("DISTINCT"))
                if self.current().kind == "OPERATOR" and self.current().value == "*":
                    self.index += 1
                    argument = "*"
                else:
                    argument = self.expression()
                self.expect("RPAREN")
                return FunctionCall(name.upper(), argument, distinct)
            if self.match("DOT"):
                if self.current().kind == "OPERATOR" and self.current().value == "*":
                    self.index += 1
                    return ColumnRef("*", name)
                return ColumnRef(self.identifier(), name)
            # Bare names that are aggregate keywords are not columns unless called as functions.
            if token.kind in AGGREGATES:
                raise SyntaxError(f"Expected '(' after function name {name!r} at line {token.line}, column {token.column}")
            return ColumnRef(name)
        raise SyntaxError(
            f"Syntax error at line {token.line}, column {token.column}: "
            f"unexpected {token.kind} ({token.value!r})"
        )


def parse_tokens(tokens: list[Token]) -> SelectQuery:
    return Parser(tokens).parse()


def parse_sql(sql: str) -> SelectQuery:
    return parse_tokens(tokenize(sql))
```

---

## `ast_nodes.py`

```python
"""Abstract syntax tree nodes and safe SQL pretty-printing for COSTRA's SQL subset."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ColumnRef:
    name: str
    table: Optional[str] = None


@dataclass(frozen=True)
class Literal:
    value: Any


@dataclass(frozen=True)
class BinaryExpr:
    left: Any
    operator: str
    right: Any


@dataclass(frozen=True)
class UnaryExpr:
    operator: str
    operand: Any


@dataclass(frozen=True)
class IsNullExpr:
    expression: Any
    negated: bool = False


@dataclass(frozen=True)
class InExpr:
    expression: Any
    values: tuple[Any, ...]
    negated: bool = False


@dataclass(frozen=True)
class BetweenExpr:
    expression: Any
    lower: Any
    upper: Any
    negated: bool = False


@dataclass(frozen=True)
class FunctionCall:
    name: str
    argument: Any
    distinct: bool = False


@dataclass(frozen=True)
class SelectItem:
    expression: Any
    alias: Optional[str] = None


@dataclass(frozen=True)
class TableRef:
    name: str
    alias: Optional[str] = None

    @property
    def reference_name(self) -> str:
        return self.alias or self.name


@dataclass(frozen=True)
class JoinClause:
    table: TableRef
    condition: Any
    join_type: str = "INNER"


@dataclass(frozen=True)
class OrderItem:
    expression: Any
    direction: str = "ASC"


@dataclass
class SelectQuery:
    columns: list[SelectItem] = field(default_factory=list)
    table: Optional[TableRef] = None
    joins: list[JoinClause] = field(default_factory=list)
    where: Optional[Any] = None
    group_by: list[Any] = field(default_factory=list)
    having: Optional[Any] = None
    order_by: list[OrderItem] = field(default_factory=list)
    limit: Optional[int] = None
    distinct: bool = False


def format_expr(node: Any) -> str:
    if isinstance(node, ColumnRef):
        if node.name == "*":
            return f"{node.table}.*" if node.table else "*"
        return f"{node.table}.{node.name}" if node.table else node.name
    if isinstance(node, Literal):
        if node.value is None:
            return "NULL"
        if isinstance(node.value, bool):
            return "TRUE" if node.value else "FALSE"
        if isinstance(node.value, str):
            return "'" + node.value.replace("'", "''") + "'"
        return str(node.value)
    if isinstance(node, BinaryExpr):
        return f"({format_expr(node.left)} {node.operator} {format_expr(node.right)})"
    if isinstance(node, UnaryExpr):
        if node.operator in ("+", "-"):
            return f"({node.operator}{format_expr(node.operand)})"
        return f"({node.operator} {format_expr(node.operand)})"
    if isinstance(node, IsNullExpr):
        return f"({format_expr(node.expression)} IS {'NOT ' if node.negated else ''}NULL)"
    if isinstance(node, InExpr):
        vals = ", ".join(format_expr(v) for v in node.values)
        return f"({format_expr(node.expression)} {'NOT ' if node.negated else ''}IN ({vals}))"
    if isinstance(node, BetweenExpr):
        return (f"({format_expr(node.expression)} {'NOT ' if node.negated else ''}BETWEEN "
                f"{format_expr(node.lower)} AND {format_expr(node.upper)})")
    if isinstance(node, FunctionCall):
        arg = "*" if node.argument == "*" else format_expr(node.argument)
        distinct = "DISTINCT " if node.distinct else ""
        return f"{node.name.upper()}({distinct}{arg})"
    return str(node)


def format_query(query: SelectQuery) -> str:
    """Render the AST back to a single SELECT statement accepted by SQLite."""
    if query.table is None:
        raise ValueError("Cannot format a SELECT without a FROM table")
    select = "SELECT DISTINCT" if query.distinct else "SELECT"
    projection = []
    for item in query.columns:
        piece = format_expr(item.expression)
        if item.alias:
            piece += f" AS {item.alias}"
        projection.append(piece)
    parts = [select, ", ".join(projection), "FROM", query.table.name]
    if query.table.alias:
        parts += ["AS", query.table.alias]
    for join in query.joins:
        join_type = join.join_type.upper()
        parts += [join_type, "JOIN", join.table.name]
        if join.table.alias:
            parts += ["AS", join.table.alias]
        if join_type != "CROSS":
            parts += ["ON", format_expr(join.condition)]
    if query.where is not None:
        parts += ["WHERE", format_expr(query.where)]
    if query.group_by:
        parts += ["GROUP BY", ", ".join(format_expr(item) for item in query.group_by)]
    if query.having is not None:
        parts += ["HAVING", format_expr(query.having)]
    if query.order_by:
        parts += ["ORDER BY", ", ".join(
            f"{format_expr(item.expression)} {item.direction.upper()}" for item in query.order_by
        )]
    if query.limit is not None:
        parts += ["LIMIT", str(query.limit)]
    return " ".join(parts) + ";"
```

---

## `semantic.py`

```python
"""Schema-aware semantic analysis for the supported SQL subset."""
from __future__ import annotations
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr,
    Literal, UnaryExpr, format_expr,
)
from schema import SCHEMA, canonical_table_name

AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
NUMERIC_TYPES = {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}


def walk_expression(node):
    """Yield an expression tree in preorder."""
    if node is None:
        return
    yield node
    if isinstance(node, BinaryExpr):
        yield from walk_expression(node.left)
        yield from walk_expression(node.right)
    elif isinstance(node, UnaryExpr):
        yield from walk_expression(node.operand)
    elif isinstance(node, FunctionCall) and node.argument != "*":
        yield from walk_expression(node.argument)
    elif isinstance(node, IsNullExpr):
        yield from walk_expression(node.expression)
    elif isinstance(node, InExpr):
        yield from walk_expression(node.expression)
        for value in node.values:
            yield from walk_expression(value)
    elif isinstance(node, BetweenExpr):
        yield from walk_expression(node.expression)
        yield from walk_expression(node.lower)
        yield from walk_expression(node.upper)


def contains_aggregate(node) -> bool:
    return any(isinstance(part, FunctionCall) and part.name.upper() in AGGREGATES
               for part in walk_expression(node))


def unaggregated_columns(node, inside_aggregate=False):
    """Collect column references not protected by an aggregate function."""
    found = []
    if node is None:
        return found
    if isinstance(node, ColumnRef):
        if node.name != "*" and not inside_aggregate:
            found.append(node)
    elif isinstance(node, FunctionCall):
        is_aggregate = node.name.upper() in AGGREGATES
        if node.argument != "*":
            found.extend(unaggregated_columns(node.argument, inside_aggregate or is_aggregate))
    elif isinstance(node, BinaryExpr):
        found.extend(unaggregated_columns(node.left, inside_aggregate))
        found.extend(unaggregated_columns(node.right, inside_aggregate))
    elif isinstance(node, UnaryExpr):
        found.extend(unaggregated_columns(node.operand, inside_aggregate))
    elif isinstance(node, IsNullExpr):
        found.extend(unaggregated_columns(node.expression, inside_aggregate))
    elif isinstance(node, InExpr):
        found.extend(unaggregated_columns(node.expression, inside_aggregate))
        for value in node.values:
            found.extend(unaggregated_columns(value, inside_aggregate))
    elif isinstance(node, BetweenExpr):
        for value in (node.expression, node.lower, node.upper):
            found.extend(unaggregated_columns(value, inside_aggregate))
    return found


class SemanticAnalyzer:
    def analyze(self, query):
        errors: list[str] = []
        aliases: dict[str, str] = {}
        references = []  # (reference name, canonical table name)

        all_refs = ([query.table] if query.table else []) + [join.table for join in query.joins]
        for table_ref in all_refs:
            actual = canonical_table_name(table_ref.name)
            if actual is None:
                errors.append(f"Unknown table: {table_ref.name}")
                continue
            ref_name = table_ref.alias or table_ref.name
            key = ref_name.casefold()
            if key in aliases:
                errors.append(f"Duplicate table alias/reference: {ref_name}")
                continue
            aliases[key] = actual
            references.append((ref_name, actual))

        select_aliases = {
            item.alias.casefold(): item.expression
            for item in query.columns if item.alias
        }

        def resolve_column(column: ColumnRef, allow_select_alias=False):
            if column.name == "*":
                if column.table:
                    key = column.table.casefold()
                    if key not in aliases:
                        errors.append(f"Unknown table or alias: {column.table}")
                return None
            if allow_select_alias and not column.table and column.name.casefold() in select_aliases:
                return "SELECT_ALIAS"
            if column.table:
                key = column.table.casefold()
                actual = aliases.get(key)
                if actual is None:
                    errors.append(f"Unknown table or alias: {column.table}")
                    return None
                real_col = next((name for name in SCHEMA[actual] if name.casefold() == column.name.casefold()), None)
                if real_col is None:
                    errors.append(f"Unknown column: {column.table}.{column.name}")
                    return None
                return actual, real_col

            matches = []
            for ref_name, actual in references:
                real_col = next((name for name in SCHEMA[actual] if name.casefold() == column.name.casefold()), None)
                if real_col is not None:
                    matches.append((ref_name, actual, real_col))
            if not matches:
                errors.append(f"Unknown column: {column.name}")
                return None
            if len(matches) > 1:
                names = ", ".join(f"{ref}.{column.name}" for ref, _, _ in matches)
                errors.append(f"Ambiguous column: {column.name} (matches {names})")
                return None
            return matches[0][1], matches[0][2]

        def visit(node, *, allow_aggregate=True, allow_select_alias=False):
            if node is None:
                return
            if isinstance(node, ColumnRef):
                return resolve_column(node, allow_select_alias=allow_select_alias)
            if isinstance(node, Literal):
                return None
            if isinstance(node, FunctionCall):
                name = node.name.upper()
                if name not in AGGREGATES:
                    errors.append(f"Unsupported function: {node.name}")
                    return None
                if not allow_aggregate:
                    errors.append(f"Aggregate function {name} is not allowed in this clause")
                if node.argument == "*":
                    if name != "COUNT":
                        errors.append(f"{name}(*) is not supported; use COUNT(*) or a column argument")
                    if node.distinct:
                        errors.append("DISTINCT * is not supported inside an aggregate")
                else:
                    visit(node.argument, allow_aggregate=False, allow_select_alias=allow_select_alias)
                    if name in {"SUM", "AVG"} and isinstance(node.argument, ColumnRef):
                        column_info = resolve_column(node.argument)
                        if column_info and column_info != "SELECT_ALIAS":
                            table_name, column_name = column_info
                            if SCHEMA[table_name][column_name].upper() not in NUMERIC_TYPES:
                                errors.append(f"{name} requires a numeric column, got {node.argument.name}")
                return None
            if isinstance(node, BinaryExpr):
                visit(node.left, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.right, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, UnaryExpr):
                visit(node.operand, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, IsNullExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, InExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                for value in node.values:
                    visit(value, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, BetweenExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.lower, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.upper, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            return None

        for item in query.columns:
            visit(item.expression)
        for join in query.joins:
            visit(join.condition, allow_aggregate=False)
        visit(query.where, allow_aggregate=False)
        for expression in query.group_by:
            visit(expression, allow_aggregate=False)
        visit(query.having)
        for item in query.order_by:
            visit(item.expression, allow_select_alias=True)

        # GROUP BY validation for non-aggregated column references. COSTRA deliberately
        # supports a conservative subset instead of SQLite's permissive bare-column rules.
        aggregate_query = bool(query.group_by) or any(
            contains_aggregate(item.expression) for item in query.columns
        ) or contains_aggregate(query.having)
        if aggregate_query:
            grouped = {format_expr(expr).casefold() for expr in query.group_by}
            for item in query.columns:
                for column in unaggregated_columns(item.expression):
                    expression_text = format_expr(column)
                    if not query.group_by:
                        errors.append(
                            f"Selected column {expression_text} must be aggregated when GROUP BY is absent"
                        )
                    elif expression_text.casefold() not in grouped:
                        errors.append(
                            f"Selected column {expression_text} must appear in GROUP BY or be aggregated"
                        )
            for column in unaggregated_columns(query.having):
                expression_text = format_expr(column)
                if not query.group_by:
                    errors.append(f"HAVING column {expression_text} must be aggregated when GROUP BY is absent")
                elif expression_text.casefold() not in grouped:
                    errors.append(f"HAVING column {expression_text} must appear in GROUP BY or be aggregated")

        # Remove duplicates while keeping first occurrence/order.
        return list(dict.fromkeys(errors)), aliases
```

---

## `schema.py`

```python
"""Logical schema and synthetic planning statistics used by COSTRA.

STATS are intentionally synthetic and are kept separate from the small in-memory
SQLite fixture used for executable examples. Estimated rows/cost are not measured
runtime results and are not collected from SQLite.
"""
from typing import Optional
SCHEMA = {
    "Employee": {
        "id": "INTEGER", "name": "TEXT", "salary": "INTEGER",
        "dept_id": "INTEGER", "experience": "INTEGER",
    },
    "Department": {"id": "INTEGER", "name": "TEXT"},
    "Project": {
        "id": "INTEGER", "name": "TEXT", "budget": "INTEGER",
        "manager_id": "INTEGER", "dept_id": "INTEGER",
    },
    "Assignment": {
        "employee_id": "INTEGER", "project_id": "INTEGER", "hours": "INTEGER",
    },
}

STATS = {
    "Employee": {"rows": 10000, "columns": {
        "id": {"distinct": 10000, "min": 1, "max": 10000},
        "name": {"distinct": 9200},
        "salary": {"distinct": 7000, "min": 25000, "max": 150000},
        "dept_id": {"distinct": 4, "min": 1, "max": 4},
        "experience": {"distinct": 16, "min": 0, "max": 15},
    }},
    "Department": {"rows": 4, "columns": {
        "id": {"distinct": 4, "min": 1, "max": 4},
        "name": {"distinct": 4},
    }},
    "Project": {"rows": 1200, "columns": {
        "id": {"distinct": 1200, "min": 1, "max": 1200},
        "name": {"distinct": 1180},
        "budget": {"distinct": 900, "min": 20000, "max": 500000},
        "manager_id": {"distinct": 800, "min": 1, "max": 10000},
        "dept_id": {"distinct": 4, "min": 1, "max": 4},
    }},
    "Assignment": {"rows": 30000, "columns": {
        "employee_id": {"distinct": 9000, "min": 1, "max": 10000},
        "project_id": {"distinct": 1200, "min": 1, "max": 1200},
        "hours": {"distinct": 80, "min": 1, "max": 80},
    }},
}

# These are modelled as existing indexes for access-path cost estimation only.
INDEXES = {
    ("Employee", "id"), ("Employee", "salary"), ("Employee", "dept_id"),
    ("Employee", "experience"), ("Department", "id"), ("Project", "id"),
    ("Project", "budget"), ("Project", "manager_id"), ("Project", "dept_id"),
    ("Assignment", "employee_id"), ("Assignment", "project_id"),
}


def canonical_table_name(name: str) -> Optional[str]:
    return next((table for table in SCHEMA if table.casefold() == name.casefold()), None)
```

---

## `statistics.py`

```python
"""Synthetic cardinality/selectivity helpers used by the estimated cost model."""
from __future__ import annotations
from typing import Optional, Dict
from ast_nodes import BetweenExpr, BinaryExpr, ColumnRef, InExpr, IsNullExpr, Literal, UnaryExpr
from schema import STATS, SCHEMA


def table_rows(table: str) -> float:
    stats = STATS.get(table)
    return float(stats["rows"]) if stats else 1000.0


def referenced_columns(expression) -> list[ColumnRef]:
    from semantic import walk_expression
    return [node for node in walk_expression(expression) if isinstance(node, ColumnRef) and node.name != "*"]


def referenced_aliases(expression, aliases: dict[str, str], table_refs=None) -> set[str]:
    """Resolve expression column references to table aliases for predicate placement."""
    found = set()
    for column in referenced_columns(expression):
        if column.table:
            found.add(column.table.casefold())
            continue
        matches = []
        for alias, table in aliases.items():
            if any(name.casefold() == column.name.casefold() for name in SCHEMA.get(table, {})):
                matches.append(alias)
        if len(matches) == 1:
            found.add(matches[0])
        elif matches:
            found.update(matches)
    return found


def _column_stats(column: ColumnRef, aliases: Optional[Dict[str, str]]):
    if not aliases:
        return None
    if column.table:
        table = aliases.get(column.table.casefold())
        if not table:
            return None
    else:
        tables = [t for t in aliases.values() if any(c.casefold() == column.name.casefold() for c in SCHEMA.get(t, {}))]
        if len(tables) != 1:
            return None
        table = tables[0]
    return STATS.get(table, {}).get("columns", {}).get(column.name.casefold()) or next(
        (v for name, v in STATS.get(table, {}).get("columns", {}).items() if name.casefold() == column.name.casefold()),
        None,
    )


def _range_fraction(column, operator, literal, aliases):
    stats = _column_stats(column, aliases)
    if not stats or "min" not in stats or "max" not in stats:
        return None
    low, high = stats["min"], stats["max"]
    try:
        value = float(literal.value)
        low, high = float(low), float(high)
    except (TypeError, ValueError):
        return None
    if high <= low:
        return 1.0 if ((operator in (">=", "<=") and value == low) or (operator == "=" and value == low)) else 0.0
    if operator in (">", ">="):
        return max(0.0, min(1.0, (high - value) / (high - low)))
    if operator in ("<", "<="):
        return max(0.0, min(1.0, (value - low) / (high - low)))
    return None


def selectivity(expression, aliases: Optional[Dict[str, str]] = None) -> float:
    """Return a heuristic fraction in [0, 1]; these estimates are not live DB stats."""
    if expression is None:
        return 1.0
    if isinstance(expression, Literal):
        if expression.value is True:
            return 1.0
        if expression.value in (False, None):
            return 0.0
        return 1.0
    if isinstance(expression, UnaryExpr):
        if expression.operator.upper() == "NOT":
            return max(0.0, min(1.0, 1.0 - selectivity(expression.operand, aliases)))
        return 0.5
    if isinstance(expression, IsNullExpr):
        return 0.05 if not expression.negated else 0.95
    if isinstance(expression, InExpr):
        if isinstance(expression.expression, ColumnRef):
            stats = _column_stats(expression.expression, aliases)
            if stats:
                fraction = min(0.95, len(expression.values) / max(1.0, float(stats.get("distinct", 10))))
            else:
                fraction = min(0.95, len(expression.values) * 0.1)
        else:
            fraction = min(0.95, len(expression.values) * 0.1)
        return 1.0 - fraction if expression.negated else fraction
    if isinstance(expression, BetweenExpr):
        low = _range_fraction(expression.expression, ">=", expression.lower, aliases) if isinstance(expression.expression, ColumnRef) and isinstance(expression.lower, Literal) else None
        high = _range_fraction(expression.expression, "<=", expression.upper, aliases) if isinstance(expression.expression, ColumnRef) and isinstance(expression.upper, Literal) else None
        fraction = max(0.0, min(1.0, (low if low is not None else 0.5) + (high if high is not None else 0.5) - 1.0))
        if fraction == 0.0:
            fraction = 0.25
        return 1.0 - fraction if expression.negated else fraction
    if not isinstance(expression, BinaryExpr):
        return 0.5

    op = expression.operator.upper()
    if op == "AND":
        return max(0.0, min(1.0, selectivity(expression.left, aliases) * selectivity(expression.right, aliases)))
    if op == "OR":
        left, right = selectivity(expression.left, aliases), selectivity(expression.right, aliases)
        return max(0.0, min(1.0, left + right - left * right))
    if op == "LIKE":
        return 0.1
    if isinstance(expression.left, ColumnRef) and isinstance(expression.right, Literal):
        if op == "=":
            stats = _column_stats(expression.left, aliases)
            return max(0.0001, min(1.0, 1.0 / max(1.0, float(stats.get("distinct", 10))))) if stats else 0.1
        if op in (">", "<", ">=", "<="):
            fraction = _range_fraction(expression.left, op, expression.right, aliases)
            return max(0.0001, fraction) if fraction is not None else 0.3
        if op in ("<>", "!="):
            stats = _column_stats(expression.left, aliases)
            return max(0.0, 1.0 - 1.0 / max(1.0, float(stats.get("distinct", 10)))) if stats else 0.9
    if isinstance(expression.left, ColumnRef) and isinstance(expression.right, ColumnRef):
        if op == "=":
            left, right = _column_stats(expression.left, aliases), _column_stats(expression.right, aliases)
            if left and right:
                return 1.0 / max(1.0, float(left.get("distinct", 10)), float(right.get("distinct", 10)))
            return 0.1
        if op in ("<>", "!="):
            return 0.9
    return 0.5
```

---

## `ir.py`

```python
"""Logical relational IR for the COSTRA SQL-processing pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr,
    UnaryExpr, format_expr,
)


@dataclass
class PlanNode:
    op: str
    children: list["PlanNode"] = field(default_factory=list)
    detail: str = ""
    rows: float = 0.0
    cost: float = 0.0
    algorithm: str = ""

    def pretty(self, level: int = 0, include_estimates: bool = True) -> str:
        """Format the plan tree. Logical IR omits estimates; physical candidates include them."""
        line = "  " * level + self.op
        if self.algorithm:
            line += f" <{self.algorithm}>"
        if self.detail:
            line += f" [{self.detail}]"
        if include_estimates:
            line += f" {{estimated rows≈{self.rows:.2f}, cumulative cost≈{self.cost:.2f}}}"
        return "\n".join(
            [line] + [child.pretty(level + 1, include_estimates) for child in self.children]
        )


def contains_aggregate(node) -> bool:
    if isinstance(node, FunctionCall):
        return node.name.upper() in {"COUNT", "SUM", "AVG", "MIN", "MAX"} or (
            node.argument != "*" and contains_aggregate(node.argument)
        )
    if isinstance(node, BinaryExpr):
        return contains_aggregate(node.left) or contains_aggregate(node.right)
    if isinstance(node, UnaryExpr):
        return contains_aggregate(node.operand)
    if isinstance(node, IsNullExpr):
        return contains_aggregate(node.expression)
    if isinstance(node, InExpr):
        return contains_aggregate(node.expression) or any(contains_aggregate(v) for v in node.values)
    if isinstance(node, BetweenExpr):
        return any(contains_aggregate(v) for v in (node.expression, node.lower, node.upper))
    return False


def build_logical_plan(query):
    """Build a logical operator tree without attaching a physical join algorithm."""
    table = query.table
    node = PlanNode("TABLE_SCAN", detail=f"{table.name}" + (f" AS {table.alias}" if table.alias else ""))
    for join in query.joins:
        scan = PlanNode("TABLE_SCAN", detail=f"{join.table.name}" + (f" AS {join.table.alias}" if join.table.alias else ""))
        node = PlanNode("JOIN", [node, scan], f"{join.join_type} ON {format_expr(join.condition)}")
    if query.where is not None:
        node = PlanNode("FILTER", [node], format_expr(query.where))
    aggregate = bool(query.group_by) or any(contains_aggregate(i.expression) for i in query.columns) or contains_aggregate(query.having)
    if aggregate:
        details = ", ".join(format_expr(x) for x in query.group_by) if query.group_by else "global aggregate"
        node = PlanNode("AGGREGATE", [node], details)
    if query.having is not None:
        node = PlanNode("HAVING", [node], format_expr(query.having))
    if query.distinct:
        node = PlanNode("DISTINCT", [node], "remove duplicate result rows")
    if query.order_by:
        details = ", ".join(f"{format_expr(i.expression)} {i.direction}" for i in query.order_by)
        node = PlanNode("SORT", [node], details)
    if query.limit is not None:
        node = PlanNode("LIMIT", [node], str(query.limit))
    return PlanNode("PROJECT", [node], ", ".join(format_expr(i.expression) for i in query.columns))
```

---

## `optimizer.py`

```python
"""Educational cost-based optimizer for COSTRA.

The optimizer creates estimated candidate plans and selects the minimum estimated
cost. SQLite independently executes the normalized SQL; COSTRA does not inject its
chosen plan into SQLite's internal planner.
"""
from __future__ import annotations
import itertools
import math
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr,
    Literal, UnaryExpr, format_expr,
)
from ir import PlanNode, build_logical_plan, contains_aggregate
from schema import INDEXES, SCHEMA, STATS, canonical_table_name
from statistics import referenced_aliases, selectivity


def split_conjuncts(expression):
    if isinstance(expression, BinaryExpr) and expression.operator.upper() == "AND":
        return split_conjuncts(expression.left) + split_conjuncts(expression.right)
    return [expression] if expression is not None else []


def combine_conjuncts(expressions):
    if not expressions:
        return None
    current = expressions[0]
    for expr in expressions[1:]:
        current = BinaryExpr(current, "AND", expr)
    return current


def _column_refs(expression):
    from semantic import walk_expression
    return [part for part in walk_expression(expression) if isinstance(part, ColumnRef) and part.name != "*"]


class CostModel:
    """Consistent relative cost units; not wall-clock milliseconds."""
    def full_scan(self, rows: float) -> float:
        return rows * 1.0

    def index_scan(self, table_rows: float, output_rows: float) -> float:
        # Index descent + leaf visits/output fetches in simplified relative units.
        return math.log2(max(2.0, table_rows)) * 2.0 + output_rows * 0.60

    def predicate(self, input_rows: float) -> float:
        return input_rows * 0.20

    def nested_loop_join(self, left_rows: float, right_rows: float) -> float:
        return left_rows * max(1.0, right_rows) * 0.15

    def hash_join(self, left_rows: float, right_rows: float) -> float:
        return (left_rows + right_rows) * 1.10 + min(left_rows, right_rows) * 0.25

    def merge_join(self, left_rows: float, right_rows: float) -> float:
        sort_left = left_rows * math.log2(max(2.0, left_rows)) * 0.45
        sort_right = right_rows * math.log2(max(2.0, right_rows)) * 0.45
        return (left_rows + right_rows) * 0.80 + sort_left + sort_right

    def aggregate(self, rows: float) -> float:
        return rows * 0.45

    def distinct(self, rows: float) -> float:
        return rows * 0.30

    def sort(self, rows: float) -> float:
        return rows * math.log2(max(2.0, rows)) * 0.35

    def project(self, rows: float) -> float:
        return rows * 0.05


class Optimizer:
    def __init__(self, max_candidates: int = 6, max_join_orders: int = 720):
        self.cost_model = CostModel()
        self.max_candidates = max_candidates
        self.max_join_orders = max_join_orders

    def optimize(self, query):
        logical = build_logical_plan(query)
        candidates = self.enumerate_plans(query)
        if not candidates:
            raise ValueError("The optimizer could not generate a candidate plan")
        best = min(candidates, key=lambda plan: plan.cost)
        return logical, candidates, best

    def _alias_map(self, query):
        refs = ([query.table] if query.table else []) + [join.table for join in query.joins]
        mapping = {}
        for ref in refs:
            table = canonical_table_name(ref.name)
            if table:
                mapping[(ref.alias or ref.name).casefold()] = table
        return mapping

    def _base_scans(self, query, aliases):
        predicates = split_conjuncts(query.where)
        local = {alias: [] for alias in aliases}
        remaining = []
        for predicate in predicates:
            refs = referenced_aliases(predicate, aliases)
            if len(refs) == 1 and next(iter(refs)) in local:
                local[next(iter(refs))].append(predicate)
            else:
                remaining.append(predicate)

        scans = {}
        for ref in ([query.table] if query.table else []) + [join.table for join in query.joins]:
            alias_key = (ref.alias or ref.name).casefold()
            table = aliases.get(alias_key, canonical_table_name(ref.name) or ref.name)
            table_stats = STATS.get(table, {"rows": 1000, "columns": {}})
            input_rows = float(table_stats["rows"])
            selectivity_fraction = 1.0
            for predicate in local.get(alias_key, []):
                selectivity_fraction *= selectivity(predicate, aliases)
            selectivity_fraction = max(0.0, min(1.0, selectivity_fraction))
            output_rows = max(1.0, input_rows * selectivity_fraction)
            predicate = combine_conjuncts(local.get(alias_key, []))

            full_cost = self.cost_model.full_scan(input_rows)
            if predicate is not None:
                full_cost += self.cost_model.predicate(input_rows)
            indexed = self._indexed_predicate_columns(predicate, ref, table)
            index_cost = self.cost_model.index_scan(input_rows, output_rows) if indexed else float("inf")
            if index_cost < full_cost:
                op = "INDEX_SCAN"
                cost = index_cost
                algorithm = "INDEX"
            else:
                op = "TABLE_SCAN"
                cost = full_cost
                algorithm = "FULL_SCAN"
            detail = f"{table}" + (f" AS {ref.alias}" if ref.alias else "")
            if indexed and op == "INDEX_SCAN":
                detail += f"; indexed predicate on {', '.join(indexed)}"
            if predicate is not None:
                detail += f"; pushed filter: {format_expr(predicate)}"
            scans[alias_key] = PlanNode(op, detail=detail, rows=output_rows, cost=cost, algorithm=algorithm)
        return scans, remaining

    def _indexed_predicate_columns(self, predicate, ref, table):
        if predicate is None:
            return []
        available = {col.casefold(): col for indexed_table, col in INDEXES if indexed_table.casefold() == table.casefold()}
        found = []
        # Inspect each conjunct independently so a predicate such as
        # salary > 60000 AND experience >= 5 can still use a relevant index.
        for term in split_conjuncts(predicate):
            supported_shape = (
                isinstance(term, BinaryExpr) and term.operator.upper() in {"=", "<", "<=", ">", ">="}
            ) or isinstance(term, (InExpr, BetweenExpr))
            if not supported_shape:
                continue
            for column in _column_refs(term):
                if column.table and column.table.casefold() != (ref.alias or ref.name).casefold():
                    continue
                if column.name.casefold() in available:
                    found.append(available[column.name.casefold()])
        return sorted(set(found))

    def _join_condition_for_step(self, query, new_alias, joined_aliases, combined_aliases, applied):
        applicable = []
        for index, join in enumerate(query.joins):
            if index in applied:
                continue
            condition_aliases = referenced_aliases(join.condition, self._active_aliases)
            if new_alias not in condition_aliases:
                continue
            if not condition_aliases.issubset(combined_aliases):
                continue
            if not condition_aliases.intersection(joined_aliases):
                # A single-table ON expression is not a join edge, but must still be applied.
                if not (join.join_type == "CROSS" and not condition_aliases):
                    continue
            applicable.append((index, join))
        return applicable

    def _equijoin_selectivity(self, conditions, aliases):
        if not conditions:
            return 1.0
        fractions = []
        for condition in conditions:
            fractions.append(selectivity(condition, aliases))
        result = 1.0
        for fraction in fractions:
            result *= max(0.00001, min(1.0, fraction))
        return result

    def _combine_conditions(self, conditions):
        return " AND ".join(format_expr(condition) for condition in conditions) if conditions else "CROSS JOIN"

    def _make_join(self, left, right, conditions, join_type, aliases):
        left_rows, right_rows = max(1.0, left.rows), max(1.0, right.rows)
        selectivity_fraction = self._equijoin_selectivity(conditions, aliases)
        output_rows = max(1.0, left_rows * right_rows * selectivity_fraction)
        if join_type in {"LEFT", "RIGHT"}:
            output_rows = max(output_rows, left_rows if join_type == "LEFT" else right_rows)

        if join_type in {"LEFT", "RIGHT"}:
            algorithm = "NESTED_LOOP"
            join_cost = self.cost_model.nested_loop_join(left_rows, right_rows)
        else:
            options = [
                ("NESTED_LOOP", self.cost_model.nested_loop_join(left_rows, right_rows)),
                ("HASH_JOIN", self.cost_model.hash_join(left_rows, right_rows)),
                ("MERGE_JOIN", self.cost_model.merge_join(left_rows, right_rows)),
            ]
            algorithm, join_cost = min(options, key=lambda item: item[1])
        op = "JOIN" if join_type == "INNER" else f"{join_type}_JOIN"
        condition_text = self._combine_conditions(conditions)
        detail = f"{join_type} ON {condition_text}"
        cumulative = left.cost + right.cost + join_cost
        return PlanNode(op, [left, right], detail, output_rows, cumulative, algorithm)

    def _estimate_group_rows(self, query, input_rows, aliases):
        if not query.group_by:
            return 1.0  # scalar aggregate such as COUNT(*)
        estimate = 1.0
        for expression in query.group_by:
            if isinstance(expression, ColumnRef):
                table = aliases.get(expression.table.casefold()) if expression.table else None
                if table is None and not expression.table:
                    matches = [name for name, columns in SCHEMA.items()
                               if any(column.casefold() == expression.name.casefold() for column in columns)]
                    if len(matches) == 1:
                        table = matches[0]
                stats = STATS.get(table, {}).get("columns", {}).get(expression.name.casefold(), {}) if table else {}
                estimate *= max(1.0, float(stats.get("distinct", max(1.0, input_rows * 0.25))))
            else:
                estimate *= max(1.0, input_rows * 0.25)
        return max(1.0, min(input_rows, estimate))

    def _build_candidate(self, query, order, scans, remaining_where, aliases):
        current = scans[(order[0].alias or order[0].name).casefold()]
        joined = {(order[0].alias or order[0].name).casefold()}
        applied_join_indexes = set()
        # If outer/cross joins are present, order is fixed and ON semantics are retained.
        fixed_join_order = any(j.join_type != "INNER" for j in query.joins)
        for ref in order[1:]:
            new_alias = (ref.alias or ref.name).casefold()
            combined = joined | {new_alias}
            applicable = self._join_condition_for_step(query, new_alias, joined, combined, applied_join_indexes)
            conditions = [join.condition for _, join in applicable]
            join_type = "INNER"
            if fixed_join_order:
                # The incoming relation follows its original JoinClause; do not commute outer joins.
                match = next((j for j in query.joins if (j.table.alias or j.table.name).casefold() == new_alias), None)
                join_type = match.join_type if match else "INNER"
                if join_type == "CROSS":
                    conditions = []
                elif not conditions and match:
                    conditions = [match.condition]
            for index, _ in applicable:
                applied_join_indexes.add(index)
            right = scans[new_alias]
            current = self._make_join(current, right, conditions, join_type, aliases)
            joined.add(new_alias)

        # Any ON expression that could not be attached during reordering is retained as a filter.
        residual_on = [join.condition for i, join in enumerate(query.joins) if i not in applied_join_indexes and join.join_type == "INNER"]
        if residual_on:
            residual = combine_conjuncts(residual_on)
            fraction = selectivity(residual, aliases)
            rows = max(1.0, current.rows * fraction)
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("FILTER", [current], f"join predicates: {format_expr(residual)}", rows, cost)
        if remaining_where:
            predicate = combine_conjuncts(remaining_where)
            rows = max(1.0, current.rows * selectivity(predicate, aliases))
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("FILTER", [current], format_expr(predicate), rows, cost)

        aggregate_query = bool(query.group_by) or any(contains_aggregate(item.expression) for item in query.columns) or contains_aggregate(query.having)
        if aggregate_query:
            output_rows = self._estimate_group_rows(query, current.rows, aliases)
            output_rows = max(1.0, min(current.rows, output_rows)) if query.group_by else 1.0
            group_by = ", ".join(format_expr(x) for x in query.group_by) or "global aggregate"
            cost = current.cost + self.cost_model.aggregate(current.rows)
            current = PlanNode("HASH_AGGREGATE", [current], group_by, output_rows, cost, "HASH")
        if query.having is not None:
            rows = max(1.0, current.rows * selectivity(query.having, aliases))
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("HAVING_FILTER", [current], format_expr(query.having), rows, cost)
        if query.distinct:
            rows = max(1.0, current.rows * 0.5)
            cost = current.cost + self.cost_model.distinct(current.rows)
            current = PlanNode("DISTINCT", [current], "remove duplicate rows", rows, cost)
        if query.order_by:
            details = ", ".join(f"{format_expr(item.expression)} {item.direction}" for item in query.order_by)
            cost = current.cost + self.cost_model.sort(current.rows)
            current = PlanNode("SORT", [current], details, current.rows, cost)
        if query.limit is not None:
            current = PlanNode("LIMIT", [current], str(query.limit), min(current.rows, float(query.limit)), current.cost)
        projection = ", ".join(format_expr(item.expression) for item in query.columns)
        return PlanNode("PROJECT", [current], projection, current.rows, current.cost + self.cost_model.project(current.rows))

    def enumerate_plans(self, query):
        aliases = self._alias_map(query)
        self._active_aliases = aliases
        tables = ([query.table] if query.table else []) + [join.table for join in query.joins]
        scans, remaining_where = self._base_scans(query, aliases)
        fixed_order = any(join.join_type != "INNER" for join in query.joins)
        if fixed_order or len(tables) <= 1:
            orders = [tables]
        else:
            orders = itertools.permutations(tables)

        results = []
        signatures = set()
        for order_index, order in enumerate(orders):
            if order_index >= self.max_join_orders:
                break
            candidate = self._build_candidate(query, list(order), scans, remaining_where, aliases)
            signature = tuple((ref.alias or ref.name).casefold() for ref in order)
            if signature in signatures:
                continue
            signatures.add(signature)
            results.append(candidate)
        return sorted(results, key=lambda plan: plan.cost)[:self.max_candidates]


def optimize(query):
    return Optimizer().optimize(query)
```

---

## `executor.py`

```python
"""SQLite-backed execution backend using a small deterministic demo database."""
from __future__ import annotations
import sqlite3
from ast_nodes import format_query


class ExecutionError(RuntimeError):
    """Friendly error wrapper for failed SQLite execution."""


class Executor:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = None
        self._seed_database()

    def _seed_database(self):
        cursor = self.db.cursor()
        cursor.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE Department (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE Employee (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                salary INTEGER NOT NULL CHECK (salary >= 0),
                dept_id INTEGER NOT NULL REFERENCES Department(id),
                experience INTEGER NOT NULL CHECK (experience >= 0)
            );
            CREATE TABLE Project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                budget INTEGER NOT NULL CHECK (budget >= 0),
                manager_id INTEGER REFERENCES Employee(id),
                dept_id INTEGER REFERENCES Department(id)
            );
            CREATE TABLE Assignment (
                employee_id INTEGER NOT NULL REFERENCES Employee(id),
                project_id INTEGER NOT NULL REFERENCES Project(id),
                hours INTEGER NOT NULL CHECK (hours BETWEEN 0 AND 80),
                PRIMARY KEY (employee_id, project_id)
            );
            CREATE INDEX idx_employee_salary ON Employee(salary);
            CREATE INDEX idx_employee_department ON Employee(dept_id);
            CREATE INDEX idx_project_budget ON Project(budget);
            CREATE INDEX idx_assignment_employee ON Assignment(employee_id);
            CREATE INDEX idx_assignment_project ON Assignment(project_id);
        """)
        cursor.executemany("INSERT INTO Department VALUES (?, ?)", [
            (1, "Engineering"), (2, "HR"), (3, "Sales"), (4, "Finance"),
        ])
        cursor.executemany("INSERT INTO Employee VALUES (?, ?, ?, ?, ?)", [
            (1, "Arjun", 85000, 1, 5), (2, "Neha", 72000, 1, 4),
            (3, "Riya", 48000, 2, 2), (4, "Kabir", 65000, 3, 6),
            (5, "Ishita", 91000, 4, 8), (6, "Rahul", 54000, 3, 3),
            (7, "Aman", 78000, 1, 7), (8, "Priya", 69000, 2, 5),
        ])
        cursor.executemany("INSERT INTO Project VALUES (?, ?, ?, ?, ?)", [
            (1, "AI Platform", 250000, 1, 1), (2, "Mobile App", 150000, 2, 1),
            (3, "ERP", 300000, 4, 3), (4, "Analytics", 180000, 5, 4),
            (5, "CRM", 110000, 7, 1),
        ])
        cursor.executemany("INSERT INTO Assignment VALUES (?, ?, ?)", [
            (1, 1, 30), (2, 1, 25), (7, 1, 35), (1, 2, 15),
            (4, 3, 30), (5, 4, 28), (7, 5, 20), (8, 2, 18),
        ])
        self.db.commit()

    def execute(self, query):
        sql = format_query(query)
        try:
            cursor = self.db.cursor()
            cursor.execute(sql)
            if cursor.description is None:
                raise ExecutionError("Only SELECT statements produce results in this demo")
            headers = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            return headers, rows, sql
        except sqlite3.Error as exc:
            raise ExecutionError(f"SQLite execution failed: {exc}") from exc

    def explain(self, query):
        """Return SQLite's actual plan separately from COSTRA's estimated candidate plan."""
        sql = format_query(query)
        try:
            rows = self.db.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
            return [str(row[3]) for row in rows]
        except sqlite3.Error as exc:
            raise ExecutionError(f"SQLite could not explain the query: {exc}") from exc

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False
```

---

## `test_costra.py`

```python
"""Regression tests for COSTRA's lexer, parser, semantics, optimizer and SQLite backend."""
import unittest
import subprocess
import sys
from pathlib import Path
from compiler import compile_sql
from executor import Executor, ExecutionError
from lexer import tokenize
from main import DEMO_SQL, run_query
from ast_nodes import ColumnRef, SelectItem, SelectQuery, TableRef
from optimizer import optimize
from parser import parse_sql
from semantic import SemanticAnalyzer


class TestLexer(unittest.TestCase):
    def test_classifies_basic_tokens(self):
        kinds = [token.kind for token in tokenize("SELECT name FROM Employee;")]
        self.assertEqual(kinds, ["SELECT", "IDENTIFIER", "FROM", "IDENTIFIER", "SEMICOLON", "EOF"])

    def test_case_insensitive_keywords(self):
        self.assertEqual(tokenize("select name from Employee")[0].kind, "SELECT")

    def test_line_and_column_tracking(self):
        with self.assertRaisesRegex(ValueError, r"line 2, column 3"):
            tokenize("SELECT\n  @ FROM Employee")

    def test_comments_are_ignored(self):
        tokens = tokenize("SELECT name -- comment\nFROM Employee")
        self.assertEqual([t.kind for t in tokens[:4]], ["SELECT", "IDENTIFIER", "FROM", "IDENTIFIER"])

    def test_escaped_single_quote(self):
        tokens = tokenize("SELECT 'Arsh''s row' FROM Employee")
        self.assertEqual(tokens[1].value, "'Arsh''s row'")

    def test_lexical_error_has_location(self):
        with self.assertRaisesRegex(ValueError, r"line 1, column 8.*'@'"):
            tokenize("SELECT @ FROM Employee")


class TestParser(unittest.TestCase):
    def test_basic_select(self):
        query = parse_sql("SELECT e.name FROM Employee e WHERE e.salary > 60000;")
        self.assertEqual(query.table.name, "Employee")
        self.assertEqual(query.table.alias, "e")
        self.assertIsNotNone(query.where)

    def test_complex_query_clauses(self):
        query = parse_sql(DEMO_SQL)
        self.assertEqual(len(query.joins), 3)
        self.assertEqual(len(query.columns), 3)
        self.assertEqual(len(query.group_by), 1)
        self.assertIsNotNone(query.having)
        self.assertEqual(query.order_by[0].direction, "DESC")
        self.assertEqual(query.limit, 5)

    def test_distinct_and_count_distinct(self):
        query = parse_sql("SELECT DISTINCT COUNT(DISTINCT e.id) AS n FROM Employee e;")
        self.assertTrue(query.distinct)
        self.assertTrue(query.columns[0].expression.distinct)

    def test_star_and_qualified_star(self):
        self.assertEqual(parse_sql("SELECT * FROM Employee;").columns[0].expression.name, "*")
        query = parse_sql("SELECT e.* FROM Employee e;")
        self.assertEqual(query.columns[0].expression.table, "e")

    def test_precedence_and_parentheses(self):
        query = parse_sql("SELECT name FROM Employee WHERE salary > 60000 OR experience > 5 AND dept_id = 1;")
        self.assertEqual(query.where.operator, "OR")
        self.assertEqual(query.where.right.operator, "AND")

    def test_predicate_extensions(self):
        for condition in (
            "salary IS NULL", "salary IS NOT NULL", "dept_id IN (1, 2, 4)",
            "dept_id NOT IN (3)", "salary BETWEEN 60000 AND 90000",
            "salary NOT BETWEEN 100 AND 200", "name LIKE 'A%'", "name NOT LIKE 'B%'",
        ):
            with self.subTest(condition=condition):
                query = parse_sql(f"SELECT name FROM Employee WHERE {condition};")
                self.assertIsNotNone(query.where)

    def test_arithmetic_and_unary(self):
        query = parse_sql("SELECT -salary + 5 * 2 AS adjusted FROM Employee;")
        self.assertEqual(query.columns[0].alias, "adjusted")

    def test_limit_must_be_integer(self):
        with self.assertRaisesRegex(SyntaxError, "non-negative integer"):
            parse_sql("SELECT name FROM Employee LIMIT 2.5;")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(SyntaxError):
            parse_sql("SELECT name FROM Employee; SELECT name FROM Department;")

    def test_rejects_missing_projection(self):
        with self.assertRaises(SyntaxError):
            parse_sql("SELECT FROM Employee;")

    def test_rejects_invalid_in_list(self):
        with self.assertRaises(SyntaxError):
            parse_sql("SELECT name FROM Employee WHERE id IN ();")


class TestSemanticAnalysis(unittest.TestCase):
    def errors(self, sql):
        query = parse_sql(sql)
        return SemanticAnalyzer().analyze(query)[0]

    def test_valid_qualified_and_unqualified_columns(self):
        self.assertEqual(self.errors("SELECT e.name, salary FROM Employee e WHERE e.salary > 70000;"), [])

    def test_unknown_table(self):
        self.assertTrue(any("Unknown table" in e for e in self.errors("SELECT name FROM Staff;")))

    def test_unknown_alias(self):
        self.assertTrue(any("Unknown table or alias" in e for e in self.errors("SELECT x.name FROM Employee e;")))

    def test_unknown_column(self):
        self.assertTrue(any("Unknown column" in e for e in self.errors("SELECT e.unknown FROM Employee e;")))

    def test_ambiguous_unqualified_column(self):
        errors = self.errors("SELECT id FROM Employee e JOIN Department d ON e.dept_id = d.id;")
        self.assertTrue(any("Ambiguous column" in e for e in errors))

    def test_duplicate_alias(self):
        errors = self.errors("SELECT e.id FROM Employee e JOIN Department e ON e.dept_id = e.id;")
        self.assertTrue(any("Duplicate table alias" in e for e in errors))

    def test_aggregate_not_allowed_in_where(self):
        errors = self.errors("SELECT e.name FROM Employee e WHERE AVG(e.salary) > 50000;")
        self.assertTrue(any("not allowed in this clause" in e for e in errors))

    def test_unknown_function(self):
        errors = self.errors("SELECT explode(e.salary) FROM Employee e;")
        self.assertTrue(any("Unsupported function" in e for e in errors))

    def test_avg_text_column_rejected(self):
        errors = self.errors("SELECT AVG(e.name) FROM Employee e;")
        self.assertTrue(any("requires a numeric column" in e for e in errors))

    def test_group_by_projection_validation(self):
        errors = self.errors("SELECT e.name, COUNT(*) FROM Employee e GROUP BY e.dept_id;")
        self.assertTrue(any("must appear in GROUP BY" in e for e in errors))

    def test_order_by_projection_alias(self):
        self.assertEqual(self.errors("SELECT salary AS pay FROM Employee ORDER BY pay DESC;"), [])


class TestOptimizer(unittest.TestCase):
    def test_minimum_estimated_cost_is_selected(self):
        query = parse_sql(DEMO_SQL)
        _, candidates, best = optimize(query)
        self.assertGreater(len(candidates), 1)
        self.assertEqual(best.cost, min(candidate.cost for candidate in candidates))

    def test_inner_join_orders_are_compared(self):
        query = parse_sql("SELECT e.name FROM Employee e JOIN Department d ON e.dept_id = d.id JOIN Project p ON p.dept_id = d.id;")
        _, candidates, _ = optimize(query)
        self.assertGreater(len(candidates), 1)

    def test_outer_join_order_is_preserved(self):
        query = parse_sql("SELECT e.name, d.name FROM Employee e LEFT JOIN Department d ON e.dept_id = d.id;")
        _, candidates, best = optimize(query)
        self.assertEqual(len(candidates), 1)
        self.assertIn("LEFT_JOIN", best.pretty())

    def test_index_path_used_for_sargable_filter(self):
        query = parse_sql("SELECT name FROM Employee WHERE salary > 60000;")
        _, _, best = optimize(query)
        self.assertIn("INDEX_SCAN", best.pretty())

    def test_scalar_aggregate_estimates_one_row(self):
        query = parse_sql("SELECT COUNT(*) FROM Employee;")
        _, _, best = optimize(query)
        self.assertEqual(best.rows, 1.0)
        self.assertIn("HASH_AGGREGATE", best.pretty())

    def test_distinct_operator_present(self):
        query = parse_sql("SELECT DISTINCT dept_id FROM Employee;")
        _, _, best = optimize(query)
        self.assertIn("DISTINCT", best.pretty())

    def test_outer_join_does_not_enumerate_semantically_unsafe_orders(self):
        query = parse_sql("SELECT e.name FROM Employee e LEFT JOIN Department d ON e.dept_id = d.id JOIN Project p ON d.id = p.dept_id;")
        _, candidates, _ = optimize(query)
        self.assertEqual(len(candidates), 1)


class TestCommandLineDemo(unittest.TestCase):
    """Review-day CLI modes should run from a fresh Python process."""

    def _run_cli(self, *args, input_text=None):
        project_dir = Path(__file__).resolve().parent
        return subprocess.run(
            [sys.executable, str(project_dir / "main.py"), *args],
            cwd=project_dir,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )

    def test_cli_demo_prints_pipeline_and_results(self):
        completed = self._run_cli("--demo")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("LEXICAL ANALYSIS", completed.stdout)
        self.assertIn("SELECTED ESTIMATED PLAN", completed.stdout)
        self.assertIn("Rows returned: 3", completed.stdout)
        self.assertIn("SQLITE'S OWN QUERY PLAN", completed.stdout)

    def test_cli_error_demo_stops_before_execution(self):
        completed = self._run_cli("--error-demo")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("SEMANTIC ANALYSIS FAILED", completed.stdout)
        self.assertIn("No SQL was executed", completed.stdout)

    def test_cli_custom_query_runs(self):
        completed = self._run_cli("--query", "SELECT name FROM Employee WHERE salary > 80000 LIMIT 2;")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("EXECUTION RESULTS", completed.stdout)
        self.assertIn("Rows returned:", completed.stdout)

    def test_cost_demo_shows_worked_formula_and_lowest_candidate(self):
        completed = self._run_cli("--cost-demo")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Full scan + predicate", completed.stdout)
        self.assertIn("4,346.58", completed.stdout)
        self.assertIn("115,222.63 model units", completed.stdout)
        self.assertIn("Selection rule: choose the candidate", completed.stdout)

    def test_review_progress_demo_covers_all_three_reviews(self):
        completed = self._run_cli("--progress-demo")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for stage in ("REVIEW 1 | DESIGN", "REVIEW 2 | CORE IMPLEMENTATION", "REVIEW 3 | INTEGRATION & VALIDATION"):
            self.assertIn(stage, completed.stdout)

    def test_switch_style_menu_lists_professor_choices(self):
        completed = self._run_cli(input_text="5\n6\n8\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("COSTRA — PROFESSOR-SELECTABLE DEMO MENU", completed.stdout)
        self.assertIn("Enter my own SELECT query", completed.stdout)
        self.assertIn("COST CALCULATION & BEST ESTIMATED PLAN", completed.stdout)
        self.assertIn("REVIEW 3 | INTEGRATION & VALIDATION", completed.stdout)
        self.assertIn("Goodbye.", completed.stdout)

    def test_custom_sql_menu_option_executes_user_input(self):
        completed = self._run_cli(input_text="4\nSELECT name FROM Employee LIMIT 2;\n8\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("SQL> ", completed.stdout)
        self.assertIn("EXECUTION RESULTS", completed.stdout)
        self.assertIn("Rows returned: 2", completed.stdout)


class TestExecutionAndPipeline(unittest.TestCase):
    def test_demo_executes_and_returns_repeatable_result(self):
        result = run_query(DEMO_SQL)
        self.assertTrue(result.compilation.success)
        self.assertTrue(result.executed)
        self.assertEqual(result.headers, ["department", "employee_count", "average_salary"])
        self.assertEqual(result.rows[0][0], "Finance")
        self.assertEqual(len(result.rows), 3)

    def test_sqlite_query_plan_is_separate_and_available(self):
        result = run_query("SELECT name FROM Employee WHERE salary > 80000;")
        self.assertTrue(result.sqlite_plan)
        self.assertIn("SQLite EXPLAIN QUERY PLAN", result.timings_ms)

    def test_string_literal_escaping(self):
        result = run_query("SELECT name FROM Employee WHERE name = 'Ishita';")
        self.assertEqual(result.rows, [("Ishita",)])

    def test_left_join_executes(self):
        result = run_query("SELECT e.name, d.name FROM Employee e LEFT JOIN Department d ON e.dept_id = d.id LIMIT 2;")
        self.assertTrue(result.executed)
        self.assertEqual(len(result.rows), 2)

    def test_lexical_error_stops_pipeline(self):
        result = run_query("SELECT @ FROM Employee;")
        self.assertFalse(result.compilation.success)
        self.assertEqual(result.compilation.failed_stage, "LEXICAL ANALYSIS")
        self.assertFalse(result.executed)

    def test_syntax_error_stops_pipeline(self):
        result = run_query("SELECT FROM Employee;")
        self.assertEqual(result.compilation.failed_stage, "SYNTAX ANALYSIS")
        self.assertFalse(result.executed)

    def test_semantic_error_stops_execution(self):
        result = run_query("SELECT e.unknown FROM Employee e;")
        self.assertEqual(result.compilation.failed_stage, "SEMANTIC ANALYSIS")
        self.assertFalse(result.executed)

    def test_execution_error_is_wrapped(self):
        # Bypass semantics intentionally to check the executor wrapper itself.
        invalid_ast = SelectQuery(columns=[SelectItem(ColumnRef("name"))], table=TableRef("MissingTable"))
        with Executor() as executor:
            with self.assertRaises(ExecutionError):
                executor.execute(invalid_ast)

    def test_count_distinct_executes(self):
        result = run_query("SELECT COUNT(DISTINCT dept_id) AS departments FROM Employee;")
        self.assertTrue(result.executed)
        self.assertEqual(result.rows, [(4,)])

    def test_cross_join_executes(self):
        result = run_query("SELECT e.name, d.name FROM Employee e CROSS JOIN Department d LIMIT 2;")
        self.assertTrue(result.executed)
        self.assertEqual(len(result.rows), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

---

## `benchmark.py`

```python
"""Repeatable, local end-to-end timing sampler for COSTRA's supported SQL examples."""
from __future__ import annotations
import csv
import json
import platform
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from executor import Executor
from main import DEMO_SQL, run_query

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
RUNS = 30
WARMUP_RUNS = 3
QUERIES = {
    "multi_join_aggregation": DEMO_SQL,
    "indexed_salary_filter": "SELECT name, salary FROM Employee WHERE salary > 80000 ORDER BY salary DESC LIMIT 3;",
    "grouped_department_counts": "SELECT d.name AS department, COUNT(e.id) AS total_employees FROM Employee e JOIN Department d ON e.dept_id = d.id GROUP BY d.name ORDER BY total_employees DESC;",
    "distinct_departments": "SELECT DISTINCT dept_id FROM Employee ORDER BY dept_id;",
}


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def mean(values):
    return sum(values) / len(values) if values else None


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        return None
    index = round((len(ordered) - 1) * pct)
    return ordered[index]


def benchmark_query(name, sql, executor):
    for _ in range(WARMUP_RUNS):
        warmup = run_query(sql, executor)
        if not warmup.compilation.success or not warmup.executed:
            raise RuntimeError(f"Warm-up failed for {name}: {warmup.compilation.errors or warmup.execution_error}")

    samples_ms = []
    last_result = None
    component_samples = {}
    result_signature = None
    for _ in range(RUNS):
        start = time.perf_counter()
        result = run_query(sql, executor)
        elapsed = (time.perf_counter() - start) * 1000
        if not result.compilation.success or not result.executed:
            raise RuntimeError(f"Benchmark failed for {name}: {result.compilation.errors or result.execution_error}")
        signature = (tuple(result.headers), tuple(result.rows))
        if result_signature is not None and signature != result_signature:
            raise RuntimeError(f"Non-repeatable result encountered for {name}")
        result_signature = signature
        samples_ms.append(elapsed)
        for stage, value in result.timings_ms.items():
            component_samples.setdefault(stage, []).append(value)
        last_result = result

    return {
        "query_name": name,
        "runs": RUNS,
        "warmup_runs": WARMUP_RUNS,
        "rows_returned": len(last_result.rows),
        "candidate_plans": len(last_result.compilation.candidates),
        "selected_estimated_cost_model_units": round(last_result.compilation.best_plan.cost, 4),
        "elapsed_ms": {
            "min": round(min(samples_ms), 4),
            "median": round(median(samples_ms), 4),
            "mean": round(mean(samples_ms), 4),
            "p95": round(percentile(samples_ms, 0.95), 4),
            "max": round(max(samples_ms), 4),
        },
        "stage_median_ms": {stage: round(median(values), 4) for stage, values in component_samples.items()},
        "result_is_repeatable": True,
        "interpretation": "Local end-to-end timing on a tiny in-memory fixture; not a general performance guarantee.",
    }


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = {
        "project": "COSTRA - Cost-Based SQL Compiler & Query Optimizer",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "sqlite_version": sqlite3.sqlite_version,
        "environment": "current local runtime; measurements vary by machine and load",
        "note": "COSTRA's estimated cost values are synthetic model units and are not elapsed milliseconds. SQLite executes normalized SQL independently.",
        "benchmarks": [],
    }
    with Executor() as executor:
        for name, sql in QUERIES.items():
            record = benchmark_query(name, sql, executor)
            record["sql"] = " ".join(sql.split())
            output["benchmarks"].append(record)

    json_path = REPORTS / "benchmark_results.json"
    csv_path = REPORTS / "benchmark_results.csv"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "query_name", "runs", "warmup_runs", "rows_returned", "candidate_plans",
            "selected_estimated_cost_model_units", "min_ms", "median_ms", "mean_ms", "p95_ms", "max_ms",
            "result_is_repeatable",
        ])
        writer.writeheader()
        for item in output["benchmarks"]:
            writer.writerow({
                "query_name": item["query_name"], "runs": item["runs"], "warmup_runs": item["warmup_runs"],
                "rows_returned": item["rows_returned"], "candidate_plans": item["candidate_plans"],
                "selected_estimated_cost_model_units": item["selected_estimated_cost_model_units"],
                "min_ms": item["elapsed_ms"]["min"], "median_ms": item["elapsed_ms"]["median"],
                "mean_ms": item["elapsed_ms"]["mean"], "p95_ms": item["elapsed_ms"]["p95"],
                "max_ms": item["elapsed_ms"]["max"], "result_is_repeatable": item["result_is_repeatable"],
            })
    print(f"Wrote {json_path.relative_to(ROOT)}")
    print(f"Wrote {csv_path.relative_to(ROOT)}")
    for item in output["benchmarks"]:
        print(f"{item['query_name']}: median {item['elapsed_ms']['median']:.4f} ms, "
              f"{item['rows_returned']} rows, estimated cost "
              f"{item['selected_estimated_cost_model_units']:.2f} model units")


if __name__ == "__main__":
    main()
```

---

## `requirements.txt`

```text
# COSTRA uses only the Python standard library. No pip install is required.
```
