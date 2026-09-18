import unittest

from lexer import tokenize
from parser import parse_sql
from semantic import analyze
from optimizer import optimize


class CostraTests(unittest.TestCase):

    def test_lexer(self):

        tokens = tokenize(
            "SELECT e.name FROM Employee e;"
        )

        kinds = [
            token.kind
            for token in tokens
        ]

        self.assertIn(
            "SELECT",
            kinds
        )

        self.assertIn(
            "FROM",
            kinds
        )

        self.assertIn(
            "DOT",
            kinds
        )

    def test_parser(self):

        query = parse_sql(
            """
            SELECT
                e.name,
                e.salary
            FROM Employee e
            WHERE e.salary > 60000;
            """
        )

        self.assertEqual(
            query.from_table.name,
            "Employee"
        )

        self.assertEqual(
            query.from_table.alias,
            "e"
        )

        self.assertIsNotNone(
            query.where
        )

    def test_join_parser(self):

        query = parse_sql(
            """
            SELECT e.name, d.name
            FROM Employee e
            JOIN Department d
                ON e.dept_id = d.id;
            """
        )

        self.assertEqual(
            len(query.joins),
            1
        )

        self.assertEqual(
            query.joins[0].table.name,
            "Department"
        )

    def test_aggregate_parser(self):

        query = parse_sql(
            """
            SELECT
                d.name,
                COUNT(e.id),
                AVG(e.salary)
            FROM Employee e
            JOIN Department d
                ON e.dept_id = d.id
            GROUP BY d.name
            HAVING AVG(e.salary) > 60000
            ORDER BY AVG(e.salary) DESC
            LIMIT 5;
            """
        )

        self.assertEqual(
            len(query.select_items),
            3
        )

        self.assertEqual(
            len(query.group_by),
            1
        )

        self.assertIsNotNone(
            query.having
        )

        self.assertEqual(
            query.limit,
            5
        )

    def test_semantic_analysis(self):

        query = parse_sql(
            """
            SELECT e.name
            FROM Employee e
            WHERE e.salary > 60000;
            """
        )

        result = analyze(query)

        self.assertTrue(
            result
        )

    def test_optimizer(self):

        query = parse_sql(
            """
            SELECT
                e.name,
                d.name
            FROM Employee e
            JOIN Department d
                ON e.dept_id = d.id
            WHERE e.salary > 60000;
            """
        )

        best_plan, plans = optimize(
            query
        )

        self.assertGreater(
            len(plans),
            0
        )

        self.assertIn(
            "estimated_cost",
            best_plan
        )

        self.assertIn(
            "join_order",
            best_plan
        )

    def test_complex_query(self):

        query = parse_sql(
            """
            SELECT
                d.name AS department,
                COUNT(e.id) AS employee_count,
                AVG(e.salary) AS average_salary
            FROM Employee e
            JOIN Department d
                ON e.dept_id = d.id
            JOIN Assignment a
                ON e.id = a.employee_id
            JOIN Project p
                ON a.project_id = p.id
            WHERE
                e.salary > 60000
                AND p.budget > 100000
            GROUP BY d.name
            HAVING AVG(e.salary) > 65000
            ORDER BY AVG(e.salary) DESC
            LIMIT 5;
            """
        )

        self.assertEqual(
            len(query.joins),
            3
        )

        self.assertEqual(
            len(query.group_by),
            1
        )

        best_plan, plans = optimize(
            query
        )

        self.assertGreater(
            len(plans),
            1
        )

        self.assertGreater(
            best_plan["estimated_cost"],
            0
        )


if __name__ == "__main__":
    unittest.main()