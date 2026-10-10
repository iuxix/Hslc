from fastapi import APIRouter, HTTPException
from app.database import Base, engine
from app import models  # noqa — register all models
from app.config import settings

router = APIRouter(prefix="/api/setup", tags=["Setup"])


@router.post("/create-tables")
def create_tables(secret: str):
    """Temporary endpoint — creates all database tables."""
    if secret != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        Base.metadata.create_all(bind=engine)
        return {
            "status": "success",
            "message": "All tables created successfully",
            "tables": sorted(Base.metadata.tables.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
