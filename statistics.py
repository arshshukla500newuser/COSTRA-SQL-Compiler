from schema import (
    TABLE_ROWS,
    SCHEMA,
)


COLUMN_STATS = {

    "Employee": {
        "id": {
            "distinct": 8,
            "nulls": 0,
            "min": 1,
            "max": 8,
        },

        "salary": {
            "distinct": 8,
            "nulls": 0,
            "min": 48000,
            "max": 91000,
        },

        "dept_id": {
            "distinct": 3,
            "nulls": 0,
            "min": 1,
            "max": 4,
        },

        "experience": {
            "distinct": 7,
            "nulls": 0,
            "min": 2,
            "max": 8,
        },
    },

    "Department": {
        "id": {
            "distinct": 4,
            "nulls": 0,
            "min": 1,
            "max": 4,
        },

        "name": {
            "distinct": 4,
            "nulls": 0,
        },
    },

    "Project": {
        "id": {
            "distinct": 5,
            "nulls": 0,
            "min": 1,
            "max": 5,
        },

        "budget": {
            "distinct": 5,
            "nulls": 0,
            "min": 110000,
            "max": 300000,
        },

        "dept_id": {
            "distinct": 3,
            "nulls": 0,
            "min": 1,
            "max": 4,
        },
    },

    "Assignment": {
        "employee_id": {
            "distinct": 6,
            "nulls": 0,
            "min": 1,
            "max": 8,
        },

        "project_id": {
            "distinct": 5,
            "nulls": 0,
            "min": 1,
            "max": 5,
        },

        "hours": {
            "distinct": 7,
            "nulls": 0,
            "min": 15,
            "max": 35,
        },
    },
}


def table_rows(table_name):

    return TABLE_ROWS.get(
        table_name,
        1000
    )


def get_column_stats(
    table_name,
    column_name
):

    return COLUMN_STATS.get(
        table_name,
        {}
    ).get(
        column_name,
        {}
    )


def equality_selectivity(
    table_name,
    column_name
):

    stats = get_column_stats(
        table_name,
        column_name
    )

    distinct = stats.get(
        "distinct",
        max(1, table_rows(table_name))
    )

    return 1.0 / max(1, distinct)


def range_selectivity(
    table_name,
    column_name,
    operator,
    value
):

    stats = get_column_stats(
        table_name,
        column_name
    )

    minimum = stats.get("min")
    maximum = stats.get("max")

    if (
        minimum is None
        or maximum is None
        or maximum <= minimum
    ):
        return 0.33

    try:
        value = float(value)
        minimum = float(minimum)
        maximum = float(maximum)

    except (TypeError, ValueError):
        return 0.33

    if operator in {">", ">="}:

        selectivity = (
            maximum - value
        ) / (
            maximum - minimum
        )

    elif operator in {"<", "<="}:

        selectivity = (
            value - minimum
        ) / (
            maximum - minimum
        )

    else:

        return 0.33

    return max(
        0.01,
        min(0.99, selectivity)
    )


def predicate_selectivity(
    expression,
    aliases
):

    from ast_nodes import (
        BinaryExpr,
        UnaryExpr,
        ColumnRef,
        Literal,
    )

    if isinstance(expression, BinaryExpr):

        operator = expression.operator.upper()

        if operator == "AND":

            return (
                predicate_selectivity(
                    expression.left,
                    aliases
                )
                *
                predicate_selectivity(
                    expression.right,
                    aliases
                )
            )

        if operator == "OR":

            left = predicate_selectivity(
                expression.left,
                aliases
            )

            right = predicate_selectivity(
                expression.right,
                aliases
            )

            return min(
                0.99,
                left + right - left * right
            )

        if (
            isinstance(expression.left, ColumnRef)
            and isinstance(expression.right, Literal)
        ):

            column = expression.left

            table = aliases.get(
                column.table,
                column.table
            )

            if not table:
                return 0.33

            if operator == "=":

                return equality_selectivity(
                    table,
                    column.name
                )

            if operator in {
                "<",
                "<=",
                ">",
                ">="
            }:

                return range_selectivity(
                    table,
                    column.name,
                    operator,
                    expression.right.value
                )

        return 0.33

    if isinstance(expression, UnaryExpr):

        if expression.operator.upper() == "NOT":

            return max(
                0.01,
                1.0
                - predicate_selectivity(
                    expression.operand,
                    aliases
                )
            )

    return 1.0