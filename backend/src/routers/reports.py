import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

REPORTS_DIR = "/tmp/reports"


@router.get("/{report_id}")
async def get_report(report_id: str):
    file_path = os.path.join(REPORTS_DIR, f"{report_id}.pdf")
    if not os.path.exists(file_path):
        return {"error": "Report not found"}
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
    )
