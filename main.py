from lexer import tokenize
from parser import parse_sql
from semantic import analyze
from optimizer import Optimizer
from executor import execute_query
from ir import build_logical_plan


DEMO_QUERY = """
SELECT
    d.name AS department,
    COUNT(e.id) AS employee_count,
    AVG(e.salary) AS average_salary
FROM Employee e
JOIN Department d
    ON e.dept_id = d.id
JOIN Assignment a
    ON e.id = a.employee_id
JOIN Project p
    ON a.project_id = p.id
WHERE
    e.salary > 60000
    AND p.budget > 100000
GROUP BY d.name
HAVING AVG(e.salary) > 65000
ORDER BY AVG(e.salary) DESC
LIMIT 5;
"""


def print_line():
    print("=" * 75)


def show_tokens(sql):
    tokens = tokenize(sql)

    print("\nLEXICAL ANALYSIS")
    print("-" * 75)
    print(f"Token count: {len(tokens) - 1}")

    for token in tokens:
        if token.kind != "EOF":
            print(f"{token.kind:<15} {token.value}")


def show_ast(query):
    print("\nSYNTAX ANALYSIS")
    print("-" * 75)

    print("AST successfully generated.")
    print(f"FROM TABLE : {query.from_table.name}")
    print(f"JOINS      : {len(query.joins)}")
    print(f"SELECT ITEMS: {len(query.select_items)}")
    print(f"WHERE      : {'YES' if query.where else 'NO'}")
    print(f"GROUP BY   : {len(query.group_by)}")
    print(f"HAVING     : {'YES' if query.having else 'NO'}")
    print(f"ORDER BY   : {len(query.order_by)}")
    print(f"LIMIT      : {query.limit}")


def show_logical_plan(query):
    print("\nRELATIONAL IR / LOGICAL PLAN")
    print("-" * 75)

    plan = build_logical_plan(query)
    print(plan.pretty())


def run_demo():
    print_line()
    print("COSTRA")
    print("Cost-Based SQL Compiler and Query Optimizer")
    print_line()

    print("\nINPUT SQL")
    print("-" * 75)
    print(DEMO_QUERY)

    # ---------------------------------------------------------
    # 1. LEXICAL ANALYSIS
    # ---------------------------------------------------------
    try:
        show_tokens(DEMO_QUERY)
    except Exception as e:
        print("\nLEXICAL ERROR")
        print(e)
        return

    # ---------------------------------------------------------
    # 2. SYNTAX ANALYSIS
    # ---------------------------------------------------------
    try:
        query = parse_sql(DEMO_QUERY)
        show_ast(query)
    except Exception as e:
        print("\nSYNTAX ERROR")
        print(e)
        return

    # ---------------------------------------------------------
    # 3. SEMANTIC ANALYSIS
    # ---------------------------------------------------------
    print("\nSEMANTIC ANALYSIS")
    print("-" * 75)

    try:
        analyze(query)
        print("Semantic analysis successful.")
        print("All referenced tables and columns are valid.")
    except Exception as e:
        print("SEMANTIC ERROR")
        print(e)
        return

    # ---------------------------------------------------------
    # 4. RELATIONAL IR
    # ---------------------------------------------------------
    try:
        show_logical_plan(query)
    except Exception as e:
        print("\nIR GENERATION ERROR")
        print(e)

    # ---------------------------------------------------------
    # 5. COST-BASED OPTIMIZATION
    # ---------------------------------------------------------
    print("\nCOST-BASED OPTIMIZATION")
    print("-" * 75)

    try:
        optimizer = Optimizer()
        plans = optimizer.optimize(query)

        if not plans:
            print("No execution plans generated.")
            return

        print(f"Candidate plans generated: {len(plans)}")

        print("\nTOP CANDIDATE PLANS")
        print("-" * 75)

        for i, plan in enumerate(plans[:5], start=1):
            print(f"\nPlan {i}")
            print(f"Estimated Rows : {plan.estimated_rows:.2f}")
            print(f"Estimated Cost : {plan.estimated_cost:.4f}")

            if hasattr(plan, "pretty"):
                print(plan.pretty())

        selected_plan = plans[0]

        print("\nSELECTED PLAN")
        print("-" * 75)
        print(f"Estimated Rows : {selected_plan.estimated_rows:.2f}")
        print(f"Estimated Cost : {selected_plan.estimated_cost:.4f}")

        print("\nPhysical plan selected using minimum estimated cost.")

    except Exception as e:
        print("\nOPTIMIZATION ERROR")
        print(e)
        return

    # ---------------------------------------------------------
    # 6. EXECUTION
    # ---------------------------------------------------------
    print("\nSQL EXECUTION")
    print("-" * 75)

    try:
        result = execute_query(query)

        if isinstance(result, tuple):
            headers, rows, sql = result
        else:
            headers = []
            rows = result
            sql = ""

        print("Execution successful.")

        if sql:
            print("\nGenerated SQL:")
            print(sql)

        print("\nRESULT")
        print("-" * 75)

        if headers:
            print(" | ".join(str(h) for h in headers))
            print("-" * 75)

        for row in rows:
            print(" | ".join(str(value) for value in row))

        print(f"\nRows returned: {len(rows)}")

    except Exception as e:
        print("\nEXECUTION ERROR")
        print(e)
        return

    # ---------------------------------------------------------
    # 7. SUMMARY
    # ---------------------------------------------------------
    print("\nCOMPILER PIPELINE")
    print("-" * 75)

    print("""
SQL Query
   ↓
Lexical Analysis
   ↓
Syntax Analysis
   ↓
AST Generation
   ↓
Semantic Analysis
   ↓
Relational Intermediate Representation
   ↓
Cardinality Estimation
   ↓
Multiple Plan Generation
   ↓
Cost Estimation
   ↓
Cost-Based Plan Selection
   ↓
SQL Execution
   ↓
Result
""")

    print_line()
    print("COSTRA DEMO COMPLETED")
    print_line()


def custom_query():
    print_line()
    print("COSTRA - CUSTOM SQL MODE")
    print_line()

    print("\nEnter your SQL query.")
    print("Type END on a new line when finished.\n")

    lines = []

    while True:
        line = input()

        if line.strip().upper() == "END":
            break

        lines.append(line)

    sql = "\n".join(lines)

    if not sql.strip():
        print("No SQL query entered.")
        return

    print("\nProcessing query...")

    try:
        show_tokens(sql)

        query = parse_sql(sql)

        print("\nSYNTAX ANALYSIS")
        print("-" * 75)
        print("AST successfully generated.")

        analyze(query)

        print("\nSEMANTIC ANALYSIS")
        print("-" * 75)
        print("Semantic analysis successful.")

        optimizer = Optimizer()
        plans = optimizer.optimize(query)

        print("\nOPTIMIZATION")
        print("-" * 75)
        print(f"Candidate plans generated: {len(plans)}")

        if plans:
            print(f"Selected plan cost: {plans[0].estimated_cost:.4f}")

        result = execute_query(query)

        if isinstance(result, tuple):
            headers, rows, generated_sql = result
        else:
            headers = []
            rows = result
            generated_sql = ""

        print("\nEXECUTION RESULT")
        print("-" * 75)

        if headers:
            print(" | ".join(str(h) for h in headers))
            print("-" * 75)

        for row in rows:
            print(" | ".join(str(value) for value in row))

        print(f"\nRows returned: {len(rows)}")

    except Exception as e:
        print("\nERROR")
        print("-" * 75)
        print(e)


def semantic_error_demo():
    print_line()
    print("COSTRA - SEMANTIC ERROR DEMO")
    print_line()

    bad_query = """
    SELECT
        e.unknown_column,
        d.name
    FROM Employee e
    JOIN Department d
        ON e.dept_id = d.id;
    """

    print("\nInvalid SQL:")
    print(bad_query)

    try:
        query = parse_sql(bad_query)
        analyze(query)

        print("No semantic error detected.")

    except Exception as e:
        print("\nEXPECTED SEMANTIC ERROR")
        print("-" * 75)
        print(e)


def main():
    while True:
        print("\n")
        print_line()
        print("COSTRA - SQL COMPILER")
        print_line()

        print("1. Run complete demo")
        print("2. Enter custom SQL query")
        print("3. Demonstrate semantic error")
        print("4. Exit")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            run_demo()

        elif choice == "2":
            custom_query()

        elif choice == "3":
            semantic_error_demo()

        elif choice == "4":
            print("\nExiting COSTRA.")
            break

        else:
            print("\nInvalid choice. Enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()