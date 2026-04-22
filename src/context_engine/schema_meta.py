"""Controlled vocabulary, validation rules, and auto-enrichment maps for Context Engine.

Toto je "schema-aware" vrstva — definuje:
- platne hodnoty pre domain, category, sentiment...
- mapy na normalizaciu (alias → canonical)
- mapping pravidla pre auto-enrichment (category → domain, atď.)
"""

from __future__ import annotations
import re
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────────────
# DOMAINS — zatvoreny zoznam
# ─────────────────────────────────────────────────────────────────────

DOMAINS: set[str] = {
    "work", "personal", "family", "health", "finance", "home", "education",
}

# ─────────────────────────────────────────────────────────────────────
# CATEGORIES — controlled vocabulary pre `notes.category`
# Kľúč = canonical, hodnota = ľudský popis (pre Claude tooltip)
# ─────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, str] = {
    # Work / ops
    "ops-summary": "Operatívny súhrn (chat/meeting summary, denný/týždenný update)",
    "weekly-review": "Týždenný review výkonu, retrospektíva",
    "monthly-review": "Mesačný review",
    "decision": "Zaznamenané rozhodnutie + jeho odôvodnenie",
    "strategy": "Strategická myšlienka, dlhodobý plán",
    "priority": "Krátkodobá priorita, fokus",
    "weekly-plan": "Týždenný plán",
    "milestone": "Míľnik (project, business, personal)",
    "run-metrics": "Operatívne metriky (tržby, KPI, čísla)",

    # Knowledge / reference
    "reference": "Referenčná informácia, fact, lookup",
    "insight": "Aha moment, lesson learned, pattern",
    "idea": "Nápad (ešte nezrealizovaný)",
    "question": "Otázka na zodpovedanie",
    "todo": "Krátka úloha (alternatíva k action_items pre veci bez deadline)",

    # Meetings & community
    "meeting-notes": "Detailný zápis z meetingu (vrátane fireflies)",
    "q&a": "Q&A session, otázky a odpovede",
    "session-recap": "Krátke zhrnutie session/eventu",

    # Business / sales / deals
    "deal-analysis": "Analýza dealu, term sheet, akvizícia",
    "pricing": "Cenotvorba, pricing strategy",
    "competitor-analysis": "Analýza konkurencie",
    "client-communication": "Záznam komunikácie s klientom",
    "offer-process": "Vývoj offer-u, ponukový proces",

    # Marketing / content
    "content-pattern": "Content pattern, swipe, štruktúra obsahu",
    "messaging": "Messaging, positioning, copy",
    "marketing": "Marketing nápad/kampaň/insight",
    "branding": "Brand, identita",

    # Education / bootcamp
    "bootcamp-notes": "Claude Bootcamp lekcia/zápis",
    "lecture": "Lekcia, prednáška",
    "course-content": "Kurzový obsah",
    "mentoring": "Mentoring sessions",

    # Personal / lifestyle
    "personal-reflection": "Osobná reflexia",
    "health-record": "Zdravotný záznam",
    "family-event": "Rodinná udalosť",
    "home-maintenance": "Údržba domu, dodávatelia",

    # Tech / infrastructure
    "infrastructure": "Tech infraštruktúra, deployment",
    "architecture": "Architektonické rozhodnutie, design",
    "tech": "Technická poznámka (bez konkrétnej kategórie)",
    "ai-tools": "AI tools, prompty, automatizácie",
    "workflow": "Workflow / proces popis",

    # Misc
    "other": "Iné — použi LEN ak žiadna iná kategória nesedí",
}

# Normalizačná mapa — alias → canonical category
# Pri pridávaní raw category sa najprv pozrie sem
CATEGORY_ALIASES: dict[str, str] = {
    # ops variants
    "ops/chat summary": "ops-summary",
    "ops/chat-summary": "ops-summary",
    "chat-summary": "ops-summary",
    "operations": "ops-summary",
    "ops": "ops-summary",
    # meeting variants
    "meeting": "meeting-notes",
    "meeting_note": "meeting-notes",
    "meeting_notes": "meeting-notes",
    "meeting-info": "meeting-notes",
    # decision variants
    "decisions": "decision",
    "rozhodnutie": "decision",
    # strategy variants
    "strategy_analysis": "strategy",
    "business-analysis": "strategy",
    "business-insight": "insight",
    "business_update": "ops-summary",
    # deal variants
    "deal_analysis": "deal-analysis",
    "debt_analysis": "deal-analysis",
    # priority variants
    "priorities": "priority",
    # plan variants
    "weekly-reflection": "weekly-review",
    "reflexia": "personal-reflection",
    # other common typos
    "rule": "reference",
    "protocol": "reference",
    "automatizácia": "ai-tools",
    "tech": "tech",
    "technology": "tech",
    "presentation-learnings": "lecture",
    "writing-style": "content-pattern",
    "youtube-inspiration": "content-pattern",
    # SK → EN
    "rodina": "family-event",
    "bývanie": "home-maintenance",
    "nákup": "home-maintenance",
    "účtovníctvo": "finance",
    "zmluva": "reference",
    "právny dokument": "reference",
    "ponuka": "offer-process",
    "produkt": "milestone",
    "sales": "client-communication",
    "sales-lead": "client-communication",
    "prieskum": "competitor-analysis",
    "media": "marketing",
    "media_research": "marketing",
    "research": "reference",
    "market-research": "competitor-analysis",
    "vendor-comparison": "competitor-analysis",
    "benchmark": "competitor-analysis",
    "feedback": "insight",
    # bootcamp variants
    "bootcamp": "bootcamp-notes",
    "bootcamp-delivery": "bootcamp-notes",
    "bootcamp-schedule": "bootcamp-notes",
    # finance
    "revenue": "run-metrics",
    "trading-analysis": "deal-analysis",
}


def normalize_category(raw: str | None) -> tuple[str, bool]:
    """Vráti (canonical_category, was_normalized).

    1. Ak je raw priamo v CATEGORIES → vráti raw, False
    2. Ak je raw v CATEGORY_ALIASES → vráti canonical, True
    3. Inak vráti 'other', True (aj malo by sa logovať warning)
    """
    if not raw:
        return ("other", True)
    raw_clean = raw.strip().lower()
    if raw_clean in CATEGORIES:
        return (raw_clean, False)
    if raw_clean in CATEGORY_ALIASES:
        return (CATEGORY_ALIASES[raw_clean], True)
    return ("other", True)


# ─────────────────────────────────────────────────────────────────────
# DOMAIN_FROM_CATEGORY — auto-derive domain
# ─────────────────────────────────────────────────────────────────────

DOMAIN_FROM_CATEGORY: dict[str, str] = {
    # Work
    "ops-summary": "work", "weekly-review": "work", "monthly-review": "work",
    "decision": "work", "strategy": "work", "priority": "work",
    "weekly-plan": "work", "milestone": "work", "run-metrics": "work",
    "meeting-notes": "work", "q&a": "work", "session-recap": "work",
    "client-communication": "work", "offer-process": "work",
    "competitor-analysis": "work", "pricing": "work",
    "content-pattern": "work", "messaging": "work", "marketing": "work",
    "branding": "work", "infrastructure": "work", "architecture": "work",
    "tech": "work", "ai-tools": "work", "workflow": "work",
    # Education
    "bootcamp-notes": "education", "lecture": "education",
    "course-content": "education", "mentoring": "education",
    # Finance
    "deal-analysis": "finance",
    # Personal
    "personal-reflection": "personal", "insight": "personal",
    "idea": "personal", "question": "personal", "todo": "personal",
    "reference": "personal",  # default — can be overridden per note
    # Health
    "health-record": "health",
    # Family
    "family-event": "family",
    # Home
    "home-maintenance": "home",
}


# ─────────────────────────────────────────────────────────────────────
# SENTIMENT — controlled values
# ─────────────────────────────────────────────────────────────────────

SENTIMENTS: set[str] = {"positive", "neutral", "negative", "mixed"}


# ─────────────────────────────────────────────────────────────────────
# CHANNELS — controlled values pre interactions.channel
# ─────────────────────────────────────────────────────────────────────

CHANNELS: set[str] = {
    "email", "slack", "asana", "call", "meeting", "sms",
    "whatsapp", "telegram", "linkedin", "in-person", "video-call",
}


# ─────────────────────────────────────────────────────────────────────
# FORMALITY, TONE, RELATIONSHIP — controlled values pre people
# ─────────────────────────────────────────────────────────────────────

FORMALITIES: set[str] = {"ty", "vy", "uncertain"}
TONES: set[str] = {"formalny", "priatelsky", "vecny", "neformalny", "uncertain"}
RELATIONSHIPS: set[str] = {
    "klient", "partner", "tim", "vendor", "kontakt",
    "mentor", "mentee", "investor", "speaker", "novinar",
    "rodina", "priatel", "kolega", "uncertain",
}


# ─────────────────────────────────────────────────────────────────────
# TIME MARKER UTILS — pre tagy
# ─────────────────────────────────────────────────────────────────────

TIME_PATTERN = re.compile(
    r"(20\d{2}-W\d{1,2}|Q[1-4]-20\d{2}|20\d{2}-\d{2}-\d{2}|20\d{2}-\d{2})"
)


def has_time_marker(tags: list[str]) -> bool:
    """True ak aspoň jeden tag matchuje časový pattern."""
    return any(TIME_PATTERN.search(t) for t in tags if isinstance(t, str))


def auto_time_marker(date_str: str | None = None) -> str:
    """Vráti časový marker tag pre dnes alebo pre daný dátum.

    Format: 'YYYY-Www' (napr. '2026-W17').
    """
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def quarter_marker(date_str: str | None = None) -> str:
    """Vráti kvartálny marker, napr. 'Q2-2026'."""
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    q = (dt.month - 1) // 3 + 1
    return f"Q{q}-{dt.year}"


# ─────────────────────────────────────────────────────────────────────
# REQUIRED FIELDS — per table
# ─────────────────────────────────────────────────────────────────────

REQUIRED_FIELDS: dict[str, set[str]] = {
    "notes": {"title", "content", "domain", "category", "tags", "source"},
    "interactions": {"channel"},  # date má default, person_name dôležité ale nie hard-required
    "people": {"name"},
    "companies": {"name"},
    "projects": {"name"},
    "rules": {"context", "rule"},
    "action_items": {"title"},
    "decisions": {"title"},
}


# Mäkké odporúčania — warning, nie error
RECOMMENDED_FIELDS: dict[str, set[str]] = {
    "notes": {"related_person_id", "related_project_id"},
    "interactions": {"person_name", "summary", "details", "topics", "duration_minutes", "date"},
    "people": {"email", "relationship", "formality", "company_name"},
    "companies": {"type", "industry"},
    "projects": {"company_name", "status"},
}
