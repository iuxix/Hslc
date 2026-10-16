from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from app.config import settings
from app.database import engine
from app.routers import ai_test, auth, exam, student, public
from app.routers.admin import curriculum as admin_curriculum
from app.routers.admin import users as admin_users
from app.routers.admin import questions as admin_questions
from app import models  # noqa
from app.routers.admin import migration as admin_migration
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

# Routers
app.include_router(auth.router)
app.include_router(ai_test.router)
app.include_router(public.router)
app.include_router(exam.router)
app.include_router(student.router)
app.include_router(admin_curriculum.router)
app.include_router(admin_users.router)
app.include_router(admin_questions.router)
app.include_router(admin_migration.router)


# ========== LIGHTWEIGHT ENDPOINTS ==========

@app.get("/api/ping")
def ping():
    """Fastest possible ping — UptimeRobot use kare"""
    return {"pong": True}


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
    """Lightweight health check — no DB call"""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/full")
def health_check_full():
    """Full health — with DB (jab chahiye)"""
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


@app.head("/health")
def health_head():
    return Response(status_code=200)


@app.head("/api/ping")
def ping_head():
    return Response(status_code=200)
