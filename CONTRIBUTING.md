---
title: Contributing to Context Engine
description: Guide pre prispievateľov — ako pridať feature, fix bug alebo nový NICKNAMES záznam
---

# Prispievanie do Context Engine

Ďakujem za záujem prispieť! Tento projekt rastie organicky s komunitou Claude Bootcampu a vďaka externým prispievateľom.

## Typy príspevkov

- 🐛 **Bug fixes** — našiel si chybu? Otvor issue alebo rovno PR.
- ✨ **Nové features** — nový MCP nástroj, nová tabuľka, nová integrácia. Pre väčšie zmeny otvor najprv issue.
- 📚 **Dokumentácia** — fix typo, zlepšenie SETUP-GUIDE, nové FAQ.
- 🌍 **NICKNAMES dictionary** — doplnenie chýbajúcich slovenských mien (alebo českých/poľských ekvivalentov).
- 🧪 **Testy** — vždy vítané, najmä pre edge cases.

## Ako prispieť (krok za krokom)

### 1. Forkni repo

Klikni "Fork" vpravo hore na GitHub stránke.

### 2. Klonuj svoj fork

```bash
git clone https://github.com/TVOJ_USERNAME/context-engine-community.git
cd context-engine-community
```

### 3. Nainštaluj dev dependencies

```bash
pip install -e ".[dev]"
```

### 4. Vytvor branch

```bash
git checkout -b feature/moja-zmena
# alebo
git checkout -b fix/nazov-bugu
```

### 5. Sprav zmeny + spusti testy

```bash
pytest tests/ -v
```

Všetky existujúce testy musia prejsť. Ak pridávaš nový feature, **napíš preňho test**.

### 6. Commit s jasnou správou

```bash
git commit -m "Add NICKNAMES for Czech names (Honza, Pepa, Mirek)"
```

Commit message convention:
- `Add ...` — nový feature/súbor
- `Fix ...` — bug fix
- `Update ...` — zlepšenie existujúcej veci
- `Refactor ...` — zmena kódu bez funkčnej zmeny
- `Docs: ...` — len dokumentácia
- `Test: ...` — len testy

### 7. Push a otvor PR

```bash
git push origin feature/moja-zmena
```

Otvor pull request na GitHub. V popise PR:
- **Čo** sa zmenilo
- **Prečo** (motivácia, link na issue ak existuje)
- **Ako otestovať** (kroky pre reviewera)

## Pridanie nového mena do NICKNAMES

Najjednoduchší typ príspevku. Edit `src/context_engine/nicknames.py`:

```python
NICKNAMES = {
    # ...existujúce mená...
    "Vladimír": ["Vlado", "Vladko"],  # ← nový záznam
}
```

Pravidlá:
- **Plné meno s diakritikou** ako kľúč
- **Zoznam prezývok** ako hodnota (case-sensitive, zachovaj diakritiku)
- Diakritika-insensitive matching funguje automaticky cez `_strip_diacritics()`
- Pri kolíziách (napr. "Maťo" je prezývka pre Martin aj Matej) — keep first wins

Po pridaní spusti testy:
```bash
pytest tests/test_db.py -v
```

A otvor PR s popisom čo si pridal a prečo.

## Pridanie nového MCP nástroja

1. Definuj funkciu v `src/context_engine/db.py`:
```python
def my_new_tool(query: str, db_path: str | None = None) -> dict:
    """Stručný docstring."""
    with get_db(db_path) as db:
        # logika
        return {"status": "ok", "result": ...}
```

2. Pridaj wrapper v `src/context_engine/server.py`:
```python
@mcp.tool()
def ctx_my_new_tool(query: str) -> dict:
    """Slovenský popis pre Claude — kedy a ako použiť."""
    return db.my_new_tool(query)
```

3. Pridaj test do `tests/test_db.py`:
```python
def test_my_new_tool(self):
    db.add_record("people", {"name": "Test"}, self.db_path)
    result = db.my_new_tool("Test", self.db_path)
    assert result["status"] == "ok"
```

4. Updatni `skill/SKILL.md` — pridaj nový riadok do tabuľky nástrojov.

## Pravidlá kvality kódu

- **Žiadne breaking changes** bez diskusie — existujúce nástroje musia ostať funkčné
- **Bezpečnosť** — nikdy nepridávaj raw SQL string interpoláciu (vždy parametrizované queries)
- **Validácia vstupov** — používaj `_validate_table()` a `_validate_columns()`
- **Slovenčina v docstringoch** pre `@mcp.tool()` (Claude potrebuje slovenský popis)
- **Žiadne secrets v kóde** — všetko cez env vars

## Code review process

PR-y reviewuje maintainer (zatiaľ @jarosatori). Dostávaš spätnú väzbu, niekedy návrhy na zmeny. Po schválení sa PR mergne do `main`.

## Bezpečnostné chyby

Ak nájdeš security vulnerability, **neotvor public issue**. Napíš priamo Jarovi cez LinkedIn alebo email.

## Code of Conduct

Buď slušný, konštruktívny a otvorený. Toto je komunitný projekt — všetci sme tu aby sme sa učili a posúvali Context Engine ďalej.

## Otázky?

Otvor GitHub Discussion alebo issue s tagom `question`.

Ďakujem za príspevok! 🚀
