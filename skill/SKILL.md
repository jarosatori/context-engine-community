---
name: context-engine
description: "Strukturovana kontextova pamat pre cely zivot. Udrzuje databazu ludi, firiem, projektov, produktov, pravidiel, interakcii a poznamok. Pouzi VZDY ked: pises email alebo spravu (na zistenie tonu, tykania/vykania, kontextu vztahu), pracujes s Asana taskami (na pochopenie projektu a timu), pripravujes cokolvek pre konkretnu osobu alebo firmu, potrebujes vediet kto je kto, potrebujes si nieco zapamatat. Spustaj aj ked task zmienuje meno osoby, nazov firmy, alebo projekt. Pouzi aj na osobne veci — dom, zdravie, financie, rodina. Tento skill je 'vzdy zapnuty'."
---

# Context Engine — Behavioral Guide

Toto je tvoja dlhodobá pamäť. SQLite databáza s ľuďmi, firmami, projektami, produktmi, pravidlami, interakciami a poznámkami. Pokrýva prácu aj osobný život cez domain systém.

Všetky operácie robíš cez MCP tooly s prefixom `ctx_*`.

---

## 1. AUTO-TRIGGERY — kedy sa aktivuješ

Spusti Context Engine **automaticky** (bez toho, aby sa ťa používateľ pýtal) keď:

| Trigger | Čo urobiť | Príklad |
|---------|-----------|---------|
| Píšeš email alebo správu | `ctx_context("meno")` PRED písaním | "Napíš email Martinovi" |
| Task zmieňuje meno osoby | `ctx_person("meno")` | "Zavolaj Janke" |
| Task zmieňuje firmu | `ctx_company("firma")` | "Priprav ponuku pre Acme" |
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
| Osobná poznámka | `ctx_add_note(title, content, domain)` | "Mám termín u lekára 15.3." |
| Procesné pravidlo | `ctx_add_rule(context, rule, category="procesy")` | "Faktúry vždy v EUR" |

**Po pridaní vždy potvrď** čo si uložil, stručne.

### 2.5 Po odoslaní emailu / po callu / po meetingu

```
ctx_log(
    person_name="Meno",
    channel="email|call|meeting|slack",
    direction="outgoing|incoming|both",
    summary="Stručné zhrnutie",
    context="Názov projektu ak relevantné",
    date="YYYY-MM-DD"
)
```

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

---

## 3. AKTÍVNE DOPYTOVANIE

Context Engine nie je pasívny archív. Aktívne sa pýtaj na chýbajúce informácie.

### 3.1 Pri lookup-e s dierami (PRED komunikáciou)

| Čo chýba | Ako sa opýtať |
|-----------|--------------|
| `formality: "uncertain"` | "Martinovi tykáme alebo vykáme?" |
| `tone: null` | "Aký tón s Martinom — formálny, priateľský, vecný?" |
| `language: null` | "Píšeme Martinovi po slovensky alebo anglicky?" |

**Pravidlo:** Max 2-3 otázky naraz. Pýtaj sa LEN na to čo reálne potrebuješ.

Po odpovedi okamžite ulož:
```
ctx_update("people", record_id, {"formality": "ty", "tone": "priatelsky"})
```

---

## 4. DOMAIN SYSTÉM

| Domain | Čo tam patrí |
|--------|-------------|
| **work** | Pracovné kontakty, klienti, projekty, pravidlá |
| **personal** | Osobné poznámky, nápady, referencie |
| **home** | Dom, nehnuteľnosti, dodávatelia, údržba |
| **health** | Zdravotné záznamy, lekári, lieky, termíny |
| **finance** | Finančné poznámky, účty, investície |
| **family** | Rodina, udalosti, kontakty |
| **education** | Kurzy, učenie, certifikácie |

---

## 5. TOOL REFERENCIA

### Vyhľadávanie (read-only, bezpečné volať kedykoľvek)

| Tool | Kedy | Čo vráti |
|------|------|----------|
| `ctx_find(query, domain?)` | Hľadáš čokoľvek | Výsledky zo všetkých tabuliek (hľadá aj v aliasoch a prezývkach) |
| `ctx_context(query)` | **PRED emailom/správou** | Formality, tón, jazyk, firma, interakcie, pravidlá |
| `ctx_person(query)` | Potrebuješ detail osoby | Údaje + interakcie + projekty + pravidlá. Podporuje prezývky ("Samo" → "Samuel") a fuzzy matching priezvisk ("Schovajsa" → "Skovajsa") |
| `ctx_company(query)` | Potrebuješ detail firmy | Firma + ľudia + projekty + produkty |
| `ctx_project(query)` | Potrebuješ detail projektu | Projekt + tím s detailmi |
| `ctx_find_notes(query, domain?, category?)` | Hľadáš v poznámkach | Poznámky matchujúce query |
| `ctx_get_note(note_id)` | Detail jednej poznámky | Kompletná poznámka podľa ID |

### Action items a rozhodnutia

| Tool | Kedy |
|------|------|
| `ctx_action_items(status?, owner?, project_id?)` | Prehľad úloh z meetingov |
| `ctx_mark_action_done(item_id, asana_task_id?)` | Posunul si úlohu do Asany |
| `ctx_decisions(project_id?, status?)` | "Čo sme sa dohodli?" |
| `ctx_meeting_participants(interaction_id?, person_id?)` | Kto bol na meetingu? |

### Pridávanie (zapisuje do DB)

| Tool | Kedy |
|------|------|
| `ctx_add_person(name, email?, company_name?, role?, formality?, tone?, language?, domain?)` | Nový kontakt |
| `ctx_add_company(name, type?, industry?, my_role?, domain?)` | Nová firma |
| `ctx_add_project(name, company_name?, description?, type?, team?, domain?)` | Nový projekt |
| `ctx_add_product(name, company_name?, price?, format?, domain?)` | Nový produkt/služba |
| `ctx_add_rule(context, rule, priority?, category?, applies_to?, domain?)` | Nové pravidlo |
| `ctx_add_note(title, content?, domain?, category?, tags?)` | Poznámka/znalosť |
| `ctx_log(person_name?, channel?, direction?, summary?, context?, date?)` | Záznam interakcie |

### Aktualizácia a údržba

| Tool | Kedy |
|------|------|
| `ctx_update(table, record_id, data)` | Zmena existujúceho záznamu. Pre aliases: automaticky appenduje do existujúceho JSON array |
| `ctx_populate_aliases()` | Jednorazová migrácia: vygeneruje aliasy (prezývky) pre všetkých ľudí. Bezpečné spustiť opakovane |
| `ctx_stats(domain?)` | Štatistiky registra |
| `ctx_incomplete(domain?)` | Záznamy na doplnenie |
| `ctx_stale(days?, domain?)` | Zastarané záznamy |
| `ctx_recent(days?, domain?)` | Posledné zmeny |
| `ctx_export(domain?)` | Export celého registra |

### Scan management

| Tool | Kedy |
|------|------|
| `ctx_scan_status()` | Stav posledných scanov |
| `ctx_set_scan(source, timestamp)` | Nastav scan marker |
| `ctx_update_scan(source, processed, added, updated, notes?)` | Zaloguj dokončený scan |

---

## 6. ALIASY A FUZZY SEARCH

People tabuľka má `aliases` pole (TEXT, JSON array) — automaticky generované prezývky.

### 6.1 Ako funguje smart search

`ctx_person()`, `ctx_context()` a `ctx_find()` hľadajú v 4 krokoch:

1. **Exact match** — hľadá v name/email (pôvodné správanie)
2. **Alias match** — hľadá v aliases poli (napr. "Samo Skovajsa" nájde "Samuel Skovajsa")
3. **Nickname expansion** — rozloží prezývku na plné meno a skúsi znova (napr. "Peťo" → "Peter")
4. **Fuzzy surname** — porovná priezviská cez SequenceMatcher, threshold 0.75 (napr. "Schovajsa" nájde "Skovajsa" so score 0.82)

Výsledok obsahuje `_match_type` ak nebol exact match: `"alias"`, `"nickname"`, alebo `"fuzzy"`.

### 6.2 Správa aliasov

Aliasy sa generujú automaticky zo slovenského NICKNAMES dictionary (60+ mien):
- Samuel → Samo, Samko
- Peter → Peťo, Peto, Peťko
- Jakub → Kuba, Kubo, Kubko
- Katarína → Katka, Kaťa
- atď.

**Jednorazová migrácia:** `ctx_populate_aliases()` — vygeneruje aliasy pre všetkých existujúcich ľudí.

**Manuálne pridanie:** `ctx_update("people", record_id, {"aliases": "[\"prezývka\"]"})` — appenduje do existujúcich aliasov.

---

## 7. ANTI-DUPLICITY — pred pridaním VŽDY hľadaj

```
PRED pridaním novej osoby:
1. ctx_find("meno osoby") → hľadaj presnú zhodu
2. Ak má email → ctx_find("email@...") → email je unikátny identifikátor
3. Ak nájdeš zhodu → ctx_update() namiesto ctx_add_person()
4. Ak nenájdeš → ctx_add_person()
```

Rovnaký postup pre firmy — hľadaj varianty ("Firma s.r.o." vs "Firma").

---

## 8. LINKAGE — prepájanie ľudí, firiem a projektov

Pri pridávaní/aktualizácii osoby:
```
1. Ak vieš firmu → nastav OBE polia: company_name (text) + company_id (FK)
   → ctx_find("firma") → ak firma existuje v DB, vezmi jej ID
   → ctx_update("people", person_id, {"company_name": "Firma", "company_id": firma_id})

2. Ak vieš projekt → pridaj do projects poľa (JSON array)
   → ctx_update("people", person_id, {"projects": '["Projekt A", "Projekt B"]'})
```

Pri pridávaní/aktualizácii projektu:
```
1. Ak vieš firmu → nastav company_name + company_id
2. Ak vieš tím → nastav team (JSON array mien)
   → ctx_update("projects", project_id, {"team": '["Meno 1", "Meno 2"]'})
```

---

## 9. TAGY NA ĽUĎOCH

People tabuľka má `tags` pole (TEXT, JSON array). Použi ho na kategorizáciu.

Príklady tagov (prispôsob podľa potreby):

| Tag | Kedy použiť |
|-----|------------|
| `klient` | Klient / zákazník |
| `partner` | Biznis partner |
| `tim` | Člen tímu |
| `dodavatel` | Dodávateľ služieb (účtovník, právnik...) |
| `investor` | Investor alebo investičný kontakt |
| `rodina` | Rodinný príslušník |
| `priatel` | Osobný priateľ |

Formát:
```
ctx_update("people", record_id, {"tags": '["klient", "partner"]'})
```

Pri aktualizácii vždy zachovaj existujúce tagy a pridaj nové.

---

## 10. EMAIL SIGNATURE PARSING

Pri čítaní emailov parsuj podpis odosielateľa. Podpisy obsahujú cenné dáta.

Čo extrahovať: telefón, rola/titul, firma, web.

Kde hľadať podpis: za `--`, za `Best regards` / `S pozdravom`, alebo posledných 5-10 riadkov emailu.

Pravidlá:
- Ak odosielateľ je v DB a chýba mu phone/role/company → doplň z podpisu
- NEPREPÍŠ existujúcu rolu — len doplň prázdne polia
- Po extrakcii → `ctx_update("people", id, {extrahované dáta})`

---

## 11. INTEGRAČNÉ VZORY

### Email workflow
```
1. ctx_context("meno príjemcu") → formality, tone, language, rules
2. Napíš email podľa kontextu (VŽDY len DRAFT)
3. ctx_log(person_name, channel="email", direction="outgoing", summary="...")
```

### Meeting workflow
```
1. ctx_log(channel="meeting", summary="...") → dostaneš interaction_id
2. Pre účastníkov: ctx_update("meeting_participants", ...)
3. Pre úlohy: ctx_update("action_items", ...)
4. Pre rozhodnutia: ctx_update("decisions", ...)
```

### Scan workflow (Gmail/Slack/Asana)
```
1. ctx_scan_status() → zisti posledné scan timestamps
2. Prejdi nové správy od posledného markeru
3. Pre nové kontakty: ctx_add_person(status="to_verify")
4. Pre existujúcich s novou info: ctx_update()
5. ctx_update_scan(source, processed, added, updated)
```

---

## 12. PRINCÍPY (dodržuj vždy)

1. **NIKDY nepíš email/správu bez ctx_context().** Najdôležitejšie pravidlo.
2. **NIKDY nepíš do DB vymyslené informácie.** Ak nevieš → `status="to_verify"`.
3. **Loguj zmysluplné interakcie.** Každý email, call, meeting.
4. **Pravidlá s priority=high sú POVINNÉ.** Nemôžeš ich ignorovať.
5. **Inkrementálne updaty.** Nikdy nemažni — len pridávaj alebo `status="inactive"`.
6. **Domain je dôležitý.** Správne zaraď záznamy.
7. **Notes na všetko čo nemá vlastnú tabuľku.** Recepty, heslá, nápady → `ctx_add_note()`.
8. **Ak nájdeš novú informáciu, ulož ju.** DB rastie organicky.
9. **ANTI-DUPLICITY: Vždy hľadaj pred pridaním.** Viď sekciu 7.
10. **LINKAGE: Prepájaj ľudí s firmami cez ID.** Viď sekciu 8.
11. **TAGY na ľuďoch.** Viď sekciu 9.
12. **EMAIL SIGNATURE PARSING pri každom emaile.** Viď sekciu 10.
