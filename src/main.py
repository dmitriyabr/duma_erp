"""School ERP FastAPI application."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

# macOS: so WeasyPrint finds pango/glib when generating PDFs (only if not already set)
if os.name == "posix" and os.environ.get("DYLD_LIBRARY_PATH") in (None, ""):
    _brew_lib = "/opt/homebrew/opt/glib/lib:/opt/homebrew/opt/pango/lib:/opt/homebrew/lib"
    if os.path.exists("/opt/homebrew/opt/glib/lib"):
        os.environ["DYLD_LIBRARY_PATH"] = _brew_lib

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.core.auth.router import router as auth_router
from src.core.attachments.router import router as attachments_router
from src.core.school_settings.router import router as school_settings_router
from src.modules.users.router import router as users_router
from src.modules.terms.router import router as terms_router
from src.modules.items.router import router as items_router
from src.modules.inventory.router import router as inventory_router
from src.modules.students.router import router as students_router
from src.modules.invoices.router import router as invoices_router
from src.modules.discounts.router import router as discounts_router
from src.modules.payments.router import router as payments_router
from src.modules.reservations.router import router as reservations_router
from src.modules.procurement.router import router as procurement_router
from src.modules.compensations.router import (
    router as compensations_router,
    payouts_router as compensations_payouts_router,
)
from src.modules.accountant.router import router as accountant_router
from src.modules.dashboard.router import router as dashboard_router
from src.modules.reports.router import router as reports_router
from src.core.config import settings
from src.core.exceptions import AppException
from src.core.exceptions.handlers import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from fastapi import HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="School ERP",
        description="ERP system for a private school in Kenya",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Health check endpoint (must be first for Railway/Heroku health checks)
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    # Routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(attachments_router, prefix="/api/v1")
    app.include_router(school_settings_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(terms_router, prefix="/api/v1")
    app.include_router(items_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(students_router, prefix="/api/v1")
    app.include_router(invoices_router, prefix="/api/v1")
    app.include_router(discounts_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(reservations_router, prefix="/api/v1")
    app.include_router(procurement_router, prefix="/api/v1")
    app.include_router(compensations_router, prefix="/api/v1")
    app.include_router(compensations_payouts_router, prefix="/api/v1")
    app.include_router(accountant_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")

    # Serve frontend static files (production)
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Serve index.html for all non-API routes (SPA routing)
            # Exclude health check and API routes
            if full_path.startswith("api/") or full_path == "health":
                return {"detail": "Not found"}
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
