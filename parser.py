"""Recursive-descent parser for COSTRA's documented SELECT grammar."""
from __future__ import annotations
from typing import Optional
from ast_nodes import (
    BetweenExpr, BinaryExpr, ColumnRef, FunctionCall, InExpr, IsNullExpr, Literal,
    JoinClause, OrderItem, SelectItem, SelectQuery, TableRef, UnaryExpr,
)
from lexer import Token, tokenize

AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def current(self) -> Token:
        return self.tokens[self.index]

    def match(self, *kinds: str) -> Optional[Token]:
        if self.current().kind in kinds:
            token = self.current()
            self.index += 1
            return token
        return None

    def expect(self, kind: str) -> Token:
        token = self.current()
        if token.kind != kind:
            raise SyntaxError(
                f"Syntax error at line {token.line}, column {token.column}: "
                f"expected {kind}, found {token.kind} ({token.value!r})"
            )
        self.index += 1
        return token

    def identifier(self) -> str:
        return self.expect("IDENTIFIER").value

    def parse(self) -> SelectQuery:
        query = self.select_statement()
        self.match("SEMICOLON")
        self.expect("EOF")
        return query

    def select_statement(self) -> SelectQuery:
        self.expect("SELECT")
        distinct = bool(self.match("DISTINCT"))
        columns = self.select_list()
        self.expect("FROM")
        table = self.table_ref()
        joins = []
        while self.current().kind in ("JOIN", "INNER", "LEFT", "RIGHT", "CROSS"):
            joins.append(self.join_clause())
        where = self.expression() if self.match("WHERE") else None
        group_by = []
        if self.match("GROUP"):
            self.expect("BY")
            group_by = self.expression_list()
        having = self.expression() if self.match("HAVING") else None
        order_by = []
        if self.match("ORDER"):
            self.expect("BY")
            order_by = self.order_list()
        limit = None
        if self.match("LIMIT"):
            token = self.expect("NUMBER")
            # LIMIT is deliberately restricted to a non-negative integer.
            if not token.value.isdigit():
                raise SyntaxError(
                    f"LIMIT must be a non-negative integer at line {token.line}, column {token.column}"
                )
            limit = int(token.value)
        return SelectQuery(columns, table, joins, where, group_by, having, order_by, limit, distinct)

    def select_list(self) -> list[SelectItem]:
        items = []
        while True:
            expression = self.expression()
            alias = None
            if self.match("AS"):
                alias = self.identifier()
            elif self.current().kind == "IDENTIFIER":
                alias = self.identifier()
            items.append(SelectItem(expression, alias))
            if not self.match("COMMA"):
                return items

    def table_ref(self) -> TableRef:
        name = self.identifier()
        alias = None
        if self.match("AS"):
            alias = self.identifier()
        elif self.current().kind == "IDENTIFIER":
            alias = self.identifier()
        return TableRef(name, alias)

    def join_clause(self):
        join_type = "INNER"
        if self.match("INNER"):
            self.expect("JOIN")
        elif self.match("LEFT"):
            join_type = "LEFT"
            self.match("OUTER")
            self.expect("JOIN")
        elif self.match("RIGHT"):
            join_type = "RIGHT"
            self.match("OUTER")
            self.expect("JOIN")
        elif self.match("CROSS"):
            join_type = "CROSS"
            self.expect("JOIN")
            table = self.table_ref()
            return JoinClause(table, Literal(True), join_type)
        else:
            self.expect("JOIN")
        table = self.table_ref()
        self.expect("ON")
        return JoinClause(table, self.expression(), join_type)

    def expression_list(self):
        values = [self.expression()]
        while self.match("COMMA"):
            values.append(self.expression())
        return values

    def order_list(self):
        items = []
        while True:
            expr = self.expression()
            direction = "DESC" if self.match("DESC") else "ASC"
            if direction == "ASC":
                self.match("ASC")
            items.append(OrderItem(expr, direction))
            if not self.match("COMMA"):
                return items

    # Precedence, low to high: OR, AND, NOT, comparison, +/-, */%, unary, primary.
    def expression(self):
        return self.or_expression()

    def or_expression(self):
        node = self.and_expression()
        while self.match("OR"):
            node = BinaryExpr(node, "OR", self.and_expression())
        return node

    def and_expression(self):
        node = self.not_expression()
        while self.match("AND"):
            node = BinaryExpr(node, "AND", self.not_expression())
        return node

    def not_expression(self):
        if self.match("NOT"):
            return UnaryExpr("NOT", self.not_expression())
        return self.comparison()

    def comparison(self):
        node = self.additive()
        if self.current().kind == "OPERATOR" and self.current().value in {
            "=", "!=", "<>", "<", "<=", ">", ">="
        }:
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, "<>" if op == "!=" else op, self.additive())
            return node
        if self.match("IS"):
            negated = bool(self.match("NOT"))
            self.expect("NULL")
            return IsNullExpr(node, negated)
        negated = False
        if self.current().kind == "NOT" and self.index + 1 < len(self.tokens) and self.tokens[self.index + 1].kind in ("IN", "BETWEEN", "LIKE"):
            self.index += 1
            negated = True
        if self.match("IN"):
            self.expect("LPAREN")
            values = []
            if self.current().kind != "RPAREN":
                values = self.expression_list()
            self.expect("RPAREN")
            if not values:
                raise SyntaxError("IN lists must contain at least one value")
            return InExpr(node, tuple(values), negated)
        if self.match("BETWEEN"):
            lower = self.additive()
            self.expect("AND")
            upper = self.additive()
            return BetweenExpr(node, lower, upper, negated)
        if self.match("LIKE"):
            right = self.additive()
            like = BinaryExpr(node, "LIKE", right)
            return UnaryExpr("NOT", like) if negated else like
        if negated:
            token = self.current()
            raise SyntaxError(f"Expected IN, BETWEEN, or LIKE after NOT at line {token.line}, column {token.column}")
        return node

    def additive(self):
        node = self.multiplicative()
        while self.current().kind == "OPERATOR" and self.current().value in ("+", "-"):
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, op, self.multiplicative())
        return node

    def multiplicative(self):
        node = self.unary()
        while self.current().kind == "OPERATOR" and self.current().value in ("*", "/", "%"):
            op = self.current().value
            self.index += 1
            node = BinaryExpr(node, op, self.unary())
        return node

    def unary(self):
        if self.current().kind == "OPERATOR" and self.current().value in ("+", "-"):
            op = self.current().value
            self.index += 1
            return UnaryExpr(op, self.unary())
        return self.primary()

    def primary(self):
        token = self.current()
        if self.match("LPAREN"):
            expr = self.expression()
            self.expect("RPAREN")
            return expr
        if token.kind == "NUMBER":
            self.index += 1
            try:
                value = float(token.value) if any(c in token.value.lower() for c in (".", "e")) else int(token.value)
            except ValueError as exc:
                raise SyntaxError(f"Invalid numeric literal {token.value!r}") from exc
            return Literal(value)
        if token.kind == "STRING":
            self.index += 1
            return Literal(token.value[1:-1].replace("''", "'"))
        if self.match("NULL"):
            return Literal(None)
        if self.match("TRUE"):
            return Literal(True)
        if self.match("FALSE"):
            return Literal(False)
        if token.kind == "OPERATOR" and token.value == "*":
            self.index += 1
            return ColumnRef("*")
        if token.kind == "IDENTIFIER" or token.kind in AGGREGATES:
            self.index += 1
            name = token.value
            if self.match("LPAREN"):
                distinct = bool(self.match("DISTINCT"))
                if self.current().kind == "OPERATOR" and self.current().value == "*":
                    self.index += 1
                    argument = "*"
                else:
                    argument = self.expression()
                self.expect("RPAREN")
                return FunctionCall(name.upper(), argument, distinct)
            if self.match("DOT"):
                if self.current().kind == "OPERATOR" and self.current().value == "*":
                    self.index += 1
                    return ColumnRef("*", name)
                return ColumnRef(self.identifier(), name)
            # Bare names that are aggregate keywords are not columns unless called as functions.
            if token.kind in AGGREGATES:
                raise SyntaxError(f"Expected '(' after function name {name!r} at line {token.line}, column {token.column}")
            return ColumnRef(name)
        raise SyntaxError(
            f"Syntax error at line {token.line}, column {token.column}: "
            f"unexpected {token.kind} ({token.value!r})"
        )


def parse_tokens(tokens: list[Token]) -> SelectQuery:
    return Parser(tokens).parse()


def parse_sql(sql: str) -> SelectQuery:
    return parse_tokens(tokenize(sql))
