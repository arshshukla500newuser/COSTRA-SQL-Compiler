# COSTRA Architecture

```mermaid
flowchart TD
    A[SQL input] --> B[Lexer]
    B --> C[Recursive-descent parser]
    C --> D[AST]
    D --> E[Schema-aware semantic analysis]
    E -->|valid| F[Logical relational IR]
    E -->|invalid| X[Diagnostic; stop]
    F --> G[Synthetic statistics / selectivity]
    G --> H[Candidate access paths and join orders]
    H --> I[Relative cost model]
    I --> J[Lowest-estimated-cost candidate]
    D --> K[SQL pretty-printer]
    K --> L[SQLite executor]
    L --> M[Rows + SQLite EXPLAIN QUERY PLAN]
    J --> N[Candidate estimates for inspection]
```

The logical route and executable route share the validated AST, but the optimizer's chosen physical-plan estimate is **not** an input to SQLite. SQLite parses and plans the normalized SQL independently. This separation is intentional and must be explained during demonstration.

## Module responsibilities

- Lexical and syntax stages convert text to structured query data.
- Semantic analysis rejects references and aggregate usage that violate the supported schema/rules.
- The logical IR represents operations such as scan, join, filter, aggregate, having, distinct, sort, limit and projection.
- The cost model estimates alternative access paths and join orders using synthetic statistics.
- The executor uses SQLite for reproducible output and displays SQLite's own plan separately.
