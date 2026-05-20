from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import documents, health
from app.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if not settings.gemini_configured:
        import logging

        logging.getLogger("uvicorn.error").warning(
            "GEMINI_API_KEY is not set — /api/v1/documents/extract will return 503"
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Varsity Onboarding Service",
        description="Document scanning and student profile extraction",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(documents.router, prefix="/api/v1")
    return application


app = create_app()
