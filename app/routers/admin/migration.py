from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_admin

router = APIRouter(prefix="/api/admin/migration", tags=["Migration"])


@router.get("/dump", response_class=PlainTextResponse, dependencies=[Depends(get_current_admin)])
def dump_database(db: Session = Depends(get_db)):
    """
    Generate complete SQL dump for migration.
    Browser mein kholo → SQL text file download hogi.
    """
    tables_ordered = [
        # Order matters for FK
        "subjects",
        "sections",
        "chapters",
        "topics",
        "users",
        "questions",
        "question_options",
        "tests",
        "test_questions",
        "attempts",
        "answers",
        "question_timing",
    ]
    
    lines = []
    lines.append("-- ============================================")
    lines.append("-- SEBA HSLC Database Migration Dump")
    lines.append("-- Generated: " + str(__import__('datetime').datetime.now()))
    lines.append("-- ============================================")
    lines.append("")
    lines.append("-- FK constraints temporarily disable")
    lines.append("SET session_replication_role = 'replica';")
    lines.append("")
    
    for table in tables_ordered:
        try:
            rows = db.execute(text(f'SELECT * FROM "{table}"')).fetchall()
        except Exception as e:
            lines.append(f"-- Table {table} skipped: {e}")
            continue
        
        if not rows:
            lines.append(f"-- Table {table}: 0 rows")
            continue
        
        cols = db.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)).fetchall()
        col_names = [c[0] for c in cols]
        
        lines.append("")
        lines.append(f"-- ============ {table} ({len(rows)} rows) ============")
        
        for row in rows:
            values = []
            for v in row:
                if v is None:
                    values.append("NULL")
                elif isinstance(v, bool):
                    values.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    values.append(str(v))
                elif isinstance(v, dict):
                    import json
                    json_str = json.dumps(v).replace("'", "''")
                    values.append(f"'{json_str}'::jsonb")
                elif isinstance(v, list):
                    import json
                    json_str = json.dumps(v).replace("'", "''")
                    values.append(f"'{json_str}'::jsonb")
                elif isinstance(v, __import__('datetime').datetime):
                    values.append(f"'{v.isoformat()}'")
                else:
                    escaped = str(v).replace("'", "''")
                    values.append(f"'{escaped}'")
            
            cols_quoted = ", ".join(f'"{c}"' for c in col_names)
            lines.append(
                f'INSERT INTO "{table}" ({cols_quoted}) VALUES ({", ".join(values)});'
            )
    
    lines.append("")
    lines.append("-- Re-enable FK constraints")
    lines.append("SET session_replication_role = 'origin';")
    lines.append("")
    lines.append("-- Reset ID sequences so new inserts work correctly")
    for table in tables_ordered:
        lines.append(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 1), true);"
        )
    lines.append("")
    lines.append("-- ✅ Migration dump complete")
    
    sql_text = "\n".join(lines)
    
    return PlainTextResponse(
        content=sql_text,
        headers={
            "Content-Disposition": 'attachment; filename="seba_migration_dump.sql"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
