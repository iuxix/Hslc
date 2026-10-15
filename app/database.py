from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Optimized connection pool
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=False,     # No per-connection ping (faster)
    pool_size=5,              # 5 ready connections
    max_overflow=10,          # 10 extra if needed
    pool_timeout=30,          # Wait 30s if pool empty
    pool_recycle=1800,        # Refresh connections every 30 min
    echo=False,               # No SQL logging (faster)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
