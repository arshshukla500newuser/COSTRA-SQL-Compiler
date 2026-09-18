from ast_nodes import (
    ColumnRef,
    BinaryExpr,
    UnaryExpr,
    FunctionCall,
)

from schema import (
    SCHEMA,
    table_exists,
    column_exists,
)


class SemanticAnalyzer:

    def __init__(self, query):

        self.query = query

        self.aliases = {}

        self.errors = []

    def analyze(self):

        self.collect_tables()

        self.check_tables()

        self.check_select()

        self.check_where()

        self.check_group_by()

        self.check_having()

        self.check_order_by()

        if self.errors:

            raise ValueError(
                "Semantic analysis failed:\n"
                + "\n".join(
                    f"  - {error}"
                    for error in self.errors
                )
            )

        return True

    def collect_tables(self):

        table = self.query.from_table

        if table:

            self.add_table(table)

        for join in self.query.joins:

            self.add_table(
                join.table
            )

    def add_table(self, table):

        if not table_exists(table.name):

            self.errors.append(
                f"Unknown table '{table.name}'"
            )

            return

        alias = (
            table.alias
            if table.alias
            else table.name
        )

        if alias in self.aliases:

            self.errors.append(
                f"Duplicate table alias '{alias}'"
            )

            return

        self.aliases[alias] = table.name

    def check_tables(self):

        for join in self.query.joins:

            self.check_expression(
                join.condition
            )

    def check_select(self):

        for item in self.query.select_items:

            self.check_expression(
                item.expression
            )

    def check_where(self):

        if self.query.where:

            self.check_expression(
                self.query.where
            )

    def check_group_by(self):

        for expression in self.query.group_by:

            self.check_expression(
                expression
            )

    def check_having(self):

        if self.query.having:

            self.check_expression(
                self.query.having
            )

    def check_order_by(self):

        for item in self.query.order_by:

            self.check_expression(
                item.expression
            )

    def check_expression(self, expression):

        if isinstance(expression, ColumnRef):

            if expression.name == "*":
                return

            if expression.table:

                if expression.table not in self.aliases:

                    self.errors.append(
                        f"Unknown table or alias "
                        f"'{expression.table}'"
                    )

                    return

                table_name = self.aliases[
                    expression.table
                ]

                if not column_exists(
                    table_name,
                    expression.name
                ):

                    self.errors.append(
                        f"Unknown column "
                        f"'{expression.table}."
                        f"{expression.name}'"
                    )

                return

            matches = []

            for table_name in self.aliases.values():

                if column_exists(
                    table_name,
                    expression.name
                ):
                    matches.append(
                        table_name
                    )

            if len(matches) == 0:

                self.errors.append(
                    f"Unknown column "
                    f"'{expression.name}'"
                )

            elif len(matches) > 1:

                self.errors.append(
                    f"Ambiguous column "
                    f"'{expression.name}'"
                )

            return

        if isinstance(expression, BinaryExpr):

            self.check_expression(
                expression.left
            )

            self.check_expression(
                expression.right
            )

            return

        if isinstance(expression, UnaryExpr):

            self.check_expression(
                expression.operand
            )

            return

        if isinstance(expression, FunctionCall):

            for argument in expression.arguments:

                self.check_expression(
                    argument
                )


def analyze(query):

    analyzer = SemanticAnalyzer(query)

    analyzer.analyze()

    return analyzer