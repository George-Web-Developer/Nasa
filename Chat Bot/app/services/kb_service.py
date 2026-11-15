import re
from typing import List, Dict, Any, Optional
from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from app.models import KBChunk, KBUsage, utc_now
from app.database import engine
from app.config import logger

# Anthropic Tool Definition for function calling
KB_TOOL_DEFINITION = {
    "name": "search_knowledge_base",
    "description": (
        "Search the official spaceflight psychology knowledge base for evidence-based "
        "operational countermeasures, self-help techniques, and protocols. "
        "Returns up to 3 approved chunks with citations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query keywords (e.g., 'box breathing', 'sleep circadian', 'grounding').",
            },
            "topic": {
                "type": "string",
                "enum": ["sleep", "stress", "anxiety", "fatigue", "isolation", "mood", "focus", "escalation"],
                "description": "Optional topic category to restrict the search.",
            },
        },
        "required": ["query"],
    },
}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "am", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    "you", "your", "me", "my", "i", "we", "our", "it", "its", "they", "them",
    "their", "this", "that", "these", "those", "what", "which", "who", "whom",
    "how", "give", "tell", "please", "some", "any", "rising", "help",
    "fine", "good", "well", "great", "nice", "cool", "okay", "ok", "thanks", "thank", "much", "just", "really"
}


def extract_search_tokens(query_str: str) -> List[str]:
    """Extract meaningful search keywords removing punctuation and common stop words."""
    if not query_str:
        return []
    cleaned = re.sub(r'["*:\^()\-+?.,!]', ' ', query_str)
    tokens = [t.strip() for t in cleaned.split() if t.strip() and t.strip().lower() not in STOP_WORDS]
    if not tokens:
        tokens = [t.strip() for t in cleaned.split() if t.strip()]
    return tokens


def sanitize_fts_query(query_str: str) -> str:
    """
    Sanitizes user queries for SQLite FTS5 syntax.
    Connects keywords with OR so that BM25 can score documents containing any or all keywords.
    """
    tokens = extract_search_tokens(query_str)
    if not tokens:
        return ""
    # In SQLite FTS5: "token1"* OR "token2"*
    return " OR ".join(f'"{token}"*' for token in tokens)


def search_knowledge_base(
    db: Session,
    query: Optional[str] = None,
    topic: Optional[str] = None,
    severity: Optional[float] = None,
    language: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Search approved KB chunks filtered by topic, severity, language, and ranked by FTS5 BM25.
    Returns list of dicts with chunk metadata and content.
    """
    is_sqlite = (engine.dialect.name == "sqlite")
    fts_sanitized = sanitize_fts_query(query) if query else ""

    results = []

    # 1. Try SQLite FTS5 bm25 full-text match if on SQLite
    if is_sqlite and fts_sanitized:
        try:
            sql = """
                SELECT k.id, k.title, k.topic, k.severity_min, k.severity_max,
                       k.content, k.source_name, k.source_url, k.language, k.last_reviewed,
                       bm25(astro_kb_chunks_fts) as rank
                FROM astro_kb_chunks k
                JOIN astro_kb_chunks_fts f ON k.id = f.rowid
                WHERE astro_kb_chunks_fts MATCH :fts_q
                  AND k.approved = 1
            """
            params: Dict[str, Any] = {"fts_q": fts_sanitized, "limit": limit}

            if topic:
                sql += " AND k.topic = :topic"
                params["topic"] = topic.strip().lower()

            if language:
                sql += " AND k.language = :language"
                params["language"] = language.strip().lower()

            if severity is not None:
                sql += " AND k.severity_min <= :severity AND k.severity_max >= :severity"
                params["severity"] = float(severity)

            sql += " ORDER BY rank ASC LIMIT :limit"

            cursor = db.execute(text(sql), params)
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r.id,
                    "title": r.title,
                    "topic": r.topic,
                    "severity_min": r.severity_min,
                    "severity_max": r.severity_max,
                    "content": r.content,
                    "source_name": r.source_name,
                    "source_url": r.source_url,
                    "language": r.language,
                })
        except Exception as e:
            logger.warning(f"FTS5 query failed, falling back to standard SQL filter: {e}")
            results = []

    # 2. Fallback to standard SQLAlchemy query if FTS5 returned nothing or non-sqlite
    if not results:
        q = db.query(KBChunk).filter(KBChunk.approved == True)

        if topic:
            q = q.filter(KBChunk.topic == topic.strip().lower())
        if language:
            q = q.filter(KBChunk.language == language.strip().lower())
        if severity is not None:
            q = q.filter(KBChunk.severity_min <= severity, KBChunk.severity_max >= severity)

        if query and query.strip():
            tokens = extract_search_tokens(query)
            if tokens:
                clauses = []
                for tok in tokens:
                    clauses.append(KBChunk.title.ilike(f"%{tok}%"))
                    clauses.append(KBChunk.content.ilike(f"%{tok}%"))
                q = q.filter(or_(*clauses))
            else:
                search_term = f"%{query.strip()}%"
                q = q.filter((KBChunk.title.ilike(search_term)) | (KBChunk.content.ilike(search_term)))

        chunks = q.limit(limit).all()
        for c in chunks:
            results.append({
                "id": c.id,
                "title": c.title,
                "topic": c.topic,
                "severity_min": c.severity_min,
                "severity_max": c.severity_max,
                "content": c.content,
                "source_name": c.source_name,
                "source_url": c.source_url,
                "language": c.language,
            })

    # 3. If still empty and severity filter was applied, retry matching without strict severity bound
    # to avoid dropping relevant help if astronaut's score is marginally outside placeholder boundaries
    if not results and severity is not None and (query or topic):
        q = db.query(KBChunk).filter(KBChunk.approved == True)
        if topic:
            q = q.filter(KBChunk.topic == topic.strip().lower())
        if language:
            q = q.filter(KBChunk.language == language.strip().lower())
        if query and query.strip():
            tokens = extract_search_tokens(query)
            if tokens:
                clauses = [or_(KBChunk.title.ilike(f"%{t}%"), KBChunk.content.ilike(f"%{t}%")) for t in tokens]
                q = q.filter(or_(*clauses))
        chunks = q.limit(limit).all()
        for c in chunks:
            results.append({
                "id": c.id,
                "title": c.title,
                "topic": c.topic,
                "severity_min": c.severity_min,
                "severity_max": c.severity_max,
                "content": c.content,
                "source_name": c.source_name,
                "source_url": c.source_url,
                "language": c.language,
            })

    return results


def log_kb_usage(db: Session, message_id: int, chunk_ids: List[int]) -> None:
    """Log KB chunks used in an assistant response into kb_usage table."""
    if not chunk_ids:
        return

    try:
        for cid in set(chunk_ids):
            exists = db.query(KBUsage).filter(KBUsage.message_id == message_id, KBUsage.chunk_id == cid).first()
            if not exists:
                usage = KBUsage(
                    message_id=message_id,
                    chunk_id=cid,
                    created_at=utc_now(),
                )
                db.add(usage)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log KB usage for message_id {message_id}: {e}")
