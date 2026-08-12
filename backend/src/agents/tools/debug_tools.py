import logging
import re
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
    """Execute a read-only database query for debugging purposes. Admin use only.
    Only SELECT statements are permitted."""
    from ...database import async_session
    from ...config import settings
    from ...security.sql import (
        enforce_read_only_transaction,
        normalize_read_only_query,
    )
    from sqlalchemy import text

    difficulty = settings.difficulty.lower()
    if difficulty != "easy":
        normalized_query = normalize_read_only_query(query)
        if normalized_query is None:
            return (
                "Query rejected: only one plain SELECT statement is permitted in "
                "debug mode. Use the appropriate admin API endpoints for data "
                "modifications."
            )
        query = normalized_query

    async with async_session() as db:
        try:
            if difficulty != "easy":
                await enforce_read_only_transaction(db)
            result = await db.execute(text(query))
            rows = result.fetchall()
            if rows:
                return "\n".join([str(dict(row._mapping)) for row in rows[:50]])
            return "Query executed successfully. No results."
        except Exception as e:
            if difficulty == "easy":
                return (
                    f"Query error: {str(e)}\n"
                    f"Stack: File '/app/src/agents/tools/debug_tools.py', line 12\n"
                    f"Database: postgresql://autopilot:autopilot@postgres-internal:5432/autopilot"
                )
            return f"Query error: {str(e)}"


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
    from ...config import settings

    difficulty = settings.difficulty.lower()

    if difficulty == "easy":  # weak normalisation — intentionally bypassable
        flight_number = _normalize_input(flight_number)
        report_type = _normalize_input(report_type)
        if date_range:
            date_range = _normalize_input(date_range)
    else:
        if not re.fullmatch(r"[A-Za-z0-9]{2,10}", flight_number):
            return "Invalid flight number format."
        allowed_types = {"summary", "delay", "load_factor", "revenue"}
        if report_type not in allowed_types:
            return f"Invalid report type. Allowed: {', '.join(sorted(allowed_types))}"
        if date_range and not re.fullmatch(r"\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}", date_range):
            return "Invalid date_range format. Use YYYY-MM-DD:YYYY-MM-DD."

    output_dir = "/tmp/reports"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = f"rpt_{flight_number}_{report_type}_{timestamp}"

    if difficulty == "easy":
        # shell=True with f-string args — intentionally vulnerable
        cmd = (
            f"/usr/local/bin/uv run /usr/local/bin/autoreport "
            f"--flight {flight_number} --type {report_type} "
            f"--format pdf --output {output_dir}/{report_id}.pdf"
        )
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
    else:
        args = [
            "/usr/local/bin/uv", "run", "/usr/local/bin/autoreport",
            "--flight", flight_number,
            "--type", report_type,
            "--format", "pdf",
            "--output", f"{output_dir}/{report_id}.pdf",
        ]
        if date_range:
            args += ["--range", date_range]
        logger.info(f"Executing: {' '.join(args)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
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
                return f"Report generation failed. Please try again or contact support."
        except asyncio.TimeoutError:
            return f"Report generation timed out for flight {flight_number}. Try a narrower date range."
        except Exception as e:
            return f"Report service error. Please contact support."
