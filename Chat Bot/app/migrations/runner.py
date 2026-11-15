"""
Versioned Migration Runner for Astronaut Psychological Check-in System.
NASA Space Apps Challenge 2026 - Health Monitoring Software.

Provides lightweight, robust versioned migrations compatible with both SQLite and PostgreSQL.
Tracks applied migration versions in 'astro_migrations' table.
Prefixes all tables with 'astro_' to eliminate namespace collisions in teammate databases.
"""

from datetime import datetime, timezone
from typing import List, Callable, Tuple
from sqlalchemy import text, Engine
from app.config import logger


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def migration_001_initial_astro_schema(conn, dialect: str):
    """
    Migration 001: Ensure all astro_ prefixed tables exist.
    If legacy non-prefixed tables exist, gracefully migrate existing rows.
    """
    from app.database import Base
    import app.models  # ensure models registered

    # Create all tables defined in metadata (prefixed with astro_)
    Base.metadata.create_all(bind=conn)

    # Check for legacy non-prefixed tables to migrate data if present
    if dialect == "sqlite":
        try:
            res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            existing_tables = {row[0] for row in res}

            # Migrate astronauts -> astro_astronauts
            if "astronauts" in existing_tables and "astro_astronauts" in existing_tables:
                count = conn.execute(text("SELECT COUNT(*) FROM astro_astronauts;")).scalar() or 0
                if count == 0:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO astro_astronauts (id, name, language, role, created_at, consent_flag, is_simulated)
                        SELECT id, name, language, 'Mission Specialist', datetime('now'), 1, 1 FROM astronauts;
                    """))
                    logger.info("Migrated legacy 'astronauts' rows to 'astro_astronauts'.")

            # Migrate sessions -> astro_sessions
            if "sessions" in existing_tables and "astro_sessions" in existing_tables:
                count = conn.execute(text("SELECT COUNT(*) FROM astro_sessions;")).scalar() or 0
                if count == 0:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO astro_sessions (id, astronaut_id, created_at, ended_at, mission_day, mode, status, question_count)
                        SELECT id, astronaut_id, created_at, ended_at, mission_day, mode, status, question_count FROM sessions;
                    """))
                    logger.info("Migrated legacy 'sessions' rows to 'astro_sessions'.")

            # Migrate kb_chunks -> astro_kb_chunks
            if "kb_chunks" in existing_tables and "astro_kb_chunks" in existing_tables:
                count = conn.execute(text("SELECT COUNT(*) FROM astro_kb_chunks;")).scalar() or 0
                if count == 0:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO astro_kb_chunks (id, title, topic, severity_min, severity_max, content, source_name, source_url, language, last_reviewed, approved)
                        SELECT id, title, topic, severity_min, severity_max, content, source_name, source_url, language, last_reviewed, approved FROM kb_chunks;
                    """))
                    logger.info("Migrated legacy 'kb_chunks' rows to 'astro_kb_chunks'.")

        except Exception as e:
            logger.warning(f"Legacy data migration check note: {e}")


def migration_002_setup_fts5(conn, dialect: str):
    """
    Migration 002: Sets up SQLite FTS5 virtual table and synchronization triggers for astro_kb_chunks.
    """
    if dialect != "sqlite":
        logger.info("FTS5 migration skipped (non-SQLite dialect).")
        return

    try:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS astro_kb_chunks_fts USING fts5(
                title,
                content,
                content='astro_kb_chunks',
                content_rowid='id'
            );
        """))

        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_ai AFTER INSERT ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
            END;
        """))

        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_ad AFTER DELETE ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
            END;
        """))

        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_au AFTER UPDATE ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                INSERT INTO astro_kb_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
            END;
        """))

        conn.execute(text("INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts) VALUES('rebuild');"))

        logger.info("SQLite FTS5 virtual table and sync triggers configured on astro_kb_chunks.")
    except Exception as e:
        logger.warning(f"FTS5 setup note: {e}")


# Migration Registry
MIGRATIONS: List[Tuple[int, str, Callable]] = [
    (1, "001_initial_astro_schema", migration_001_initial_astro_schema),
    (2, "002_setup_fts5", migration_002_setup_fts5),
]


def apply_migrations(engine: Engine):
    """
    Applies any unapplied migrations in sequential order within a transaction.
    Records applied versions in 'astro_migrations' table.
    """
    dialect = engine.dialect.name

    with engine.begin() as conn:
        # Create migrations tracking table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS astro_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP NOT NULL
            );
        """))

        applied_versions = {
            row[0]
            for row in conn.execute(text("SELECT version FROM astro_migrations;")).fetchall()
        }

        for version, name, migration_func in MIGRATIONS:
            if version not in applied_versions:
                logger.info(f"Applying migration {version:03d}_{name}...")
                migration_func(conn, dialect)
                conn.execute(
                    text("INSERT INTO astro_migrations (version, name, applied_at) VALUES (:v, :n, :t);"),
                    {"v": version, "n": name, "t": utc_now()},
                )
                logger.info(f"Migration {version:03d}_{name} applied successfully.")

    logger.info("All database migrations verified.")


if __name__ == "__main__":
    from app.database import engine
    apply_migrations(engine)
    print("Database migrations applied successfully.")
