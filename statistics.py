"""Synthetic cardinality/selectivity helpers used by the estimated cost model."""
from __future__ import annotations
from typing import Optional, Dict
from ast_nodes import BetweenExpr, BinaryExpr, ColumnRef, InExpr, IsNullExpr, Literal, UnaryExpr
from schema import STATS, SCHEMA


def table_rows(table: str) -> float:
    stats = STATS.get(table)
    return float(stats["rows"]) if stats else 1000.0


def referenced_columns(expression) -> list[ColumnRef]:
    from semantic import walk_expression
    return [node for node in walk_expression(expression) if isinstance(node, ColumnRef) and node.name != "*"]


def referenced_aliases(expression, aliases: dict[str, str], table_refs=None) -> set[str]:
    """Resolve expression column references to table aliases for predicate placement."""
    found = set()
    for column in referenced_columns(expression):
        if column.table:
            found.add(column.table.casefold())
            continue
        matches = []
        for alias, table in aliases.items():
            if any(name.casefold() == column.name.casefold() for name in SCHEMA.get(table, {})):
                matches.append(alias)
        if len(matches) == 1:
            found.add(matches[0])
        elif matches:
            found.update(matches)
    return found


def _column_stats(column: ColumnRef, aliases: Optional[Dict[str, str]]):
    if not aliases:
        return None
    if column.table:
        table = aliases.get(column.table.casefold())
        if not table:
            return None
    else:
        tables = [t for t in aliases.values() if any(c.casefold() == column.name.casefold() for c in SCHEMA.get(t, {}))]
        if len(tables) != 1:
            return None
        table = tables[0]
    return STATS.get(table, {}).get("columns", {}).get(column.name.casefold()) or next(
        (v for name, v in STATS.get(table, {}).get("columns", {}).items() if name.casefold() == column.name.casefold()),
        None,
    )


def _range_fraction(column, operator, literal, aliases):
    stats = _column_stats(column, aliases)
    if not stats or "min" not in stats or "max" not in stats:
        return None
    low, high = stats["min"], stats["max"]
    try:
        value = float(literal.value)
        low, high = float(low), float(high)
    except (TypeError, ValueError):
        return None
    if high <= low:
        return 1.0 if ((operator in (">=", "<=") and value == low) or (operator == "=" and value == low)) else 0.0
    if operator in (">", ">="):
        return max(0.0, min(1.0, (high - value) / (high - low)))
    if operator in ("<", "<="):
        return max(0.0, min(1.0, (value - low) / (high - low)))
    return None


def selectivity(expression, aliases: Optional[Dict[str, str]] = None) -> float:
    """Return a heuristic fraction in [0, 1]; these estimates are not live DB stats."""
    if expression is None:
        return 1.0
    if isinstance(expression, Literal):
        if expression.value is True:
            return 1.0
        if expression.value in (False, None):
            return 0.0
        return 1.0
    if isinstance(expression, UnaryExpr):
        if expression.operator.upper() == "NOT":
            return max(0.0, min(1.0, 1.0 - selectivity(expression.operand, aliases)))
        return 0.5
    if isinstance(expression, IsNullExpr):
        return 0.05 if not expression.negated else 0.95
    if isinstance(expression, InExpr):
        if isinstance(expression.expression, ColumnRef):
            stats = _column_stats(expression.expression, aliases)
            if stats:
                fraction = min(0.95, len(expression.values) / max(1.0, float(stats.get("distinct", 10))))
            else:
                fraction = min(0.95, len(expression.values) * 0.1)
        else:
            fraction = min(0.95, len(expression.values) * 0.1)
        return 1.0 - fraction if expression.negated else fraction
    if isinstance(expression, BetweenExpr):
        low = _range_fraction(expression.expression, ">=", expression.lower, aliases) if isinstance(expression.expression, ColumnRef) and isinstance(expression.lower, Literal) else None
        high = _range_fraction(expression.expression, "<=", expression.upper, aliases) if isinstance(expression.expression, ColumnRef) and isinstance(expression.upper, Literal) else None
        fraction = max(0.0, min(1.0, (low if low is not None else 0.5) + (high if high is not None else 0.5) - 1.0))
        if fraction == 0.0:
            fraction = 0.25
        return 1.0 - fraction if expression.negated else fraction
    if not isinstance(expression, BinaryExpr):
        return 0.5

    op = expression.operator.upper()
    if op == "AND":
        return max(0.0, min(1.0, selectivity(expression.left, aliases) * selectivity(expression.right, aliases)))
    if op == "OR":
        left, right = selectivity(expression.left, aliases), selectivity(expression.right, aliases)
        return max(0.0, min(1.0, left + right - left * right))
    if op == "LIKE":
        return 0.1
    if isinstance(expression.left, ColumnRef) and isinstance(expression.right, Literal):
        if op == "=":
            stats = _column_stats(expression.left, aliases)
            return max(0.0001, min(1.0, 1.0 / max(1.0, float(stats.get("distinct", 10))))) if stats else 0.1
        if op in (">", "<", ">=", "<="):
            fraction = _range_fraction(expression.left, op, expression.right, aliases)
            return max(0.0001, fraction) if fraction is not None else 0.3
        if op in ("<>", "!="):
            stats = _column_stats(expression.left, aliases)
            return max(0.0, 1.0 - 1.0 / max(1.0, float(stats.get("distinct", 10)))) if stats else 0.9
    if isinstance(expression.left, ColumnRef) and isinstance(expression.right, ColumnRef):
        if op == "=":
            left, right = _column_stats(expression.left, aliases), _column_stats(expression.right, aliases)
            if left and right:
                return 1.0 / max(1.0, float(left.get("distinct", 10)), float(right.get("distinct", 10)))
            return 0.1
        if op in ("<>", "!="):
            return 0.9
    return 0.5
