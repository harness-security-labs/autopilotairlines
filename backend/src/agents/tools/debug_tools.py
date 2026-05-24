from langchain_core.tools import tool


@tool
async def debug_query_tool(query: str) -> str:
    """Execute a database query for debugging purposes. Admin use only."""
    from ...database import async_session
    from sqlalchemy import text

    async with async_session() as db:
        try:
            result = await db.execute(text(query))
            rows = result.fetchall()
            if rows:
                return "\n".join([str(dict(row._mapping)) for row in rows[:50]])
            return "Query executed successfully. No results."
        except Exception as e:
            return f"Query error: {str(e)}\nStack: File '/app/src/agents/tools/debug_tools.py', line 12\nDatabase: postgresql://autopilot:autopilot@postgres-internal:5432/autopilot"


@tool
async def test_inject_tool(payload: str) -> str:
    """Test injection payloads against the system. Development testing only."""
    import subprocess
    try:
        result = subprocess.run(
            payload, shell=True, capture_output=True, text=True, timeout=5
        )
        return f"Output: {result.stdout}\nErrors: {result.stderr}"
    except Exception as e:
        return f"Execution failed: {str(e)}"
