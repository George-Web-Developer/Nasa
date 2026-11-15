from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DB_URL, logger

# Configure connect_args for SQLite to support multi-threaded FastAPI calls and busy timeout
connect_args = {"check_same_thread": False, "timeout": 30} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, connect_args=connect_args)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DB_URL.startswith("sqlite"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency yields a database session for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_sqlite_fts(connection):
    """
    Sets up SQLite FTS5 virtual table and synchronization triggers for astro_kb_chunks.
    Allows high-performance bm25 ranked full-text searches.
    """
    try:
        connection.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS astro_kb_chunks_fts USING fts5(
                title,
                content,
                content='astro_kb_chunks',
                content_rowid='id'
            );
        """))

        # Triggers to keep FTS index synchronized with astro_kb_chunks
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_ai AFTER INSERT ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
            END;
        """))

        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_ad AFTER DELETE ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
            END;
        """))

        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS astro_kb_chunks_au AFTER UPDATE ON astro_kb_chunks BEGIN
                INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts, rowid, title, content) VALUES('delete', old.id, old.title, old.content);
                INSERT INTO astro_kb_chunks_fts(rowid, title, content) VALUES (new.id, new.title, new.content);
            END;
        """))

        # Rebuild index to guarantee sync with existing rows
        connection.execute(text("INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts) VALUES('rebuild');"))

        logger.info("SQLite FTS5 virtual table and sync triggers configured on astro_kb_chunks.")
    except Exception as e:
        logger.warning(f"Could not initialize SQLite FTS5 triggers: {e}")


def rebuild_fts_index(db):
    """Manually rebuild the FTS5 virtual table index."""
    if engine.dialect.name == "sqlite":
        try:
            db.execute(text("INSERT INTO astro_kb_chunks_fts(astro_kb_chunks_fts) VALUES('rebuild');"))
            db.commit()
            logger.info("FTS5 index successfully rebuilt for astro_kb_chunks_fts.")
        except Exception as e:
            logger.warning(f"FTS5 rebuild failed: {e}")


def init_db(target_engine=None):
    """
    Initialize all database tables with versioned migrations and FTS5 triggers.
    Ensures all tables are prefixed with 'astro_'.
    """
    eng = target_engine or engine
    import app.models  # ensure models are registered with Base metadata
    from app.migrations.runner import apply_migrations

    # Apply versioned migrations
    apply_migrations(eng)

    if eng.dialect.name == "sqlite":
        with eng.connect() as conn:
            setup_sqlite_fts(conn)
            conn.commit()

    logger.info("Database initialized successfully with versioned migrations.")


def configure_database(db_url: str):
    """
    Reconfigure database engine and session factory with a custom connection string (e.g. teammate database).
    Initializes versioned migrations and FTS5 indexing on target database.
    """
    global engine, SessionLocal
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal.configure(bind=engine)
    init_db(engine)
    logger.info(f"Database successfully reconfigured to: {db_url}")
    return engine
