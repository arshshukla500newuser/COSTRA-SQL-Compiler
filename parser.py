from lexer import tokenize
from ast_nodes import (
    ColumnRef,
    Literal,
    BinaryExpr,
    UnaryExpr,
    FunctionCall,
    SelectItem,
    TableRef,
    JoinClause,
    OrderItem,
    SelectQuery,
)


class Parser:

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    def current(self):
        return self.tokens[self.position]

    def peek(self, offset=1):

        index = self.position + offset

        if index >= len(self.tokens):
            return self.tokens[-1]

        return self.tokens[index]

    def advance(self):
        token = self.current()

        if not self.at_end():
            self.position += 1

        return token

    def at_end(self):
        return self.current().kind == "EOF"

    def check_kind(self, kind):
        return self.current().kind == kind

    def check_value(self, value):
        return (
            self.current().value.upper()
            == value.upper()
        )

    def match_kind(self, *kinds):

        if self.current().kind in kinds:
            return self.advance()

        return None

    def match_value(self, *values):

        current = self.current()

        for value in values:

            if current.value.upper() == value.upper():
                return self.advance()

        return None

    def expect_kind(self, kind):

        if self.current().kind != kind:

            raise SyntaxError(
                f"Expected {kind}, "
                f"found '{self.current().value}' "
                f"at position {self.position}"
            )

        return self.advance()

    def expect_value(self, value):

        if not self.check_value(value):

            raise SyntaxError(
                f"Expected '{value}', "
                f"found '{self.current().value}' "
                f"at position {self.position}"
            )

        return self.advance()

    def parse(self):

        query = self.parse_select()

        self.match_kind("SEMICOLON")

        if not self.at_end():

            raise SyntaxError(
                f"Unexpected token "
                f"'{self.current().value}'"
            )

        return query

    # ================================================================
    # SELECT
    # ================================================================

    def parse_select(self):

        self.expect_value("SELECT")

        distinct = False

        if self.match_value("DISTINCT"):
            distinct = True

        select_items = self.parse_select_list()

        self.expect_value("FROM")

        from_table = self.parse_table()

        joins = []

        while self.is_join_start():
            joins.append(
                self.parse_join()
            )

        where = None

        if self.match_value("WHERE"):
            where = self.parse_expression()

        group_by = []

        if self.match_value("GROUP"):

            self.expect_value("BY")

            group_by = self.parse_expression_list()

        having = None

        if self.match_value("HAVING"):
            having = self.parse_expression()

        order_by = []

        if self.match_value("ORDER"):

            self.expect_value("BY")

            order_by = self.parse_order_list()

        limit = None

        if self.match_value("LIMIT"):

            token = self.expect_kind("NUMBER")

            limit = int(float(token.value))

        return SelectQuery(
            select_items=select_items,
            from_table=from_table,
            joins=joins,
            where=where,
            group_by=group_by,
            having=having,
            order_by=order_by,
            limit=limit,
            distinct=distinct,
        )

    # ================================================================
    # SELECT LIST
    # ================================================================

    def parse_select_list(self):

        items = []

        if self.check_kind("OPERATOR") and self.current().value == "*":

            self.advance()

            items.append(
                SelectItem(
                    expression=ColumnRef("*")
                )
            )

            return items

        while True:

            expression = self.parse_expression()

            alias = None

            if self.match_value("AS"):

                alias = self.parse_identifier()

            elif self.current().kind == "IDENTIFIER":

                alias = self.parse_identifier()

            items.append(
                SelectItem(
                    expression=expression,
                    alias=alias
                )
            )

            if not self.match_kind("COMMA"):
                break

        return items

    # ================================================================
    # TABLE
    # ================================================================

    def parse_table(self):

        name = self.parse_identifier()

        alias = None

        if self.match_value("AS"):

            alias = self.parse_identifier()

        elif self.current().kind == "IDENTIFIER":

            alias = self.parse_identifier()

        return TableRef(
            name=name,
            alias=alias
        )

    # ================================================================
    # JOIN
    # ================================================================

    def is_join_start(self):

        return self.current().value.upper() in {
            "JOIN",
            "INNER",
            "LEFT",
            "RIGHT",
            "FULL"
        }

    def parse_join(self):

        join_type = "INNER"

        if self.match_value("INNER"):

            join_type = "INNER"
            self.expect_value("JOIN")

        elif self.match_value("LEFT"):

            join_type = "LEFT"
            self.match_value("OUTER")
            self.expect_value("JOIN")

        elif self.match_value("RIGHT"):

            join_type = "RIGHT"
            self.match_value("OUTER")
            self.expect_value("JOIN")

        elif self.match_value("FULL"):

            join_type = "FULL"
            self.match_value("OUTER")
            self.expect_value("JOIN")

        else:

            self.expect_value("JOIN")

        table = self.parse_table()

        self.expect_value("ON")

        condition = self.parse_expression()

        return JoinClause(
            table=table,
            condition=condition,
            join_type=join_type
        )

    # ================================================================
    # EXPRESSION LIST
    # ================================================================

    def parse_expression_list(self):

        expressions = [
            self.parse_expression()
        ]

        while self.match_kind("COMMA"):

            expressions.append(
                self.parse_expression()
            )

        return expressions

    # ================================================================
    # ORDER BY
    # ================================================================

    def parse_order_list(self):

        items = []

        while True:

            expression = self.parse_expression()

            direction = "ASC"

            if self.match_value("ASC"):
                direction = "ASC"

            elif self.match_value("DESC"):
                direction = "DESC"

            items.append(
                OrderItem(
                    expression=expression,
                    direction=direction
                )
            )

            if not self.match_kind("COMMA"):
                break

        return items

    # ================================================================
    # EXPRESSIONS
    # ================================================================

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):

        expression = self.parse_and()

        while self.match_value("OR"):

            right = self.parse_and()

            expression = BinaryExpr(
                left=expression,
                operator="OR",
                right=right
            )

        return expression

    def parse_and(self):

        expression = self.parse_not()

        while self.match_value("AND"):

            right = self.parse_not()

            expression = BinaryExpr(
                left=expression,
                operator="AND",
                right=right
            )

        return expression

    def parse_not(self):

        if self.match_value("NOT"):

            return UnaryExpr(
                operator="NOT",
                operand=self.parse_not()
            )

        return self.parse_comparison()

    def parse_comparison(self):

        expression = self.parse_additive()

        if self.current().kind == "OPERATOR":

            operator = self.current().value

            if operator in {
                "=", "!=", "<>", "<",
                "<=", ">", ">="
            }:

                self.advance()

                right = self.parse_additive()

                return BinaryExpr(
                    left=expression,
                    operator=operator,
                    right=right
                )

        return expression

    def parse_additive(self):

        expression = self.parse_multiplicative()

        while (
            self.current().kind == "OPERATOR"
            and self.current().value in {"+", "-"}
        ):

            operator = self.advance().value

            right = self.parse_multiplicative()

            expression = BinaryExpr(
                left=expression,
                operator=operator,
                right=right
            )

        return expression

    def parse_multiplicative(self):

        expression = self.parse_unary()

        while (
            self.current().kind == "OPERATOR"
            and self.current().value in {"*", "/", "%"}
        ):

            operator = self.advance().value

            right = self.parse_unary()

            expression = BinaryExpr(
                left=expression,
                operator=operator,
                right=right
            )

        return expression

    def parse_unary(self):

        if (
            self.current().kind == "OPERATOR"
            and self.current().value in {"+", "-"}
        ):

            operator = self.advance().value

            return UnaryExpr(
                operator=operator,
                operand=self.parse_unary()
            )

        return self.parse_primary()

    # ================================================================
    # PRIMARY
    # ================================================================

    def parse_primary(self):

        token = self.current()

        if self.match_kind("LPAREN"):

            expression = self.parse_expression()

            self.expect_kind("RPAREN")

            return expression

        if token.kind == "NUMBER":

            self.advance()

            if "." in token.value:
                value = float(token.value)
            else:
                value = int(token.value)

            return Literal(value)

        if token.kind == "STRING":

            self.advance()

            value = token.value[1:-1]

            value = value.replace(
                "''",
                "'"
            )

            return Literal(value)

        if token.kind == "NULL":

            self.advance()
            return Literal(None)

        if token.kind == "TRUE":

            self.advance()
            return Literal(True)

        if token.kind == "FALSE":

            self.advance()
            return Literal(False)

        if (
            token.kind == "OPERATOR"
            and token.value == "*"
        ):

            self.advance()

            return ColumnRef("*")

        if token.kind in {
            "IDENTIFIER",
            "COUNT",
            "SUM",
            "AVG",
            "MIN",
            "MAX"
        }:

            return self.parse_identifier_expression()

        raise SyntaxError(
            f"Unexpected token "
            f"'{token.value}' "
            f"at position {self.position}"
        )

    # ================================================================
    # IDENTIFIER / FUNCTION
    # ================================================================

    def parse_identifier_expression(self):

        first = self.advance().value

        # Function call
        if self.match_kind("LPAREN"):

            arguments = []

            if (
                self.current().kind == "OPERATOR"
                and self.current().value == "*"
            ):

                self.advance()

                arguments.append(
                    ColumnRef("*")
                )

            elif not self.check_kind("RPAREN"):

                arguments = (
                    self.parse_expression_list()
                )

            self.expect_kind("RPAREN")

            return FunctionCall(
                name=first,
                arguments=arguments
            )

        # table.column
        if self.match_kind("DOT"):

            second = self.parse_identifier()

            return ColumnRef(
                name=second,
                table=first
            )

        # column
        return ColumnRef(
            name=first
        )

    # ================================================================
    # IDENTIFIER
    # ================================================================

    def parse_identifier(self):

        token = self.current()

        if token.kind != "IDENTIFIER":

            raise SyntaxError(
                f"Expected identifier, "
                f"found '{token.value}' "
                f"at position {self.position}"
            )

        self.advance()

        return token.value


# ====================================================================
# PUBLIC FUNCTION
# ====================================================================

def parse_sql(sql):

    tokens = tokenize(sql)

    parser = Parser(tokens)

    return parser.parse()


parse = parse_sql