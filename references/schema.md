# Databázová schéma — Context Engine

## Prehľad tabuliek

```
companies ←──── people ←──── interactions ←── meeting_participants
    ↑               ↑             ↑
    ├── projects     ├── (projects via team JSON)
    ├── products     └── rules (via applies_to)
    └── rules (via applies_to)
                          ↓
                    action_items ──→ projects
                    decisions    ──→ projects

notes (standalone, optional FK to people/projects)
scan_log (nezávislá — tracking scanov)
```

## companies — Firmy

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| name | TEXT UNIQUE | Názov firmy | |
| type | TEXT | Typ vzťahu | vlastna, klient, partner, vendor, ina |
| industry | TEXT | Odvetvie | |
| my_role | TEXT | Moja rola voči firme | konzultant, zamestnanec, spolupracovník... |
| website | TEXT | Web | |
| notes | TEXT | Poznámky | |
| status | TEXT | Stav | active, inactive, to_verify |
| created_at | TEXT | Vytvorené | auto |
| updated_at | TEXT | Aktualizované | auto |

## people — Ľudia

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| name | TEXT | Meno a priezvisko | |
| email | TEXT | Email | |
| phone | TEXT | Telefón | |
| company_id | INTEGER FK | Odkaz na firmu | |
| company_name | TEXT | Firma (denormalizované) | pre rýchly prístup |
| role | TEXT | Pracovná pozícia | CEO, CTO, manažér... |
| relationship | TEXT | Vzťah ku mne | klient, partner, tim, vendor, kontakt, mentor |
| formality | TEXT | Tykanie/vykanie | ty, vy, uncertain |
| tone | TEXT | Komunikačný tón | formalny, priatelsky, vecny, neformlny |
| language | TEXT | Jazyk komunikácie | sk, en, cs, de |
| projects | TEXT | Projekty (JSON array) | '["Proj1", "Proj2"]' |
| notes | TEXT | Dôležité poznámky | |
| status | TEXT | Stav | active, inactive, to_verify |
| source | TEXT | Odkiaľ záznam | gmail, slack, asana, manual |
| first_seen | TEXT | Prvý kontakt | auto |
| updated_at | TEXT | Posledná aktualizácia | auto |

**UNIQUE constraint**: (name, email) — zabraňuje duplicitám

## projects — Projekty

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| name | TEXT | Názov projektu | |
| company_id | INTEGER FK | Odkaz na firmu | |
| company_name | TEXT | Firma (denormalizované) | |
| description | TEXT | Popis projektu | |
| type | TEXT | Typ | produkt, kampan, interni, klientsky, strategia |
| status | TEXT | Stav | active, paused, done, cancelled, to_verify |
| team | TEXT | Tím (JSON array mien) | '["Meno1", "Meno2"]' |
| my_role | TEXT | Moja rola na projekte | |
| asana_id | TEXT | ID v Asane | |
| slack_channel | TEXT | Slack kanál | |
| drive_folder | TEXT | Priečinok v Drive | |
| key_contacts | TEXT | Kľúčové kontakty (JSON) | |
| notes | TEXT | Poznámky | |
| deadline | TEXT | Deadline | YYYY-MM-DD |
| created_at | TEXT | Vytvorené | auto |
| updated_at | TEXT | Aktualizované | auto |

## products — Produkty a služby

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| name | TEXT | Názov | |
| company_id | INTEGER FK | Odkaz na firmu | |
| company_name | TEXT | Firma | |
| description | TEXT | Popis | |
| price | TEXT | Cena (text — flexibilné) | "497 EUR", "od 99 EUR/mes" |
| format | TEXT | Formát | fyzicky, digitalny, sluzba, saas |
| availability | TEXT | Dostupnosť | aktivny, pripravuje_sa, ukonceny |
| target_audience | TEXT | Cieľovka | |
| min_criteria | TEXT | Min. kritériá na predaj | |
| notes | TEXT | Poznámky | |
| status | TEXT | Stav | active, inactive |
| updated_at | TEXT | Aktualizované | auto |

## rules — Pravidlá a preferencie

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| context | TEXT | Kedy pravidlo platí | "Komunikácia s enterprise klientmi" |
| rule | TEXT | Čo robiť | "Vždy vykať, formálny tón" |
| example | TEXT | Príklad | "Dobrý deň, pán riaditeľ..." |
| priority | TEXT | Priorita | high, medium, low |
| category | TEXT | Kategória | komunikacia, procesy, rozhodovanie, delegovanie |
| applies_to | TEXT | Na koho/čo sa vzťahuje | JSON: '["Firma X", "Osoba Y"]' |
| notes | TEXT | Poznámky | |
| status | TEXT | Stav | active, inactive |
| created_at | TEXT | Vytvorené | auto |
| updated_at | TEXT | Aktualizované | auto |

## interactions — Log interakcií

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| person_id | INTEGER FK | Odkaz na osobu | |
| person_name | TEXT | Meno (denormalizované) | |
| channel | TEXT | Kanál | email, slack, asana, call, meeting |
| direction | TEXT | Smer | incoming, outgoing, both |
| summary | TEXT | Stručné zhrnutie (1-2 vety) | |
| details | TEXT | Detailný zápis (paragraf+) | celý kontext meetingu, dlhý popis |
| topics | TEXT | Témy (JSON array) | '["pricing", "Q2 launch"]' |
| key_points | TEXT | Kľúčové body (JSON array) | '["dohodli sme 15% zľavu"]' |
| sentiment | TEXT | Sentiment interakcie | positive, neutral, negative, mixed |
| follow_up | TEXT | Čo treba spraviť | voľný text |
| duration_minutes | INTEGER | Dĺžka v minútach | |
| context | TEXT | Kontext/projekt | |
| date | TEXT | Dátum | YYYY-MM-DD |
| source_ref | TEXT | Odkaz na zdroj | gmail:msgId, slack:ts... |
| created_at | TEXT | Vytvorené | auto |

## scan_log — Tracking scanov

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| source | TEXT UNIQUE | Zdroj | gmail, slack, asana, drive, calendar |
| last_scan | TEXT | Posledný scan | ISO timestamp |
| items_processed | INTEGER | Spracované položky | |
| items_added | INTEGER | Pridané záznamy | |
| items_updated | INTEGER | Aktualizované | |
| notes | TEXT | Poznámky | |
| updated_at | TEXT | Aktualizované | auto |

## action_items — Úlohy z meetingov/interakcií

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| title | TEXT | Názov úlohy | |
| owner_name | TEXT | Meno zodpovednej osoby | |
| owner_id | INTEGER FK | Odkaz na people | |
| source_interaction_id | INTEGER FK | Z ktorej interakcie | |
| related_project_id | INTEGER FK | Súvisiaci projekt | |
| due_date | TEXT | Deadline | YYYY-MM-DD |
| status | TEXT | Stav | extracted, pushed_to_asana, done |
| priority | TEXT | Priorita | high, medium, low |
| notes | TEXT | Poznámky | |
| domain | TEXT | Doména | work, personal... |
| created_at | TEXT | Vytvorené | auto |
| completed_at | TEXT | Dokončené | |
| asana_task_id | TEXT | ID tasku v Asane | po push-e |

## decisions — Zaznamenané rozhodnutia

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| id | INTEGER PK | Auto ID | |
| title | TEXT | Rozhodnutie | |
| context | TEXT | Kontext/dôvod | |
| decided_by | TEXT | Kto rozhodol | |
| source_interaction_id | INTEGER FK | Z ktorej interakcie | |
| related_project_id | INTEGER FK | Súvisiaci projekt | |
| date | TEXT | Dátum | YYYY-MM-DD |
| status | TEXT | Stav | active, revoked |
| notes | TEXT | Poznámky | |
| domain | TEXT | Doména | work, personal... |
| created_at | TEXT | Vytvorené | auto |

## meeting_participants — Účastníci meetingov

| Pole | Typ | Popis | Hodnoty |
|------|-----|-------|---------|
| interaction_id | INTEGER FK PK | Odkaz na interakciu | |
| person_id | INTEGER FK PK | Odkaz na osobu | |
| person_name | TEXT | Meno (denormalizované) | |

**Composite PK**: (interaction_id, person_id)
**CASCADE DELETE** na obe FK.

## Full-Text Search

DB obsahuje FTS5 virtuálne tabuľky pre rýchle fulltextové vyhľadávanie:
- `people_fts` — hľadá cez name, email, company_name, role, notes, projects, aliases
- `projects_fts` — hľadá cez name, company_name, description, team, notes
- `notes_fts` — hľadá cez title, content, category, tags
- `companies_fts` — hľadá cez name, type, industry, notes
- `interactions_fts` — hľadá cez person_name, summary, details, context, topics, key_points, follow_up

FTS sa automaticky synchronizuje cez SQL triggre pri INSERT/UPDATE/DELETE.

`ctx_find()` prehľadáva **všetky** FTS tabuľky vrátane interactions — takže ak niečo bolo povedané na meetingu a zalogované cez `ctx_log`, `ctx_find` to nájde.
