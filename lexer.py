"""Lexer for the SQL subset supported by COSTRA."""
from __future__ import annotations
from dataclasses import dataclass
import re

KEYWORDS = {
    "SELECT", "DISTINCT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
    "ON", "AND", "OR", "NOT", "GROUP", "BY", "HAVING", "ORDER", "ASC", "DESC", "LIMIT",
    "AS", "COUNT", "SUM", "AVG", "MIN", "MAX", "IS", "NULL", "LIKE", "IN", "BETWEEN",
    "TRUE", "FALSE", "CROSS",
}

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


TOKEN_SPEC = [
    ("COMMENT", r"--[^\n]*"),
    ("NUMBER", r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"),
    ("STRING", r"'(?:''|[^'])*'"),
    ("OPERATOR", r"!=|<>|<=|>=|=|<|>|\+|-|\*|/|%"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SEMICOLON", r";"),
    ("IDENTIFIER", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP", r"[ \t\r\n]+"),
    ("MISMATCH", r"."),
]
MASTER = re.compile("|".join(f"(?P<{kind}>{pattern})" for kind, pattern in TOKEN_SPEC))


def tokenize(sql: str) -> list[Token]:
    if not isinstance(sql, str):
        raise TypeError("SQL input must be a string")
    tokens: list[Token] = []
    line = 1
    line_start = 0
    for match in MASTER.finditer(sql):
        kind = match.lastgroup or "MISMATCH"
        value = match.group()
        column = match.start() - line_start + 1
        if kind in ("COMMENT", "SKIP"):
            newline_count = value.count("\n")
            if newline_count:
                line += newline_count
                line_start = match.start() + value.rfind("\n") + 1
            continue
        if kind == "IDENTIFIER" and value.upper() in KEYWORDS:
            kind = value.upper()
        if kind == "MISMATCH":
            raise ValueError(
                f"Lexical error at line {line}, column {column}: unexpected character {value!r}"
            )
        tokens.append(Token(kind, value, line, column))
    tokens.append(Token("EOF", "", line, len(sql.rsplit("\n", 1)[-1]) + 1))
    return tokens
