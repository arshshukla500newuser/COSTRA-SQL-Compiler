import re
from dataclasses import dataclass


KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT",
    "FULL", "OUTER", "ON", "AND", "OR", "NOT", "GROUP", "BY",
    "HAVING", "ORDER", "ASC", "DESC", "LIMIT", "AS", "DISTINCT",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "NULL", "TRUE", "FALSE"
}


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


TOKEN_SPEC = [
    ("COMMENT", r"--[^\n]*"),
    ("NUMBER", r"\d+(?:\.\d+)?"),
    ("STRING", r"'(?:''|[^'])*'"),
    ("OPERATOR", r"<>|!=|<=|>=|=|<|>|\+|-|\*|/|%"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("SEMICOLON", r";"),
    ("IDENTIFIER", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP", r"[ \t\r\n]+"),
    ("MISMATCH", r"."),
]


MASTER = re.compile(
    "|".join(
        f"(?P<{kind}>{pattern})"
        for kind, pattern in TOKEN_SPEC
    )
)


def tokenize(sql):

    if not isinstance(sql, str):
        raise TypeError("SQL input must be a string")

    tokens = []

    line = 1
    line_start = 0

    for match in MASTER.finditer(sql):

        kind = match.lastgroup
        value = match.group()

        column = match.start() - line_start + 1

        if kind in ("COMMENT", "SKIP"):

            newline_count = value.count("\n")

            if newline_count:
                line += newline_count

                last_newline = value.rfind("\n")

                line_start = (
                    match.start()
                    + last_newline
                    + 1
                )

            continue

        if kind == "IDENTIFIER":

            upper_value = value.upper()

            if upper_value in KEYWORDS:
                kind = upper_value

        if kind == "MISMATCH":

            raise SyntaxError(
                f"Lexical error at line {line}, "
                f"column {column}: "
                f"unexpected character {value!r}"
            )

        tokens.append(
            Token(
                kind=kind,
                value=value,
                line=line,
                column=column
            )
        )

    tokens.append(
        Token(
            kind="EOF",
            value="",
            line=line,
            column=1
        )
    )

    return tokens


if __name__ == "__main__":

    sql = """
    SELECT
        d.name AS department,
        COUNT(e.id) AS employee_count,
        AVG(e.salary) AS average_salary
    FROM Employee e
    JOIN Department d
        ON e.dept_id = d.id
    WHERE e.salary > 60000
    GROUP BY d.name
    HAVING AVG(e.salary) > 65000
    ORDER BY AVG(e.salary) DESC
    LIMIT 5;
    """

    tokens = tokenize(sql)

    for token in tokens:
        print(
            f"{token.kind:<12} "
            f"{token.value!r:<20} "
            f"line={token.line:<3} "
            f"column={token.column}"
        )