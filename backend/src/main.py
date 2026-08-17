import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import engine, Base
from .routers import auth, flights, bookings, users, payments, loyalty, refunds, chat, admin, memory, checkin, baggage, payment_methods, reports
from .mcp.server import (
    mcp_app,
    admin_router as mcp_admin_router,
    session_manager as mcp_session_manager,
)
from .services.flight_scheduler import run_scheduler


async def _sync_schema(conn):
    """Add any columns that exist in models but not in the database."""
    from sqlalchemy import inspect, text

    def _do_sync(sync_conn):
        inspector = inspect(sync_conn)
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(sync_conn.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default = ""
                    if col.server_default:
                        default = f" DEFAULT {col.server_default.arg}"
                    sync_conn.execute(text(
                        f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type} {nullable}{default}'
                    ))

    await conn.run_sync(_do_sync)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_session_manager.run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _sync_schema(conn)
        scheduler_task = asyncio.create_task(run_scheduler())
        yield
        scheduler_task.cancel()
        await engine.dispose()


app = FastAPI(
    title="AutoPilot Airlines API",
    version="1.0.0",
    description="AI-powered airline booking platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(flights.router)
app.include_router(bookings.router)
app.include_router(users.router)
app.include_router(payments.router)
app.include_router(loyalty.router)
app.include_router(refunds.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(memory.router)
app.include_router(checkin.router)
app.include_router(baggage.router)
app.include_router(payment_methods.router)
app.include_router(reports.router)
app.include_router(mcp_admin_router)
app.mount("/mcp", mcp_app)


from starlette.middleware.base import BaseHTTPMiddleware


class ServerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Server"] = "uvicorn/0.29.0"
        response.headers["X-Powered-By"] = "FastAPI/0.115.0, Python/3.12"
        response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")
        return response


app.add_middleware(ServerHeaderMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.error_detail_level == "full":
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
                "path": str(request.url),
                "server": "autopilot-backend-v1.0.0",
                "host": "autopilot-api-internal.svc:8000",
            },
        )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "autopilot-airlines-backend"}


@app.get("/")
async def root():
    return {
        "name": "AutoPilot Airlines API",
        "version": "1.0.0",
        "docs": "/docs",
    }
