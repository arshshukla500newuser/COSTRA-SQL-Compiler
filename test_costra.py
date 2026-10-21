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

    def test_integrated_menu_offers_one_complete_workflow(self):
        completed = self._run_cli(input_text="1\n1\n2\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("COSTRA — INTEGRATED DEMONSTRATION", completed.stdout)
        self.assertIn("Start complete Review 1 → Review 2 → Review 3 workflow", completed.stdout)
        self.assertIn("ONE QUERY, THREE REVIEW STAGES", completed.stdout)
        self.assertIn("REVIEW 2 — COMPILATION", completed.stdout)
        self.assertIn("REVIEW 3 — OPTIMIZATION, COSTING & EXECUTION", completed.stdout)
        self.assertIn("Goodbye.", completed.stdout)

    def test_custom_sql_menu_option_executes_same_query_through_all_reviews(self):
        completed = self._run_cli(input_text="1\n2\nSELECT name FROM Employee LIMIT 2;\n2\n")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("SQL> ", completed.stdout)
        self.assertIn("REVIEW 1 COMPLETE — continuing with the same SQL input", completed.stdout)
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
