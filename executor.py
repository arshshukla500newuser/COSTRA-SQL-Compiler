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
