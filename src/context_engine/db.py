"""SQLite database layer for Context Engine."""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from difflib import SequenceMatcher
from context_engine.nicknames import expand_query_names, surname_similarity, FUZZY_THRESHOLD

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
                     "context", "date", "source_ref", "domain"},
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


@contextmanager
def get_db(db_path: str | None = None):
    """Context manager for database connections."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
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


def init_db(db_path: str | None = None) -> dict:
    """Create database with full schema."""
    with get_db(db_path) as db:
        db.executescript(SCHEMA_SQL)
        _migrate(db)
        for source in SCAN_SOURCES:
            db.execute("INSERT OR IGNORE INTO scan_log (source) VALUES (?)", (source,))
        db.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (3)")
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

        # Companies
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

        # Notes — FTS with LIKE fallback
        try:
            rows = db.execute(
                f"SELECT n.* FROM notes n JOIN notes_fts f ON n.id = f.rowid WHERE notes_fts MATCH ? {('AND n.domain = ?' if domain else '')} ORDER BY rank LIMIT 20",
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

        # Recent interactions
        interactions = db.execute(
            "SELECT * FROM interactions WHERE person_id = ? ORDER BY date DESC LIMIT 10",
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

        # Last 5 interactions
        interactions = db.execute(
            "SELECT channel, direction, summary, date FROM interactions WHERE person_id = ? ORDER BY date DESC LIMIT 5",
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


def add_record(table: str, data: dict, db_path: str | None = None) -> dict:
    """Add a record to a table with validation."""
    _validate_table(table)
    columns_to_write = set(data.keys())
    valid = VALID_COLUMNS.get(table, set()) | {"name", "title", "context", "rule", "person_id",
                                                 "person_name", "channel", "direction", "summary",
                                                 "date", "source_ref", "created_at", "first_seen",
                                                 "email", "phone", "company_id"}
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
            return {"status": "ok", "id": cursor.lastrowid, "table": table}
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

        data["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [int(record_id)]

        db.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
        updated = db.execute(f"SELECT * FROM {table} WHERE id = ?", (int(record_id),)).fetchone()
        if updated:
            return {"status": "ok", "record": dict(updated)}
        return {"status": "error", "message": f"Record {record_id} not found in {table}"}


def log_interaction(data: dict, db_path: str | None = None) -> dict:
    """Log an interaction."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?" for _ in data])
    values = list(data.values())

    with get_db(db_path) as db:
        cursor = db.execute(f"INSERT INTO interactions ({columns}) VALUES ({placeholders})", values)
        if "person_id" in data:
            db.execute("UPDATE people SET updated_at = ? WHERE id = ?",
                       (datetime.now().isoformat(), data["person_id"]))
        return {"status": "ok", "id": cursor.lastrowid}


def add_note(data: dict, db_path: str | None = None) -> dict:
    """Add a note to the knowledge base."""
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
