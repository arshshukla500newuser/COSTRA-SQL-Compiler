from itertools import permutations

from ir import PlanNode
from statistics import (
    table_rows,
    predicate_selectivity,
    get_column_stats
)
from schema import (
    has_index,
    get_row_count
)


class CostModel:

    def __init__(self):
        # Cost weights
        self.io_weight = 1.0
        self.cpu_weight = 0.5
        self.memory_weight = 0.2
        self.network_weight = 0.1

    # ---------------------------------------------------------
    # TABLE SCAN COST
    # ---------------------------------------------------------

    def sequential_scan_cost(self, rows):
        io_cost = rows * self.io_weight
        cpu_cost = rows * self.cpu_weight

        return io_cost + cpu_cost

    def index_scan_cost(self, rows):
        # Educational approximation of index access.
        io_cost = max(1.0, rows * 0.25)
        cpu_cost = rows * 0.15

        return io_cost + cpu_cost

    # ---------------------------------------------------------
    # FILTER COST
    # ---------------------------------------------------------

    def filter_cost(self, input_rows, output_rows):
        cpu_cost = input_rows * self.cpu_weight

        memory_cost = output_rows * self.memory_weight

        return cpu_cost + memory_cost

    # ---------------------------------------------------------
    # JOIN COSTS
    # ---------------------------------------------------------

    def nested_loop_cost(self, left_rows, right_rows):
        cpu = left_rows * right_rows * self.cpu_weight

        io = (left_rows + right_rows) * self.io_weight

        return cpu + io

    def hash_join_cost(self, left_rows, right_rows):
        cpu = (left_rows + right_rows) * self.cpu_weight

        memory = min(left_rows, right_rows) * self.memory_weight

        return cpu + memory

    def merge_join_cost(self, left_rows, right_rows):
        sort_left = left_rows * 0.6
        sort_right = right_rows * 0.6

        merge = (left_rows + right_rows) * 0.3

        return sort_left + sort_right + merge

    # ---------------------------------------------------------
    # SORT
    # ---------------------------------------------------------

    def sort_cost(self, rows):
        if rows <= 1:
            return 0.0

        return rows * 0.8

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------

    def aggregate_cost(self, rows):
        return rows * 0.6


class Optimizer:

    def __init__(self, query=None):

        self.query = query
        self.cost_model = CostModel()

        self.table_aliases = {}
        self.table_rows = {}

    # =========================================================
    # PUBLIC OPTIMIZATION FUNCTION
    # =========================================================

    def optimize(self, query=None):

        if query is not None:
            self.query = query

        if self.query is None:
            raise ValueError("No SQL query supplied to optimizer.")

        self.build_metadata()

        plans = self.generate_candidate_plans()

        plans.sort(
            key=lambda plan: plan.estimated_cost
        )

        return plans

    # =========================================================
    # METADATA
    # =========================================================

    def build_metadata(self):

        query = self.query

        self.table_aliases = {}

        base_table = query.from_table

        base_alias = (
            base_table.alias
            if base_table.alias
            else base_table.name
        )

        self.table_aliases[base_alias] = base_table.name

        self.table_rows[base_alias] = table_rows(
            base_table.name
        )

        for join in query.joins:

            table = join.table

            alias = (
                table.alias
                if table.alias
                else table.name
            )

            self.table_aliases[alias] = table.name

            self.table_rows[alias] = table_rows(
                table.name
            )

    # =========================================================
    # SCAN SELECTION
    # =========================================================

    def choose_scan(self, table_name, alias):

        rows = table_rows(table_name)

        sequential_cost = self.cost_model.sequential_scan_cost(
            rows
        )

        sequential = PlanNode(
            operator="SEQ_SCAN",
            properties={
                "table": table_name,
                "alias": alias
            },
            estimated_rows=float(rows),
            estimated_cost=sequential_cost
        )

        # -----------------------------------------------------
        # INDEX ALTERNATIVE
        # -----------------------------------------------------

        index_available = False

        try:
            columns = [
                "id",
                "dept_id",
                "employee_id",
                "project_id"
            ]

            for column in columns:
                if has_index(table_name, column):
                    index_available = True
                    break

        except Exception:
            index_available = False

        candidates = [sequential]

        if index_available:

            index_cost = self.cost_model.index_scan_cost(
                rows
            )

            indexed = PlanNode(
                operator="INDEX_SCAN",
                properties={
                    "table": table_name,
                    "alias": alias
                },
                estimated_rows=float(rows),
                estimated_cost=index_cost
            )

            candidates.append(indexed)

        candidates.sort(
            key=lambda plan: plan.estimated_cost
        )

        return candidates

    # =========================================================
    # SELECTIVITY
    # =========================================================

    def estimate_filter_selectivity(self, predicate):

        try:
            value = predicate_selectivity(predicate)

            if value is None:
                return 0.5

            return max(
                0.001,
                min(1.0, float(value))
            )

        except Exception:
            return 0.5

    # =========================================================
    # JOIN ALGORITHM
    # =========================================================

    def choose_join_algorithm(
        self,
        left_rows,
        right_rows
    ):

        nested_cost = self.cost_model.nested_loop_cost(
            left_rows,
            right_rows
        )

        hash_cost = self.cost_model.hash_join_cost(
            left_rows,
            right_rows
        )

        merge_cost = self.cost_model.merge_join_cost(
            left_rows,
            right_rows
        )

        choices = [
            (
                "NESTED_LOOP_JOIN",
                nested_cost
            ),
            (
                "HASH_JOIN",
                hash_cost
            ),
            (
                "MERGE_JOIN",
                merge_cost
            )
        ]

        choices.sort(
            key=lambda x: x[1]
        )

        return choices[0]

    # =========================================================
    # JOIN TREE
    # =========================================================

    def build_join_plan(self, order):

        query = self.query

        # -----------------------------------------------------
        # BASE TABLE
        # -----------------------------------------------------

        base_alias = (
            query.from_table.alias
            if query.from_table.alias
            else query.from_table.name
        )

        base_table = query.from_table.name

        base_rows = table_rows(base_table)

        base_cost = self.cost_model.sequential_scan_cost(
            base_rows
        )

        current = PlanNode(
            operator="TABLE_SCAN",
            properties={
                "table": base_table,
                "alias": base_alias
            },
            estimated_rows=float(base_rows),
            estimated_cost=base_cost
        )

        current_rows = float(base_rows)

        # -----------------------------------------------------
        # JOIN TABLES
        # -----------------------------------------------------

        join_map = {}

        for join in query.joins:

            alias = (
                join.table.alias
                if join.table.alias
                else join.table.name
            )

            join_map[alias] = join

        for alias in order:

            if alias == base_alias:
                continue

            if alias not in join_map:
                continue

            join = join_map[alias]

            table_name = join.table.name

            right_rows = float(
                table_rows(table_name)
            )

            algorithm, join_cost = (
                self.choose_join_algorithm(
                    current_rows,
                    right_rows
                )
            )

            # -------------------------------------------------
            # JOIN SELECTIVITY
            # -------------------------------------------------

            join_selectivity = 0.1

            estimated_join_rows = max(
                1.0,
                current_rows *
                right_rows *
                join_selectivity
            )

            node = PlanNode(
                operator=algorithm,
                children=[current],
                properties={
                    "table": table_name,
                    "alias": alias,
                    "condition": str(join.condition),
                    "join_type": join.join_type
                },
                estimated_rows=estimated_join_rows,
                estimated_cost=(
                    current.estimated_cost
                    + join_cost
                )
            )

            current = node

            current_rows = estimated_join_rows

        # -----------------------------------------------------
        # WHERE
        # -----------------------------------------------------

        if query.where:

            selectivity = (
                self.estimate_filter_selectivity(
                    query.where
                )
            )

            output_rows = max(
                1.0,
                current_rows * selectivity
            )

            filter_cost = self.cost_model.filter_cost(
                current_rows,
                output_rows
            )

            current = PlanNode(
                operator="FILTER",
                children=[current],
                properties={
                    "predicate": str(query.where)
                },
                estimated_rows=output_rows,
                estimated_cost=(
                    current.estimated_cost
                    + filter_cost
                )
            )

            current_rows = output_rows

        # -----------------------------------------------------
        # GROUP BY / AGGREGATION
        # -----------------------------------------------------

        if query.group_by:

            output_rows = max(
                1.0,
                min(
                    current_rows,
                    current_rows * 0.2
                )
            )

            aggregate_cost = (
                self.cost_model.aggregate_cost(
                    current_rows
                )
            )

            current = PlanNode(
                operator="AGGREGATE",
                children=[current],
                properties={
                    "group_by": [
                        str(x)
                        for x in query.group_by
                    ]
                },
                estimated_rows=output_rows,
                estimated_cost=(
                    current.estimated_cost
                    + aggregate_cost
                )
            )

            current_rows = output_rows

        # -----------------------------------------------------
        # HAVING
        # -----------------------------------------------------

        if query.having:

            selectivity = (
                self.estimate_filter_selectivity(
                    query.having
                )
            )

            output_rows = max(
                1.0,
                current_rows * selectivity
            )

            filter_cost = self.cost_model.filter_cost(
                current_rows,
                output_rows
            )

            current = PlanNode(
                operator="HAVING",
                children=[current],
                properties={
                    "predicate": str(query.having)
                },
                estimated_rows=output_rows,
                estimated_cost=(
                    current.estimated_cost
                    + filter_cost
                )
            )

            current_rows = output_rows

        # -----------------------------------------------------
        # ORDER BY
        # -----------------------------------------------------

        if query.order_by:

            sort_cost = self.cost_model.sort_cost(
                current_rows
            )

            current = PlanNode(
                operator="SORT",
                children=[current],
                properties={
                    "order_by": [
                        str(x)
                        for x in query.order_by
                    ]
                },
                estimated_rows=current_rows,
                estimated_cost=(
                    current.estimated_cost
                    + sort_cost
                )
            )

        # -----------------------------------------------------
        # LIMIT
        # -----------------------------------------------------

        if query.limit is not None:

            output_rows = min(
                current_rows,
                float(query.limit)
            )

            current = PlanNode(
                operator="LIMIT",
                children=[current],
                properties={
                    "limit": query.limit
                },
                estimated_rows=output_rows,
                estimated_cost=current.estimated_cost
            )

            current_rows = output_rows

        # -----------------------------------------------------
        # PROJECTION
        # -----------------------------------------------------

        current = PlanNode(
            operator="PROJECT",
            children=[current],
            properties={
                "columns": len(
                    query.select_items
                )
            },
            estimated_rows=current_rows,
            estimated_cost=current.estimated_cost
        )

        return current

    # =========================================================
    # PLAN GENERATION
    # =========================================================

    def generate_candidate_plans(self):

        query = self.query

        aliases = []

        base_alias = (
            query.from_table.alias
            if query.from_table.alias
            else query.from_table.name
        )

        aliases.append(base_alias)

        for join in query.joins:

            alias = (
                join.table.alias
                if join.table.alias
                else join.table.name
            )

            aliases.append(alias)

        # -----------------------------------------------------
        # Generate different join orders
        # -----------------------------------------------------

        unique_orders = list(
            permutations(aliases)
        )

        plans = []

        for order in unique_orders:

            try:

                plan = self.build_join_plan(
                    order
                )

                plans.append(plan)

            except Exception:
                continue

        # -----------------------------------------------------
        # Remove duplicate costs
        # -----------------------------------------------------

        unique_plans = []

        seen = set()

        for plan in plans:

            key = round(
                plan.estimated_cost,
                6
            )

            if key not in seen:

                seen.add(key)
                unique_plans.append(plan)

        unique_plans.sort(
            key=lambda p: p.estimated_cost
        )

        return unique_plans