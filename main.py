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
    print("\nREVIEW 2 — COMPILATION: LEXER, PARSER, SEMANTICS & IR")
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
    print("\nREVIEW 3 — OPTIMIZATION, COSTING & EXECUTION")
    print("\n5. CANDIDATE PHYSICAL PLANS — SYNTHETIC ESTIMATES")
    if comp.candidates:
        lowest_cost = min(plan.cost for plan in comp.candidates)
        winners = [i for i, plan in enumerate(comp.candidates, start=1)
                   if abs(plan.cost - lowest_cost) < 1e-9]
        print(f"{'Candidate plan':<18} {'Estimated cost':>18} {'Estimated rows':>16}  Selection")
        print("-" * 78)
        for index, plan in enumerate(comp.candidates, start=1):
            if index == winners[0]:
                status = "SELECTED"
            elif index in winners:
                status = "TIED FOR MINIMUM"
            else:
                status = "Not selected"
            print(f"{'Plan ' + str(index):<18} {plan.cost:>18,.2f} {plan.rows:>16,.2f}  {status}")
    print("\n6. SELECTED ESTIMATED PLAN")
    if comp.best_plan:
        lowest_cost = min((plan.cost for plan in comp.candidates), default=comp.best_plan.cost)
        print(f"Cost comparison: {len(comp.candidates)} candidate plan(s) evaluated.")
        print("Selection rule: minimum estimated total cost = min(candidate costs).")
        print(f"Lowest estimated cost: {lowest_cost:,.2f} model units")
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
    lowest = min(p.cost for p in multi.candidates)
    winners = [i for i, p in enumerate(multi.candidates, 1) if abs(p.cost - lowest) < 1e-9]
    print(f"{'Candidate plan':<18} {'Estimated cost':>18} {'Estimated rows':>16}  Selection")
    print("-" * 78)
    for i, candidate in enumerate(multi.candidates, 1):
        if i == winners[0]:
            status = "SELECTED"
        elif i in winners:
            status = "TIED FOR MINIMUM"
        else:
            status = "Not selected"
        print(f"{'Plan ' + str(i):<18} {candidate.cost:>18,.2f} {candidate.rows:>16,.2f}  {status}")
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


def _read_multiline_sql():
    """Read a query once; allow either a one-line or multi-line SQL statement."""
    print("Enter your SQL query. Finish with a semicolon (;) or submit a blank line after the query.")
    lines = []
    try:
        first = input("SQL> ")
        if not first.strip():
            return ""
        lines.append(first)
        while not lines[-1].rstrip().endswith(";"):
            line = input("...  ")
            if not line.strip():
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        print("\nInput cancelled.")
        return ""
    return "\n".join(lines).strip()


def _run_all_reviews(sql: str, result: Optional[QueryRunResult] = None):
    """Run one chosen SQL input through the complete Review 1 → 2 → 3 narrative."""
    print("\n" + "=" * 78)
    print("COSTRA — ONE QUERY, THREE REVIEW STAGES")
    print("=" * 78)
    print("The SQL selected below is the single input for the integrated demonstration.")
    _print_review1_summary()
    print("\nREVIEW 1 COMPLETE — continuing with the same SQL input; no second query is requested.")
    result = result or run_query(sql)
    _print_result(result)
    print("\n" + "=" * 78)
    print("FINAL DEMONSTRATION SUMMARY")
    print("=" * 78)
    print("Review 1: design, problem statement, objectives, scope and architecture shown.")
    if result.compilation.success and result.compilation.query is not None:
        print("Review 2: lexical, syntax, semantic and relational-IR stages completed successfully.")
        print("Review 3: candidate cost estimates and the best estimated plan are shown above.")
        if result.executed:
            print(f"Execution: SQLite returned {len(result.rows)} row(s).")
        elif result.execution_error:
            print("Execution: compilation succeeded, but SQLite reported an execution error:")
            print("  " + result.execution_error)
        else:
            print("Execution: did not complete; inspect the stage output above.")
    else:
        print("Review 2: compilation did not pass; the failure stage and diagnostic are shown above.")
        print("Review 3: optimization/execution were skipped because compilation failed.")
    print("Reminder: COSTRA's costs are synthetic relative model units; SQLite independently chooses its execution plan.")


def _custom_query_prompt():
    sql = _read_multiline_sql()
    if not sql:
        print("No SQL entered. Returning to menu.")
        return
    _run_all_reviews(sql)


def _unified_demo_prompt():
    print("\n" + "=" * 68 + "\nCOSTRA — INTEGRATED REVIEW DEMONSTRATION\n" + "=" * 68)
    print("1. Use built-in multi-join demo query")
    print("2. Enter my own SQL query")
    try:
        choice = input("Choose input (1-2): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nReturning to menu.")
        return
    if choice == "1":
        sql = DEMO_SQL
    elif choice == "2":
        sql = _read_multiline_sql()
        if not sql:
            print("No SQL entered. Returning to menu.")
            return
    else:
        print("Invalid option. Choose 1 or 2.")
        return
    _run_all_reviews(sql)


def interactive_menu():
    """Offer one integrated demonstration rather than separate review menus."""
    while True:
        print("\n" + "=" * 68 + "\nCOSTRA — INTEGRATED DEMONSTRATION\n" + "=" * 68)
        print("1. Start complete Review 1 → Review 2 → Review 3 workflow")
        print("2. Exit")
        try:
            choice = input("Choose an option (1-2): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting COSTRA.")
            break
        if choice == "2":
            print("Goodbye.")
            break
        if choice == "1":
            _unified_demo_prompt()
        else:
            print("Invalid option. Please choose 1 or 2.")


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
        _run_all_reviews(DEMO_SQL)
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
        _run_all_reviews(args.query, result)
        return 0 if result.compilation.success and result.executed else 2

    interactive_menu()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
