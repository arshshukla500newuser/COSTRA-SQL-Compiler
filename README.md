# COSTRA — Cost-Based SQL Compiler & Query Optimizer

COSTRA is an educational SQL compiler and query optimizer implemented
in Python. It processes a supported subset of SELECT queries through
lexical analysis, recursive-descent parsing, AST construction,
semantic validation, relational intermediate representation,
cardinality estimation and candidate-plan cost comparison.

Validated SQL is executed separately through SQLite. COSTRA's
estimated plan is not injected into SQLite's query planner.

## Requirements

Python 3.9 or newer. See requirements.txt for dependencies.

## Run

Interactive menu:
    python3 main.py

Complete demonstration:
    python3 main.py --demo

Semantic-error demonstration:
    python3 main.py --error-demo

Optimizer cost demonstration:
    python3 main.py --cost-demo

Automated tests:
    python3 -m unittest -v

Benchmark:
    python3 benchmark.py

## Core modules

- main.py — command-line interface
- compiler.py — pipeline orchestration
- lexer.py — SQL tokenization
- parser.py — recursive-descent parser
- ast_nodes.py — AST structures
- semantic.py — semantic validation
- schema.py — schema and optimizer metadata
- statistics.py — selectivity estimation
- ir.py — relational intermediate representation
- optimizer.py — candidate-plan cost comparison
- executor.py — SQLite execution and query-plan output
- test_costra.py — regression tests
- benchmark.py — local benchmark runner

## Scope

COSTRA supports a subset of SQL, not the full SQL standard.
Its optimizer uses synthetic statistics and relative model costs.
SQLite independently selects the plan used for actual execution.
