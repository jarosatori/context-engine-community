"""Context Engine — MCP Server.

Strukturovana kontextova pamat pre zivot. Udrzuje databazu ludi, firiem,
projektov, produktov, pravidiel, interakcii a poznamok.
"""

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


class _HealthHandler(BaseHTTPRequestHandler):
    """Simple health endpoint for Railway healthcheck."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass  # suppress logs

from context_engine import db
from context_engine.models import (
    PersonInput, CompanyInput, ProjectInput, ProductInput,
    RuleInput, InteractionInput, NoteInput, UpdateInput,
)


def _create_mcp():
    """Create FastMCP instance, with OAuth if configured."""
    oauth_url = os.environ.get("CTX_OAUTH_URL")  # e.g. http://localhost:9000

    if oauth_url:
        from mcp.server.auth.settings import AuthSettings
        from mcp_oauth import IntrospectionTokenVerifier
        from pydantic import AnyHttpUrl

        server_url = os.environ.get("CTX_SERVER_URL", "http://localhost:8000")
        token_verifier = IntrospectionTokenVerifier(
            introspection_endpoint=f"{oauth_url}/introspect",
            server_url=server_url,
            validate_resource=False,
        )
        return FastMCP(
            "Context Engine",
            instructions="Strukturovana kontextova pamat — ludia, firmy, projekty, pravidla, poznamky. Life OS.",
            token_verifier=token_verifier,
            auth=AuthSettings(
                issuer_url=AnyHttpUrl(oauth_url),
                required_scopes=["user"],
                resource_server_url=AnyHttpUrl(f"{server_url}/Context Engine"),
            ),
        )
    else:
        return FastMCP(
            "Context Engine",
            instructions="Strukturovana kontextova pamat — ludia, firmy, projekty, pravidla, poznamky. Life OS.",
        )


mcp = _create_mcp()


# --- Initialization ---

@mcp.tool()
def ctx_init() -> dict:
    """Inicializuj databazu. Bezpecne spustit opakovane."""
    return db.init_db()


@mcp.tool()
def ctx_populate_aliases() -> dict:
    """Jednorazova migracia: vygeneruj aliasy (prezyvky) pre vsetkych ludi z NICKNAMES dictionary.
    Bezpecne spustit opakovane — merguje s existujucimi aliasmi."""
    return db.populate_aliases()


# --- Search ---

@mcp.tool()
def ctx_find(query: str, domain: str | None = None) -> dict:
    """RÝCHLY lexikálny lookup naprieč celou DB (BM25, žiadny API call, <50ms).

    KEDY POUŽIŤ:
      ✅ Quick lookup známeho keyword/mena (rýchle, lacné, deterministické)
      ✅ Keď chceš všetko z viacerých tabuliek naraz a ide ti o speed

    KEDY POUŽIŤ INÉ:
      ❌ Concept query / parafráza / cross-language → ctx_search_semantic
      ❌ Štruktúrované filtre (date range, category, tags) → ctx_search
      ❌ Detail jednej osoby/firmy/projektu → ctx_person/ctx_company/ctx_project
      ❌ Pred písaním emailu → ctx_context (vráti aj formality, tone, rules)

    Volitelne filtruj podla domeny (work, personal, home, health, finance, family, education).
    """
    return db.find(query, domain)


# --- Search decision guide (for Claude) ------------------------------------
# 1. Poznáš presné meno?         → ctx_person / ctx_company / ctx_project
# 2. Pred písaním emailu/správy?  → ctx_context  (formality, tone, rules)
# 3. Štruktúrované filtre?         → ctx_search  (date range, category, tags, person)
# 4. Concept / "find anything"?   → ctx_search_semantic  (Voyage embeddings + RRF hybrid)
# 5. "Find similar to this"?       → ctx_find_similar  (nearest neighbors via embedding)
# 6. Quick keyword lookup?         → ctx_find    (BM25, no API call, fastest)


# --- Detail views ---

@mcp.tool()
def ctx_person(query: str) -> dict:
    """Detail osoby — udaje, interakcie, projekty, pravidla.
    Hladaj podla mena, emailu, prezyvky alebo aliasu. Podporuje fuzzy matching priezvisk."""
    return db.get_person(query)


@mcp.tool()
def ctx_company(query: str) -> dict:
    """Detail firmy — ludia, projekty, produkty, pravidla."""
    return db.get_company(query)


@mcp.tool()
def ctx_project(query: str) -> dict:
    """Detail projektu — popis, tim, status."""
    return db.get_project(query)


@mcp.tool()
def ctx_context(query: str) -> dict:
    """Plny komunikacny kontext pre osobu. Pouzi VZDY pred pisanim emailu/spravy.
    Vrati: formality, ton, jazyk, firma, posledne interakcie, pravidla."""
    return db.context_for(query)


# --- Add records ---

@mcp.tool()
def ctx_add_person(
    name: str,
    email: str | None = None,
    phone: str | None = None,
    company_id: int | None = None,
    company_name: str | None = None,
    role: str | None = None,
    relationship: str | None = None,
    formality: str = "uncertain",
    tone: str | None = None,
    language: str = "sk",
    projects: str | None = None,
    notes: str | None = None,
    status: str = "active",
    source: str | None = None,
    domain: str = "work",
) -> dict:
    """Pridaj osobu do registra.
    formality: ty/vy/uncertain. tone: formalny/priatelsky/vecny/neformlny.
    domain: work/personal/home/health/finance/family/education."""
    data = PersonInput(
        name=name, email=email, phone=phone, company_id=company_id,
        company_name=company_name, role=role, relationship=relationship,
        formality=formality, tone=tone, language=language, projects=projects,
        notes=notes, status=status, source=source, domain=domain,
    )
    return db.add_record("people", data.model_dump(exclude_none=True))


@mcp.tool()
def ctx_add_company(
    name: str,
    type: str | None = None,
    industry: str | None = None,
    my_role: str | None = None,
    website: str | None = None,
    notes: str | None = None,
    status: str = "active",
    domain: str = "work",
) -> dict:
    """Pridaj firmu. type: vlastna/klient/partner/vendor/ina."""
    data = CompanyInput(
        name=name, type=type, industry=industry, my_role=my_role,
        website=website, notes=notes, status=status, domain=domain,
    )
    return db.add_record("companies", data.model_dump(exclude_none=True))


@mcp.tool()
def ctx_add_project(
    name: str,
    company_id: int | None = None,
    company_name: str | None = None,
    description: str | None = None,
    type: str | None = None,
    status: str = "active",
    team: str | None = None,
    my_role: str | None = None,
    asana_id: str | None = None,
    slack_channel: str | None = None,
    drive_folder: str | None = None,
    key_contacts: str | None = None,
    notes: str | None = None,
    deadline: str | None = None,
    domain: str = "work",
) -> dict:
    """Pridaj projekt. team a key_contacts su JSON arrays."""
    data = ProjectInput(
        name=name, company_id=company_id, company_name=company_name,
        description=description, type=type, status=status, team=team,
        my_role=my_role, asana_id=asana_id, slack_channel=slack_channel,
        drive_folder=drive_folder, key_contacts=key_contacts, notes=notes,
        deadline=deadline, domain=domain,
    )
    return db.add_record("projects", data.model_dump(exclude_none=True))


@mcp.tool()
def ctx_add_product(
    name: str,
    company_id: int | None = None,
    company_name: str | None = None,
    description: str | None = None,
    price: str | None = None,
    format: str | None = None,
    availability: str | None = None,
    target_audience: str | None = None,
    min_criteria: str | None = None,
    notes: str | None = None,
    status: str = "active",
    domain: str = "work",
) -> dict:
    """Pridaj produkt/sluzbu. format: fyzicky/digitalny/sluzba/saas."""
    data = ProductInput(
        name=name, company_id=company_id, company_name=company_name,
        description=description, price=price, format=format,
        availability=availability, target_audience=target_audience,
        min_criteria=min_criteria, notes=notes, status=status, domain=domain,
    )
    return db.add_record("products", data.model_dump(exclude_none=True))


@mcp.tool()
def ctx_add_rule(
    context: str,
    rule: str,
    example: str | None = None,
    priority: str = "medium",
    category: str | None = None,
    applies_to: str | None = None,
    notes: str | None = None,
    status: str = "active",
    domain: str = "work",
) -> dict:
    """Pridaj pravidlo. priority: high/medium/low. applies_to je JSON array mien."""
    data = RuleInput(
        context=context, rule=rule, example=example, priority=priority,
        category=category, applies_to=applies_to, notes=notes,
        status=status, domain=domain,
    )
    return db.add_record("rules", data.model_dump(exclude_none=True))


@mcp.tool()
def ctx_add_note(
    title: str,
    content: str,
    domain: str,
    category: str,
    tags: str,
    source: str,
    related_person_id: int | None = None,
    related_project_id: int | None = None,
    status: str = "active",
    skip_dedupe_check: bool = False,
) -> dict:
    """Pridaj poznámku do znalostnej bázy. POVINNÉ POLIA: title, content, domain, category, tags, source.

    domain — kde patrí: work / personal / family / health / finance / home / education
    category — typ obsahu (canonical):
      • work: ops-summary, weekly-review, decision, strategy, priority, milestone, run-metrics,
        meeting-notes, q&a, session-recap, client-communication, offer-process,
        competitor-analysis, pricing, content-pattern, messaging, marketing, branding,
        infrastructure, architecture, tech, ai-tools, workflow
      • finance: deal-analysis
      • education: bootcamp-notes, lecture, course-content, mentoring
      • personal: personal-reflection, insight, idea, question, todo, reference
      • health: health-record   • family: family-event   • home: home-maintenance
      Aliasy ako 'meeting' alebo 'rozhodnutie' sa automaticky normalizujú.
      Plný zoznam: zavolaj ctx_categories().

    tags — JSON array ako string. MUSÍ obsahovať:
      (a) časový marker: '2026-W17' alebo 'Q2-2026' alebo '2026-04-22'  (auto-doplní sa ak chýba)
      (b) 1–3 témy: 'pricing', 'hiring', 'ai-agents', ...
      Voliteľne: '@meno-osoby', '&firma', '#projekt'

    source — odkiaľ informácia pochádza: napr. 'meeting:fireflies-<ID>',
      'cowork-thread', 'scheduled-task:<name>', 'manual-input', 'email:<thread-id>'

    related_person_id / related_project_id — ak vieš osobu/projekt, prepoj.
      Ak sa meno osoby spomína v content, link sa pridá automaticky.

    skip_dedupe_check — ak True, neskontroluje existujúce podobné notes (default False).

    VRACIA:
      success → {status: 'ok', id: N, warnings: [...]}
      duplicate → {status: 'duplicate_warning', similar: [...]} — zváž ctx_update na existujúcu
      error → {status: 'error', code: 'VALIDATION_FAILED', errors: [...], hint: ...}
    """
    data = NoteInput(
        title=title, content=content, domain=domain, category=category,
        tags=tags, related_person_id=related_person_id,
        related_project_id=related_project_id, source=source, status=status,
    )
    return db.add_note(data.model_dump(exclude_none=True), skip_dedupe_check=skip_dedupe_check)


@mcp.tool()
def ctx_find_notes(
    query: str,
    domain: str | None = None,
    category: str | None = None,
) -> dict:
    """Hladaj v poznnamkach/znalostnej baze. Volitelne filtruj podla domeny a kategorie."""
    return db.find_notes(query, domain, category)


# --- Update ---

@mcp.tool()
def ctx_update(table: str, record_id: int, data: dict) -> dict:
    """Aktualizuj existujuci zaznam. table: people/companies/projects/products/rules/notes.
    data: dict s poliami na zmenu, napr. {"role": "CTO", "notes": "povyseny"}."""
    return db.update_record(table, record_id, data)


# --- Interactions ---

@mcp.tool()
def ctx_log(
    person_id: int | None = None,
    person_name: str | None = None,
    channel: str | None = None,
    direction: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    topics: str | None = None,
    key_points: str | None = None,
    sentiment: str | None = None,
    follow_up: str | None = None,
    duration_minutes: int | None = None,
    context: str | None = None,
    date: str | None = None,
    source_ref: str | None = None,
    domain: str = "work",
) -> dict:
    """Zaloguj interakciu (email, call, meeting, slack...). POVINNÉ: channel.

    Pri MEETINGU vždy vyplň aspoň: channel, person_name (alebo person_id), summary,
    DETAILS (dlhý zápis!), topics (JSON array), date, duration_minutes.
    Bez details a topics sa potom nedá nič nájsť cez ctx_find — toto je jedna
    z najčastejších chýb. Radšej napíš dlhšie, krátiť sa dá vždy.

    channel — email / slack / asana / call / meeting / sms / whatsapp / telegram
              / linkedin / in-person / video-call
    direction — incoming / outgoing / both
    summary — 1-2 vetové zhrnutie pre rýchly prehľad
    details — DETAILNÝ ZÁPIS (paragraf+). Sem patrí kontext, témy, čo sa dohodlo,
              čo ostalo otvorené. Toto je hlavný obsah, nie summary.
    topics — JSON array tém: '["pricing", "Q2 launch", "hiring"]'
    key_points — JSON array kľúčových bodov: '["dohodli sme 15% zľavu", "deadline 30.4."]'
    sentiment — positive / neutral / negative / mixed
    follow_up — voľný text čo treba urobiť po (zvážiť aj ctx_add_note action_item)
    duration_minutes — dĺžka v minútach (pri meeting/call vždy)
    date — YYYY-MM-DD (default = dnes)
    person_name — meno; ak je v DB, person_id sa auto-resolve cez fuzzy match
    domain — work (default) / personal / family / health / finance / home / education
    """
    data = InteractionInput(
        person_id=person_id, person_name=person_name, channel=channel,
        direction=direction, summary=summary, details=details,
        topics=topics, key_points=key_points, sentiment=sentiment,
        follow_up=follow_up, duration_minutes=duration_minutes,
        context=context, date=date, source_ref=source_ref, domain=domain,
    )
    return db.log_interaction(data.model_dump(exclude_none=True))


# --- Advanced search (Layer 4) ---

@mcp.tool()
def ctx_search(
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
) -> dict:
    """ŠTRUKTÚROVANÝ search s presnými filtrami (date range, category, tags, person).

    KEDY POUŽIŤ:
      ✅ Máš presné filtre — date range, category, tag set, konkrétna osoba
      ✅ Chceš zúžiť výsledky ktoré ctx_find/ctx_search_semantic vrátili priveľa
      ✅ "Všetky decisions z Q2-2026", "interactions s Petrom za posledný mesiac"

    KEDY POUŽIŤ INÉ:
      ❌ Concept query bez filtrov → ctx_search_semantic
      ❌ Quick keyword lookup → ctx_find
      ❌ Detail jednej osoby/firmy → ctx_person/ctx_company

    Argumenty:
      query: full-text (FTS5 BM25), volitelne
      table: 'notes' | 'interactions' | 'people' (default = všetky 3)
      domain: filter podľa domény
      category: filter podľa kategórie (alias sa normalizuje)
      tags_any: match ak ASPOŇ JEDEN tag z listu
      tags_all: match LEN ak VŠETKY tagy
      date_from / date_to: '2026-01-01' format
      person: meno osoby (notes → related_person_id, interactions → person_name)
      sort: 'relevance' (BM25) | 'recent' | 'oldest'
      limit: max per tabuľka (default 20)

    Príklady:
      ctx_search(person='Peter Ďurák', date_from='2026-01-01', table='interactions')
      ctx_search(category='deal-analysis', tags_all=['Q2-2026'])
      ctx_search(query='pricing', tags_any=['enterprise', '@kamil-aujesky'])
    """
    return db.search_advanced(
        query=query, table=table, domain=domain, category=category,
        tags_any=tags_any, tags_all=tags_all,
        date_from=date_from, date_to=date_to,
        person=person, sort=sort, limit=limit,
    )


# --- Categories & vocabulary (Layer 7) ---

@mcp.tool()
def ctx_categories() -> dict:
    """Vráti zoznam povolených category, domain, sentiment, channel atď.

    Vždy zavolaj PRED ctx_add_note ak nie si si istý akú category použiť.
    Ak použiješ neoficiálnu category, automaticky sa normalizuje (napr.
    'meeting' → 'meeting-notes') alebo skončí ako 'other'. Lepšie použiť
    canonical priamo.
    """
    return db.categories_list()


# --- Semantic search (Layer 8) ---

@mcp.tool()
def ctx_search_semantic(
    query: str,
    table: str | None = None,
    limit: int = 10,
    hybrid: bool = True,
) -> dict:
    """SÉMANTICKÝ search cez Voyage AI embeddings (1024 dims) + RRF hybrid s BM25.

    KEDY POUŽIŤ:
      ✅ Concept query / parafráza / "find anything related to X"
      ✅ Cross-language (SK query nájde EN dokumenty a naopak)
      ✅ Keď nepamätáš presné slová, len konceptzy / tému
      ✅ DEFAULT pre exploratívne queries — hybrid mode kombinuje aj BM25, takže funguje aj pre keywords

    KEDY POUŽIŤ INÉ:
      ❌ Poznáš presné meno → ctx_person/ctx_company/ctx_project (rýchlejšie, deterministické)
      ❌ Štruktúrované filtre (date, category, tags) → ctx_search
      ❌ Quick keyword bez API call → ctx_find
      ❌ "Find similar to this record" → ctx_find_similar

    Cost: ~$0.0001 per query, latency ~200ms.

    PRÍKLADY:
      ctx_search_semantic("frustrácia s deadlinom") — nájde aj "stres pred odovzdávkou"
      ctx_search_semantic("hiring senior dev", table="notes") — nájde aj "recruiting CTO"
      ctx_search_semantic("Q2 priority focus") — semantic + BM25 fused = top relevance

    Args:
      query: free-text (slovenčina aj angličtina)
      table: 'notes' | 'interactions' | 'people' | 'companies' | 'projects' | None (všetko)
      limit: max results per table
      hybrid: True (default) → kombinuje semantic + FTS5 BM25 cez Reciprocal Rank Fusion.
              False → čistý semantic (pre extreme concept queries kde keywords sú irelevantné).

    Returns: results per table s `_semantic_score`, `_bm25_score`, `_fused_score`, `_snippet`.
    """
    return db.search_semantic(query=query, table=table, limit=limit, hybrid=hybrid)


@mcp.tool()
def ctx_find_similar(table: str, record_id: int, limit: int = 5,
                     cross_table: bool = False) -> dict:
    """Nájdi podobné records k danému (cez embedding similarity).

    Použij keď chceš objaviť súvisiace veci — napr. "ďalšie notes podobné tejto",
    "iní ľudia podobní tomuto klientovi", "podobné meetingy v minulosti".

    Args:
      table: 'notes' | 'interactions' | 'people' | 'companies' | 'projects'
      record_id: ID source recordu
      limit: max výsledkov per cieľová tabuľka
      cross_table: True → hľadaj naprieč všetkými embeddable tabuľkami;
                   False (default) → len v tej istej tabuľke

    Returns: results per table s `_similarity` score (0-1, vyššie = bližšie).
    """
    return db.find_similar(table=table, row_id=record_id, limit=limit, cross_table=cross_table)


@mcp.tool()
def ctx_index_embeddings(table: str | None = None,
                          force_reindex: bool = False,
                          limit: int | None = None) -> dict:
    """One-time / periodický backfill — vyrobí Voyage embeddings pre existujúce records.

    Pri normálnej prevádzke nie je potrebný — `ctx_add_note`, `ctx_log`,
    `ctx_add_person` automaticky vyrábajú embeddings pri INSERT/UPDATE.

    Tento tool je na:
    1. Initial setup po deployi (embed všetkých starých records)
    2. Po zmene embedding modelu (force_reindex=True)
    3. Po batch importe ktorý obišiel auto-hook

    Args:
      table: konkrétna tabuľka alebo None (všetky embeddable: notes, interactions, people, companies, projects)
      force_reindex: True → re-embed aj records ktoré už majú aktuálny embedding (zmena modelu)
      limit: max records na batch (užitočné pre dry-run / postupné spracovanie)

    Cena: ~$0.02 per 1500 records s voyage-3-large. Idempotentné.
    """
    return db.index_embeddings(table=table, force_reindex=force_reindex, limit=limit)


# --- Health & hygiene (Layer 6) ---

@mcp.tool()
def ctx_health() -> dict:
    """Coverage report — koľko záznamov má vyplnené metadáta + embedding stats.

    Použij periodicky (napr. týždenne) aby si videl degradáciu kvality DB.
    Vracia per-tabuľka: missing_domain, missing_category, missing_tags,
    without_time_marker, missing_details (interactions), embedding coverage, atď.
    """
    metadata = db.health_report()
    metadata["embeddings"] = db.embeddings_stats()
    return metadata


@mcp.tool()
def ctx_dedupe(table: str = "notes", threshold: float = 0.85) -> dict:
    """Nájde pravdepodobné duplicity v tabuľke (notes / people / companies).

    threshold: 0.0-1.0, fuzzy match score (default 0.85 = vysoká istota).
    Pre people: aj rovnaký email = duplicita istá.
    Vráti zoznam párov s id_a, id_b, score — neslučuje automaticky.
    """
    return db.find_duplicates(table=table, threshold=threshold)


@mcp.tool()
def ctx_orphans() -> dict:
    """Nájde záznamy bez správnych väzieb:
    - notes bez related_person_id ani related_project_id
    - interactions bez person_id (ale s person_name)
    - active people bez company_id
    """
    return db.find_orphans()


@mcp.tool()
def ctx_backfill_metadata(dry_run: bool = False) -> dict:
    """One-time migration: doplní chýbajúce metadáta v existujúcich záznamoch.

    Konkrétne:
    1. Normalizuje category aliasy (meeting → meeting-notes, ops/chat-summary → ops-summary, ...)
    2. Doplní time marker do tagov (z created_at, ak chýba)
    3. Doplní domain z category mapping (ak chýba)
    4. Auto-link mentioned people v notes content → related_person_id
    5. Resolve missing person_id v interactions cez fuzzy name match

    dry_run=True → ukáže čo by spravil bez zápisu. Bezpečné spustiť.
    """
    return db.backfill_metadata(dry_run=dry_run)


# --- Statistics & maintenance ---

@mcp.tool()
def ctx_stats(domain: str | None = None) -> dict:
    """Statistiky registra. Bez domeny = celkove + breakdown per domain."""
    return db.stats(domain)


@mcp.tool()
def ctx_incomplete(domain: str | None = None) -> dict:
    """Zaznamy na doplnenie — to_verify, chybajuce emaily, uncertain formality."""
    return db.incomplete(domain)


@mcp.tool()
def ctx_stale(days: int = 30, domain: str | None = None) -> dict:
    """Zaznamy neaktualizovane dlhsie ako N dni."""
    return db.stale(days, domain)


@mcp.tool()
def ctx_recent(days: int = 7, domain: str | None = None) -> dict:
    """Co sa zmenilo za poslednuch N dni."""
    return db.recent(days, domain)


# --- Scan management ---

@mcp.tool()
def ctx_scan_status() -> list[dict]:
    """Stav poslednuch scanov pre kazdy zdroj."""
    return db.scan_status()


@mcp.tool()
def ctx_set_scan(source: str, timestamp: str) -> dict:
    """Nastav timestamp posledneho scanu. source: gmail/slack/asana/drive/calendar."""
    return db.set_scan_marker(source, timestamp)


@mcp.tool()
def ctx_update_scan(source: str, processed: int, added: int, updated: int, notes: str = "") -> dict:
    """Zaloguj dokonceny scan. Pouzivaj na konci kazdeho scanning tasku."""
    return db.update_scan_stats(source, processed, added, updated, notes)


# --- Action items ---

@mcp.tool()
def ctx_action_items(
    status: str | None = "extracted",
    owner: str | None = None,
    project_id: int | None = None,
) -> dict:
    """Zoznam action itemov z meetingov/interakcii.
    status: extracted/pushed_to_asana/done. owner: meno osoby. project_id: filter podla projektu."""
    return db.get_action_items(status, owner, project_id)


@mcp.tool()
def ctx_mark_action_done(item_id: int, asana_task_id: str | None = None) -> dict:
    """Oznac action item ako pushed do Asany alebo done."""
    return db.mark_action_item_pushed(item_id, asana_task_id)


# --- Decisions ---

@mcp.tool()
def ctx_decisions(project_id: int | None = None, status: str | None = "active") -> dict:
    """Zoznam rozhodnuti. Volitelne filtruj podla projektu alebo statusu."""
    return db.get_decisions(project_id, status)


# --- Meeting participants ---

@mcp.tool()
def ctx_meeting_participants(interaction_id: int | None = None, person_id: int | None = None) -> dict:
    """Ucastnici meetingu (podla interaction_id) alebo meetingy osoby (podla person_id)."""
    return db.get_meeting_participants(interaction_id, person_id)


# --- Single note ---

@mcp.tool()
def ctx_get_note(note_id: int) -> dict:
    """Detail jednej poznamky podla ID."""
    return db.get_note(note_id)


# --- Export ---

@mcp.tool()
def ctx_export(domain: str | None = None) -> dict:
    """Export celeho registra ako JSON. Volitelne filtruj podla domeny."""
    return db.export_data(domain)


# --- DB Restore (for Railway deployment) ---

@mcp.tool()
def ctx_restore_db(b64_chunk: str, chunk_index: int, total_chunks: int, upload_id: str = "default") -> dict:
    """Nahraj DB po castiach (base64 chunky). Posledny chunk spusti restore.
    Pouzivaj na migration DB na Railway."""
    import base64
    tmp_dir = "/tmp/db_upload"
    os.makedirs(tmp_dir, exist_ok=True)
    chunk_path = f"{tmp_dir}/{upload_id}_{chunk_index:04d}"
    with open(chunk_path, "wb") as f:
        f.write(base64.b64decode(b64_chunk))

    if chunk_index + 1 == total_chunks:
        # All chunks received — assemble and restore
        db_path = db.DB_PATH
        assembled = f"{tmp_dir}/{upload_id}_assembled.db"
        with open(assembled, "wb") as out:
            for i in range(total_chunks):
                cp = f"{tmp_dir}/{upload_id}_{i:04d}"
                with open(cp, "rb") as inp:
                    out.write(inp.read())
                os.remove(cp)
        # Replace current DB
        import shutil
        shutil.copy2(assembled, db_path)
        os.remove(assembled)
        return {"status": "ok", "message": f"DB restored from {total_chunks} chunks", "path": db_path}

    return {"status": "ok", "message": f"Chunk {chunk_index+1}/{total_chunks} received"}


# --- Entry point ---

def main():
    """Run the MCP server.

    Usage:
        context-engine          # stdio (for Claude Code)
        context-engine --http   # HTTP on port 8080 (for Cowork / remote)
        context-engine --sse    # SSE on port 8080
    Port override: CTX_PORT env var.
    """
    # Railway sets PORT, fallback to CTX_PORT, then 8080
    port = int(os.environ.get("PORT", os.environ.get("CTX_PORT", "8080")))
    host = os.environ.get("CTX_HOST", "0.0.0.0")
    if "--http" in sys.argv:
        # Override settings directly (env vars are read at FastMCP init time, too early)
        mcp.settings.port = port
        mcp.settings.host = host
        mcp.run(transport="streamable-http")
    elif "--sse" in sys.argv:
        mcp.settings.port = port
        mcp.settings.host = host
        # Disable DNS rebinding protection for ngrok/Railway tunneling
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
        mcp.run(transport="sse")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
