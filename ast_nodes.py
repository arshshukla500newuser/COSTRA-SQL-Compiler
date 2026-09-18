from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ColumnRef:
    name: str
    table: Optional[str] = None


@dataclass
class Literal:
    value: Any


@dataclass
class BinaryExpr:
    left: Any
    operator: str
    right: Any


@dataclass
class UnaryExpr:
    operator: str
    operand: Any


@dataclass
class FunctionCall:
    name: str
    arguments: list = field(default_factory=list)

    def __post_init__(self):
        self.name = self.name.upper()


@dataclass
class SelectItem:
    expression: Any
    alias: Optional[str] = None


@dataclass
class TableRef:
    name: str
    alias: Optional[str] = None


@dataclass
class JoinClause:
    table: TableRef
    condition: Any
    join_type: str = "INNER"

    def __post_init__(self):
        self.join_type = self.join_type.upper()


@dataclass
class OrderItem:
    expression: Any
    direction: str = "ASC"

    def __post_init__(self):
        self.direction = self.direction.upper()


@dataclass
class SelectQuery:
    select_items: list = field(default_factory=list)
    from_table: Optional[TableRef] = None
    joins: list = field(default_factory=list)
    where: Optional[Any] = None
    group_by: list = field(default_factory=list)
    having: Optional[Any] = None
    order_by: list = field(default_factory=list)
    limit: Optional[int] = None
    distinct: bool = False

    @property
    def columns(self):
        return self.select_items

    @columns.setter
    def columns(self, value):
        self.select_items = value

    @property
    def table(self):
        return self.from_table

    @table.setter
    def table(self, value):
        self.from_table = value


def format_expr(expression):

    if isinstance(expression, ColumnRef):

        if expression.name == "*":

            if expression.table:
                return f"{expression.table}.*"

            return "*"

        if expression.table:
            return f"{expression.table}.{expression.name}"

        return expression.name

    if isinstance(expression, Literal):

        if expression.value is None:
            return "NULL"

        if expression.value is True:
            return "TRUE"

        if expression.value is False:
            return "FALSE"

        if isinstance(expression.value, str):

            return (
                "'"
                + expression.value.replace("'", "''")
                + "'"
            )

        return str(expression.value)

    if isinstance(expression, BinaryExpr):

        return (
            f"({format_expr(expression.left)} "
            f"{expression.operator} "
            f"{format_expr(expression.right)})"
        )

    if isinstance(expression, UnaryExpr):

        if expression.operator.upper() == "NOT":

            return (
                f"(NOT "
                f"{format_expr(expression.operand)})"
            )

        return (
            f"({expression.operator}"
            f"{format_expr(expression.operand)})"
        )

    if isinstance(expression, FunctionCall):

        arguments = ", ".join(
            format_expr(argument)
            for argument in expression.arguments
        )

        return f"{expression.name}({arguments})"

    return str(expression)


def format_query(query):

    parts = ["SELECT"]

    if query.distinct:
        parts.append("DISTINCT")

    columns = query.select_items

    parts.append(
        ", ".join(
            (
                format_expr(item.expression)
                + (
                    f" AS {item.alias}"
                    if item.alias
                    else ""
                )
            )
            for item in columns
        )
    )

    parts.append("FROM")

    table = query.from_table

    parts.append(table.name)

    if table.alias:
        parts.append(table.alias)

    for join in query.joins:

        parts.append(join.join_type)
        parts.append("JOIN")
        parts.append(join.table.name)

        if join.table.alias:
            parts.append(join.table.alias)

        parts.append("ON")
        parts.append(
            format_expr(join.condition)
        )

    if query.where is not None:

        parts.append("WHERE")
        parts.append(
            format_expr(query.where)
        )

    if query.group_by:

        parts.append("GROUP")
        parts.append("BY")

        parts.append(
            ", ".join(
                format_expr(x)
                for x in query.group_by
            )
        )

    if query.having is not None:

        parts.append("HAVING")
        parts.append(
            format_expr(query.having)
        )

    if query.order_by:

        parts.append("ORDER")
        parts.append("BY")

        parts.append(
            ", ".join(
                f"{format_expr(item.expression)} "
                f"{item.direction}"
                for item in query.order_by
            )
        )

    if query.limit is not None:

        parts.append("LIMIT")
        parts.append(str(query.limit))

    return " ".join(parts) + ";"


def print_ast(query):

    print("\n" + "=" * 80)
    print("ABSTRACT SYNTAX TREE")
    print("=" * 80)

    print("SELECT")

    for item in query.select_items:

        print(
            f"  {format_expr(item.expression)}"
            + (
                f" AS {item.alias}"
                if item.alias
                else ""
            )
        )

    print(
        f"FROM {query.from_table.name}"
        + (
            f" {query.from_table.alias}"
            if query.from_table.alias
            else ""
        )
    )

    for join in query.joins:

        print(
            f"{join.join_type} JOIN "
            f"{join.table.name}"
        )

        print(
            "  ON "
            + format_expr(join.condition)
        )

    if query.where:

        print(
            "WHERE "
            + format_expr(query.where)
        )

    if query.group_by:

        print(
            "GROUP BY "
            + ", ".join(
                format_expr(x)
                for x in query.group_by
            )
        )

    if query.having:

        print(
            "HAVING "
            + format_expr(query.having)
        )

    if query.order_by:

        print(
            "ORDER BY "
            + ", ".join(
                f"{format_expr(x.expression)} "
                f"{x.direction}"
                for x in query.order_by
            )
        )

    if query.limit is not None:
        print(f"LIMIT {query.limit}")