"""Orchestrates COSTRA's lexical, syntax, semantic and optimization stages."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from time import perf_counter
from ast_nodes import SelectQuery, format_query
from ir import PlanNode
from lexer import Token, tokenize
from optimizer import optimize
from parser import parse_tokens
from semantic import SemanticAnalyzer


@dataclass
class CompilationResult:
    success: bool
    sql: str
    tokens: list[Token] = field(default_factory=list)
    query: Optional[SelectQuery] = None
    aliases: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    failed_stage: Optional[str] = None
    logical_plan: Optional[PlanNode] = None
    candidates: list[PlanNode] = field(default_factory=list)
    best_plan: Optional[PlanNode] = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    normalized_sql: Optional[str] = None


def compile_sql(sql: str) -> CompilationResult:
    """Run COSTRA's compile/optimization pipeline without executing the SQL."""
    result = CompilationResult(success=False, sql=sql)
    start = perf_counter()
    try:
        result.tokens = tokenize(sql)
        result.timings_ms["lexical analysis"] = (perf_counter() - start) * 1000
    except (ValueError, TypeError) as exc:
        result.failed_stage = "LEXICAL ANALYSIS"
        result.errors = [str(exc)]
        result.timings_ms["lexical analysis"] = (perf_counter() - start) * 1000
        return result

    start = perf_counter()
    try:
        result.query = parse_tokens(result.tokens)
        result.normalized_sql = format_query(result.query)
        result.timings_ms["syntax analysis + AST"] = (perf_counter() - start) * 1000
    except (SyntaxError, ValueError, IndexError) as exc:
        result.failed_stage = "SYNTAX ANALYSIS"
        result.errors = [str(exc)]
        result.timings_ms["syntax analysis + AST"] = (perf_counter() - start) * 1000
        return result

    start = perf_counter()
    result.errors, result.aliases = SemanticAnalyzer().analyze(result.query)
    result.timings_ms["semantic analysis"] = (perf_counter() - start) * 1000
    if result.errors:
        result.failed_stage = "SEMANTIC ANALYSIS"
        return result

    start = perf_counter()
    try:
        result.logical_plan, result.candidates, result.best_plan = optimize(result.query)
        result.timings_ms["cost estimation + plan search"] = (perf_counter() - start) * 1000
    except (ValueError, KeyError, TypeError) as exc:
        result.failed_stage = "OPTIMIZATION"
        result.errors = [str(exc)]
        result.timings_ms["cost estimation + plan search"] = (perf_counter() - start) * 1000
        return result

    result.success = True
    return result
