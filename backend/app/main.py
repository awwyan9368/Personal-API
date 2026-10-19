from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
import app.models.entities  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema exists on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Local-first Personal Life Operating System & REST API. "
        "Track habits, finance, screen time, focus activities, goals, journal, and wellbeing with complete data ownership."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def redacted_global_exception_handler(request: Request, exc: Exception):
    # Redact internal stack traces, secrets, or tokens from unhandled 500 error responses
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Sensitive details have been redacted.",
            "error_type": exc.__class__.__name__,
        },
    )


app.include_router(api_router, prefix="/api/v1")

