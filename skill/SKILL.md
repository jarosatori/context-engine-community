---
name: context-engine
description: "Strukturovana kontextova pamat pre cely zivot. Udrzuje databazu ludi, firiem, projektov, produktov, pravidiel, interakcii a poznamok. Pouzi VZDY ked: pises email alebo spravu (na zistenie tonu, tykania/vykania, kontextu vztahu), pracujes s Asana taskami (na pochopenie projektu a timu), pripravujes cokolvek pre konkretnu osobu alebo firmu, potrebujes vediet kto je kto, potrebujes si nieco zapamatat. Spustaj aj ked task zmienuje meno osoby, nazov firmy, alebo projekt. Pouzi aj na osobne veci — dom, zdravie, financie, rodina. Tento skill je 'vzdy zapnuty'."
---

# Context Engine — Behavioral Guide

Toto je tvoja dlhodobá pamäť. SQLite databáza s ľuďmi, firmami, projektami, produktmi, pravidlami, interakciami a poznámkami. Pokrýva prácu aj osobný život cez domain systém.

Všetky operácie robíš cez MCP tooly s prefixom `ctx_*`. Nepoužívaj CLI (`python ctx.py ...`) — to je legacy rozhranie.

---

## 1. AUTO-TRIGGERY — kedy sa aktivuješ

Spusti Context Engine **automaticky** (bez toho, aby sa ťa používateľ pýtal) keď:

| Trigger | Čo urobiť | Príklad |
|---------|-----------|---------|
| Píšeš email alebo správu | `ctx_context("meno")` PRED písaním | "Napíš email Martinovi" |
| Task zmieňuje meno osoby | `ctx_person("meno")` | "Zavolaj Janke" |
| Task zmieňuje firmu | `ctx_company("firma")` | "Priprav ponuku pre Dedoles" |
| Task zmieňuje projekt | `ctx_project("projekt")` | "Aktualizuj task na Rebrande" |
| Používateľ hovorí "zapamätaj si" | `ctx_add_note(...)` alebo `ctx_add_rule(...)` | "Zapamätaj si že s XY vykáme" |
| Asana task | `ctx_project(...)` + `ctx_person(...)` pre assignees | "Aktualizuj task v Asane" |
| Hľadá informáciu o osobe/firme | `ctx_find("query")` | "Čo vieme o XY?" |
| Spomína doménu (zdravie, dom, financie) | `ctx_find_notes("query", domain="...")` | "Aké mám poznámky k domu?" |

**Ak nie si istý, či sa trigger aplikuje — radšej spusti.** Zbytočný lookup stojí milisekundy. Chýbajúci kontext stojí zlý email.

---

## 2. DECISION TREES — presný postup

### 2.1 Pred písaním emailu / správy (POVINNÉ)

```
1. ctx_context("meno príjemcu")
   ├── Nájdený → použi formality, tone, language, rules
   │   └── Ak sú rules s priority=high → VŽDY dodržať
   └── Nenájdený → ctx_find("meno")
       ├── Nájdený v inej forme → použi čo máš
       └── Nenájdený nikde → píš neutrálne, na konci ponúkni:
           "Chceš aby som si uložil kontext pre [meno]?"
```

**Z výstupu ctx_context použi:**
- `communication.formality` → ty/vy/uncertain (ak uncertain, použi "vy" default)
- `communication.tone` → prispôsob štýl (formálny = dlhšie vety, priateľský = kratšie)
- `communication.language` → sk/en/cs/de
- `rules` → akékoľvek rules s priority "high" sú POVINNÉ
- `recent_interactions` → zorientuj sa v kontexte poslednej komunikácie

### 2.2 Pred prácou na projekte / Asana tasku

```
1. ctx_project("názov projektu")
   ├── Nájdený → máš tím, rolu, kontakty, deadline
   │   └── Pre každého člena tímu: ctx_context() ak budeš komunikovať
   └── Nenájdený → ctx_find("názov")
       └── Stále nič → pracuj bez kontextu, na konci ponúkni pridanie
```

### 2.3 Keď sa používateľ pýta "čo vieme o X?"

```
1. ctx_find("X")
   → Vráti výsledky z people, companies, projects, products, rules, notes
   → Ak treba detail: ctx_person() / ctx_company() / ctx_project()
```

### 2.4 Keď používateľ hovorí "zapamätaj si..."

Rozpoznaj typ informácie:

| Informácia | Tool | Príklad |
|------------|------|---------|
| Komunikačné pravidlo | `ctx_add_rule(context, rule, priority)` | "S Marekom vždy vykaj" |
| Nová osoba | `ctx_add_person(name, ...)` | "Martin je nový CTO v XY" |
| Nová firma | `ctx_add_company(name, ...)` | "Firma ABC je náš nový klient" |
| Osobná poznámka | `ctx_add_note(title, content, domain, category, tags, source)` | "Mám termín u lekára 15.3." |
| Procesné pravidlo | `ctx_add_rule(context, rule, category="procesy")` | "Faktúry vždy v EUR" |

**Pri `ctx_add_note` sú POVINNÉ polia: `title`, `content`, `domain`, `category`, `tags`, `source`.**
- `domain` — work/personal/family/health/finance/home/education
- `category` — `meeting-notes`, `decision`, `strategy`, `deal-analysis`, `bootcamp-notes`, `personal-reflection`, `health-record`... Plný zoznam cez `ctx_categories()`. Aliasy ako `meeting`/`rozhodnutie` sa automaticky normalizujú.
- `tags` — JSON array, MUSÍ obsahovať časový marker (`2026-W17`, `Q2-2026`) a 1-3 témy. Auto-doplňuje sa ak chýba.
- `source` — `meeting:fireflies-<ID>`, `cowork-thread`, `scheduled-task:<name>`, `manual-input`, `email:<thread>`.
- Server vráti `duplicate_warning` ak existuje podobná note — zváž `ctx_update` namiesto novej.

**Po pridaní vždy potvrď** čo si uložil, stručne.

### 2.5 Po odoslaní emailu / po callu / po meetingu

```
ctx_log(
    person_name="Meno",
    channel="email|call|meeting|slack|...",
    direction="outgoing|incoming|both",
    summary="Stručné 1-2 vetové zhrnutie",
    details="DLHÝ DETAILNÝ ZÁPIS — toto je hlavný obsah, nie summary!",
    topics='["pricing", "Q2", "hiring"]',
    key_points='["dohodli 15% zľavu", "deadline 30.4."]',
    sentiment="positive|neutral|negative|mixed",
    follow_up="Čo treba urobiť po",
    duration_minutes=60,
    date="YYYY-MM-DD"
)
```

**Pri MEETING/CALL vždy aspoň: `channel`, `person_name`, `summary`, `details`, `topics`, `duration_minutes`, `date`.** Bez `details` a `topics` nie je interakcia použiteľná pre neskorší search. Radšej napíš dlhšie — krátiť sa dá vždy.

Loguj automaticky ak si ty písal email alebo správu. Neloguj triviálne veci.

### 2.6 Po meetingu — action items a rozhodnutia

Keď spracovávaš meeting notes alebo transkript:

```
1. ctx_log(..., channel="meeting") → zaloguj meeting, dostaneš interaction_id

2. Pre účastníkov:
   ctx_update("meeting_participants", ...) s interaction_id, person_id, person_name

3. Pre každú extrahovanú úlohu:
   ctx_update("action_items", ...) s title, owner_name, due_date, priority,
   source_interaction_id, related_project_id

4. Pre každé rozhodnutie:
   ctx_update("decisions", ...) s title, decided_by, context,
   source_interaction_id, related_project_id
```

### 2.7 Action items workflow

```
1. ctx_action_items(status="extracted") → neposunuté úlohy
2. Push do Asany → ctx_mark_action_done(item_id, asana_task_id="...")
3. ctx_action_items(owner="Meno") → úlohy konkrétnej osoby
```

### 2.8 Rozhodnutia — lookup

```
ctx_decisions(project_id=123) → rozhodnutia pre projekt
→ Užitočné pri retrospektíve, konflikte, alebo "čo sme sa dohodli?"
```

---

## 3. AKTÍVNE DOPYTOVANIE — pýtaj sa na to čo chýba

Context Engine nie je pasívny archív. Aktívne sa pýtaj na chýbajúce informácie, aby databáza rástla a bola presná. Ale nerob to otravne — max 2-3 otázky naraz, vždy s kontextom prečo sa pýtaš.

### 3.1 Pri lookup-e s dierami (PRED komunikáciou)

Keď `ctx_context()` vráti nekompletný záznam a ideš písať email/správu:

| Čo chýba | Ako sa opýtať |
|-----------|--------------|
| `formality: "uncertain"` | "Martinovi tykáme alebo vykáme?" |
| `tone: null` | "Aký tón s Martinom — formálny, priateľský, vecný?" |
| `language: null` | "Píšeme Martinovi po slovensky alebo anglicky?" |
| `relationship: null` | "Martin je klient, partner, alebo z tímu?" |

**Pravidlo:** Pýtaj sa LEN na to čo reálne potrebuješ pre aktuálny task. Ak píšeš email, formality a language sú kritické. Ak len hľadáš info, nepýtaj sa na tón.

Po odpovedi okamžite ulož:
```
ctx_update("people", record_id, {"formality": "ty", "tone": "priatelsky"})
```

### 3.2 Po pridaní nového kontaktu

Keď pridáš osobu (z emailu, scanu, alebo manuálne) a chýbajú kľúčové údaje:

```
"Pridala som Janu Novú do databázy (z emailu). Vieš mi povedať:
 1. Je to klientka, partnerka, alebo niekto z tímu?
 2. Tykáme si s ňou?"
```

**Max 2-3 otázky.** Zvyšok nechaj na neskôr alebo označ `to_verify`.

### 3.3 Pri konflikte dát

Keď nájdeš v komunikácii info čo sa líši od DB:

```
"V poslednom emaile sa Martin podpísal ako CTO, ale v databáze ho mám ako CMO.
Aktualizujem na CTO?"
```

**NIKDY neprepíš bez potvrdenia** — môže ísť o chybu v emaile, nie o skutočnú zmenu.

### 3.4 Po dokončení tasku (nízka priorita)

Ak bol task spojený s osobou/firmou a máš priestor (nie uprostred urgentnej práce):

```
"Ešte k tomu emailu pre Dedoles — chceš aby som si zapamätal niečo nové?
Napríklad zmenu kontaktnej osoby, nové pravidlo, alebo poznámku k projektu?"
```

**Toto rob LEN keď je priestor.** Ak používateľ chce ísť ďalej, nerieš to.

### 3.5 Proaktívne surfacovanie (pri voľnom priestore)

Keď konverzácia prirodzene stojí (po dokončení tasku, pred novým):

```
ctx_incomplete()
```

Ak sú záznamy na doplnenie, vyber 1-2 NAJDÔLEŽITEJŠIE (nie všetky):

```
"Mám v databáze 3 kontakty kde neviem formality. Najdôležitejší je asi
Marek z Dedoles — tykáme si s ním? Ostatné doplníme neskôr."
```

**Pravidlá pre proaktívne otázky:**
- Max 1-2 otázky naraz
- Vždy najdôležitejšie prvé (ľudia s ktorými sa komunikuje často)
- Ak používateľ povie "teraz nie" alebo ignoruje → rešpektuj, neopakuj
- Nerobí to uprostred tasku, len v prirodzených pauzách

### 3.6 Formát otázok

Vždy použi stručné, konkrétne otázky s kontextom:

**SPRÁVNE:**
- "Martinovi tykáme alebo vykáme? (píšem mu email)"
- "Jana Nová z Gmailu — je klientka alebo partnerka?"
- "Projekt Rebrand — deadline je stále jún 2026?"

**NESPRÁVNE:**
- "Povedz mi všetko o Martinovi" (príliš široké)
- "Chýba ti veľa údajov, doplň prosím" (nekonkrétne)
- "Mám 47 neúplných záznamov" (zahltenie)

---

## 4. DOMAIN SYSTÉM

Každý záznam má `domain` pole. Správne zaradenie je dôležité pre filtrovanie.

| Domain | Čo tam patrí |
|--------|-------------|
| **work** | Pracovné kontakty, klienti, projekty, pravidlá |
| **personal** | Osobné poznámky, nápady, referencie |
| **home** | Dom, nehnuteľnosti, dodávatelia, údržba |
| **health** | Zdravotné záznamy, lekári, lieky, termíny |
| **finance** | Finančné poznámky, účty, investície |
| **family** | Rodina, udalosti, kontakty |
| **education** | Kurzy, učenie, certifikácie |

Ak si nie si istý → použi "work" pre pracovné, "personal" pre ostatné.

---

## 5. TOOL REFERENCIA

### Vyhľadávanie (read-only, bezpečné volať kedykoľvek)

**Search Decision Tree** — vyber správny tool podľa typu otázky:

| Situácia | Tool | Prečo |
|----------|------|-------|
| Pred písaním emailu / správy | `ctx_context("meno")` | Vráti formality, tón, jazyk, pravidlá. **POVINNÉ pred komunikáciou.** |
| Poznám presné meno osoby/firmy/projektu | `ctx_person` / `ctx_company` / `ctx_project` | Najrýchlejšie, deterministické, $0 |
| **Concept query** ("AI agenty", "frustrácia s deadline"), parafrázy, cross-language SK↔EN | `ctx_search_semantic(query)` | Voyage embeddings + RRF hybrid s BM25. **Default pre exploratívne queries.** ~$0.0001/query, ~200ms |
| **Štruktúrované filtre** (date range, category, tags, osoba ako filter) | `ctx_search(filters)` | Presné DB filtrovanie, žiadne embeddings nutné |
| "Nájdi mi podobné notes/ľudí k tomuto" | `ctx_find_similar(table, id)` | Nearest neighbors v embedding space |
| Quick keyword lookup (chcem rýchlo, žiadny API call) | `ctx_find(query)` | BM25 lexical, $0, <50ms |

Tieto tools sa **nenahradzajú** — `ctx_search_semantic` je default pre "find anything related", ale pre exact mená je `ctx_person` rýchlejší a presnejší. Pre Q2 priorities by si volal `ctx_search(category='priority', tags_all=['Q2-2026'])` namiesto semantic, lebo máš presné filtre.

| Tool | Kedy | Čo vráti |
|------|------|----------|
| `ctx_find(query, domain?)` | Quick lexical lookup | BM25 results s `_snippet` + `_score`, naprieč všetkými tabuľkami |
| `ctx_search(query?, table?, domain?, category?, tags_any?, tags_all?, date_from?, date_to?, person?, sort?)` | Štruktúrované filtre | Filtrované rows s `_snippet` + `_score` |
| `ctx_search_semantic(query, table?, limit?, hybrid?)` | **Sémantický search** | Voyage embeddings, vracia `_semantic_score`, `_bm25_score`, `_fused_score`, `_snippet` |
| `ctx_find_similar(table, record_id, limit?, cross_table?)` | Nearest neighbors k existujúcemu recordu | Records s `_similarity` score (0-1) |
| `ctx_categories()` | Pred ctx_add_note ak nevieš akú category | Plný zoznam povolených category, domains, channels, sentiments + aliasy |
| `ctx_context(query)` | **PRED emailom/správou** | Formality, tón, jazyk, firma, interakcie, pravidlá |
| `ctx_person(query)` | Potrebuješ detail osoby | Údaje + interakcie + projekty + pravidlá + action items + meetingy. Podporuje prezývky ("Samo" → "Samuel") a fuzzy matching priezvisk ("Schovajsa" → "Skovajsa") |
| `ctx_company(query)` | Potrebuješ detail firmy | Firma + ľudia + projekty + produkty + pravidlá |
| `ctx_project(query)` | Potrebuješ detail projektu | Projekt + tím s detailmi |
| `ctx_find_notes(query, domain?, category?)` | Hľadáš v poznámkach | Poznámky matchujúce query |
| `ctx_get_note(note_id)` | Potrebuješ detail jednej poznámky | Kompletná poznámka podľa ID |

### Action items a rozhodnutia

| Tool | Kedy | Čo vráti |
|------|------|----------|
| `ctx_action_items(status?, owner?, project_id?)` | Prehľad úloh z meetingov | Action items s filtrami |
| `ctx_mark_action_done(item_id, asana_task_id?)` | Posunul si úlohu do Asany | Označí item ako pushed/done |
| `ctx_decisions(project_id?, status?)` | "Čo sme sa dohodli?" | Rozhodnutia pre projekt |
| `ctx_meeting_participants(interaction_id?, person_id?)` | Kto bol na meetingu? | Účastníci meetingu alebo meetingy osoby |

### Pridávanie (zapisuje do DB)

| Tool | Kedy |
|------|------|
| `ctx_add_person(name, email?, company_name?, role?, relationship?, formality?, tone?, language?, domain?)` | Nový kontakt |
| `ctx_add_company(name, type?, industry?, my_role?, domain?)` | Nová firma |
| `ctx_add_project(name, company_name?, description?, type?, team?, my_role?, asana_id?, domain?)` | Nový projekt |
| `ctx_add_product(name, company_name?, price?, format?, domain?)` | Nový produkt/služba |
| `ctx_add_rule(context, rule, priority?, category?, applies_to?, domain?)` | Nové pravidlo |
| `ctx_add_note(title, content, domain, category, tags, source, related_person_id?, related_project_id?)` | Poznámka. **Všetkých 6 polí je povinných.** Vráti `duplicate_warning` ak existuje podobná. |
| `ctx_log(person_name?, channel, direction?, summary?, details?, topics?, key_points?, sentiment?, follow_up?, duration_minutes?, context?, date?, domain?)` | Záznam interakcie. **`channel` povinný + aspoň jedno z (summary, details).** Pri meeting vždy aj `details` + `topics` + `duration_minutes`. |

### Aktualizácia a údržba

| Tool | Kedy |
|------|------|
| `ctx_update(table, record_id, data)` | Zmena existujúceho záznamu (aj action_items, decisions, meeting_participants). Pre aliases: automaticky appenduje do existujúceho JSON array |
| `ctx_populate_aliases()` | Jednorazová migrácia: vygeneruje aliasy (prezývky) pre všetkých ľudí. Bezpečné spustiť opakovane |
| `ctx_stats(domain?)` | Štatistiky registra |
| `ctx_incomplete(domain?)` | Záznamy na doplnenie |
| `ctx_stale(days?, domain?)` | Zastarané záznamy |
| `ctx_recent(days?, domain?)` | Posledné zmeny |
| `ctx_export(domain?)` | Export celého registra |
| `ctx_health()` | Coverage report — % záznamov s/bez metadát + embedding stats + recommendations |
| `ctx_index_embeddings(table?, force_reindex?, limit?)` | Backfill Voyage embeddings pre existujúce records (auto-embed beží pri každom INSERT/UPDATE) |
| `ctx_dedupe(table, threshold?)` | Nájde pravdepodobné duplicity (notes/people/companies) |
| `ctx_orphans()` | Nájde záznamy bez správnych väzieb (notes bez person link, atď.) |
| `ctx_backfill_metadata(dry_run?)` | One-time migration — normalizuje categories, doplní time markery, person linky |

### Scan management

| Tool | Kedy |
|------|------|
| `ctx_scan_status()` | Stav posledných scanov |
| `ctx_set_scan(source, timestamp)` | Nastav scan marker |
| `ctx_update_scan(source, processed, added, updated, notes?)` | Zaloguj dokončený scan |

---

## 6. INTEGRAČNÉ VZORY

### Gmail + Context Engine

```
Používateľ: "Napíš email Martinovi ohľadom faktúry"

1. ctx_context("Martin")
   → formality: "ty", tone: "priatelsky", language: "sk"
   → rules: ["Faktúry vždy v EUR", "Krátke emaily"]
   → recent_interactions: posledný email bol o projekte Rebrand

2. Napíš email s týmto kontextom:
   - Tykaj mu
   - Priateľský tón
   - Slovenčina
   - Spomeň posledný kontext ak relevantné
   - Dodržuj pravidlá (EUR, krátky email)

3. Po odoslaní:
   ctx_log(person_name="Martin", channel="email", direction="outgoing",
           summary="Faktúra za január - Rebrand", date="2026-02-27")
```

### Slack + Context Engine

```
Používateľ: "Napíš Janke na Slack o deadline"

1. ctx_context("Janka")
   → formality, tone, projekty, pravidlá

2. Napíš správu podľa kontextu

3. ctx_log(person_name="Janka", channel="slack", direction="outgoing",
           summary="Pripomienka deadline", date="2026-02-27")
```

### Asana + Context Engine

```
Používateľ: "Aktualizuj task Rebrand v Asane"

1. ctx_project("Rebrand")
   → tím, moja rola, deadline, stav, Asana ID

2. Použi asana_id na nájdenie projektu v Asane
   Použi team_details na pochopenie kto čo robí

3. Aktualizuj task s kontextom
```

### Calendar + Context Engine

```
Používateľ: "Naplánuj meeting s Marekom"

1. ctx_context("Marek")
   → firma, vzťah, posledné interakcie

2. Použi info na vytvorenie meetingu s relevantným titulom a popisom
```

### Meeting Ingest + Context Engine

```
Používateľ: "Spracuj zápis z meetingu" (transkript alebo poznámky)

1. ctx_log(channel="meeting", summary="...", date="...")
   → interaction_id

2. Pre každého účastníka:
   ctx_person("meno") → ak existuje, vezmi person_id
   ctx_update("meeting_participants", ...) s interaction_id + person_id

3. Extrahuj action items:
   ctx_update("action_items", ...) pre každú úlohu
   → title, owner_name, due_date, priority, source_interaction_id

4. Extrahuj rozhodnutia:
   ctx_update("decisions", ...) pre každé rozhodnutie
   → title, decided_by, context, source_interaction_id

5. ctx_action_items(status="extracted") → zobraz čo sa extrahovali
   → Ponúkni push do Asany
```

---

## 7. SCANNING WORKFLOW (pre scheduled tasks)

Scanning používa MCP tooly, nie CLI. Detailný postup je v `references/scanning-guide.md`.

### Denný watcher — stručný prehľad

```
1. ctx_scan_status() → zisti posledné scan timestamps

2. Gmail scan (od posledného markeru):
   gmail_search_messages(q="after:YYYY/MM/DD")
   → Pre nové kontakty: ctx_add_person(name=..., email=..., source="gmail", status="to_verify")
   → Pre existujúcich s novou info: ctx_update("people", id, {...})
   → ctx_update_scan(source="gmail", processed=N, added=N, updated=N)

3. Slack scan (od posledného markeru):
   slack_read_channel(channel_id=..., oldest="timestamp")
   → Rovnaký vzor ako Gmail
   → ctx_update_scan(source="slack", ...)

4. Asana scan:
   search_objects/get_tasks s modified_since
   → Aktualizuj statusy projektov
   → ctx_update_scan(source="asana", ...)

5. ctx_incomplete() → priprav max 5 otázok na doplnenie
```

### Týždenná údržba — stručný prehľad

```
1. ctx_stats() + ctx_recent(7) → prehľad
2. ctx_export() → analyzuj duplicity, zlúč ak treba
3. ctx_stale(60) → označ neaktívnych (ctx_update, NIE mazať)
4. Sync s Asanou → aktualizuj statusy
5. ctx_incomplete() → prioritizované otázky
6. Vytvor weekly report
```

Pre kompletné prompty na scheduled tasks pozri `references/scheduled-tasks.md`.

---

## 8. PRINCÍPY (dodržuj vždy)

1. **NIKDY nepíš email/správu bez ctx_context().** Toto je najdôležitejšie pravidlo celého skillu. Ak DB neexistuje alebo osoba nie je nájdená, píš neutrálne — ale pokús sa lookup urobiť vždy.

2. **NIKDY nepíš do DB vymyslené informácie.** Ak nevieš, nastav `status="to_verify"`. Halucinácia v kontextovom registri je horšia ako prázdne pole.

3. **Loguj zmysluplné interakcie.** Každý odoslaný email, dôležitý call, meeting. Neloguj triviality.

4. **Pravidlá s priority=high sú POVINNÉ.** Nemôžeš ich ignorovať, ani keď sa ti zdajú nepraktické. Používateľ ich nastavil vedome.

5. **Inkrementálne updaty.** Nikdy nemažni záznamy — len pridávaj informácie alebo aktualizuj polia. Na deaktiváciu použi `status="inactive"`.

6. **Domain je dôležitý.** Správne zaraď záznamy — pomáha to pri filtrovaní. Work veci do work, zdravie do health, dom do home.

7. **Notes na všetko čo nemá vlastnú tabuľku.** Recepty, heslá, referencie, nápady, zdravotné záznamy — všetko do `ctx_add_note()` s príslušným domain a category.

8. **Ak nájdeš novú informáciu počas práce, ulož ju.** Ak z emailu zistíš že Martin zmenil rolu → `ctx_update("people", id, {"role": "nová rola"})`. Ak sa dozvieš nové pravidlo → `ctx_add_rule(...)`. Databáza rastie organicky.

9. **ANTI-DUPLICITY: Vždy hľadaj pred pridaním.** Viď sekciu 11.

10. **TAGY na ľuďoch sú povinné.** Použi tags pole pre kategorizáciu. Viď sekciu 12.

11. **LINKAGE: Prepájaj ľudí s firmami a projektmi cez ID.** Viď sekciu 13.

12. **EMAIL SIGNATURE PARSING pri každom emaile.** Viď sekciu 14.

---

## 10. ALIASY A FUZZY SEARCH

People tabuľka má `aliases` pole (TEXT, JSON array) — automaticky generované prezývky.

### 10.1 Ako funguje smart search

`ctx_person()`, `ctx_context()` a `ctx_find()` hľadajú v 4 krokoch:

1. **Exact match** — hľadá v name/email (pôvodné správanie)
2. **Alias match** — hľadá v aliases poli (napr. "Samo Skovajsa" nájde "Samuel Skovajsa")
3. **Nickname expansion** — rozloží prezývku na plné meno a skúsi znova (napr. "Peťo" → "Peter")
4. **Fuzzy surname** — porovná priezviská cez SequenceMatcher, threshold 0.75 (napr. "Schovajsa" nájde "Skovajsa" so score 0.82)

Výsledok obsahuje `_match_type` ak nebol exact match: `"alias"`, `"nickname"`, alebo `"fuzzy"`.

### 10.2 Správa aliasov

Aliasy sa generujú automaticky zo slovenského NICKNAMES dictionary (60+ mien):
- Samuel → Samo, Samko
- Peter → Peťo, Peto, Peťko
- Jakub → Kuba, Kubo, Kubko
- Katarína → Katka, Kaťa
- atď.

**Jednorazová migrácia:** `ctx_populate_aliases()` — vygeneruje aliasy pre všetkých existujúcich ľudí.

**Manuálne pridanie:** `ctx_update("people", record_id, {"aliases": "[\"prezývka\"]"})` — appenduje do existujúcich aliasov.

---

## 11. ANTI-DUPLICITY — pred pridaním VŽDY hľadaj

Toto je kritické pravidlo. V databáze sa opakovane stávali duplicity (12 duplicitných ľudí, 4 skupiny duplicitných firiem), pretože sa pred pridaním nekontrolovalo, či záznam už existuje.

### 11.1 Pred ctx_add_person() — POVINNÝ check

```
PRED pridaním novej osoby VŽDY urob:
1. ctx_find("meno osoby") → hľadaj presnú zhodu
2. Ak meno je bežné (Martin, Peter...) → hľadaj aj s priezviskom
3. Ak má email → ctx_find("email@...") → email je unikátny identifikátor
4. Ak nájdeš zhodu → ctx_update() namiesto ctx_add_person()
5. Ak nenájdeš → ctx_add_person()
```

**Typické chyby, ktoré sa stali:**
- "Dalibor Cicman" pridaný 3× (z VCF, Slacku, a manuálne)
- "ISALI s.r.o." vs "isali, s.r.o." vs "Isali s.r.o." — 3 rôzne záznamy pre jednu firmu
- "Ales Lettrich A" a "Ales Lettrich" — dva záznamy kvôli VCF formátu

### 11.2 Pred ctx_add_company() — POVINNÝ check

```
PRED pridaním firmy:
1. ctx_find("názov firmy") → hľadaj presnú zhodu
2. Hľadaj aj varianty: "Firma s.r.o." vs "Firma" vs "firma, s.r.o."
   → Normalizuj: odstráň "s.r.o.", "s. r. o.", čiarky, veľké/malé písmená
3. Ak nájdeš zhodu → ctx_update() namiesto ctx_add_company()
```

### 11.3 Pri VCF/bulk importe

Pri hromadnom importe kontaktov (VCF, CSV, Asana sync):
- VŽDY normalizuj mená (trim whitespace, odstráň čísla na konci typu "2", oprav "Osobne" suffix)
- Porovnávaj case-insensitive
- Ak meno existuje s iným emailom → pravdepodobne tá istá osoba, NEPRIDÁVAJ duplicitu
- Ak meno existuje a nový záznam nemá email → NEPRIDÁVAJ, iba aktualizuj existujúci

---

## 12. TAGY NA ĽUĎOCH

People tabuľka má `tags` pole (TEXT, JSON array). Použi ho na kategorizáciu ľudí.

### 12.1 Štandardné tagy

| Tag | Kedy použiť |
|-----|------------|
| `me-clen` | Člen Miliónovej Evolúcie |
| `me-speaker` | Speaker/hosť na ME evente |
| `investor` | Investor alebo investičný kontakt |
| `partner` | Biznis partner |
| `team-satori` | Člen Satori tímu (Alexandra, Martin, Samuel...) |
| `supplier` | Dodávateľ služieb (účtovník, právnik, dizajnér...) |
| `media` | Novinár, podcaster, influencer |
| `family` | Rodinný príslušník |
| `mentor` | Mentor alebo mentee |
| `prospect` | Potenciálny klient/člen |
| `friend` | Osobný priateľ |

### 12.2 Formát a použitie

```
ctx_update("people", record_id, {"tags": "[\"me-clen\", \"investor\"]"})
```

Tags je JSON array ako string. Pri aktualizácii vždy zachovaj existujúce tagy a pridaj nové.

### 12.3 Kedy tagovať

- Pri pridaní novej osoby → ak vieš kategóriu, hneď tagni
- Pri scane emailov/Slacku → ak kontext napovedá (napr. správa z #me-predaj → prospect)
- Pri spracovaní Asana taskov → ak task súvisí s ME → tagni assignees
- Pri čítaní emailu → ak podpis napovedá rolu/firmu → tagni podľa relationship

---

## 13. LINKAGE — prepájanie ľudí, firiem a projektov

### 13.1 Problém

V databáze sú ľudia, firmy a projekty väčšinou neprepojené:
- `company_id` (foreign key) sa takmer nikdy nepoužíva — len `company_name` (text)
- `projects` pole na ľuďoch je takmer vždy prázdne
- `team` pole na projektoch je takmer vždy prázdne

### 13.2 Pravidlá pre linkage

**Pri pridávaní/aktualizácii osoby:**
```
1. Ak vieš firmu → nastav OBE polia: company_name (text) + company_id (FK)
   → ctx_find("firma") → ak firma existuje v DB, vezmi jej ID
   → ctx_update("people", person_id, {"company_name": "Firma", "company_id": firma_id})

2. Ak vieš projekt → pridaj do projects poľa (JSON array)
   → ctx_update("people", person_id, {"projects": "[\"Projekt A\", \"Projekt B\"]"})
```

**Pri pridávaní/aktualizácii projektu:**
```
1. Ak vieš firmu → nastav company_name + company_id
2. Ak vieš tím → nastav team (JSON array mien)
   → ctx_update("projects", project_id, {"team": "[\"Meno 1\", \"Meno 2\"]"})
```

**Pri spracovaní emailov/meetingov:**
- Ak osoba diskutuje o projekte → pridaj projekt do jej `projects` poľa
- Ak osoba je z firmy (vidno v podpise) → nastav `company_name` + `company_id`
- Ak projekt má nového člena tímu → pridaj do `team`

---

## 14. EMAIL SIGNATURE PARSING

Pri čítaní emailov VŽDY parsuj podpis odosielateľa. Podpisy obsahujú cenné dáta, ktoré inak chýbajú v DB.

### 14.1 Čo extrahovať z podpisu

| Dáta | Kde hľadať | Príklad |
|------|---------|---------|
| Telefón | `+421...`, `09...`, `+420...`, `📞`, `tel:`, `phone:` | +421 908 504 432 |
| Rola/titul | Text pred `@`, `|`, alebo na samostatnom riadku | "CEO Associate @ GymBeam" |
| Firma | Za `@` alebo `|`, alebo URL v podpise | GymBeam |
| Web | URL pattern | gymbeam.com |

### 14.2 Kedy parsovať

- **Pri KAŽDOM čítaní emailu** kde odosielateľ je v DB
- Skontroluj či máme phone, role, company_name
- Ak chýba → extrahuj z podpisu a ulož cez ctx_update()
- **NEPREPÍŠ existujúcu rolu** — len doplň prázdne polia

### 14.3 Kde nájsť podpis

Podpis je zvyčajne za jedným z:
- `--` (dvojitá pomlčka)
- `Kind regards`, `Best regards`, `S pozdravom`, `Prajem krásny deň`
- Posledné 5-10 riadkov emailu

---

## 9. REFERENCIE

Pre detailnejšie informácie načítaj tieto súbory (sú relatívne k skill path):

| Súbor | Čo obsahuje | Kedy načítať |
|-------|------------|--------------|
| `../references/schema.md` | Kompletná DB schéma — všetky tabuľky a polia | Keď potrebuješ vedieť presné polia |
| `../references/scanning-guide.md` | Detailný postup pre scanning zdrojov | Pri scanning taskoch |
| `../references/scheduled-tasks.md` | Hotové prompty pre scheduled tasks | Pri nastavovaní scheduled tasks |
| `../ARCHITECTURE.md` | Architektúra, rollout plán, FAQ | Pre pochopenie celkového dizajnu |
