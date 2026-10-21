"""Abstract syntax tree nodes and safe SQL pretty-printing for COSTRA's SQL subset."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ColumnRef:
    name: str
    table: Optional[str] = None


@dataclass(frozen=True)
class Literal:
    value: Any


@dataclass(frozen=True)
class BinaryExpr:
    left: Any
    operator: str
    right: Any


@dataclass(frozen=True)
class UnaryExpr:
    operator: str
    operand: Any


@dataclass(frozen=True)
class IsNullExpr:
    expression: Any
    negated: bool = False


@dataclass(frozen=True)
class InExpr:
    expression: Any
    values: tuple[Any, ...]
    negated: bool = False


@dataclass(frozen=True)
class BetweenExpr:
    expression: Any
    lower: Any
    upper: Any
    negated: bool = False


@dataclass(frozen=True)
class FunctionCall:
    name: str
    argument: Any
    distinct: bool = False


@dataclass(frozen=True)
class SelectItem:
    expression: Any
    alias: Optional[str] = None


@dataclass(frozen=True)
class TableRef:
    name: str
    alias: Optional[str] = None

    @property
    def reference_name(self) -> str:
        return self.alias or self.name


@dataclass(frozen=True)
class JoinClause:
    table: TableRef
    condition: Any
    join_type: str = "INNER"


@dataclass(frozen=True)
class OrderItem:
    expression: Any
    direction: str = "ASC"


@dataclass
class SelectQuery:
    columns: list[SelectItem] = field(default_factory=list)
    table: Optional[TableRef] = None
    joins: list[JoinClause] = field(default_factory=list)
    where: Optional[Any] = None
    group_by: list[Any] = field(default_factory=list)
    having: Optional[Any] = None
    order_by: list[OrderItem] = field(default_factory=list)
    limit: Optional[int] = None
    distinct: bool = False


def format_expr(node: Any) -> str:
    if isinstance(node, ColumnRef):
        if node.name == "*":
            return f"{node.table}.*" if node.table else "*"
        return f"{node.table}.{node.name}" if node.table else node.name
    if isinstance(node, Literal):
        if node.value is None:
            return "NULL"
        if isinstance(node.value, bool):
            return "TRUE" if node.value else "FALSE"
        if isinstance(node.value, str):
            return "'" + node.value.replace("'", "''") + "'"
        return str(node.value)
    if isinstance(node, BinaryExpr):
        return f"({format_expr(node.left)} {node.operator} {format_expr(node.right)})"
    if isinstance(node, UnaryExpr):
        if node.operator in ("+", "-"):
            return f"({node.operator}{format_expr(node.operand)})"
        return f"({node.operator} {format_expr(node.operand)})"
    if isinstance(node, IsNullExpr):
        return f"({format_expr(node.expression)} IS {'NOT ' if node.negated else ''}NULL)"
    if isinstance(node, InExpr):
        vals = ", ".join(format_expr(v) for v in node.values)
        return f"({format_expr(node.expression)} {'NOT ' if node.negated else ''}IN ({vals}))"
    if isinstance(node, BetweenExpr):
        return (f"({format_expr(node.expression)} {'NOT ' if node.negated else ''}BETWEEN "
                f"{format_expr(node.lower)} AND {format_expr(node.upper)})")
    if isinstance(node, FunctionCall):
        arg = "*" if node.argument == "*" else format_expr(node.argument)
        distinct = "DISTINCT " if node.distinct else ""
        return f"{node.name.upper()}({distinct}{arg})"
    return str(node)


def format_query(query: SelectQuery) -> str:
    """Render the AST back to a single SELECT statement accepted by SQLite."""
    if query.table is None:
        raise ValueError("Cannot format a SELECT without a FROM table")
    select = "SELECT DISTINCT" if query.distinct else "SELECT"
    projection = []
    for item in query.columns:
        piece = format_expr(item.expression)
        if item.alias:
            piece += f" AS {item.alias}"
        projection.append(piece)
    parts = [select, ", ".join(projection), "FROM", query.table.name]
    if query.table.alias:
        parts += ["AS", query.table.alias]
    for join in query.joins:
        join_type = join.join_type.upper()
        parts += [join_type, "JOIN", join.table.name]
        if join.table.alias:
            parts += ["AS", join.table.alias]
        if join_type != "CROSS":
            parts += ["ON", format_expr(join.condition)]
    if query.where is not None:
        parts += ["WHERE", format_expr(query.where)]
    if query.group_by:
        parts += ["GROUP BY", ", ".join(format_expr(item) for item in query.group_by)]
    if query.having is not None:
        parts += ["HAVING", format_expr(query.having)]
    if query.order_by:
        parts += ["ORDER BY", ", ".join(
            f"{format_expr(item.expression)} {item.direction.upper()}" for item in query.order_by
        )]
    if query.limit is not None:
        parts += ["LIMIT", str(query.limit)]
    return " ".join(parts) + ";"
