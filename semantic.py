"""Schema-aware semantic analysis for the supported SQL subset."""
from __future__ import annotations
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr,
    Literal, UnaryExpr, format_expr,
)
from schema import SCHEMA, canonical_table_name

AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
NUMERIC_TYPES = {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}


def walk_expression(node):
    """Yield an expression tree in preorder."""
    if node is None:
        return
    yield node
    if isinstance(node, BinaryExpr):
        yield from walk_expression(node.left)
        yield from walk_expression(node.right)
    elif isinstance(node, UnaryExpr):
        yield from walk_expression(node.operand)
    elif isinstance(node, FunctionCall) and node.argument != "*":
        yield from walk_expression(node.argument)
    elif isinstance(node, IsNullExpr):
        yield from walk_expression(node.expression)
    elif isinstance(node, InExpr):
        yield from walk_expression(node.expression)
        for value in node.values:
            yield from walk_expression(value)
    elif isinstance(node, BetweenExpr):
        yield from walk_expression(node.expression)
        yield from walk_expression(node.lower)
        yield from walk_expression(node.upper)


def contains_aggregate(node) -> bool:
    return any(isinstance(part, FunctionCall) and part.name.upper() in AGGREGATES
               for part in walk_expression(node))


def unaggregated_columns(node, inside_aggregate=False):
    """Collect column references not protected by an aggregate function."""
    found = []
    if node is None:
        return found
    if isinstance(node, ColumnRef):
        if node.name != "*" and not inside_aggregate:
            found.append(node)
    elif isinstance(node, FunctionCall):
        is_aggregate = node.name.upper() in AGGREGATES
        if node.argument != "*":
            found.extend(unaggregated_columns(node.argument, inside_aggregate or is_aggregate))
    elif isinstance(node, BinaryExpr):
        found.extend(unaggregated_columns(node.left, inside_aggregate))
        found.extend(unaggregated_columns(node.right, inside_aggregate))
    elif isinstance(node, UnaryExpr):
        found.extend(unaggregated_columns(node.operand, inside_aggregate))
    elif isinstance(node, IsNullExpr):
        found.extend(unaggregated_columns(node.expression, inside_aggregate))
    elif isinstance(node, InExpr):
        found.extend(unaggregated_columns(node.expression, inside_aggregate))
        for value in node.values:
            found.extend(unaggregated_columns(value, inside_aggregate))
    elif isinstance(node, BetweenExpr):
        for value in (node.expression, node.lower, node.upper):
            found.extend(unaggregated_columns(value, inside_aggregate))
    return found


class SemanticAnalyzer:
    def analyze(self, query):
        errors: list[str] = []
        aliases: dict[str, str] = {}
        references = []  # (reference name, canonical table name)

        all_refs = ([query.table] if query.table else []) + [join.table for join in query.joins]
        for table_ref in all_refs:
            actual = canonical_table_name(table_ref.name)
            if actual is None:
                errors.append(f"Unknown table: {table_ref.name}")
                continue
            ref_name = table_ref.alias or table_ref.name
            key = ref_name.casefold()
            if key in aliases:
                errors.append(f"Duplicate table alias/reference: {ref_name}")
                continue
            aliases[key] = actual
            references.append((ref_name, actual))

        select_aliases = {
            item.alias.casefold(): item.expression
            for item in query.columns if item.alias
        }

        def resolve_column(column: ColumnRef, allow_select_alias=False):
            if column.name == "*":
                if column.table:
                    key = column.table.casefold()
                    if key not in aliases:
                        errors.append(f"Unknown table or alias: {column.table}")
                return None
            if allow_select_alias and not column.table and column.name.casefold() in select_aliases:
                return "SELECT_ALIAS"
            if column.table:
                key = column.table.casefold()
                actual = aliases.get(key)
                if actual is None:
                    errors.append(f"Unknown table or alias: {column.table}")
                    return None
                real_col = next((name for name in SCHEMA[actual] if name.casefold() == column.name.casefold()), None)
                if real_col is None:
                    errors.append(f"Unknown column: {column.table}.{column.name}")
                    return None
                return actual, real_col

            matches = []
            for ref_name, actual in references:
                real_col = next((name for name in SCHEMA[actual] if name.casefold() == column.name.casefold()), None)
                if real_col is not None:
                    matches.append((ref_name, actual, real_col))
            if not matches:
                errors.append(f"Unknown column: {column.name}")
                return None
            if len(matches) > 1:
                names = ", ".join(f"{ref}.{column.name}" for ref, _, _ in matches)
                errors.append(f"Ambiguous column: {column.name} (matches {names})")
                return None
            return matches[0][1], matches[0][2]

        def visit(node, *, allow_aggregate=True, allow_select_alias=False):
            if node is None:
                return
            if isinstance(node, ColumnRef):
                return resolve_column(node, allow_select_alias=allow_select_alias)
            if isinstance(node, Literal):
                return None
            if isinstance(node, FunctionCall):
                name = node.name.upper()
                if name not in AGGREGATES:
                    errors.append(f"Unsupported function: {node.name}")
                    return None
                if not allow_aggregate:
                    errors.append(f"Aggregate function {name} is not allowed in this clause")
                if node.argument == "*":
                    if name != "COUNT":
                        errors.append(f"{name}(*) is not supported; use COUNT(*) or a column argument")
                    if node.distinct:
                        errors.append("DISTINCT * is not supported inside an aggregate")
                else:
                    visit(node.argument, allow_aggregate=False, allow_select_alias=allow_select_alias)
                    if name in {"SUM", "AVG"} and isinstance(node.argument, ColumnRef):
                        column_info = resolve_column(node.argument)
                        if column_info and column_info != "SELECT_ALIAS":
                            table_name, column_name = column_info
                            if SCHEMA[table_name][column_name].upper() not in NUMERIC_TYPES:
                                errors.append(f"{name} requires a numeric column, got {node.argument.name}")
                return None
            if isinstance(node, BinaryExpr):
                visit(node.left, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.right, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, UnaryExpr):
                visit(node.operand, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, IsNullExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, InExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                for value in node.values:
                    visit(value, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            elif isinstance(node, BetweenExpr):
                visit(node.expression, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.lower, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
                visit(node.upper, allow_aggregate=allow_aggregate, allow_select_alias=allow_select_alias)
            return None

        for item in query.columns:
            visit(item.expression)
        for join in query.joins:
            visit(join.condition, allow_aggregate=False)
        visit(query.where, allow_aggregate=False)
        for expression in query.group_by:
            visit(expression, allow_aggregate=False)
        visit(query.having)
        for item in query.order_by:
            visit(item.expression, allow_select_alias=True)

        # GROUP BY validation for non-aggregated column references. COSTRA deliberately
        # supports a conservative subset instead of SQLite's permissive bare-column rules.
        aggregate_query = bool(query.group_by) or any(
            contains_aggregate(item.expression) for item in query.columns
        ) or contains_aggregate(query.having)
        if aggregate_query:
            grouped = {format_expr(expr).casefold() for expr in query.group_by}
            for item in query.columns:
                for column in unaggregated_columns(item.expression):
                    expression_text = format_expr(column)
                    if not query.group_by:
                        errors.append(
                            f"Selected column {expression_text} must be aggregated when GROUP BY is absent"
                        )
                    elif expression_text.casefold() not in grouped:
                        errors.append(
                            f"Selected column {expression_text} must appear in GROUP BY or be aggregated"
                        )
            for column in unaggregated_columns(query.having):
                expression_text = format_expr(column)
                if not query.group_by:
                    errors.append(f"HAVING column {expression_text} must be aggregated when GROUP BY is absent")
                elif expression_text.casefold() not in grouped:
                    errors.append(f"HAVING column {expression_text} must appear in GROUP BY or be aggregated")

        # Remove duplicates while keeping first occurrence/order.
        return list(dict.fromkeys(errors)), aliases
