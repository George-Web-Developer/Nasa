"""
Unit tests for versioned database migrations and 'astro_' table prefix isolation.
NASA Space Apps Challenge 2026 - Health Monitoring Software.
"""

import pytest
from sqlalchemy import create_engine, text
from app.migrations.runner import apply_migrations, MIGRATIONS
from app.database import Base, init_db


def test_migrations_runner_on_fresh_db():
    """Verify migrations apply cleanly on a fresh database and track version history."""
    engine = create_engine("sqlite:///:memory:")
    apply_migrations(engine)

    with engine.connect() as conn:
        # Check migrations table exists
        rows = conn.execute(text("SELECT version, name FROM astro_migrations ORDER BY version ASC;")).fetchall()
        applied = {row[0]: row[1] for row in rows}

        assert 1 in applied
        assert applied[1] == "001_initial_astro_schema"
        assert 2 in applied
        assert applied[2] == "002_setup_fts5"


def test_table_prefix_isolation():
    """Verify all application tables carry the 'astro_' prefix to avoid collision."""
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with engine.connect() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            ).fetchall()
        ]

    # Every table must start with astro_
    for t in tables:
        assert t.startswith("astro_"), f"Table '{t}' does not have 'astro_' prefix!"

    # Specific required tables must be present
    expected_tables = {
        "astro_migrations",
        "astro_astronauts",
        "astro_sessions",
        "astro_messages",
        "astro_task_events",
        "astro_signals",
        "astro_analyses",
        "astro_fusion_results",
        "astro_baselines",
        "astro_alerts",
        "astro_kb_chunks",
        "astro_kb_usage",
        "astro_kb_chunks_fts",
    }
    assert expected_tables.issubset(set(tables))


def test_idempotent_migrations():
    """Verify running migrations multiple times is completely idempotent and safe."""
    engine = create_engine("sqlite:///:memory:")
    apply_migrations(engine)
    # Run second time
    apply_migrations(engine)

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM astro_migrations;")).scalar()
        assert count == len(MIGRATIONS)
