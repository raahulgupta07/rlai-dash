"""
Routing Cases
=============

Leader delegates to the right specialist and triggers the right tools.
Eval type: ReliabilityEval (expected tool calls)
"""

CASES: list[dict] = [
    {"input": "What's our current MRR?", "expected_tools": ["run_sql_query"]},
    {"input": "Which plan has the highest churn rate?", "expected_tools": ["run_sql_query"]},
    {"input": "Show me the customers table schema", "expected_tools": ["introspect_schema"]},
    {"input": "Create a view for monthly MRR by plan", "expected_tools": ["run_sql_query"]},
    {"input": "How many active subscriptions do we have?", "expected_tools": ["run_sql_query"]},
    {"input": "What are the top cancellation reasons?", "expected_tools": ["run_sql_query"]},
]
