SCHEMA = {
    "Department": {
        "id": "INTEGER",
        "name": "TEXT",
    },

    "Employee": {
        "id": "INTEGER",
        "name": "TEXT",
        "salary": "INTEGER",
        "dept_id": "INTEGER",
        "experience": "INTEGER",
    },

    "Project": {
        "id": "INTEGER",
        "name": "TEXT",
        "budget": "INTEGER",
        "manager_id": "INTEGER",
        "dept_id": "INTEGER",
    },

    "Assignment": {
        "employee_id": "INTEGER",
        "project_id": "INTEGER",
        "hours": "INTEGER",
    },
}


TABLE_ROWS = {
    "Department": 4,
    "Employee": 8,
    "Project": 5,
    "Assignment": 8,
}


INDEXES = {
    "Department": {
        "id"
    },

    "Employee": {
        "id",
        "dept_id",
        "salary"
    },

    "Project": {
        "id",
        "manager_id",
        "dept_id",
        "budget"
    },

    "Assignment": {
        "employee_id",
        "project_id"
    },
}


def table_exists(table_name):

    return table_name in SCHEMA


def get_columns(table_name):

    return SCHEMA.get(
        table_name,
        {}
    )


def column_exists(table_name, column_name):

    return (
        table_name in SCHEMA
        and column_name in SCHEMA[table_name]
    )


def has_index(table_name, column_name):

    return (
        column_name in INDEXES.get(
            table_name,
            set()
        )
    )


def get_row_count(table_name):

    return TABLE_ROWS.get(
        table_name,
        0
    )