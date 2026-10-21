"""Educational cost-based optimizer for COSTRA.

The optimizer creates estimated candidate plans and selects the minimum estimated
cost. SQLite independently executes the normalized SQL; COSTRA does not inject its
chosen plan into SQLite's internal planner.
"""
from __future__ import annotations
import itertools
import math
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr,
    Literal, UnaryExpr, format_expr,
)
from ir import PlanNode, build_logical_plan, contains_aggregate
from schema import INDEXES, SCHEMA, STATS, canonical_table_name
from statistics import referenced_aliases, selectivity


def split_conjuncts(expression):
    if isinstance(expression, BinaryExpr) and expression.operator.upper() == "AND":
        return split_conjuncts(expression.left) + split_conjuncts(expression.right)
    return [expression] if expression is not None else []


def combine_conjuncts(expressions):
    if not expressions:
        return None
    current = expressions[0]
    for expr in expressions[1:]:
        current = BinaryExpr(current, "AND", expr)
    return current


def _column_refs(expression):
    from semantic import walk_expression
    return [part for part in walk_expression(expression) if isinstance(part, ColumnRef) and part.name != "*"]


class CostModel:
    """Consistent relative cost units; not wall-clock milliseconds."""
    def full_scan(self, rows: float) -> float:
        return rows * 1.0

    def index_scan(self, table_rows: float, output_rows: float) -> float:
        # Index descent + leaf visits/output fetches in simplified relative units.
        return math.log2(max(2.0, table_rows)) * 2.0 + output_rows * 0.60

    def predicate(self, input_rows: float) -> float:
        return input_rows * 0.20

    def nested_loop_join(self, left_rows: float, right_rows: float) -> float:
        return left_rows * max(1.0, right_rows) * 0.15

    def hash_join(self, left_rows: float, right_rows: float) -> float:
        return (left_rows + right_rows) * 1.10 + min(left_rows, right_rows) * 0.25

    def merge_join(self, left_rows: float, right_rows: float) -> float:
        sort_left = left_rows * math.log2(max(2.0, left_rows)) * 0.45
        sort_right = right_rows * math.log2(max(2.0, right_rows)) * 0.45
        return (left_rows + right_rows) * 0.80 + sort_left + sort_right

    def aggregate(self, rows: float) -> float:
        return rows * 0.45

    def distinct(self, rows: float) -> float:
        return rows * 0.30

    def sort(self, rows: float) -> float:
        return rows * math.log2(max(2.0, rows)) * 0.35

    def project(self, rows: float) -> float:
        return rows * 0.05


class Optimizer:
    def __init__(self, max_candidates: int = 6, max_join_orders: int = 720):
        self.cost_model = CostModel()
        self.max_candidates = max_candidates
        self.max_join_orders = max_join_orders

    def optimize(self, query):
        logical = build_logical_plan(query)
        candidates = self.enumerate_plans(query)
        if not candidates:
            raise ValueError("The optimizer could not generate a candidate plan")
        best = min(candidates, key=lambda plan: plan.cost)
        return logical, candidates, best

    def _alias_map(self, query):
        refs = ([query.table] if query.table else []) + [join.table for join in query.joins]
        mapping = {}
        for ref in refs:
            table = canonical_table_name(ref.name)
            if table:
                mapping[(ref.alias or ref.name).casefold()] = table
        return mapping

    def _base_scans(self, query, aliases):
        predicates = split_conjuncts(query.where)
        local = {alias: [] for alias in aliases}
        remaining = []
        for predicate in predicates:
            refs = referenced_aliases(predicate, aliases)
            if len(refs) == 1 and next(iter(refs)) in local:
                local[next(iter(refs))].append(predicate)
            else:
                remaining.append(predicate)

        scans = {}
        for ref in ([query.table] if query.table else []) + [join.table for join in query.joins]:
            alias_key = (ref.alias or ref.name).casefold()
            table = aliases.get(alias_key, canonical_table_name(ref.name) or ref.name)
            table_stats = STATS.get(table, {"rows": 1000, "columns": {}})
            input_rows = float(table_stats["rows"])
            selectivity_fraction = 1.0
            for predicate in local.get(alias_key, []):
                selectivity_fraction *= selectivity(predicate, aliases)
            selectivity_fraction = max(0.0, min(1.0, selectivity_fraction))
            output_rows = max(1.0, input_rows * selectivity_fraction)
            predicate = combine_conjuncts(local.get(alias_key, []))

            full_cost = self.cost_model.full_scan(input_rows)
            if predicate is not None:
                full_cost += self.cost_model.predicate(input_rows)
            indexed = self._indexed_predicate_columns(predicate, ref, table)
            index_cost = self.cost_model.index_scan(input_rows, output_rows) if indexed else float("inf")
            if index_cost < full_cost:
                op = "INDEX_SCAN"
                cost = index_cost
                algorithm = "INDEX"
            else:
                op = "TABLE_SCAN"
                cost = full_cost
                algorithm = "FULL_SCAN"
            detail = f"{table}" + (f" AS {ref.alias}" if ref.alias else "")
            if indexed and op == "INDEX_SCAN":
                detail += f"; indexed predicate on {', '.join(indexed)}"
            if predicate is not None:
                detail += f"; pushed filter: {format_expr(predicate)}"
            scans[alias_key] = PlanNode(op, detail=detail, rows=output_rows, cost=cost, algorithm=algorithm)
        return scans, remaining

    def _indexed_predicate_columns(self, predicate, ref, table):
        if predicate is None:
            return []
        available = {col.casefold(): col for indexed_table, col in INDEXES if indexed_table.casefold() == table.casefold()}
        found = []
        # Inspect each conjunct independently so a predicate such as
        # salary > 60000 AND experience >= 5 can still use a relevant index.
        for term in split_conjuncts(predicate):
            supported_shape = (
                isinstance(term, BinaryExpr) and term.operator.upper() in {"=", "<", "<=", ">", ">="}
            ) or isinstance(term, (InExpr, BetweenExpr))
            if not supported_shape:
                continue
            for column in _column_refs(term):
                if column.table and column.table.casefold() != (ref.alias or ref.name).casefold():
                    continue
                if column.name.casefold() in available:
                    found.append(available[column.name.casefold()])
        return sorted(set(found))

    def _join_condition_for_step(self, query, new_alias, joined_aliases, combined_aliases, applied):
        applicable = []
        for index, join in enumerate(query.joins):
            if index in applied:
                continue
            condition_aliases = referenced_aliases(join.condition, self._active_aliases)
            if new_alias not in condition_aliases:
                continue
            if not condition_aliases.issubset(combined_aliases):
                continue
            if not condition_aliases.intersection(joined_aliases):
                # A single-table ON expression is not a join edge, but must still be applied.
                if not (join.join_type == "CROSS" and not condition_aliases):
                    continue
            applicable.append((index, join))
        return applicable

    def _equijoin_selectivity(self, conditions, aliases):
        if not conditions:
            return 1.0
        fractions = []
        for condition in conditions:
            fractions.append(selectivity(condition, aliases))
        result = 1.0
        for fraction in fractions:
            result *= max(0.00001, min(1.0, fraction))
        return result

    def _combine_conditions(self, conditions):
        return " AND ".join(format_expr(condition) for condition in conditions) if conditions else "CROSS JOIN"

    def _make_join(self, left, right, conditions, join_type, aliases):
        left_rows, right_rows = max(1.0, left.rows), max(1.0, right.rows)
        selectivity_fraction = self._equijoin_selectivity(conditions, aliases)
        output_rows = max(1.0, left_rows * right_rows * selectivity_fraction)
        if join_type in {"LEFT", "RIGHT"}:
            output_rows = max(output_rows, left_rows if join_type == "LEFT" else right_rows)

        if join_type in {"LEFT", "RIGHT"}:
            algorithm = "NESTED_LOOP"
            join_cost = self.cost_model.nested_loop_join(left_rows, right_rows)
        else:
            options = [
                ("NESTED_LOOP", self.cost_model.nested_loop_join(left_rows, right_rows)),
                ("HASH_JOIN", self.cost_model.hash_join(left_rows, right_rows)),
                ("MERGE_JOIN", self.cost_model.merge_join(left_rows, right_rows)),
            ]
            algorithm, join_cost = min(options, key=lambda item: item[1])
        op = "JOIN" if join_type == "INNER" else f"{join_type}_JOIN"
        condition_text = self._combine_conditions(conditions)
        detail = f"{join_type} ON {condition_text}"
        cumulative = left.cost + right.cost + join_cost
        return PlanNode(op, [left, right], detail, output_rows, cumulative, algorithm)

    def _estimate_group_rows(self, query, input_rows, aliases):
        if not query.group_by:
            return 1.0  # scalar aggregate such as COUNT(*)
        estimate = 1.0
        for expression in query.group_by:
            if isinstance(expression, ColumnRef):
                table = aliases.get(expression.table.casefold()) if expression.table else None
                if table is None and not expression.table:
                    matches = [name for name, columns in SCHEMA.items()
                               if any(column.casefold() == expression.name.casefold() for column in columns)]
                    if len(matches) == 1:
                        table = matches[0]
                stats = STATS.get(table, {}).get("columns", {}).get(expression.name.casefold(), {}) if table else {}
                estimate *= max(1.0, float(stats.get("distinct", max(1.0, input_rows * 0.25))))
            else:
                estimate *= max(1.0, input_rows * 0.25)
        return max(1.0, min(input_rows, estimate))

    def _build_candidate(self, query, order, scans, remaining_where, aliases):
        current = scans[(order[0].alias or order[0].name).casefold()]
        joined = {(order[0].alias or order[0].name).casefold()}
        applied_join_indexes = set()
        # If outer/cross joins are present, order is fixed and ON semantics are retained.
        fixed_join_order = any(j.join_type != "INNER" for j in query.joins)
        for ref in order[1:]:
            new_alias = (ref.alias or ref.name).casefold()
            combined = joined | {new_alias}
            applicable = self._join_condition_for_step(query, new_alias, joined, combined, applied_join_indexes)
            conditions = [join.condition for _, join in applicable]
            join_type = "INNER"
            if fixed_join_order:
                # The incoming relation follows its original JoinClause; do not commute outer joins.
                match = next((j for j in query.joins if (j.table.alias or j.table.name).casefold() == new_alias), None)
                join_type = match.join_type if match else "INNER"
                if join_type == "CROSS":
                    conditions = []
                elif not conditions and match:
                    conditions = [match.condition]
            for index, _ in applicable:
                applied_join_indexes.add(index)
            right = scans[new_alias]
            current = self._make_join(current, right, conditions, join_type, aliases)
            joined.add(new_alias)

        # Any ON expression that could not be attached during reordering is retained as a filter.
        residual_on = [join.condition for i, join in enumerate(query.joins) if i not in applied_join_indexes and join.join_type == "INNER"]
        if residual_on:
            residual = combine_conjuncts(residual_on)
            fraction = selectivity(residual, aliases)
            rows = max(1.0, current.rows * fraction)
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("FILTER", [current], f"join predicates: {format_expr(residual)}", rows, cost)
        if remaining_where:
            predicate = combine_conjuncts(remaining_where)
            rows = max(1.0, current.rows * selectivity(predicate, aliases))
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("FILTER", [current], format_expr(predicate), rows, cost)

        aggregate_query = bool(query.group_by) or any(contains_aggregate(item.expression) for item in query.columns) or contains_aggregate(query.having)
        if aggregate_query:
            output_rows = self._estimate_group_rows(query, current.rows, aliases)
            output_rows = max(1.0, min(current.rows, output_rows)) if query.group_by else 1.0
            group_by = ", ".join(format_expr(x) for x in query.group_by) or "global aggregate"
            cost = current.cost + self.cost_model.aggregate(current.rows)
            current = PlanNode("HASH_AGGREGATE", [current], group_by, output_rows, cost, "HASH")
        if query.having is not None:
            rows = max(1.0, current.rows * selectivity(query.having, aliases))
            cost = current.cost + self.cost_model.predicate(current.rows)
            current = PlanNode("HAVING_FILTER", [current], format_expr(query.having), rows, cost)
        if query.distinct:
            rows = max(1.0, current.rows * 0.5)
            cost = current.cost + self.cost_model.distinct(current.rows)
            current = PlanNode("DISTINCT", [current], "remove duplicate rows", rows, cost)
        if query.order_by:
            details = ", ".join(f"{format_expr(item.expression)} {item.direction}" for item in query.order_by)
            cost = current.cost + self.cost_model.sort(current.rows)
            current = PlanNode("SORT", [current], details, current.rows, cost)
        if query.limit is not None:
            current = PlanNode("LIMIT", [current], str(query.limit), min(current.rows, float(query.limit)), current.cost)
        projection = ", ".join(format_expr(item.expression) for item in query.columns)
        return PlanNode("PROJECT", [current], projection, current.rows, current.cost + self.cost_model.project(current.rows))

    def enumerate_plans(self, query):
        aliases = self._alias_map(query)
        self._active_aliases = aliases
        tables = ([query.table] if query.table else []) + [join.table for join in query.joins]
        scans, remaining_where = self._base_scans(query, aliases)
        fixed_order = any(join.join_type != "INNER" for join in query.joins)
        if fixed_order or len(tables) <= 1:
            orders = [tables]
        else:
            orders = itertools.permutations(tables)

        results = []
        signatures = set()
        for order_index, order in enumerate(orders):
            if order_index >= self.max_join_orders:
                break
            candidate = self._build_candidate(query, list(order), scans, remaining_where, aliases)
            signature = tuple((ref.alias or ref.name).casefold() for ref in order)
            if signature in signatures:
                continue
            signatures.add(signature)
            results.append(candidate)
        return sorted(results, key=lambda plan: plan.cost)[:self.max_candidates]


def optimize(query):
    return Optimizer().optimize(query)
