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
