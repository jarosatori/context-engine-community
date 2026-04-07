---
title: Context Engine
description: Štruktúrovaná dlhodobá pamäť pre Claude — ľudia, firmy, projekty, pravidlá, interakcie a poznámky cez MCP
license: MIT
---

# Context Engine

> **Štruktúrovaná dlhodobá pamäť pre Claude.** Databáza ľudí, firiem, projektov, pravidiel, interakcií a poznámok dostupná cez MCP zo všetkých Claude klientov (Claude Code, Cowork/Claude.ai, agenti).

Context Engine je MCP server, ktorý dáva Claude (alebo akémukoľvek MCP klientovi) prístup k tvojej osobnej znalostnej databáze. Pred každým emailom Claude vie tón, jazyk a vzťah s príjemcom. Pri každom úlohe vie tím, deadline a kontext projektu. Pri každom mene vie kto je kto.

**Kľúčové vlastnosti:**

- 🧠 **Štruktúrovaná pamäť** — SQLite databáza s tabuľkami pre ľudí, firmy, projekty, produkty, pravidlá, interakcie, action items, rozhodnutia, meeting participants, poznámky
- 🔍 **Smart search** — exact match → alias match → expansion prezývok → fuzzy matching priezvisk (Levenshtein). Slovenský nickname dictionary so 118 menami, tolerantný na diakritiku
- 🌐 **Multi-domain** — work, personal, home, health, finance, family, education
- 🔌 **30+ MCP tools** — `ctx_find`, `ctx_context`, `ctx_person`, `ctx_log`, `ctx_add_*`, `ctx_update`, `ctx_stats` a ďalšie
- 📥 **Full-text search** cez SQLite FTS5
- 🚀 **Dva deployment módy** — lokálne na PC alebo na Railway s OAuth zabezpečením
- 🤝 **Multi-client** — ten istý server obsluhuje Claude Code, Cowork, mobilných klientov a agentov naraz

---

## Pre koho je toto?

Tento repo bol pripravený pre účastníkov **Claude Bootcampu** od [Jaroslava Chrapka](https://www.linkedin.com/in/jaroslavchrapko/) — komunity podnikateľov, ktorí používajú Claude ako svoj primárny pracovný nástroj.

Ak si v Claude Bootcampe (alebo Miliónovej Evolúcii), tento Context Engine je tvoja cesta k tomu, aby Claude vedel kto sú tvoji ľudia, čo sú tvoje pravidlá komunikácie, a aký je kontext tvojich projektov — bez toho, aby si mu to musel vždy znova vysvetľovať.

**Ale samozrejme — je to MIT licencované**, takže ho môže použiť ktokoľvek na čokoľvek.

---

## Quick Start

### 1. Vyber si deployment

| Možnosť | Pre koho | Náročnosť | Cena |
|---------|----------|-----------|------|
| **A) Lokálne na PC** | Začiatočník, jeden user, jeden PC | ⭐ Easy (10 min) | Zadarmo |
| **B) Railway s OAuth** | Viac zariadení, agenti, production setup | ⭐⭐⭐ Medium (30 min) | ~5 USD/mes |

Detailný návod (oba postupy) je v [`SETUP-GUIDE.md`](./SETUP-GUIDE.md).

### 2. Spusti onboarding cez Claude

Najjednoduchšia cesta — nech ťa Claude prevedie celým procesom:

```
Prečítaj si súbor SETUP-GUIDE.md a skill-onboarding/SKILL.md v tomto foldri.
Potom ma preveď kompletným setupom Context Engine krok po kroku.
Začni FÁZOU 0.5 — opýtaj sa ma, či chcem inštaláciu lokálne na PC
alebo deployment na Railway s OAuth.
```

Claude prečíta inštrukcie a sám ťa povedie. Nemusíš vedieť nič technické.

---

## Architektúra

```
┌─────────────────────────────────────────────────┐
│  MCP Klienti (paralelne, zdieľaná DB)           │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Claude   │ │ Cowork   │ │ Agenti, mobil... │ │
│  │ Code     │ │ (web)    │ │                  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────────────┘ │
└───────┼────────────┼────────────┼────────────────┘
        │            │            │
        └────────────┴────────────┘
                     │
                 OAuth/SSE
                     │
        ┌────────────▼────────────┐
        │  Context Engine MCP     │
        │  Server (Python)        │
        │  ┌────────────────────┐ │
        │  │ FastMCP (SSE)      │ │
        │  │ + OAuth middleware │ │
        │  └────────┬───────────┘ │
        │           │             │
        │  ┌────────▼───────────┐ │
        │  │ db.py (sqlite3)    │ │
        │  │ + nicknames.py     │ │
        │  │ + fuzzy search     │ │
        │  └────────┬───────────┘ │
        └───────────┼─────────────┘
                    │
        ┌───────────▼─────────────┐
        │  SQLite + FTS5          │
        │  (lokálny .db alebo     │
        │   Railway volume)       │
        └─────────────────────────┘
```

**Tabuľky:** `people`, `companies`, `projects`, `products`, `rules`, `interactions`, `notes`, `action_items`, `decisions`, `meeting_participants`, `scan_log`

---

## Hlavné MCP nástroje

| Nástroj | Účel |
|---------|------|
| `ctx_context(query)` | **PRED každým emailom** — vráti formality, tón, jazyk, pravidlá, posledné interakcie |
| `ctx_person(query)` | Detail osoby vrátane projektov, pravidiel, action items, meetingov |
| `ctx_find(query)` | Hľadanie naprieč všetkými tabuľkami (FTS5 + alias + fuzzy) |
| `ctx_company(query)` | Detail firmy s ľuďmi, projektmi, produktmi |
| `ctx_project(query)` | Detail projektu s tímom |
| `ctx_log(...)` | Záznam interakcie (email, call, meeting, slack) |
| `ctx_add_person(...)` | Pridanie nového kontaktu |
| `ctx_add_rule(...)` | Pridanie komunikačného pravidla |
| `ctx_update(table, id, data)` | Aktualizácia akéhokoľvek záznamu |
| `ctx_stats()` | Štatistiky DB |

Plný zoznam (30+ nástrojov) v [`skill/SKILL.md`](./skill/SKILL.md).

---

## Smart search (aliasy + fuzzy matching)

Slovenské mená majú prezývky a často sa píšu bez diakritiky. Context Engine to rieši automaticky:

```python
ctx_person("Samo Skovajsa")     # → Samuel Skovajsa (alias)
ctx_person("Peťo Ďurák")        # → Peter Ďurák (alias)
ctx_person("Frantisek Novak")   # → František Novák (diakritika)
ctx_person("Samo Schovajsa")    # → Samuel Skovajsa (fuzzy, score 0.82)
```

Search flow:
1. **Exact** — name/email LIKE match
2. **Alias** — hľadanie v `aliases` JSON poli
3. **Nickname expansion** — "Samo" → "Samuel", "Peťo" → "Peter"
4. **Fuzzy surname** — SequenceMatcher s threshold 0.75

NICKNAMES dictionary obsahuje 118 slovenských mien (mužských + ženských), s podporou diakritika-insensitive matchovania. Migračný script `ctx_populate_aliases()` automaticky vygeneruje aliasy pre celú DB.

---

## Štruktúra repa

```
context-engine-community/
├── src/context_engine/
│   ├── server.py              # FastMCP server entry point
│   ├── db.py                  # SQLite layer + smart search
│   ├── nicknames.py           # Slovak nickname dictionary
│   ├── models.py              # Pydantic input validation
│   ├── oauth_server.py        # OAuth provider
│   └── combined_server.py     # OAuth + MCP combined entrypoint
├── tests/test_db.py           # 33 tests
├── skill/SKILL.md             # Behavioral guide pre Claude
├── skill-onboarding/SKILL.md  # Guided setup skill
├── SETUP-GUIDE.md             # Krok po kroku návod (lokálne + Railway)
├── Dockerfile                 # Docker image pre Railway
├── railway.toml               # Railway deployment config
├── start.sh                   # Server startup script
├── pyproject.toml             # Python deps
├── .env.example               # Template environment variables
├── LICENSE                    # MIT
└── README.md
```

---

## Inštalácia (rýchla verzia pre netrpezlivých)

### Lokálne

```bash
git clone https://github.com/jarosatori/context-engine-community.git
cd context-engine-community
pip install -e .
python3 -c "from context_engine.db import init_db; print(init_db())"
```

Pridaj do `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "context-engine": {
      "command": "context-engine"
    }
  }
}
```

Reštartni Claude Code → spusti `ctx_init()` → hotovo.

### Railway s OAuth

Detailný 9-krokový postup v [`SETUP-GUIDE.md`](./SETUP-GUIDE.md#fáza-1b-railway-deployment-s-oauth-20-30-minút).

---

## Príspevky

PR-y sú vítané — od fixu typo až po nové NICKNAMES, scan integrácie, alebo nové MCP nástroje. Sleduj:

1. Forkni repo
2. Vytvor branch (`git checkout -b feature/moja-vec`)
3. Spusti testy (`pytest tests/`)
4. Otvor pull request s popisom čo sa zmenilo a prečo

Pre väčšie zmeny otvor najprv issue na diskusiu.

---

## Časté otázky

**Q: Je toto bezpečné? Moje dáta sú v SQLite, kde to je?**
A: Lokálny mode → tvoje dáta sú vo súbore na tvojom PC (default `~/.context-engine/context-engine.db`). Railway mode → na Railway perzistentnom volume v EU/US regióne, zabezpečené OAuth-om. Žiadne dáta neopúšťajú tvoj setup, žiadny third-party tracking.

**Q: Funguje to s inými LLM, nielen s Claude?**
A: Áno — Context Engine je štandardný MCP server. Funguje s Claude Code, Cowork (Claude.ai), Cursor, Continue, alebo akýmkoľvek MCP klientom. Aj custom agenti (OpenClaw, LangChain s MCP adapterom) sa vedia pripojiť.

**Q: Môžem mať viac inštancií?**
A: Áno — môžeš mať lokálnu DB pre osobné veci a Railway DB pre prácu, alebo viacero Railway inštancií. Každá je oddelená svojím endpointom.

**Q: Ako urobím backup?**
A: Stačí skopírovať `.db` súbor. Pri Railway: `railway run cp /data/context-engine.db ./backup.db`.

**Q: Môžem to predávať ako vlastný produkt?**
A: Áno — MIT licencia to dovoľuje. Stačí zachovať `LICENSE` súbor s pôvodným copyright.

---

## Licencia

MIT — viď [`LICENSE`](./LICENSE) súbor.

Copyright © 2026 [Jaroslav Chrapko](https://www.linkedin.com/in/jaroslavchrapko/)

---

## Prepojenia

- 🎓 **Claude Bootcamp** (Jaroslav Chrapko) — komunita podnikateľov používajúcich Claude ako primárny pracovný nástroj
- 🌱 **Miliónová Evolúcia** — vzdelávacia spoločnosť pre podnikateľov
- 💼 **LinkedIn:** [Jaroslav Chrapko](https://www.linkedin.com/in/jaroslavchrapko/)
- 🐛 **Issues:** [github.com/jarosatori/context-engine-community/issues](https://github.com/jarosatori/context-engine-community/issues)
