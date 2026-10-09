from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine
from app.routers import ai_test, auth
from app.routers.admin import curriculum as admin_curriculum
from app import models  # noqa — register models

app = FastAPI(
    title="SEBA HSLC Study Platform API",
    description="Backend API for SEBA HSLC Class 10 exam training",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes
app.include_router(auth.router)
app.include_router(ai_test.router)

# Admin routes
app.include_router(admin_curriculum.router)


@app.get("/")
def read_root():
    return {
        "app": "SEBA HSLC API",
        "version": "0.1.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
    }
