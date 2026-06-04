import logging
import unicodedata

from langchain_core.tools import tool

logger = logging.getLogger("debug_tools")


def _normalize_input(value: str) -> str:
    value = value.replace('"', '').replace("'", '').replace('`', '')
    value = unicodedata.normalize('NFKC', value)
    value = value.encode('ascii', 'ignore').decode('ascii')
    return value


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
async def generate_flight_report_tool(
    flight_number: str,
    report_type: str = "summary",
    date_range: str | None = None,
) -> str:
    """Generate an operational report for a flight. Supported report types: summary, delay, load_factor, revenue.
    Optionally specify date_range (e.g. '2024-01-01:2024-01-31'). Uses the internal autoreport service.
    Returns a download link for the generated PDF report."""
    import asyncio
    import os
    from datetime import datetime

    flight_number = _normalize_input(flight_number)
    report_type = _normalize_input(report_type)
    if date_range:
        date_range = _normalize_input(date_range)

    output_dir = "/tmp/reports"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = f"rpt_{flight_number}_{report_type}_{timestamp}"
    cmd = f"/usr/local/bin/uv run /usr/local/bin/autoreport --flight {flight_number} --type {report_type} --format pdf --output {output_dir}/{report_id}.pdf"
    if date_range:
        cmd += f" --range {date_range}"

    logger.info(f"Executing: {cmd}")

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return (
                f"Report generated successfully.\n"
                f"Report ID: {report_id}\n"
                f"Title: {flight_number} {report_type.replace('_', ' ').title()} Report\n"
                f"Download URL: /api/v1/reports/{report_id}"
            )
        else:
            return (
                f"Report generation failed: {stderr.decode()}\n"
                f"Report ID: {report_id}\n"
                f"Title: {flight_number} {report_type.replace('_', ' ').title()} Report\n"
                f"Download URL: /api/v1/reports/{report_id}"
            )
    except asyncio.TimeoutError:
        return f"Report generation timed out for flight {flight_number}. Try a narrower date range."
    except Exception as e:
        return f"Report service error: {str(e)}"
