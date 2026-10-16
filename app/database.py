from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# ✅ Optimized for Neon serverless (free tier auto-suspend)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # ✅ Stale connections detect karega (important!)
    pool_size=5,              # 5 ready connections
    max_overflow=10,          # 10 extra if needed
    pool_timeout=30,          # Wait 30s if pool empty
    pool_recycle=180,         # ✅ 3 min — Neon 5 min suspend se pehle refresh
    echo=False,               # No SQL logging
    connect_args={
        "connect_timeout": 10,           # Max 10s wait for connection
        "keepalives": 1,                 # ✅ TCP keepalive on
        "keepalives_idle": 30,           # 30s idle → send keepalive
        "keepalives_interval": 10,       # 10s between keepalives
        "keepalives_count": 5,           # 5 attempts before giving up
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
