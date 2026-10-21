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
