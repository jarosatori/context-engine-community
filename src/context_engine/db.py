"""SQLite database layer for Context Engine."""

import json
import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from difflib import SequenceMatcher

# Prefer pysqlite3 (modern SQLite + extension support); fallback to stdlib.
# Stdlib sqlite3 on macOS lacks enable_load_extension, so sqlite-vec won't load.
try:
    import pysqlite3 as sqlite3
    _SQLITE_HAS_EXTENSIONS = True
except ImportError:
    import sqlite3
    _SQLITE_HAS_EXTENSIONS = hasattr(sqlite3.Connection, "enable_load_extension")

logger = logging.getLogger(__name__)

from context_engine.nicknames import expand_query_names, surname_similarity, FUZZY_THRESHOLD
from context_engine.schema_meta import (
    DOMAINS, CATEGORIES, CATEGORY_ALIASES, DOMAIN_FROM_CATEGORY,
    SENTIMENTS, CHANNELS, FORMALITIES, TONES, RELATIONSHIPS,
    REQUIRED_FIELDS, RECOMMENDED_FIELDS,
    normalize_category, has_time_marker, auto_time_marker, quarter_marker,
)

# Embedding layer (lazy — Voyage API key môže chýbať)
try:
    from context_engine import embeddings as _emb
    _EMBEDDINGS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Embeddings module not available: {e}")
    _EMBEDDINGS_AVAILABLE = False
    _emb = None

DB_PATH = os.environ.get("CTX_DB", str(Path.home() / ".context-engine" / "context-engine.db"))

# Whitelist of valid tables for generic operations
VALID_TABLES = {"people", "companies", "projects", "products", "rules", "interactions", "notes", "scan_log",
                 "action_items", "decisions", "meeting_participants"}

# Valid columns per table (for safe updates)
VALID_COLUMNS = {
    "people": {"name", "email", "phone", "company_id", "company_name", "role",
               "relationship", "formality", "tone", "language", "projects",
               "notes", "status", "source", "domain", "tags", "updated_at", "aliases"},
    "companies": {"name", "type", "industry", "my_role", "website", "notes",
                  "status", "domain", "updated_at"},
    "projects": {"name", "company_id", "company_name", "description", "type",
                 "status", "team", "my_role", "asana_id", "slack_channel",
                 "drive_folder", "key_contacts", "notes", "deadline", "domain", "updated_at"},
    "products": {"name", "company_id", "company_name", "description", "price",
                 "format", "availability", "target_audience", "min_criteria",
                 "notes", "status", "domain", "updated_at"},
    "rules": {"context", "rule", "example", "priority", "category", "applies_to",
              "notes", "status", "domain", "updated_at"},
    "interactions": {"person_id", "person_name", "channel", "direction", "summary",
                     "details", "topics", "key_points", "sentiment", "follow_up",
                     "duration_minutes", "context", "date", "source_ref", "domain"},
    "notes": {"title", "content", "domain", "category", "tags",
              "related_person_id", "related_project_id", "source", "status", "updated_at"},
    "action_items": {"title", "owner_name", "owner_id", "source_interaction_id",
                     "related_project_id", "due_date", "status", "priority", "notes",
                     "domain", "completed_at", "asana_task_id", "updated_at"},
    "decisions": {"title", "context", "decided_by", "source_interaction_id",
                  "related_project_id", "date", "status", "notes", "domain", "updated_at"},
    "meeting_participants": {"interaction_id", "person_id", "person_name"},
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT,
    industry TEXT,
    my_role TEXT,
    website TEXT,
    notes TEXT,
    status TEXT DEFAULT 'active',
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    role TEXT,
    relationship TEXT,
    formality TEXT DEFAULT 'uncertain',
    tone TEXT,
    language TEXT DEFAULT 'sk',
    projects TEXT,
    notes TEXT,
    status TEXT DEFAULT 'active',
    source TEXT,
    domain TEXT DEFAULT 'work',
    tags TEXT,
    aliases TEXT,
    first_seen TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name, email)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    description TEXT,
    type TEXT,
    status TEXT DEFAULT 'active',
    team TEXT,
    my_role TEXT,
    asana_id TEXT,
    slack_channel TEXT,
    drive_folder TEXT,
    key_contacts TEXT,
    notes TEXT,
    deadline TEXT,
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    description TEXT,
    price TEXT,
    format TEXT,
    availability TEXT,
    target_audience TEXT,
    min_criteria TEXT,
    notes TEXT,
    status TEXT DEFAULT 'active',
    domain TEXT DEFAULT 'work',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context TEXT NOT NULL,
    rule TEXT NOT NULL,
    example TEXT,
    priority TEXT DEFAULT 'medium',
    category TEXT,
    applies_to TEXT,
    notes TEXT,
    status TEXT DEFAULT 'active',
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER REFERENCES people(id),
    person_name TEXT,
    channel TEXT,
    direction TEXT,
    summary TEXT,
    details TEXT,
    topics TEXT,
    key_points TEXT,
    sentiment TEXT,
    follow_up TEXT,
    duration_minutes INTEGER,
    context TEXT,
    date TEXT DEFAULT (date('now')),
    source_ref TEXT,
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    domain TEXT DEFAULT 'personal',
    category TEXT,
    tags TEXT,
    related_person_id INTEGER REFERENCES people(id),
    related_project_id INTEGER REFERENCES projects(id),
    source TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    owner_name TEXT,
    owner_id INTEGER REFERENCES people(id),
    source_interaction_id INTEGER REFERENCES interactions(id),
    related_project_id INTEGER REFERENCES projects(id),
    due_date TEXT,
    status TEXT DEFAULT 'extracted',
    priority TEXT DEFAULT 'medium',
    notes TEXT,
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    asana_task_id TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    context TEXT,
    decided_by TEXT,
    source_interaction_id INTEGER REFERENCES interactions(id),
    related_project_id INTEGER REFERENCES projects(id),
    date TEXT DEFAULT (date('now')),
    status TEXT DEFAULT 'active',
    notes TEXT,
    domain TEXT DEFAULT 'work',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meeting_participants (
    interaction_id INTEGER REFERENCES interactions(id) ON DELETE CASCADE,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    person_name TEXT,
    PRIMARY KEY (interaction_id, person_id)
);

CREATE TABLE IF NOT EXISTS scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL UNIQUE,
    last_scan TEXT,
    items_processed INTEGER DEFAULT 0,
    items_added INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    notes TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- FTS indexes
CREATE VIRTUAL TABLE IF NOT EXISTS people_fts USING fts5(
    name, email, company_name, role, notes, projects, aliases,
    content='people', content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS projects_fts USING fts5(
    name, company_name, description, team, notes,
    content='projects', content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, content, category, tags,
    content='notes', content_rowid='id'
);

-- FTS triggers: people
CREATE TRIGGER IF NOT EXISTS people_ai AFTER INSERT ON people BEGIN
    INSERT INTO people_fts(rowid, name, email, company_name, role, notes, projects, aliases)
    VALUES (new.id, new.name, new.email, new.company_name, new.role, new.notes, new.projects, new.aliases);
END;

CREATE TRIGGER IF NOT EXISTS people_ad AFTER DELETE ON people BEGIN
    INSERT INTO people_fts(people_fts, rowid, name, email, company_name, role, notes, projects, aliases)
    VALUES ('delete', old.id, old.name, old.email, old.company_name, old.role, old.notes, old.projects, old.aliases);
END;

CREATE TRIGGER IF NOT EXISTS people_au AFTER UPDATE ON people BEGIN
    INSERT INTO people_fts(people_fts, rowid, name, email, company_name, role, notes, projects, aliases)
    VALUES ('delete', old.id, old.name, old.email, old.company_name, old.role, old.notes, old.projects, old.aliases);
    INSERT INTO people_fts(rowid, name, email, company_name, role, notes, projects, aliases)
    VALUES (new.id, new.name, new.email, new.company_name, new.role, new.notes, new.projects, new.aliases);
END;

-- FTS triggers: projects
CREATE TRIGGER IF NOT EXISTS projects_ai AFTER INSERT ON projects BEGIN
    INSERT INTO projects_fts(rowid, name, company_name, description, team, notes)
    VALUES (new.id, new.name, new.company_name, new.description, new.team, new.notes);
END;

CREATE TRIGGER IF NOT EXISTS projects_ad AFTER DELETE ON projects BEGIN
    INSERT INTO projects_fts(projects_fts, rowid, name, company_name, description, team, notes)
    VALUES ('delete', old.id, old.name, old.company_name, old.description, old.team, old.notes);
END;

CREATE TRIGGER IF NOT EXISTS projects_au AFTER UPDATE ON projects BEGIN
    INSERT INTO projects_fts(projects_fts, rowid, name, company_name, description, team, notes)
    VALUES ('delete', old.id, old.name, old.company_name, old.description, old.team, old.notes);
    INSERT INTO projects_fts(rowid, name, company_name, description, team, notes)
    VALUES (new.id, new.name, new.company_name, new.description, new.team, new.notes);
END;

-- FTS triggers: notes
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content, category, tags)
    VALUES (new.id, new.title, new.content, new.category, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, category, tags)
    VALUES ('delete', old.id, old.title, old.content, old.category, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, category, tags)
    VALUES ('delete', old.id, old.title, old.content, old.category, old.tags);
    INSERT INTO notes_fts(rowid, title, content, category, tags)
    VALUES (new.id, new.title, new.content, new.category, new.tags);
END;

-- FTS: companies
CREATE VIRTUAL TABLE IF NOT EXISTS companies_fts USING fts5(
    name, type, industry, notes,
    content='companies', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS companies_ai AFTER INSERT ON companies BEGIN
    INSERT INTO companies_fts(rowid, name, type, industry, notes)
    VALUES (new.id, new.name, new.type, new.industry, new.notes);
END;

CREATE TRIGGER IF NOT EXISTS companies_ad AFTER DELETE ON companies BEGIN
    INSERT INTO companies_fts(companies_fts, rowid, name, type, industry, notes)
    VALUES ('delete', old.id, old.name, old.type, old.industry, old.notes);
END;

CREATE TRIGGER IF NOT EXISTS companies_au AFTER UPDATE ON companies BEGIN
    INSERT INTO companies_fts(companies_fts, rowid, name, type, industry, notes)
    VALUES ('delete', old.id, old.name, old.type, old.industry, old.notes);
    INSERT INTO companies_fts(rowid, name, type, industry, notes)
    VALUES (new.id, new.name, new.type, new.industry, new.notes);
END;

-- FTS: interactions
CREATE VIRTUAL TABLE IF NOT EXISTS interactions_fts USING fts5(
    person_name, summary, details, context, topics, key_points, follow_up,
    content='interactions', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS interactions_ai AFTER INSERT ON interactions BEGIN
    INSERT INTO interactions_fts(rowid, person_name, summary, details, context, topics, key_points, follow_up)
    VALUES (new.id, new.person_name, new.summary, new.details, new.context, new.topics, new.key_points, new.follow_up);
END;

CREATE TRIGGER IF NOT EXISTS interactions_ad AFTER DELETE ON interactions BEGIN
    INSERT INTO interactions_fts(interactions_fts, rowid, person_name, summary, details, context, topics, key_points, follow_up)
    VALUES ('delete', old.id, old.person_name, old.summary, old.details, old.context, old.topics, old.key_points, old.follow_up);
END;

CREATE TRIGGER IF NOT EXISTS interactions_au AFTER UPDATE ON interactions BEGIN
    INSERT INTO interactions_fts(interactions_fts, rowid, person_name, summary, details, context, topics, key_points, follow_up)
    VALUES ('delete', old.id, old.person_name, old.summary, old.details, old.context, old.topics, old.key_points, old.follow_up);
    INSERT INTO interactions_fts(rowid, person_name, summary, details, context, topics, key_points, follow_up)
    VALUES (new.id, new.person_name, new.summary, new.details, new.context, new.topics, new.key_points, new.follow_up);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
CREATE INDEX IF NOT EXISTS idx_people_status ON people(status);
CREATE INDEX IF NOT EXISTS idx_people_domain ON people(domain);
CREATE INDEX IF NOT EXISTS idx_projects_company ON projects(company_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_domain ON projects(domain);
CREATE INDEX IF NOT EXISTS idx_interactions_person ON interactions(person_id);
CREATE INDEX IF NOT EXISTS idx_interactions_date ON interactions(date);
CREATE INDEX IF NOT EXISTS idx_interactions_domain ON interactions(domain);
CREATE INDEX IF NOT EXISTS idx_notes_domain ON notes(domain);
CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);
CREATE INDEX IF NOT EXISTS idx_rules_domain ON rules(domain);
CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items(status);
CREATE INDEX IF NOT EXISTS idx_action_items_owner ON action_items(owner_id);
CREATE INDEX IF NOT EXISTS idx_action_items_due ON action_items(due_date);
CREATE INDEX IF NOT EXISTS idx_action_items_interaction ON action_items(source_interaction_id);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_date ON decisions(date);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(related_project_id);
CREATE INDEX IF NOT EXISTS idx_mp_person ON meeting_participants(person_id);
CREATE INDEX IF NOT EXISTS idx_mp_interaction ON meeting_participants(interaction_id);
"""

SCAN_SOURCES = ["gmail", "slack", "asana", "drive", "calendar"]


def _load_sqlite_vec(db) -> bool:
    """Load sqlite-vec extension. Returns True if loaded successfully.

    On macOS stdlib sqlite3, enable_load_extension is missing. Caller should
    handle False gracefully (semantic search disabled, FTS5 still works).
    """
    if not _SQLITE_HAS_EXTENSIONS:
        return False
    try:
        import sqlite_vec
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        return True
    except Exception as e:
        logger.warning(f"Failed to load sqlite-vec: {e}")
        try:
            db.enable_load_extension(False)
        except Exception:
            pass
        return False


@contextmanager
def get_db(db_path: str | None = None):
    """Context manager for database connections.

    Loads sqlite-vec extension if available — silently skipped if not (allows
    DB to work without semantic search on platforms without extension support).
    """
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    _load_sqlite_vec(db)  # best-effort
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _validate_table(table: str) -> str:
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table: {table}. Must be one of: {VALID_TABLES}")
    return table


def _validate_columns(table: str, columns: set[str]) -> None:
    valid = VALID_COLUMNS.get(table, set())
    invalid = columns - valid - {"updated_at"}
    if invalid:
        raise ValueError(f"Invalid columns for {table}: {invalid}")


def _domain_filter(domain: str | None) -> tuple[str, list]:
    """Return SQL WHERE clause and params for domain filtering."""
    if domain:
        return " AND domain = ?", [domain]
    return "", []


def _migrate(db) -> None:
    """Run migrations for schema changes on existing databases."""
    cols = {row[1] for row in db.execute("PRAGMA table_info(people)").fetchall()}

    # Migration: add tags column to people (added 2026-03-17)
    if "tags" not in cols:
        db.execute("ALTER TABLE people ADD COLUMN tags TEXT")

    # Migration: add aliases column to people (added 2026-04-06)
    if "aliases" not in cols:
        db.execute("ALTER TABLE people ADD COLUMN aliases TEXT DEFAULT NULL")
        # Rebuild FTS index to include aliases
        db.execute("INSERT INTO people_fts(people_fts) VALUES('rebuild')")

    # Migration: add rich interaction columns (added 2026-04-16)
    int_cols = {row[1] for row in db.execute("PRAGMA table_info(interactions)").fetchall()}
    for col, coltype in [
        ("details", "TEXT"),
        ("topics", "TEXT"),
        ("key_points", "TEXT"),
        ("sentiment", "TEXT"),
        ("follow_up", "TEXT"),
        ("duration_minutes", "INTEGER"),
    ]:
        if col not in int_cols:
            db.execute(f"ALTER TABLE interactions ADD COLUMN {col} {coltype}")

    # Rebuild FTS indexes after migration (companies + interactions)
    try:
        db.execute("INSERT INTO companies_fts(companies_fts) VALUES('rebuild')")
    except Exception:
        pass
    try:
        db.execute("INSERT INTO interactions_fts(interactions_fts) VALUES('rebuild')")
    except Exception:
        pass

    # Migration v5: embedding storage (sqlite-vec) — added 2026-04-24
    # Skip silently if sqlite-vec isn't loaded (e.g. macOS without pysqlite3)
    try:
        # vec0 virtual table for raw embeddings
        db.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0(
                id INTEGER PRIMARY KEY,
                embedding FLOAT[1024]
            )
        """)
        # Mapping table — which CE row this embedding represents
        db.execute("""
            CREATE TABLE IF NOT EXISTS embedding_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_id INTEGER NOT NULL,
                text_hash TEXT NOT NULL,
                model TEXT NOT NULL,
                embedding_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(table_name, row_id, model)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_embedding_index_lookup ON embedding_index(table_name, row_id)")
    except Exception as e:
        logger.warning(f"sqlite-vec migration skipped: {e}")


def init_db(db_path: str | None = None) -> dict:
    """Create database with full schema."""
    with get_db(db_path) as db:
        db.executescript(SCHEMA_SQL)
        _migrate(db)
        for source in SCAN_SOURCES:
            db.execute("INSERT OR IGNORE INTO scan_log (source) VALUES (?)", (source,))
        db.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (5)")
    return {"status": "ok", "message": "Database initialized", "path": db_path or DB_PATH}


def populate_aliases(db_path: str | None = None) -> dict:
    """One-time migration: generate aliases from NICKNAMES dictionary for all people."""
    from context_engine.nicknames import generate_aliases

    with get_db(db_path) as db:
        # Ensure aliases column exists
        _migrate(db)

        rows = db.execute("SELECT id, name, aliases FROM people").fetchall()
        updated = 0
        for row in rows:
            new_aliases = generate_aliases(row["name"])
            if not new_aliases:
                continue

            # Merge with existing aliases
            existing = []
            if row["aliases"]:
                try:
                    existing = json.loads(row["aliases"])
                except (json.JSONDecodeError, TypeError):
                    existing = []

            merged = list(dict.fromkeys(existing + new_aliases))
            if merged != existing:
                db.execute(
                    "UPDATE people SET aliases = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(merged, ensure_ascii=False), datetime.now().isoformat(), row["id"])
                )
                updated += 1

    return {"status": "ok", "total_people": len(rows), "aliases_updated": updated}


def _find_person_smart(db, query: str) -> tuple[sqlite3.Row | None, str]:
    """Smart person lookup: exact → alias → nickname expansion → fuzzy.

    Returns (row, match_type) where match_type is one of:
    'exact', 'alias', 'nickname', 'fuzzy', or '' if not found.
    """
    like = f"%{query}%"

    # 1. Exact name/email match
    person = db.execute(
        "SELECT * FROM people WHERE name LIKE ? OR email LIKE ? LIMIT 1",
        (like, like)
    ).fetchone()
    if person:
        return person, "exact"

    # 2. Alias match
    person = db.execute(
        "SELECT * FROM people WHERE aliases LIKE ? LIMIT 1",
        (like,)
    ).fetchone()
    if person:
        return person, "alias"

    # 3. Nickname expansion — try alternative name forms
    alternatives = expand_query_names(query)
    for alt in alternatives:
        alt_like = f"%{alt}%"
        person = db.execute(
            "SELECT * FROM people WHERE name LIKE ? OR aliases LIKE ? LIMIT 1",
            (alt_like, alt_like)
        ).fetchone()
        if person:
            return person, "nickname"

    # 4. Fuzzy surname match — last resort
    query_parts = query.strip().split()
    if len(query_parts) >= 2:
        # Get candidate rows to compare against
        # Use first letter of surname to narrow candidates
        surname = query_parts[-1]
        first_char_like = f"% {surname[0]}%"
        candidates = db.execute(
            "SELECT * FROM people WHERE name LIKE ? LIMIT 100",
            (first_char_like,)
        ).fetchall()
        if not candidates:
            candidates = db.execute("SELECT * FROM people LIMIT 500").fetchall()

        best_match = None
        best_score = 0.0
        for candidate in candidates:
            score = surname_similarity(query, candidate["name"])
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= FUZZY_THRESHOLD:
            return best_match, "fuzzy"

    return None, ""


def find(query: str, domain: str | None = None, db_path: str | None = None) -> dict:
    """Search across all tables. Uses FTS for people/projects/notes, LIKE for others."""
    with get_db(db_path) as db:
        results = {}
        like = f"%{query}%"
        d_sql, d_params = _domain_filter(domain)

        # People — FTS with LIKE fallback, then nickname expansion + fuzzy
        try:
            rows = db.execute(
                f"SELECT p.* FROM people p JOIN people_fts f ON p.id = f.rowid WHERE people_fts MATCH ? {('AND p.domain = ?' if domain else '')} ORDER BY rank LIMIT 20",
                [query] + ([domain] if domain else [])
            ).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            rows = db.execute(
                f"SELECT * FROM people WHERE (name LIKE ? OR email LIKE ? OR company_name LIKE ? OR role LIKE ? OR notes LIKE ? OR aliases LIKE ?) {d_sql} LIMIT 20",
                [like, like, like, like, like, like] + d_params
            ).fetchall()

        # If no results, try nickname expansion
        if not rows:
            alternatives = expand_query_names(query)
            for alt in alternatives:
                alt_like = f"%{alt}%"
                rows = db.execute(
                    f"SELECT * FROM people WHERE (name LIKE ? OR aliases LIKE ?) {d_sql} LIMIT 20",
                    [alt_like, alt_like] + d_params
                ).fetchall()
                if rows:
                    break

        # If still no results, try fuzzy match
        if not rows:
            candidates = db.execute(
                f"SELECT * FROM people WHERE 1=1 {d_sql} LIMIT 500",
                d_params
            ).fetchall()
            query_parts = query.strip().split()
            fuzzy_matches = []
            for c in candidates:
                if len(query_parts) >= 2:
                    # Multi-word: compare surnames
                    score = surname_similarity(query, c["name"])
                else:
                    # Single word: compare against each part of the name
                    q_lower = query.strip().lower()
                    name_parts = c["name"].split()
                    score = max(
                        (SequenceMatcher(None, q_lower, part.lower()).ratio() for part in name_parts),
                        default=0.0
                    )
                if score >= FUZZY_THRESHOLD:
                    d = dict(c)
                    d["_match_type"] = "fuzzy"
                    d["_match_score"] = round(score, 2)
                    fuzzy_matches.append(d)
            fuzzy_matches.sort(key=lambda x: x["_match_score"], reverse=True)
            if fuzzy_matches:
                results["people"] = fuzzy_matches[:20]

        if rows and "people" not in results:
            results["people"] = [dict(r) for r in rows]

        # Companies — FTS with LIKE fallback
        try:
            rows = db.execute(
                f"SELECT c.* FROM companies c JOIN companies_fts f ON c.id = f.rowid WHERE companies_fts MATCH ? {('AND c.domain = ?' if domain else '')} ORDER BY rank LIMIT 10",
                [query] + ([domain] if domain else [])
            ).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            rows = db.execute(
                f"SELECT * FROM companies WHERE (name LIKE ? OR type LIKE ? OR notes LIKE ?) {d_sql} LIMIT 10",
                [like, like, like] + d_params
            ).fetchall()
        if rows:
            results["companies"] = [dict(r) for r in rows]

        # Projects — FTS with LIKE fallback
        try:
            rows = db.execute(
                f"SELECT p.* FROM projects p JOIN projects_fts f ON p.id = f.rowid WHERE projects_fts MATCH ? {('AND p.domain = ?' if domain else '')} ORDER BY rank LIMIT 20",
                [query] + ([domain] if domain else [])
            ).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            rows = db.execute(
                f"SELECT * FROM projects WHERE (name LIKE ? OR company_name LIKE ? OR description LIKE ? OR notes LIKE ?) {d_sql} LIMIT 20",
                [like, like, like, like] + d_params
            ).fetchall()
        if rows:
            results["projects"] = [dict(r) for r in rows]

        # Products
        rows = db.execute(
            f"SELECT * FROM products WHERE (name LIKE ? OR description LIKE ? OR company_name LIKE ?) {d_sql} LIMIT 10",
            [like, like, like] + d_params
        ).fetchall()
        if rows:
            results["products"] = [dict(r) for r in rows]

        # Rules
        rows = db.execute(
            f"SELECT * FROM rules WHERE (context LIKE ? OR rule LIKE ? OR category LIKE ?) {d_sql} LIMIT 10",
            [like, like, like] + d_params
        ).fetchall()
        if rows:
            results["rules"] = [dict(r) for r in rows]

        # Notes — FTS with snippet + bm25 score, LIKE fallback
        try:
            rows = db.execute(
                "SELECT n.*, "
                "  snippet(notes_fts, -1, '«', '»', '…', 24) AS _snippet, "
                "  bm25(notes_fts) AS _score "
                "FROM notes_fts JOIN notes n ON n.id = notes_fts.rowid "
                f"WHERE notes_fts MATCH ? {('AND n.domain = ?' if domain else '')} "
                "ORDER BY _score LIMIT 20",
                [query] + ([domain] if domain else [])
            ).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            rows = db.execute(
                f"SELECT * FROM notes WHERE (title LIKE ? OR content LIKE ? OR category LIKE ? OR tags LIKE ?) {d_sql} LIMIT 20",
                [like, like, like, like] + d_params
            ).fetchall()
        if rows:
            results["notes"] = [dict(r) for r in rows]

        # Action items
        rows = db.execute(
            f"SELECT * FROM action_items WHERE (title LIKE ? OR owner_name LIKE ? OR notes LIKE ?) {d_sql} LIMIT 10",
            [like, like, like] + d_params
        ).fetchall()
        if rows:
            results["action_items"] = [dict(r) for r in rows]

        # Decisions
        rows = db.execute(
            f"SELECT * FROM decisions WHERE (title LIKE ? OR context LIKE ? OR decided_by LIKE ?) {d_sql} LIMIT 10",
            [like, like, like] + d_params
        ).fetchall()
        if rows:
            results["decisions"] = [dict(r) for r in rows]

        # Interactions — FTS with snippet + bm25 score, LIKE fallback
        try:
            rows = db.execute(
                "SELECT i.*, "
                "  snippet(interactions_fts, -1, '«', '»', '…', 24) AS _snippet, "
                "  bm25(interactions_fts) AS _score "
                "FROM interactions_fts JOIN interactions i ON i.id = interactions_fts.rowid "
                f"WHERE interactions_fts MATCH ? {('AND i.domain = ?' if domain else '')} "
                "ORDER BY _score LIMIT 20",
                [query] + ([domain] if domain else [])
            ).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            rows = db.execute(
                f"SELECT * FROM interactions WHERE (person_name LIKE ? OR summary LIKE ? OR details LIKE ? OR context LIKE ? OR topics LIKE ? OR key_points LIKE ? OR follow_up LIKE ?) {d_sql} LIMIT 20",
                [like, like, like, like, like, like, like] + d_params
            ).fetchall()
        if rows:
            results["interactions"] = [dict(r) for r in rows]

        total = sum(len(v) for v in results.values())
        return {"total": total, "results": results}


def get_person(query: str, db_path: str | None = None) -> dict:
    """Full person detail with interactions, projects, and rules."""
    with get_db(db_path) as db:
        person, match_type = _find_person_smart(db, query)

        if not person:
            return {"error": f"Person not found: {query}"}

        result = dict(person)
        if match_type != "exact":
            result["_match_type"] = match_type

        # Recent interactions — full detail
        interactions = db.execute(
            "SELECT * FROM interactions WHERE person_id = ? ORDER BY date DESC LIMIT 15",
            (person["id"],)
        ).fetchall()
        result["recent_interactions"] = [dict(i) for i in interactions]

        # Project details
        if person["projects"]:
            try:
                project_names = json.loads(person["projects"])
                projects = []
                for pname in project_names:
                    p = db.execute("SELECT id, name, status, my_role FROM projects WHERE name LIKE ?", (f"%{pname}%",)).fetchone()
                    if p:
                        projects.append(dict(p))
                result["project_details"] = projects
            except (json.JSONDecodeError, TypeError):
                pass

        # Rules for this person
        rules = db.execute(
            "SELECT * FROM rules WHERE applies_to LIKE ? AND status = 'active'",
            (f"%{person['name']}%",)
        ).fetchall()
        result["applicable_rules"] = [dict(r) for r in rules]

        # Company rules
        if person["company_name"]:
            company_rules = db.execute(
                "SELECT * FROM rules WHERE applies_to LIKE ? AND status = 'active'",
                (f"%{person['company_name']}%",)
            ).fetchall()
            result["company_rules"] = [dict(r) for r in company_rules]

        # Action items for this person
        action_items = db.execute(
            "SELECT * FROM action_items WHERE owner_name LIKE ? OR owner_id = ? ORDER BY status, priority",
            (f"%{person['name']}%", person["id"])
        ).fetchall()
        result["action_items"] = [dict(a) for a in action_items]

        # Meetings via meeting_participants
        meetings = db.execute("""
            SELECT i.id, i.summary, i.date, i.channel, mp.person_name
            FROM meeting_participants mp
            JOIN interactions i ON mp.interaction_id = i.id
            WHERE mp.person_id = ?
            ORDER BY i.date DESC
        """, (person["id"],)).fetchall()
        result["meetings"] = [dict(m) for m in meetings]

        return result


def get_company(query: str, db_path: str | None = None) -> dict:
    """Company detail with people, projects, products, and rules."""
    with get_db(db_path) as db:
        like = f"%{query}%"
        company = db.execute("SELECT * FROM companies WHERE name LIKE ? LIMIT 1", (like,)).fetchone()
        if not company:
            return {"error": f"Company not found: {query}"}

        result = dict(company)
        result["people"] = [dict(r) for r in db.execute(
            "SELECT id, name, role, relationship, formality, status FROM people WHERE company_id = ? OR company_name LIKE ? ORDER BY status, name",
            (company["id"], f"%{company['name']}%")
        ).fetchall()]
        result["projects"] = [dict(r) for r in db.execute(
            "SELECT id, name, status, type, my_role FROM projects WHERE company_id = ? OR company_name LIKE ? ORDER BY status, name",
            (company["id"], f"%{company['name']}%")
        ).fetchall()]
        result["products"] = [dict(r) for r in db.execute(
            "SELECT id, name, price, format, availability FROM products WHERE company_id = ? OR company_name LIKE ?",
            (company["id"], f"%{company['name']}%")
        ).fetchall()]
        result["rules"] = [dict(r) for r in db.execute(
            "SELECT * FROM rules WHERE applies_to LIKE ? AND status = 'active'",
            (f"%{company['name']}%",)
        ).fetchall()]
        return result


def get_project(query: str, db_path: str | None = None) -> dict:
    """Project detail with team members."""
    with get_db(db_path) as db:
        like = f"%{query}%"
        project = db.execute("SELECT * FROM projects WHERE name LIKE ? LIMIT 1", (like,)).fetchone()
        if not project:
            return {"error": f"Project not found: {query}"}

        result = dict(project)
        if project["team"]:
            try:
                team_names = json.loads(project["team"])
                team = []
                for tname in team_names:
                    p = db.execute("SELECT id, name, role, formality, email FROM people WHERE name LIKE ?", (f"%{tname}%",)).fetchone()
                    if p:
                        team.append(dict(p))
                result["team_details"] = team
            except (json.JSONDecodeError, TypeError):
                pass
        return result


def context_for(query: str, db_path: str | None = None) -> dict:
    """Full communication context for a person — everything needed before writing a message."""
    with get_db(db_path) as db:
        person, match_type = _find_person_smart(db, query)

        if not person:
            return {"error": f"Person not found: {query}", "hint": "Try 'find' first"}

        p = dict(person)
        person_info = {
            "name": p["name"],
            "email": p.get("email"),
            "company": p.get("company_name"),
            "role": p.get("role"),
            "relationship": p.get("relationship"),
            "domain": p.get("domain"),
        }
        if match_type != "exact":
            person_info["_match_type"] = match_type
        ctx = {
            "person": person_info,
            "communication": {
                "formality": p.get("formality", "uncertain"),
                "tone": p.get("tone"),
                "language": p.get("language", "sk"),
            },
            "notes": p.get("notes"),
        }

        # Company
        if p.get("company_id"):
            company = db.execute("SELECT * FROM companies WHERE id = ?", (p["company_id"],)).fetchone()
            if company:
                ctx["company"] = {"name": company["name"], "type": company["type"], "my_role": company["my_role"]}

        # Last 10 interactions (with details)
        interactions = db.execute(
            "SELECT channel, direction, summary, details, topics, key_points, date FROM interactions WHERE person_id = ? ORDER BY date DESC LIMIT 10",
            (p["id"],)
        ).fetchall()
        ctx["recent_interactions"] = [dict(i) for i in interactions]

        # Relevant rules
        rules = []
        for r in db.execute("SELECT context, rule, priority FROM rules WHERE status = 'active'").fetchall():
            applies = r["context"] or ""
            if (p["name"] and p["name"].lower() in applies.lower()) or \
               (p.get("company_name") and p["company_name"].lower() in applies.lower()):
                rules.append(dict(r))

        more_rules = db.execute(
            "SELECT context, rule, priority FROM rules WHERE (applies_to LIKE ? OR applies_to LIKE ?) AND status = 'active'",
            (f"%{p['name']}%", f"%{p.get('company_name', '___')}%")
        ).fetchall()
        for r in more_rules:
            rd = dict(r)
            if rd not in rules:
                rules.append(rd)

        ctx["rules"] = rules
        return ctx


# ─────────────────────────────────────────────────────────────────────
# VALIDATION + AUTO-ENRICHMENT helpers (Layer 2 + 3)
# ─────────────────────────────────────────────────────────────────────

def _parse_tags(tags) -> list:
    """Robustne parsuje tags — JSON string, list, alebo CSV."""
    if tags is None:
        return []
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    if isinstance(tags, str):
        s = tags.strip()
        if not s:
            return []
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return [str(t).strip() for t in v if str(t).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback — CSV
        return [t.strip() for t in s.split(",") if t.strip()]
    return []


def _detect_mentioned_people(db, content: str, limit: int = 5) -> list[int]:
    """Nájde person_id-čka, ktorých meno sa vyskytuje v `content`.

    Použité pre auto-link notes ↔ people.
    """
    if not content or len(content) < 5:
        return []
    rows = db.execute(
        "SELECT id, name FROM people WHERE status='active' AND length(name) > 4"
    ).fetchall()
    matched = []
    for r in rows:
        name = (r["name"] or "").strip()
        if not name:
            continue
        # Whole-word match (case-insensitive)
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if pattern.search(content):
            matched.append(r["id"])
            if len(matched) >= limit:
                break
    return matched


def _validate_and_enrich_note(data: dict, db) -> tuple[dict, list[str], list[str]]:
    """Validuje + obohatí note dáta. Vracia (clean_data, warnings, errors)."""
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Required check (po enrichment-e)
    # Najprv skús auto-fill čo sa dá

    # 1a. Normalizuj category
    raw_cat = data.get("category")
    if raw_cat:
        canonical, normalized = normalize_category(raw_cat)
        data["category"] = canonical
        if normalized:
            warnings.append(f"category '{raw_cat}' → normalized to '{canonical}'")
    else:
        errors.append("category is required (e.g. 'meeting-notes', 'decision', 'strategy')")

    # 1b. Auto-fill domain z category ak chýba
    if not data.get("domain") and data.get("category"):
        derived = DOMAIN_FROM_CATEGORY.get(data["category"])
        if derived:
            data["domain"] = derived
            warnings.append(f"domain auto-derived from category → '{derived}'")
        else:
            errors.append("domain is required (work/personal/family/health/finance/home/education)")
    elif data.get("domain") and data["domain"] not in DOMAINS:
        errors.append(f"domain '{data['domain']}' invalid. Must be one of: {sorted(DOMAINS)}")

    # 1c. Tags — parse + ensure time marker
    tags = _parse_tags(data.get("tags"))
    if not tags:
        errors.append("tags is required (JSON array, must contain time marker like '2026-W17' + topic)")
    else:
        if not has_time_marker(tags):
            tm = auto_time_marker(data.get("created_at") or data.get("date"))
            tags.append(tm)
            warnings.append(f"time marker auto-added to tags → '{tm}'")
        data["tags"] = json.dumps(tags, ensure_ascii=False)

    # 1d. Source default
    if not data.get("source"):
        data["source"] = "manual-input"
        warnings.append("source defaulted to 'manual-input' (consider providing real source)")

    # 1e. Hard-required (po auto-fill-e)
    for f in REQUIRED_FIELDS["notes"]:
        if not data.get(f):
            errors.append(f"required field missing: {f}")

    # 2. Auto-link to people (mentioned in content)
    if data.get("content") and not data.get("related_person_id"):
        mentioned = _detect_mentioned_people(db, data["content"])
        if mentioned:
            data["related_person_id"] = mentioned[0]
            if len(mentioned) > 1:
                warnings.append(f"auto-linked to person {mentioned[0]}; also mentions: {mentioned[1:]}")
            else:
                warnings.append(f"auto-linked to person {mentioned[0]}")

    return data, warnings, errors


def _validate_and_enrich_interaction(data: dict, db) -> tuple[dict, list[str], list[str]]:
    """Validuje + obohatí interaction dáta."""
    warnings: list[str] = []
    errors: list[str] = []

    # channel required
    if not data.get("channel"):
        errors.append("channel is required (email/slack/asana/call/meeting/sms/...)")
    elif data["channel"] not in CHANNELS:
        warnings.append(f"channel '{data['channel']}' not in standard list: {sorted(CHANNELS)}")

    # date default = today
    if not data.get("date"):
        data["date"] = datetime.now().strftime("%Y-%m-%d")
        warnings.append("date defaulted to today")

    # sentiment validation
    if data.get("sentiment") and data["sentiment"] not in SENTIMENTS:
        warnings.append(f"sentiment '{data['sentiment']}' not in {sorted(SENTIMENTS)}")

    # need at least summary or details
    if not data.get("summary") and not data.get("details"):
        errors.append("at least one of (summary, details) is required")

    # Auto-resolve person_id from person_name
    if data.get("person_name") and not data.get("person_id"):
        # Try _find_person_smart for fuzzy resolution
        person, match_type = _find_person_smart(db, data["person_name"])
        if person:
            data["person_id"] = person["id"]
            if match_type != "exact":
                warnings.append(f"person_id resolved via {match_type} match → {person['name']} (id={person['id']})")

    # Domain default
    if not data.get("domain"):
        data["domain"] = "work"
        warnings.append("domain defaulted to 'work'")

    # Topics/key_points must be JSON arrays if provided
    for f in ("topics", "key_points"):
        if data.get(f):
            parsed = _parse_tags(data[f])
            data[f] = json.dumps(parsed, ensure_ascii=False) if parsed else None

    # Soft warnings — chýbajúce recommended
    for f in RECOMMENDED_FIELDS["interactions"]:
        if not data.get(f):
            warnings.append(f"recommended field missing: {f}")

    return data, warnings, errors


def _validate_and_enrich_person(data: dict, db) -> tuple[dict, list[str], list[str]]:
    """Validuje + obohatí person dáta."""
    warnings: list[str] = []
    errors: list[str] = []

    if not data.get("name") or not data["name"].strip():
        errors.append("name is required")
        return data, warnings, errors

    # Validate enums
    if data.get("formality") and data["formality"] not in FORMALITIES:
        warnings.append(f"formality '{data['formality']}' invalid; defaulting to 'uncertain'")
        data["formality"] = "uncertain"

    if data.get("relationship") and data["relationship"] not in RELATIONSHIPS:
        warnings.append(f"relationship '{data['relationship']}' not standard")

    # Auto-set domain
    if not data.get("domain"):
        data["domain"] = "work"

    # Soft warnings
    for f in RECOMMENDED_FIELDS["people"]:
        if not data.get(f):
            warnings.append(f"recommended field missing: {f}")

    return data, warnings, errors


def add_record(table: str, data: dict, db_path: str | None = None,
               strict: bool = True) -> dict:
    """Add a record with validation + auto-enrichment.

    `strict=True` → reject on errors (default).
    `strict=False` → return record with warnings + errors but still insert (not used in production).
    """
    _validate_table(table)

    # Schema-aware validation per table
    enrichers = {
        "notes": _validate_and_enrich_note,
        "interactions": _validate_and_enrich_interaction,
        "people": _validate_and_enrich_person,
    }

    warnings: list[str] = []
    errors: list[str] = []

    if table in enrichers:
        with get_db(db_path) as db:
            data, warnings, errors = enrichers[table](data, db)

    if errors and strict:
        return {
            "status": "error",
            "code": "VALIDATION_FAILED",
            "errors": errors,
            "warnings": warnings,
            "hint": "Doplň povinné polia a skús znova. Pre notes pozri ctx_categories() pre platné category.",
        }

    columns_to_write = set(data.keys())
    valid = VALID_COLUMNS.get(table, set()) | {
        "name", "title", "context", "rule", "person_id",
        "person_name", "channel", "direction", "summary",
        "date", "source_ref", "created_at", "first_seen",
        "email", "phone", "company_id",
    }
    invalid = columns_to_write - valid
    if invalid:
        return {"status": "error", "error": f"Invalid columns for {table}: {invalid}"}

    now = datetime.now().isoformat()
    if "updated_at" not in data and table != "interactions":
        data["updated_at"] = now

    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?" for _ in data])
    values = list(data.values())

    with get_db(db_path) as db:
        try:
            cursor = db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            new_id = cursor.lastrowid
            result = {"status": "ok", "id": new_id, "table": table}
            if warnings:
                result["warnings"] = warnings

            # Auto-embed (best-effort, never blocks the insert)
            if table in EMBEDDABLE_TABLES:
                try:
                    emb_res = _embed_and_store(db, table, new_id)
                    if emb_res.get("status") in ("indexed", "updated"):
                        result["embedding"] = emb_res["status"]
                    elif emb_res.get("status") == "error":
                        result.setdefault("warnings", []).append(
                            f"embedding failed: {emb_res.get('reason')}"
                        )
                except Exception as e:
                    result.setdefault("warnings", []).append(f"embedding hook error: {e}")

            return result
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                return {"status": "duplicate", "error": str(e), "hint": "Use 'update' command instead"}
            return {"status": "error", "error": str(e)}


def update_record(table: str, record_id: int, data: dict, db_path: str | None = None) -> dict:
    """Update an existing record. For aliases: appends to existing JSON array."""
    _validate_table(table)
    _validate_columns(table, set(data.keys()) - {"updated_at"})

    with get_db(db_path) as db:
        # Special handling for aliases — append to existing array
        if table == "people" and "aliases" in data:
            new_aliases = data.pop("aliases")
            if isinstance(new_aliases, str):
                try:
                    new_aliases = json.loads(new_aliases)
                except (json.JSONDecodeError, TypeError):
                    new_aliases = [new_aliases]
            if isinstance(new_aliases, list):
                existing = db.execute("SELECT aliases FROM people WHERE id = ?", (int(record_id),)).fetchone()
                if existing and existing["aliases"]:
                    try:
                        current = json.loads(existing["aliases"])
                    except (json.JSONDecodeError, TypeError):
                        current = []
                else:
                    current = []
                # Merge without duplicates
                merged = list(dict.fromkeys(current + new_aliases))
                data["aliases"] = json.dumps(merged, ensure_ascii=False)

        # Set updated_at LEN ak tabuľka má taký stĺpec (interactions/meeting_participants nemajú)
        table_cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if "updated_at" in table_cols:
            data["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [int(record_id)]

        db.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
        updated = db.execute(f"SELECT * FROM {table} WHERE id = ?", (int(record_id),)).fetchone()
        if updated:
            result = {"status": "ok", "record": dict(updated)}
            # Re-embed if content changed (auto-detect via text_hash)
            if table in EMBEDDABLE_TABLES:
                try:
                    emb_res = _embed_and_store(db, table, int(record_id))
                    if emb_res.get("status") in ("indexed", "updated"):
                        result["embedding"] = emb_res["status"]
                except Exception as e:
                    result["embedding_warning"] = str(e)
            return result
        return {"status": "error", "message": f"Record {record_id} not found in {table}"}


def log_interaction(data: dict, db_path: str | None = None) -> dict:
    """Log an interaction with validation + auto-enrichment."""
    # Use add_record for validation + enrichment
    result = add_record("interactions", data, db_path)
    if result.get("status") == "ok" and data.get("person_id"):
        with get_db(db_path) as db:
            db.execute("UPDATE people SET updated_at = ? WHERE id = ?",
                       (datetime.now().isoformat(), data["person_id"]))
    return result


def _find_similar_notes(db, title: str, content: str, limit: int = 3,
                        min_score: float = 0.5) -> list[dict]:
    """Nájde existujúce notes ktoré sú podobné novej (title+content prefix).

    Použité na dedupe warning v add_note.
    """
    if not title and not content:
        return []
    # Build FTS query from title + first 100 chars of content
    query_text = f"{title or ''} {(content or '')[:100]}"
    keywords = [w for w in re.findall(r"\w{4,}", query_text) if w.lower() not in {
        "this", "that", "with", "from", "about", "have", "they", "have", "their",
        "ktorý", "tento", "tato", "alebo", "preto", "veľmi", "velmi",
    }]
    if not keywords:
        return []
    fts_q = " OR ".join(keywords[:8])
    try:
        rows = db.execute(
            "SELECT n.id, n.title, n.category, n.created_at, "
            "  snippet(notes_fts, -1, '«', '»', '…', 20) as preview, "
            "  bm25(notes_fts) as score "
            "FROM notes_fts JOIN notes n ON n.id = notes_fts.rowid "
            "WHERE notes_fts MATCH ? "
            "ORDER BY score LIMIT ?",
            (fts_q, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def add_note(data: dict, db_path: str | None = None,
             skip_dedupe_check: bool = False) -> dict:
    """Add a note to the knowledge base.

    Pred zápisom skontroluje či neexistuje veľmi podobná note (dedupe warning).
    Ak áno, vráti `status='duplicate_warning'` s návrhmi — ak chceš pokračovať
    aj tak, zavolaj znova s `skip_dedupe_check=True`.
    """
    if not skip_dedupe_check and (data.get("title") or data.get("content")):
        with get_db(db_path) as db:
            similar = _find_similar_notes(db, data.get("title", ""), data.get("content", ""))
            if similar:
                return {
                    "status": "duplicate_warning",
                    "code": "SIMILAR_NOTES_EXIST",
                    "similar": similar,
                    "hint": (
                        "Nájdené podobné existujúce notes. Pred vytvorením novej zváž ctx_update "
                        "na existujúcu (id v 'similar'). Ak naozaj chceš novú, zavolaj znova "
                        "s skip_dedupe_check=True."
                    ),
                }
    return add_record("notes", data, db_path)


def find_notes(query: str, domain: str | None = None, category: str | None = None, db_path: str | None = None) -> dict:
    """Search notes with optional domain and category filters."""
    with get_db(db_path) as db:
        conditions = []
        params = []

        # Try FTS first
        try:
            fts_sql = "SELECT n.* FROM notes n JOIN notes_fts f ON n.id = f.rowid WHERE notes_fts MATCH ?"
            fts_params = [query]
            if domain:
                fts_sql += " AND n.domain = ?"
                fts_params.append(domain)
            if category:
                fts_sql += " AND n.category = ?"
                fts_params.append(category)
            fts_sql += " ORDER BY rank LIMIT 20"
            rows = db.execute(fts_sql, fts_params).fetchall()
            if not rows:
                raise Exception("no fts results")
        except Exception:
            like = f"%{query}%"
            sql = "SELECT * FROM notes WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            params = [like, like, like]
            if domain:
                sql += " AND domain = ?"
                params.append(domain)
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " LIMIT 20"
            rows = db.execute(sql, params).fetchall()

        return {"total": len(rows), "notes": [dict(r) for r in rows]}


def get_note(note_id: int, db_path: str | None = None) -> dict:
    """Get a single note by ID."""
    with get_db(db_path) as db:
        note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note:
            return dict(note)
        return {"error": f"Note not found: {note_id}"}


def stats(domain: str | None = None, db_path: str | None = None) -> dict:
    """Overall statistics, optionally filtered by domain."""
    with get_db(db_path) as db:
        result = {}
        d_sql, d_params = _domain_filter(domain)

        for table in ["people", "companies", "projects", "products", "rules", "interactions", "notes"]:
            total = db.execute(f"SELECT COUNT(*) as c FROM {table} WHERE 1=1 {d_sql}", d_params).fetchone()["c"]
            result[table] = {"total": total}

            if table in ["people", "companies", "projects", "products", "rules", "notes"]:
                active = db.execute(f"SELECT COUNT(*) as c FROM {table} WHERE status = 'active' {d_sql}", d_params).fetchone()["c"]
                to_verify = db.execute(f"SELECT COUNT(*) as c FROM {table} WHERE status = 'to_verify' {d_sql}", d_params).fetchone()["c"]
                result[table]["active"] = active
                result[table]["to_verify"] = to_verify

        # Action items stats
        ai_total = db.execute(f"SELECT COUNT(*) as c FROM action_items WHERE 1=1 {d_sql}", d_params).fetchone()["c"]
        ai_extracted = db.execute(f"SELECT COUNT(*) as c FROM action_items WHERE status = 'extracted' {d_sql}", d_params).fetchone()["c"]
        ai_pushed = db.execute(f"SELECT COUNT(*) as c FROM action_items WHERE status = 'pushed_to_asana' {d_sql}", d_params).fetchone()["c"]
        result["action_items"] = {"total": ai_total, "extracted": ai_extracted, "pushed_to_asana": ai_pushed}

        # Decisions stats
        dec_total = db.execute(f"SELECT COUNT(*) as c FROM decisions WHERE 1=1 {d_sql}", d_params).fetchone()["c"]
        result["decisions"] = {"total": dec_total}

        # Meeting participants
        mp_total = db.execute("SELECT COUNT(*) as c FROM meeting_participants").fetchone()["c"]
        result["meeting_participants"] = {"total": mp_total}

        # Domain breakdown (only when not filtering)
        if not domain:
            domains = {}
            for table in ["people", "companies", "projects", "notes"]:
                rows = db.execute(f"SELECT domain, COUNT(*) as c FROM {table} GROUP BY domain").fetchall()
                for r in rows:
                    d = r["domain"] or "unset"
                    if d not in domains:
                        domains[d] = {}
                    domains[d][table] = r["c"]
            result["domains"] = domains

        # Scan status
        scans = db.execute("SELECT * FROM scan_log ORDER BY source").fetchall()
        result["scans"] = {s["source"]: {"last_scan": s["last_scan"], "items_added": s["items_added"]} for s in scans}

        last_interaction = db.execute("SELECT date FROM interactions ORDER BY date DESC LIMIT 1").fetchone()
        result["last_interaction"] = last_interaction["date"] if last_interaction else None

        return result


def stale(days: int = 30, domain: str | None = None, db_path: str | None = None) -> dict:
    """Records not updated for more than N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    d_sql, d_params = _domain_filter(domain)
    result = {}

    with get_db(db_path) as db:
        for table in ["people", "companies", "projects"]:
            rows = db.execute(
                f"SELECT id, name, status, domain, updated_at FROM {table} WHERE updated_at < ? AND status = 'active' {d_sql} ORDER BY updated_at",
                [cutoff] + d_params
            ).fetchall()
            if rows:
                result[table] = [dict(r) for r in rows]

    total = sum(len(v) for v in result.values())
    return {"total_stale": total, "cutoff_days": days, "results": result}


def incomplete(domain: str | None = None, db_path: str | None = None) -> dict:
    """Records with status 'to_verify' or missing key fields."""
    d_sql, d_params = _domain_filter(domain)
    result = {}

    with get_db(db_path) as db:
        rows = db.execute(f"""
            SELECT id, name, email, role, formality, company_name, domain, status
            FROM people
            WHERE (status = 'to_verify' OR email IS NULL OR role IS NULL OR formality = 'uncertain') {d_sql}
            ORDER BY status DESC, name
        """, d_params).fetchall()
        if rows:
            result["people"] = [dict(r) for r in rows]

        rows = db.execute(f"""
            SELECT id, name, status, company_name, domain
            FROM projects
            WHERE (status = 'to_verify' OR description IS NULL OR team IS NULL) {d_sql}
        """, d_params).fetchall()
        if rows:
            result["projects"] = [dict(r) for r in rows]

        rows = db.execute(
            f"SELECT id, name, status, domain FROM companies WHERE status = 'to_verify' {d_sql}",
            d_params
        ).fetchall()
        if rows:
            result["companies"] = [dict(r) for r in rows]

    total = sum(len(v) for v in result.values())
    return {"total_incomplete": total, "results": result}


def recent(days: int = 7, domain: str | None = None, db_path: str | None = None) -> dict:
    """What changed in the last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    d_sql, d_params = _domain_filter(domain)
    result = {}

    with get_db(db_path) as db:
        for table in ["people", "companies", "projects", "products", "rules", "notes"]:
            rows = db.execute(
                f"SELECT * FROM {table} WHERE updated_at > ? {d_sql} ORDER BY updated_at DESC",
                [cutoff] + d_params
            ).fetchall()
            if rows:
                result[table] = [dict(r) for r in rows]

        interactions = db.execute(
            f"SELECT * FROM interactions WHERE date > ? {d_sql} ORDER BY date DESC",
            [cutoff[:10]] + d_params
        ).fetchall()
        if interactions:
            result["interactions"] = [dict(r) for r in interactions]

    total = sum(len(v) for v in result.values())
    return {"total_changes": total, "days": days, "results": result}


def scan_status(db_path: str | None = None) -> list[dict]:
    """Scan status for all sources."""
    with get_db(db_path) as db:
        rows = db.execute("SELECT * FROM scan_log ORDER BY source").fetchall()
        return [dict(r) for r in rows]


def set_scan_marker(source: str, timestamp: str, db_path: str | None = None) -> dict:
    """Set last scan timestamp for a source."""
    with get_db(db_path) as db:
        db.execute(
            "UPDATE scan_log SET last_scan = ?, updated_at = ? WHERE source = ?",
            (timestamp, datetime.now().isoformat(), source)
        )
    return {"status": "ok", "source": source, "last_scan": timestamp}


def update_scan_stats(source: str, processed: int, added: int, updated: int,
                      notes: str = "", db_path: str | None = None) -> dict:
    """Update scan statistics after a scan completes."""
    with get_db(db_path) as db:
        db.execute("""
            UPDATE scan_log
            SET last_scan = ?, items_processed = ?, items_added = ?, items_updated = ?, notes = ?, updated_at = ?
            WHERE source = ?
        """, (datetime.now().isoformat(), processed, added, updated, notes, datetime.now().isoformat(), source))
    return {"status": "ok", "source": source}


def get_action_items(status: str | None = "extracted", owner: str | None = None,
                     project_id: int | None = None, db_path: str | None = None) -> dict:
    """List action items with optional filters."""
    with get_db(db_path) as db:
        sql = "SELECT ai.*, i.summary as meeting_summary, i.date as meeting_date FROM action_items ai LEFT JOIN interactions i ON ai.source_interaction_id = i.id WHERE 1=1"
        params = []
        if status:
            sql += " AND ai.status = ?"
            params.append(status)
        if owner:
            sql += " AND (ai.owner_name LIKE ? OR ai.owner_id = (SELECT id FROM people WHERE name LIKE ? LIMIT 1))"
            params.extend([f"%{owner}%", f"%{owner}%"])
        if project_id:
            sql += " AND ai.related_project_id = ?"
            params.append(project_id)
        sql += " ORDER BY CASE ai.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END, ai.due_date"
        rows = db.execute(sql, params).fetchall()
        return {"total": len(rows), "action_items": [dict(r) for r in rows]}


def mark_action_item_pushed(item_id: int, asana_task_id: str | None = None, db_path: str | None = None) -> dict:
    """Mark an action item as pushed to Asana."""
    now = datetime.now().isoformat()
    with get_db(db_path) as db:
        if asana_task_id:
            db.execute("UPDATE action_items SET status = 'pushed_to_asana', asana_task_id = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                       (asana_task_id, now, now, item_id))
        else:
            db.execute("UPDATE action_items SET status = 'pushed_to_asana', completed_at = ?, updated_at = ? WHERE id = ?", (now, now, item_id))
        item = db.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
        if item:
            return {"status": "ok", "action_item": dict(item)}
        return {"error": f"Action item {item_id} not found"}


def get_decisions(project_id: int | None = None, status: str | None = "active",
                  db_path: str | None = None) -> dict:
    """List decisions with optional filters."""
    with get_db(db_path) as db:
        sql = "SELECT d.*, i.summary as meeting_summary FROM decisions d LEFT JOIN interactions i ON d.source_interaction_id = i.id WHERE 1=1"
        params = []
        if status:
            sql += " AND d.status = ?"
            params.append(status)
        if project_id:
            sql += " AND d.related_project_id = ?"
            params.append(project_id)
        sql += " ORDER BY d.date DESC"
        rows = db.execute(sql, params).fetchall()
        return {"total": len(rows), "decisions": [dict(r) for r in rows]}


def get_meeting_participants(interaction_id: int | None = None, person_id: int | None = None,
                             db_path: str | None = None) -> dict:
    """Get meeting participants — by meeting or by person."""
    with get_db(db_path) as db:
        if interaction_id:
            rows = db.execute("""
                SELECT mp.*, p.name, p.role, p.company_name
                FROM meeting_participants mp
                LEFT JOIN people p ON mp.person_id = p.id
                WHERE mp.interaction_id = ?
            """, (interaction_id,)).fetchall()
            return {"interaction_id": interaction_id, "participants": [dict(r) for r in rows]}
        elif person_id:
            rows = db.execute("""
                SELECT mp.*, i.summary, i.date, i.channel
                FROM meeting_participants mp
                JOIN interactions i ON mp.interaction_id = i.id
                WHERE mp.person_id = ?
                ORDER BY i.date DESC
            """, (person_id,)).fetchall()
            return {"person_id": person_id, "meetings": [dict(r) for r in rows]}
        return {"error": "Provide interaction_id or person_id"}


def export_data(domain: str | None = None, db_path: str | None = None) -> dict:
    """Export entire register as JSON."""
    d_sql, d_params = _domain_filter(domain)
    result = {}

    with get_db(db_path) as db:
        for table in ["companies", "people", "projects", "products", "rules", "notes"]:
            order = "ORDER BY name" if table != "rules" else "ORDER BY priority"
            if table == "notes":
                order = "ORDER BY updated_at DESC"
            rows = db.execute(f"SELECT * FROM {table} WHERE 1=1 {d_sql} {order}", d_params).fetchall()
            result[table] = [dict(r) for r in rows]

    return result


# ─────────────────────────────────────────────────────────────────────
# Layer 4: Advanced search (structured filters)
# ─────────────────────────────────────────────────────────────────────

def search_advanced(
    query: str | None = None,
    table: str | None = None,
    domain: str | None = None,
    category: str | None = None,
    tags_any: list[str] | None = None,
    tags_all: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    person: str | None = None,
    sort: str = "relevance",
    limit: int = 20,
    db_path: str | None = None,
) -> dict:
    """Štruktúrovaný search nad notes/interactions/people s filtrami.

    Vracia matched rows s `_snippet` a `_score` (kde dostupné).
    """
    valid_tables = {"notes", "interactions", "people"}
    if table and table not in valid_tables:
        return {"status": "error", "error": f"table must be one of {valid_tables}"}

    targets = [table] if table else list(valid_tables)
    out: dict = {}

    with get_db(db_path) as db:
        for tbl in targets:
            results = _search_table(
                db, tbl, query=query, domain=domain, category=category,
                tags_any=tags_any, tags_all=tags_all,
                date_from=date_from, date_to=date_to, person=person,
                sort=sort, limit=limit,
            )
            if results:
                out[tbl] = results

    out["total"] = sum(len(v) for v in out.values() if isinstance(v, list))
    out["filters"] = {k: v for k, v in {
        "query": query, "table": table, "domain": domain, "category": category,
        "tags_any": tags_any, "tags_all": tags_all,
        "date_from": date_from, "date_to": date_to,
        "person": person, "sort": sort, "limit": limit,
    }.items() if v is not None}
    return out


def _search_table(db, table: str, query=None, domain=None, category=None,
                  tags_any=None, tags_all=None, date_from=None, date_to=None,
                  person=None, sort="relevance", limit=20) -> list[dict]:
    """Helper — search 1 tabuľky s filtrami."""
    where = ["1=1"]
    params: list = []
    select_extra = ""
    join = ""
    order = "ORDER BY id DESC"

    fts_table_map = {
        "notes": "notes_fts",
        "interactions": "interactions_fts",
        "people": "people_fts",
    }
    fts = fts_table_map.get(table)

    if query and fts:
        select_extra = (
            f", snippet({fts}, -1, '«', '»', '…', 24) AS _snippet, "
            f"bm25({fts}) AS _score"
        )
        join = f"JOIN {fts} ON {fts}.rowid = {table}.id"
        where.append(f"{fts} MATCH ?")
        params.append(query)
        if sort == "relevance":
            order = "ORDER BY _score"
    elif query:
        # No FTS available — LIKE fallback
        like = f"%{query}%"
        if table == "notes":
            where.append("(title LIKE ? OR content LIKE ?)")
            params.extend([like, like])
        elif table == "interactions":
            where.append("(summary LIKE ? OR details LIKE ?)")
            params.extend([like, like])
        elif table == "people":
            where.append("(name LIKE ? OR email LIKE ?)")
            params.extend([like, like])

    if domain:
        where.append(f"{table}.domain = ?")
        params.append(domain)

    if category and table == "notes":
        canonical, _ = normalize_category(category)
        where.append("category = ?")
        params.append(canonical)

    if tags_all:
        for t in tags_all:
            where.append("tags LIKE ?")
            params.append(f"%{t}%")
    if tags_any:
        sub = " OR ".join("tags LIKE ?" for _ in tags_any)
        where.append(f"({sub})")
        for t in tags_any:
            params.append(f"%{t}%")

    if date_from:
        date_col = "date" if table == "interactions" else "created_at"
        where.append(f"{date_col} >= ?")
        params.append(date_from)
    if date_to:
        date_col = "date" if table == "interactions" else "created_at"
        where.append(f"{date_col} <= ?")
        params.append(date_to)

    if person:
        if table == "interactions":
            where.append("person_name LIKE ?")
            params.append(f"%{person}%")
        elif table == "notes":
            # match via related_person_id if person resolves
            p, _mt = _find_person_smart(db, person)
            if p:
                where.append("related_person_id = ?")
                params.append(p["id"])
        elif table == "people":
            where.append("name LIKE ?")
            params.append(f"%{person}%")

    if sort == "recent":
        date_col = "date" if table == "interactions" else "created_at"
        order = f"ORDER BY {date_col} DESC"
    elif sort == "oldest":
        date_col = "date" if table == "interactions" else "created_at"
        order = f"ORDER BY {date_col} ASC"

    sql = (
        f"SELECT {table}.*{select_extra} "
        f"FROM {table} {join} "
        f"WHERE {' AND '.join(where)} "
        f"{order} LIMIT ?"
    )
    params.append(limit)

    try:
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        # Fallback bez FTS
        return [{"_error": str(e)}]


# ─────────────────────────────────────────────────────────────────────
# Layer 6: Health & hygiene tools
# ─────────────────────────────────────────────────────────────────────

def health_report(db_path: str | None = None) -> dict:
    """Coverage report — koľko záznamov má vyplnené metadáta a koľko nie."""
    with get_db(db_path) as db:
        report = {}

        # NOTES
        n = db.execute("SELECT COUNT(*) c FROM notes").fetchone()["c"]
        if n > 0:
            r = db.execute("""
                SELECT
                  SUM(CASE WHEN domain IS NULL OR domain='' THEN 1 ELSE 0 END) miss_domain,
                  SUM(CASE WHEN category IS NULL OR category='' THEN 1 ELSE 0 END) miss_category,
                  SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END) miss_tags,
                  SUM(CASE WHEN source IS NULL OR source='' THEN 1 ELSE 0 END) miss_source,
                  SUM(CASE WHEN related_person_id IS NULL THEN 1 ELSE 0 END) no_person_link
                FROM notes
            """).fetchone()
            # Time markers
            tm_missing = 0
            for row in db.execute("SELECT tags FROM notes WHERE tags IS NOT NULL AND tags != ''"):
                tags = _parse_tags(row["tags"])
                if not has_time_marker(tags):
                    tm_missing += 1
            tm_missing += r["miss_tags"]  # missing tags = no time marker either
            report["notes"] = {
                "total": n,
                "missing_domain": r["miss_domain"],
                "missing_category": r["miss_category"],
                "missing_tags": r["miss_tags"],
                "without_time_marker": tm_missing,
                "missing_source": r["miss_source"],
                "no_person_link": r["no_person_link"],
            }

        # INTERACTIONS
        i = db.execute("SELECT COUNT(*) c FROM interactions").fetchone()["c"]
        if i > 0:
            r = db.execute("""
                SELECT
                  SUM(CASE WHEN details IS NULL OR details='' THEN 1 ELSE 0 END) miss_details,
                  SUM(CASE WHEN topics IS NULL OR topics='' THEN 1 ELSE 0 END) miss_topics,
                  SUM(CASE WHEN key_points IS NULL OR key_points='' THEN 1 ELSE 0 END) miss_keypoints,
                  SUM(CASE WHEN sentiment IS NULL OR sentiment='' THEN 1 ELSE 0 END) miss_sentiment,
                  SUM(CASE WHEN duration_minutes IS NULL THEN 1 ELSE 0 END) miss_duration,
                  SUM(CASE WHEN person_id IS NULL THEN 1 ELSE 0 END) no_person_id
                FROM interactions
            """).fetchone()
            report["interactions"] = {
                "total": i,
                "missing_details": r["miss_details"],
                "missing_topics": r["miss_topics"],
                "missing_key_points": r["miss_keypoints"],
                "missing_sentiment": r["miss_sentiment"],
                "missing_duration_minutes": r["miss_duration"],
                "missing_person_id": r["no_person_id"],
            }

        # PEOPLE
        p = db.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
        if p > 0:
            r = db.execute("""
                SELECT
                  SUM(CASE WHEN formality='uncertain' OR formality IS NULL THEN 1 ELSE 0 END) uncertain_formality,
                  SUM(CASE WHEN tone IS NULL OR tone='' THEN 1 ELSE 0 END) miss_tone,
                  SUM(CASE WHEN relationship IS NULL OR relationship='' THEN 1 ELSE 0 END) miss_rel,
                  SUM(CASE WHEN company_name IS NULL OR company_name='' THEN 1 ELSE 0 END) miss_company,
                  SUM(CASE WHEN tags IS NULL OR tags='' THEN 1 ELSE 0 END) miss_tags
                FROM people
            """).fetchone()
            report["people"] = {
                "total": p,
                "uncertain_formality": r["uncertain_formality"],
                "missing_tone": r["miss_tone"],
                "missing_relationship": r["miss_rel"],
                "missing_company": r["miss_company"],
                "missing_tags": r["miss_tags"],
            }

        # Recommendations
        recs = []
        nx = report.get("notes", {})
        if nx.get("without_time_marker", 0) / max(nx.get("total", 1), 1) > 0.3:
            recs.append(f"Notes — {nx['without_time_marker']}/{nx['total']} bez časového markera. Spusti ctx_backfill_metadata().")
        if nx.get("missing_tags", 0) / max(nx.get("total", 1), 1) > 0.2:
            recs.append(f"Notes — {nx['missing_tags']}/{nx['total']} bez tagov. Spusti ctx_backfill_metadata().")
        ix = report.get("interactions", {})
        if ix.get("missing_details", 0) / max(ix.get("total", 1), 1) > 0.5:
            recs.append(f"Interactions — {ix['missing_details']}/{ix['total']} bez details. Pridať z fireflies pri budúcich logoch.")
        px = report.get("people", {})
        if px.get("missing_tags", 0) / max(px.get("total", 1), 1) > 0.7:
            recs.append(f"People — {px['missing_tags']}/{px['total']} bez tagov. Pridávaj tagy pri komunikácii.")

        report["recommendations"] = recs
        return report


def find_duplicates(table: str = "notes", threshold: float = 0.85,
                    db_path: str | None = None) -> dict:
    """Nájde pravdepodobné duplicity na základe fuzzy match key fieldov."""
    if table not in {"notes", "people", "companies"}:
        return {"status": "error", "error": "table must be notes/people/companies"}

    duplicates: list[dict] = []

    with get_db(db_path) as db:
        if table == "notes":
            rows = db.execute("SELECT id, title, category, created_at FROM notes ORDER BY id").fetchall()
            for i in range(len(rows)):
                for j in range(i + 1, min(i + 50, len(rows))):  # window 50 to avoid n²
                    a, b = rows[i]["title"] or "", rows[j]["title"] or ""
                    if not a or not b:
                        continue
                    score = SequenceMatcher(None, a.lower(), b.lower()).ratio()
                    if score >= threshold:
                        duplicates.append({
                            "id_a": rows[i]["id"], "title_a": a,
                            "id_b": rows[j]["id"], "title_b": b,
                            "score": round(score, 2),
                        })
        elif table == "people":
            rows = db.execute("SELECT id, name, email FROM people").fetchall()
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, b = (rows[i]["name"] or "").lower(), (rows[j]["name"] or "").lower()
                    if not a or not b:
                        continue
                    score = SequenceMatcher(None, a, b).ratio()
                    # Same email = sure dupe
                    same_email = (rows[i]["email"] and rows[i]["email"] == rows[j]["email"])
                    if score >= threshold or same_email:
                        duplicates.append({
                            "id_a": rows[i]["id"], "name_a": rows[i]["name"], "email_a": rows[i]["email"],
                            "id_b": rows[j]["id"], "name_b": rows[j]["name"], "email_b": rows[j]["email"],
                            "score": round(score, 2),
                            "same_email": bool(same_email),
                        })
        elif table == "companies":
            rows = db.execute("SELECT id, name FROM companies").fetchall()
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, b = (rows[i]["name"] or "").lower(), (rows[j]["name"] or "").lower()
                    score = SequenceMatcher(None, a, b).ratio()
                    if score >= threshold:
                        duplicates.append({
                            "id_a": rows[i]["id"], "name_a": rows[i]["name"],
                            "id_b": rows[j]["id"], "name_b": rows[j]["name"],
                            "score": round(score, 2),
                        })

    return {"table": table, "threshold": threshold, "count": len(duplicates), "duplicates": duplicates}


def find_orphans(db_path: str | None = None) -> dict:
    """Nájde záznamy bez správnych väzieb (notes bez person/project, interactions bez person_id, atď.)."""
    out = {}
    with get_db(db_path) as db:
        out["notes_without_person_link"] = [dict(r) for r in db.execute(
            "SELECT id, title, category, created_at FROM notes "
            "WHERE related_person_id IS NULL AND related_project_id IS NULL "
            "ORDER BY created_at DESC LIMIT 50"
        ).fetchall()]
        out["interactions_without_person_id"] = [dict(r) for r in db.execute(
            "SELECT id, person_name, channel, summary, date FROM interactions "
            "WHERE person_id IS NULL AND person_name IS NOT NULL "
            "ORDER BY date DESC LIMIT 50"
        ).fetchall()]
        out["people_without_company_link"] = [dict(r) for r in db.execute(
            "SELECT id, name, email, role FROM people "
            "WHERE (company_id IS NULL OR company_id = 0) AND status = 'active' "
            "ORDER BY name LIMIT 50"
        ).fetchall()]
        out["counts"] = {k: len(v) for k, v in out.items()}
    return out


def backfill_metadata(db_path: str | None = None, dry_run: bool = False) -> dict:
    """One-time migration:
    1. Normalizuje category v notes (alias → canonical)
    2. Doplní time marker do tagov ak chýba (z created_at)
    3. Doplní domain z category mapping ak chýba
    4. Auto-link mentioned people v notes content → related_person_id
    """
    stats = {
        "notes_processed": 0,
        "categories_normalized": 0,
        "time_markers_added": 0,
        "domains_filled": 0,
        "person_links_added": 0,
        "interactions_person_id_resolved": 0,
    }

    with get_db(db_path) as db:
        notes = db.execute("SELECT * FROM notes").fetchall()
        for n in notes:
            stats["notes_processed"] += 1
            updates: dict = {}

            # 1. Normalize category
            current_cat = n["category"]
            canonical, was_normalized = normalize_category(current_cat)
            if was_normalized and current_cat:
                updates["category"] = canonical
                stats["categories_normalized"] += 1

            # 2. Fill domain from category
            if (not n["domain"]) and (canonical or current_cat):
                cat_for_domain = canonical or current_cat
                derived = DOMAIN_FROM_CATEGORY.get(cat_for_domain)
                if derived:
                    updates["domain"] = derived
                    stats["domains_filled"] += 1

            # 3. Add time marker to tags
            tags = _parse_tags(n["tags"])
            if not has_time_marker(tags):
                tm = auto_time_marker(n["created_at"])
                tags.append(tm)
                # Add quarter as bonus
                qt = quarter_marker(n["created_at"])
                if qt not in tags:
                    tags.append(qt)
                updates["tags"] = json.dumps(tags, ensure_ascii=False)
                stats["time_markers_added"] += 1

            # 4. Auto-link mentioned person
            if n["related_person_id"] is None and n["content"]:
                mentioned = _detect_mentioned_people(db, n["content"], limit=1)
                if mentioned:
                    updates["related_person_id"] = mentioned[0]
                    stats["person_links_added"] += 1

            if updates and not dry_run:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [datetime.now().isoformat(), n["id"]]
                db.execute(
                    f"UPDATE notes SET {set_clause}, updated_at = ? WHERE id = ?",
                    vals,
                )

        # 5. Resolve missing person_id in interactions
        unresolved = db.execute(
            "SELECT id, person_name FROM interactions WHERE person_id IS NULL AND person_name IS NOT NULL"
        ).fetchall()
        for row in unresolved:
            person, _mt = _find_person_smart(db, row["person_name"])
            if person and not dry_run:
                db.execute("UPDATE interactions SET person_id = ? WHERE id = ?",
                           (person["id"], row["id"]))
                stats["interactions_person_id_resolved"] += 1
            elif person:
                stats["interactions_person_id_resolved"] += 1

    stats["dry_run"] = dry_run
    return stats


def categories_list() -> dict:
    """Vráti zoznam povolených category s popismi + aliasy + DOMAIN mapping."""
    return {
        "categories": CATEGORIES,
        "aliases": CATEGORY_ALIASES,
        "domain_mapping": DOMAIN_FROM_CATEGORY,
        "domains": sorted(DOMAINS),
        "channels": sorted(CHANNELS),
        "sentiments": sorted(SENTIMENTS),
        "formalities": sorted(FORMALITIES),
        "tones": sorted(TONES),
        "relationships": sorted(RELATIONSHIPS),
        "hint": (
            "Pri ctx_add_note POVINNÉ vyplniť: title, content, domain, category, tags, source. "
            "Tags MUSIA obsahovať časový marker (napr. '2026-W17' alebo 'Q2-2026'). "
            "Ak je category alias (napr. 'meeting'), automaticky sa normalizuje na canonical ('meeting-notes')."
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# Semantic search layer (sqlite-vec + Voyage AI embeddings)
# ─────────────────────────────────────────────────────────────────────

# Tabuľky ktoré chceme indexovať pre semantic search
EMBEDDABLE_TABLES = {"notes", "interactions", "people", "companies", "projects"}


def _vec_supported(db) -> bool:
    """Test či vec0 tabuľka existuje (sqlite-vec loaded + migration prebehla)."""
    try:
        db.execute("SELECT 1 FROM embeddings LIMIT 1").fetchone()
        return True
    except Exception:
        return False


def _embed_and_store(db, table: str, row_id: int, *, model: str | None = None) -> dict:
    """Vyrobí embedding pre daný record (cez build_embedding_text), uloží do vec0.
    Idempotentné cez text_hash — re-embed len ak sa text zmenil."""
    if not _EMBEDDINGS_AVAILABLE or not _emb:
        return {"status": "skipped", "reason": "embeddings module unavailable"}

    if table not in EMBEDDABLE_TABLES:
        return {"status": "skipped", "reason": f"table {table} not embeddable"}

    if not _vec_supported(db):
        return {"status": "skipped", "reason": "sqlite-vec not loaded"}

    if not _emb.is_available():
        return {"status": "skipped", "reason": "VOYAGE_API not set"}

    model = model or _emb.DEFAULT_MODEL

    # Fetch the row
    row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not row:
        return {"status": "error", "reason": f"row {table}:{row_id} not found"}

    text = _emb.build_embedding_text(table, dict(row))
    if not text or len(text) < 3:
        return {"status": "skipped", "reason": "empty text"}

    new_hash = _emb.text_hash(text)

    # Check existing — skip if hash matches
    existing = db.execute(
        "SELECT id, text_hash, embedding_id FROM embedding_index WHERE table_name = ? AND row_id = ? AND model = ?",
        (table, row_id, model)
    ).fetchone()

    if existing and existing["text_hash"] == new_hash:
        return {"status": "skipped", "reason": "hash match", "embedding_id": existing["embedding_id"]}

    # Embed (single API call)
    try:
        vector = _emb.embed_single(text, model=model, input_type="document")
    except Exception as e:
        return {"status": "error", "reason": f"voyage embed failed: {e}"}

    blob = _emb.serialize_vector(vector)

    if existing:
        # Update existing embedding — replace vec0 row + update mapping hash
        db.execute("UPDATE embeddings SET embedding = ? WHERE id = ?", (blob, existing["embedding_id"]))
        db.execute(
            "UPDATE embedding_index SET text_hash = ?, created_at = ? WHERE id = ?",
            (new_hash, datetime.now().isoformat(), existing["id"])
        )
        return {"status": "updated", "embedding_id": existing["embedding_id"]}
    else:
        # New embedding — insert into vec0 (auto id), then mapping
        cur = db.execute("INSERT INTO embeddings(embedding) VALUES (?)", (blob,))
        emb_id = cur.lastrowid
        db.execute(
            "INSERT INTO embedding_index(table_name, row_id, text_hash, model, embedding_id) VALUES (?, ?, ?, ?, ?)",
            (table, row_id, new_hash, model, emb_id)
        )
        return {"status": "indexed", "embedding_id": emb_id}


def index_embeddings(table: str | None = None, force_reindex: bool = False,
                     limit: int | None = None, batch_size: int = 64,
                     db_path: str | None = None) -> dict:
    """Backfill embeddings pre existujúce records. Idempotentné.

    Batch-aware: posiela až `batch_size` textov per Voyage API call (max 128),
    čo je 100× rýchlejšie na rate-limited free tier.

    table=None → všetky EMBEDDABLE_TABLES.
    force_reindex=True → pre-embed aj keď text_hash matchuje (zmena modelu).
    limit → max N records na batch (užitočné pre dry runs).
    batch_size → koľko textov per Voyage API call (default 64, max 128).
    """
    if not _EMBEDDINGS_AVAILABLE:
        return {"status": "error", "reason": "embeddings module unavailable"}

    batch_size = max(1, min(int(batch_size), 128))
    targets = [table] if table else sorted(EMBEDDABLE_TABLES)
    stats = {"per_table": {}, "total_indexed": 0, "total_updated": 0,
             "total_skipped": 0, "total_errors": 0, "first_errors": []}

    with get_db(db_path) as db:
        if not _vec_supported(db):
            return {"status": "error", "reason": "sqlite-vec not loaded — install pysqlite3 + sqlite-vec"}
        if not _emb.is_available():
            return {"status": "error", "reason": "VOYAGE_API env var not set"}

        model = _emb.DEFAULT_MODEL

        for tbl in targets:
            if tbl not in EMBEDDABLE_TABLES:
                continue
            sql = f"SELECT * FROM {tbl}"
            if limit:
                sql += f" LIMIT {int(limit)}"
            rows = db.execute(sql).fetchall()

            indexed = updated = skipped = errors = 0
            first_error_examples: list[dict] = []

            # Pre-compute texts + check existing hashes
            pending: list[tuple[int, str, str]] = []  # (row_id, text, hash)
            for row in rows:
                rid = row["id"]

                if force_reindex:
                    existing = db.execute(
                        "SELECT embedding_id FROM embedding_index WHERE table_name = ? AND row_id = ?",
                        (tbl, rid)
                    ).fetchone()
                    if existing:
                        db.execute("DELETE FROM embeddings WHERE id = ?", (existing["embedding_id"],))
                        db.execute("DELETE FROM embedding_index WHERE table_name = ? AND row_id = ?",
                                   (tbl, rid))

                text = _emb.build_embedding_text(tbl, dict(row))
                if not text or len(text) < 3:
                    skipped += 1
                    continue
                new_hash = _emb.text_hash(text)

                # Skip if hash matches existing (idempotent)
                existing = db.execute(
                    "SELECT text_hash FROM embedding_index WHERE table_name = ? AND row_id = ? AND model = ?",
                    (tbl, rid, model)
                ).fetchone()
                if existing and existing["text_hash"] == new_hash:
                    skipped += 1
                    continue

                pending.append((rid, text, new_hash))

            # Batch embed pending
            for i in range(0, len(pending), batch_size):
                batch = pending[i : i + batch_size]
                texts = [b[1] for b in batch]
                try:
                    vectors = _emb.embed_texts(texts, model=model, input_type="document")
                except Exception as e:
                    errors += len(batch)
                    if len(first_error_examples) < 5:
                        first_error_examples.append({
                            "table": tbl, "batch_size": len(batch),
                            "reason": f"voyage batch failed: {str(e)[:300]}",
                        })
                    continue

                for (rid, _text, new_hash), vector in zip(batch, vectors):
                    blob = _emb.serialize_vector(vector)
                    existing = db.execute(
                        "SELECT id, embedding_id FROM embedding_index WHERE table_name = ? AND row_id = ? AND model = ?",
                        (tbl, rid, model)
                    ).fetchone()
                    try:
                        if existing:
                            db.execute("UPDATE embeddings SET embedding = ? WHERE id = ?",
                                       (blob, existing["embedding_id"]))
                            db.execute(
                                "UPDATE embedding_index SET text_hash = ?, created_at = ? WHERE id = ?",
                                (new_hash, datetime.now().isoformat(), existing["id"])
                            )
                            updated += 1
                        else:
                            cur = db.execute("INSERT INTO embeddings(embedding) VALUES (?)", (blob,))
                            emb_id = cur.lastrowid
                            db.execute(
                                "INSERT INTO embedding_index(table_name, row_id, text_hash, model, embedding_id) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (tbl, rid, new_hash, model, emb_id)
                            )
                            indexed += 1
                    except Exception as e:
                        errors += 1
                        if len(first_error_examples) < 5:
                            first_error_examples.append({
                                "table": tbl, "row_id": rid,
                                "reason": f"db write failed: {str(e)[:200]}",
                            })

            stats["per_table"][tbl] = {
                "total": len(rows), "indexed": indexed, "updated": updated,
                "skipped": skipped, "errors": errors,
            }
            stats["total_indexed"] += indexed
            stats["total_updated"] += updated
            stats["total_skipped"] += skipped
            stats["total_errors"] += errors
            stats["first_errors"].extend(first_error_examples)

    stats["model"] = _emb.DEFAULT_MODEL
    stats["batch_size_used"] = batch_size
    return stats


def search_semantic(query: str, table: str | None = None, limit: int = 10,
                    hybrid: bool = True, db_path: str | None = None) -> dict:
    """Semantic search — embed query, find nearest vectors, optionally fuse with FTS5.

    Args:
        query: free text search
        table: 'notes' | 'interactions' | 'people' | 'companies' | 'projects' | None (all)
        limit: top N results to return (per table if multi-table)
        hybrid: if True, fuse with FTS5 BM25 results via Reciprocal Rank Fusion

    Returns dict with `results` per table — each row enriched with
    `_semantic_score`, optionally `_bm25_score`, `_fused_score`, `_snippet`.
    """
    if not _EMBEDDINGS_AVAILABLE:
        return {"status": "error", "reason": "embeddings module unavailable"}

    targets = [table] if table else sorted(EMBEDDABLE_TABLES)
    out: dict = {"query": query, "model": _emb.DEFAULT_MODEL, "hybrid": hybrid, "results": {}}

    with get_db(db_path) as db:
        if not _vec_supported(db):
            return {"status": "error", "reason": "sqlite-vec not loaded"}
        if not _emb.is_available():
            return {"status": "error", "reason": "VOYAGE_API env var not set"}

        try:
            q_vector = _emb.embed_single(query, input_type="query")
        except Exception as e:
            return {"status": "error", "reason": f"voyage embed query failed: {e}"}
        q_blob = _emb.serialize_vector(q_vector)

        for tbl in targets:
            if tbl not in EMBEDDABLE_TABLES:
                continue

            # Top K via vector distance
            sem_rows = db.execute(f"""
                SELECT
                    t.*,
                    vec_distance_cosine(e.embedding, ?) AS _semantic_distance
                FROM embeddings e
                JOIN embedding_index ei ON ei.embedding_id = e.id
                JOIN {tbl} t ON t.id = ei.row_id
                WHERE ei.table_name = ?
                ORDER BY _semantic_distance ASC
                LIMIT ?
            """, (q_blob, tbl, limit * 5 if hybrid else limit)).fetchall()

            sem_ranking = [(tbl, r["id"], 1.0 - r["_semantic_distance"]) for r in sem_rows]

            if not hybrid:
                results = []
                for r in sem_rows[:limit]:
                    d = dict(r)
                    d["_semantic_score"] = round(1.0 - d["_semantic_distance"], 4)
                    results.append(d)
                if results:
                    out["results"][tbl] = results
                continue

            # Hybrid — fetch BM25 results too
            bm25_rows = []
            fts_table = {"notes": "notes_fts", "interactions": "interactions_fts",
                         "people": "people_fts", "companies": "companies_fts",
                         "projects": "projects_fts"}.get(tbl)
            if fts_table:
                try:
                    bm25_rows = db.execute(f"""
                        SELECT t.*,
                               snippet({fts_table}, -1, '«', '»', '…', 24) AS _snippet,
                               bm25({fts_table}) AS _bm25
                        FROM {fts_table} JOIN {tbl} t ON t.id = {fts_table}.rowid
                        WHERE {fts_table} MATCH ?
                        ORDER BY _bm25
                        LIMIT ?
                    """, (query, limit * 5)).fetchall()
                except Exception:
                    bm25_rows = []

            bm25_ranking = [(tbl, r["id"], -r["_bm25"]) for r in bm25_rows]  # negated bm25 = higher better

            # RRF fuse
            fused = _emb.reciprocal_rank_fusion([sem_ranking, bm25_ranking])

            # Build combined dicts
            sem_lookup = {r["id"]: r for r in sem_rows}
            bm25_lookup = {r["id"]: r for r in bm25_rows}

            results = []
            for _t, rid, fscore in fused[:limit]:
                row = bm25_lookup.get(rid) or sem_lookup.get(rid)
                if not row:
                    continue
                d = dict(row)
                if rid in sem_lookup:
                    d["_semantic_score"] = round(1.0 - sem_lookup[rid]["_semantic_distance"], 4)
                if rid in bm25_lookup:
                    d["_bm25_score"] = round(-bm25_lookup[rid]["_bm25"], 4)
                    if "_snippet" in dict(bm25_lookup[rid]):
                        d["_snippet"] = bm25_lookup[rid]["_snippet"]
                d["_fused_score"] = round(fscore, 4)
                results.append(d)

            if results:
                out["results"][tbl] = results

    out["total"] = sum(len(v) for v in out["results"].values())
    return out


def find_similar(table: str, row_id: int, limit: int = 5,
                 cross_table: bool = False, db_path: str | None = None) -> dict:
    """Nájdi podobné records k danému (cez ich embedding distance).

    cross_table=True → hľadaj naprieč všetkými EMBEDDABLE_TABLES.
    """
    if not _EMBEDDINGS_AVAILABLE:
        return {"status": "error", "reason": "embeddings module unavailable"}

    with get_db(db_path) as db:
        if not _vec_supported(db):
            return {"status": "error", "reason": "sqlite-vec not loaded"}

        # Get the source embedding
        src = db.execute(
            "SELECT e.id, e.embedding FROM embedding_index ei "
            "JOIN embeddings e ON e.id = ei.embedding_id "
            "WHERE ei.table_name = ? AND ei.row_id = ?",
            (table, row_id)
        ).fetchone()

        if not src:
            return {"status": "error", "reason": f"no embedding for {table}:{row_id} — run ctx_index_embeddings"}

        src_blob = src["embedding"]
        out: dict = {"source": {"table": table, "id": row_id}, "results": {}}

        targets = sorted(EMBEDDABLE_TABLES) if cross_table else [table]
        for tbl in targets:
            rows = db.execute(f"""
                SELECT t.*, vec_distance_cosine(e.embedding, ?) AS _distance
                FROM embeddings e
                JOIN embedding_index ei ON ei.embedding_id = e.id
                JOIN {tbl} t ON t.id = ei.row_id
                WHERE ei.table_name = ?
                  AND NOT (ei.table_name = ? AND ei.row_id = ?)
                ORDER BY _distance ASC
                LIMIT ?
            """, (src_blob, tbl, table, row_id, limit)).fetchall()

            if rows:
                out["results"][tbl] = [
                    {**dict(r), "_similarity": round(1.0 - r["_distance"], 4)}
                    for r in rows
                ]

        return out


def embeddings_stats(db_path: str | None = None) -> dict:
    """Health stats pre embedding layer — koľko records je indexovaných, stale, missing."""
    out: dict = {"available": _EMBEDDINGS_AVAILABLE,
                 "voyage_configured": _emb.is_available() if _EMBEDDINGS_AVAILABLE else False,
                 "model": _emb.DEFAULT_MODEL if _EMBEDDINGS_AVAILABLE else None,
                 "diagnostic": _emb.diagnostic_info() if _EMBEDDINGS_AVAILABLE else None,
                 "per_table": {}}

    with get_db(db_path) as db:
        if not _vec_supported(db):
            out["sqlite_vec_loaded"] = False
            return out
        out["sqlite_vec_loaded"] = True

        total_indexed = db.execute("SELECT COUNT(*) c FROM embedding_index").fetchone()["c"]
        out["total_indexed"] = total_indexed

        for tbl in sorted(EMBEDDABLE_TABLES):
            try:
                total = db.execute(f"SELECT COUNT(*) c FROM {tbl}").fetchone()["c"]
                indexed = db.execute(
                    "SELECT COUNT(*) c FROM embedding_index WHERE table_name = ?",
                    (tbl,)
                ).fetchone()["c"]
                out["per_table"][tbl] = {
                    "total_rows": total,
                    "indexed": indexed,
                    "missing": max(0, total - indexed),
                }
            except Exception as e:
                out["per_table"][tbl] = {"error": str(e)}

    return out
