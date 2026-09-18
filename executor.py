import sqlite3
import time


class SQLExecutor:

    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.create_schema()
        self.insert_data()

    def create_schema(self):

        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE Department (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE Employee (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                dept_id INTEGER,
                salary REAL,
                FOREIGN KEY (dept_id) REFERENCES Department(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE Project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                budget REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE Assignment (
                employee_id INTEGER,
                project_id INTEGER,
                hours INTEGER,
                FOREIGN KEY (employee_id) REFERENCES Employee(id),
                FOREIGN KEY (project_id) REFERENCES Project(id)
            )
        """)

        self.connection.commit()

    def insert_data(self):

        cursor = self.connection.cursor()

        departments = [
            (1, "Engineering"),
            (2, "Finance"),
            (3, "HR"),
            (4, "Marketing"),
            (5, "Operations")
        ]

        employees = [
            (1, "Alice", 1, 95000),
            (2, "Bob", 1, 85000),
            (3, "Charlie", 1, 78000),
            (4, "David", 2, 91000),
            (5, "Emma", 2, 72000),
            (6, "Frank", 3, 69000),
            (7, "Grace", 4, 65000),
            (8, "Henry", 5, 88000),
            (9, "Iris", 1, 105000),
            (10, "Jack", 5, 76000)
        ]

        projects = [
            (1, "AI Platform", 250000),
            (2, "Cloud Migration", 180000),
            (3, "Security Upgrade", 150000),
            (4, "Internal Portal", 90000),
            (5, "Data Warehouse", 300000),
            (6, "Mobile Application", 220000)
        ]

        assignments = [
            (1, 1, 120),
            (1, 2, 80),
            (2, 2, 100),
            (2, 3, 60),
            (3, 1, 90),
            (3, 5, 110),
            (4, 5, 100),
            (5, 4, 70),
            (6, 3, 80),
            (7, 4, 50),
            (8, 2, 90),
            (8, 6, 120),
            (9, 1, 130),
            (9, 5, 100),
            (10, 6, 80)
        ]

        cursor.executemany(
            "INSERT INTO Department VALUES (?, ?)",
            departments
        )

        cursor.executemany(
            "INSERT INTO Employee VALUES (?, ?, ?, ?)",
            employees
        )

        cursor.executemany(
            "INSERT INTO Project VALUES (?, ?, ?)",
            projects
        )

        cursor.executemany(
            "INSERT INTO Assignment VALUES (?, ?, ?)",
            assignments
        )

        self.connection.commit()

    def execute(self, sql):

        cursor = self.connection.cursor()

        start_time = time.perf_counter()

        cursor.execute(sql)

        rows = cursor.fetchall()

        end_time = time.perf_counter()

        execution_time = end_time - start_time

        headers = []

        if cursor.description:
            headers = [
                column[0]
                for column in cursor.description
            ]

        return {
            "headers": headers,
            "rows": rows,
            "execution_time": execution_time,
            "row_count": len(rows)
        }

    def close(self):
        self.connection.close()


def execute_query(query):

    """
    Executes the SQL represented by the parsed query.

    The parser produces an AST. The AST is converted back
    into executable SQL and evaluated using SQLite.
    """

    from ast_nodes import format_query

    sql = format_query(query)

    executor = SQLExecutor()

    try:

        result = executor.execute(sql)

        return (
            result["headers"],
            result["rows"],
            sql
        )

    finally:

        executor.close()