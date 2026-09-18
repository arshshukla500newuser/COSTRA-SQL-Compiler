# COSTRA

## Cost-Based SQL Compiler and Optimizer

COSTRA is a Compiler Design project that implements a miniature SQL compiler and cost-based query optimizer.

The system converts SQL into tokens, parses the tokens into an Abstract Syntax Tree, performs semantic analysis, creates a logical query plan, generates alternative physical execution plans, estimates their costs, selects the lowest-cost plan, and finally executes the SQL query.

---

# Architecture

SQL Query

        ↓

Lexical Analyzer

        ↓

Token Stream

        ↓

Parser

        ↓

Abstract Syntax Tree

        ↓

Semantic Analyzer

        ↓

Symbol Table

        ↓

Logical Query Plan

        ↓

Statistics / Cardinality Estimation

        ↓

Physical Plan Enumeration

        ↓

Cost Model

        ↓

Plan Comparison

        ↓

Lowest-Cost Physical Plan

        ↓

Execution Engine

        ↓

Result + Performance Metrics


---

# Phase 2 Modules

## 1. lexer.py

Responsible for lexical analysis.

Converts SQL characters into tokens.

Examples:

SELECT

FROM

WHERE

IDENTIFIER

NUMBER

OPERATOR

JOIN

GROUP BY

ORDER BY


---

## 2. parser.py

Performs syntax analysis.

Creates the Abstract Syntax Tree.

Supported SQL:

SELECT

DISTINCT

FROM

JOIN

INNER JOIN

LEFT JOIN

RIGHT JOIN

WHERE

AND

OR

NOT

GROUP BY

HAVING

ORDER BY

ASC

DESC

LIMIT

COUNT

SUM

AVG

MIN

MAX


---

## 3. ast_nodes.py

Contains AST data structures.

Important nodes:

ColumnRef

Literal

BinaryExpr

UnaryExpr

FunctionCall

SelectItem

TableRef

JoinClause

OrderItem

SelectQuery


---

## 4. semantic.py

Performs semantic analysis.

Checks:

Unknown tables

Unknown columns

Unknown aliases

Duplicate aliases

Ambiguous columns


---

## 5. schema.py

Contains database schema information.

Tables:

Employee

Department

Project

Assignment


Also contains:

Table cardinalities

Column statistics

Distinct-value counts

Minimum values

Maximum values

Index information


---

## 6. statistics.py

Responsible for cardinality and selectivity estimation.

Examples:

Equality predicates

Range predicates

AND predicates

OR predicates

NOT predicates


---

## 7. ir.py

Creates the logical intermediate representation.

Operators include:

SCAN

JOIN

FILTER

AGGREGATE

SORT

LIMIT

PROJECT


---

## 8. optimizer.py

Main optimization module.

Generates alternative physical plans.

Join algorithms:

Nested Loop Join

Hash Join

Merge Join


Access paths:

Sequential Table Scan

Index Scan


The optimizer calculates estimated cost and selects the lowest-cost plan.


---

# Cost Model

COSTRA considers:

I/O Cost

CPU Cost

Filter Cost

Aggregation Cost

Sort Cost

Index Access Cost


Example:

Total Cost

=

Scan Cost

+

Join Cost

+

Filter Cost

+

Aggregation Cost

+

Sort Cost


---

# Cardinality Estimation

COSTRA estimates the number of rows produced after operations.

For example:

Input:

10000 rows

Predicate selectivity:

0.30

Estimated output:

10000 × 0.30

= 3000 rows


The estimated cardinality is then used by the optimizer while comparing physical plans.


---

# Physical Plan Enumeration

For multiple tables, COSTRA considers different join orders.

Example:

Plan A:

Employee
→ Department
→ Assignment
→ Project


Plan B:

Project
→ Assignment
→ Employee
→ Department


Plan C:

Assignment
→ Project
→ Employee
→ Department


Each candidate receives an estimated cost.

The optimizer chooses the candidate with the minimum estimated cost.


---

# Execution

SQLite is used as the execution backend.

The compiler itself performs:

Lexing

Parsing

Semantic Analysis

IR generation

Optimization

Cost estimation

Plan selection


SQLite is only used for executing the final SQL and producing the result.


---

# Run

Open terminal:

python3 main.py


Then choose:

1

to run the complex demonstration.


---

# Run Tests

python3 -m unittest test_costra.py


---

# Phase 2 Compiler Concepts Demonstrated

Lexical Analysis

Syntax Analysis

Abstract Syntax Tree

Semantic Analysis

Symbol Table

Intermediate Representation

Query Plan Generation

Cardinality Estimation

Selectivity Estimation

Physical Plan Enumeration

Cost-Based Optimization

Join Algorithm Selection

Access Path Selection

Execution

Performance Measurement


---

# Phase 2 Objective

The major objective of COSTRA is to demonstrate how a compiler/database optimizer can transform a declarative SQL query into an efficient physical execution strategy using statistics and estimated execution cost.