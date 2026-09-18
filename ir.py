from dataclasses import dataclass, field

from ast_nodes import (
    ColumnRef,
    FunctionCall,
)


@dataclass
class PlanNode:

    operator: str

    children: list = field(
        default_factory=list
    )

    properties: dict = field(
        default_factory=dict
    )

    estimated_rows: float = 0.0

    estimated_cost: float = 0.0

    actual_rows: int = 0

    actual_time: float = 0.0

    def add_child(self, child):

        self.children.append(child)

    def pretty(self, level=0):

        indent = "  " * level

        result = (
            f"{indent}{self.operator}"
        )

        if self.properties:

            result += (
                " "
                + ", ".join(
                    f"{key}={value}"
                    for key, value
                    in self.properties.items()
                )
            )

        result += (
            f" | rows={self.estimated_rows:.2f}"
            f" | cost={self.estimated_cost:.2f}"
        )

        for child in self.children:

            result += "\n" + child.pretty(
                level + 1
            )

        return result


def contains_aggregate(query):

    expressions = [
        item.expression
        for item in query.select_items
    ]

    expressions += query.group_by

    if query.having:
        expressions.append(
            query.having
        )

    if query.order_by:

        expressions += [
            item.expression
            for item in query.order_by
        ]

    for expression in expressions:

        if expression_contains_aggregate(
            expression
        ):
            return True

    return False


def expression_contains_aggregate(
    expression
):

    if isinstance(
        expression,
        FunctionCall
    ):

        return expression.name.upper() in {
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX",
        }

    if hasattr(expression, "left"):

        return (
            expression_contains_aggregate(
                expression.left
            )
            or
            expression_contains_aggregate(
                expression.right
            )
        )

    if hasattr(expression, "operand"):

        return expression_contains_aggregate(
            expression.operand
        )

    if isinstance(expression, FunctionCall):

        return any(
            expression_contains_aggregate(
                arg
            )
            for arg in expression.arguments
        )

    return False


def build_logical_plan(query):

    current = PlanNode(
        operator="TABLE_SCAN",
        properties={
            "table":
                query.from_table.name,
            "alias":
                query.from_table.alias
                or query.from_table.name,
        }
    )

    for join in query.joins:

        join_node = PlanNode(
            operator="LOGICAL_JOIN",
            properties={
                "type":
                    join.join_type,
                "condition":
                    str(join.condition),
                "table":
                    join.table.name,
            },
            children=[
                current
            ]
        )

        current = join_node

    if query.where:

        current = PlanNode(
            operator="FILTER",
            properties={
                "predicate":
                    str(query.where)
            },
            children=[
                current
            ]
        )

    if query.group_by:

        current = PlanNode(
            operator="AGGREGATE",
            properties={
                "group_by":
                    str(query.group_by)
            },
            children=[
                current
            ]
        )

    if query.having:

        current = PlanNode(
            operator="HAVING",
            properties={
                "predicate":
                    str(query.having)
            },
            children=[
                current
            ]
        )

    if query.order_by:

        current = PlanNode(
            operator="SORT",
            properties={
                "order_by":
                    str(query.order_by)
            },
            children=[
                current
            ]
        )

    if query.limit is not None:

        current = PlanNode(
            operator="LIMIT",
            properties={
                "limit":
                    query.limit
            },
            children=[
                current
            ]
        )

    current = PlanNode(
        operator="PROJECT",
        properties={
            "columns":
                len(query.select_items)
        },
        children=[
            current
        ]
    )

    return current