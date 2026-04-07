---
name: context-engine-setup
description: "Guided setup Context Engine — krok po kroku od nuly po funkčný systém. Podporuje dve cesty: lokálnu inštaláciu na PC alebo deployment na Railway s OAuth zabezpečením. Použi keď: používateľ chce nainštalovať Context Engine, nastaviť MCP, deploynúť na Railway, pripojiť do Cowork, prvýkrát naplniť databázu, nastaviť pravidlá komunikácie, pridať prvých ľudí a firmy. Spúšťaj aj keď používateľ povie: setup context engine, nastav pamäť, inštaluj CE, deployni context engine, pripoj context engine, chcem context engine, nastav mi MCP, chcem dlhodobú pamäť, chcem mať CE na Railway."
---

# Context Engine — Guided Setup Skill

Toto je onboarding skill. Keď ho Claude načíta, aktívne naviguje nového používateľa celým procesom.

**DÔLEŽITÉ:** Tento skill je pre NOVÝCH používateľov. Nepoužívaj ho na existujúce databázy.

---

## KROK 0: Detekcia prostredia

Na začiatku zisti v akom prostredí používateľ je:

```
1. Skús zavolať ctx_stats()
   ├── Funguje → Context Engine je už pripojený
   │   ├── Má dáta (people > 0) → "CE je už nastavený. Chceš niečo doplniť?"
   │   └── Prázdna DB → Prejdi na KROK 4 (naplnenie)
   └── Nefunguje (tool not found) → CE ešte nie je pripojený
       └── Prejdi na KROK 0.5 (výber deploymentu)
```

---

## KROK 0.5: Výber deploymentu (POVINNÉ pred inštaláciou)

Pred akoukoľvek inštaláciou musíš s používateľom vyriešiť **kde to bude bežať**. Sú dve možnosti — vysvetli mu obe a pomôž mu vybrať.

```
"Pred inštaláciou si musíme vybrať, ako chceš Context Engine spustiť.
Sú dve cesty:

🅰️  LOKÁLNE NA PC (jednoduchšie, free)
   • Beží na tvojom Macu/PC
   • Funguje len keď máš PC zapnutý
   • Pre Cowork (web) potrebuješ ngrok tunel
   • Inštalácia ~10 min
   • Vhodné: jeden user, jeden PC, technicky zdatný

🅱️  RAILWAY CLOUD S OAUTH (production setup, ~5 USD/mes)
   • Beží 24/7 na Railway cloud
   • Pripojí sa Claude Code, Cowork, mobil, agenti — všetko naraz
   • Zabezpečené OAuth-om (GitHub login)
   • Inštalácia ~30 min (jednorázovo)
   • Vhodné: viac zariadení, viac klientov, ozajstný production setup
   • Toto používa Jaro

Pre väčšinu nových používateľov odporúčam ZAČAŤ LOKÁLNE — vyskúšaš si CE,
naučíš sa ho používať, a ak chceš neskôr presunúť na Railway, dáta sa
dajú jednoducho preniesť (jeden .db súbor).

Ktorú cestu chceš?
A) Lokálne
B) Railway
?)  Nie som si istý — pomôž mi vybrať
```

**Ak používateľ povie "?" — pomôž mu rozhodnúť:**

Polož 3 otázky:
1. "Budeš CE používať len na jednom počítači, alebo aj na inom zariadení/agente?"
2. "Si OK s tým, že si platíš ~5 USD/mes Railway hosting?"
3. "Si komfort s GitHub a s tým že dáta budú v cloude (Railway region EU/US)?"

Logika:
- Odpovede: "len jeden PC" + "neplatím" + "preferujem lokálne" → **Lokálne (A)**
- Odpovede: "viac zariadení" alebo "chcem 24/7 prístup" alebo "som OK platit" → **Railway (B)**
- Akákoľvek pochybnosť → **Lokálne (A)** (možnosť presunúť neskôr)

**Po výbere:**
- A → Prejdi na **KROK 1A: Lokálna inštalácia**
- B → Prejdi na **KROK 1B: Railway deployment**

---

## KROK 1A: Lokálna inštalácia (alternatíva ku KROK 1B)

Opýtaj sa používateľa:

```
"Ahoj! Idem ti pomôcť nastaviť Context Engine — tvoju dlhodobú pamäť.

Najprv zistím kde si:
1. Máš otvorený terminál / Claude Code? Alebo si v Cowork (desktop app)?
2. Máš na počítači Python 3.10+? (ak nevieš, spusti v termináli: python3 --version)
3. Stiahol si si už folder context-engine-produkt?"
```

**Ak Claude Code:**
```
Naviguj používateľa:
1. cd do foldra s context-engine
2. pip install -e .
3. Pridaj do .claude/settings.json (alebo .mcp.json):
   {
     "mcpServers": {
       "context-engine": {
         "command": "context-engine",
         "env": {
           "CTX_DB": "/Users/MENO/.context-engine/context-engine.db"
         }
       }
     }
   }
4. Reštartuj Claude Code
5. Over: ctx_init()
```

**Ak Cowork:**
```
Naviguj používateľa:
1. Otvor Terminál (Mac: Cmd+Space → "Terminal")
2. cd do foldra: cd ~/context-engine (alebo kde ho má)
3. pip install -e .
4. → Prejdi na KROK 2 (ngrok)
```

---

## KROK 2: Ngrok setup (len pre Cowork)

```
"Teraz potrebujeme vystaviť server cez internet, aby sa k nemu Cowork vedel pripojiť.
Na to použijeme ngrok — je to tunelovací nástroj, free verzia stačí.

1. Nainštaluj ngrok: brew install ngrok (Mac) alebo stiahni z ngrok.com
2. Zaregistruj sa na ngrok.com (free) a pridaj token:
   ngrok config add-authtoken TVOJ_TOKEN_Z_DASHBOARDU

3. Otvor NOVÝ terminál tab a spusti:
   context-engine --sse

4. Otvor ĎALŠÍ terminál tab a spusti:
   ngrok http 8080

5. Ngrok ti ukáže URL niečo ako: https://abc-123.ngrok-free.app
   Skopíruj ju.

Hotovo? Daj mi tú URL."
```

---

## KROK 3: Pripojenie MCP v Cowork

```
"Super! Teraz ju pripojíme do Cowork:

1. Otvor Cowork → Settings (ozubené koliesko vľavo dole)
2. Nájdi sekciu 'MCP Connectors' alebo 'Custom MCP'
3. Klikni 'Add Custom MCP'
4. Vyplň:
   - Name: context-engine
   - Type: SSE
   - URL: [URL od ngrok]/sse   (pridaj /sse na koniec!)
5. Klikni Connect

Teraz mi povedz keď je pripojené — overím to."
```

Po potvrdení:
```
ctx_init()   → Over že DB je inicializovaná
ctx_stats()  → Over že je prázdna a funkčná
```

Ak funguje, pokračuj na **KROK 4**. Ak nie, troubleshoot:
- "Tool not found" → MCP nie je pripojený, skontroluj URL
- "Connection refused" → server nebeží, over terminál s `context-engine --sse`
- URL neodpovedá → ngrok spadol, reštartni ho

---

## KROK 1B: Railway deployment (alternatíva k KROK 1A)

Toto je cesta pre používateľov, ktorí v KROKU 0.5 vybrali Railway. Vedie k stabilnému 24/7 deploymentu s OAuth zabezpečením.

### KROK 1B.1: Účty

```
"Pre Railway deployment potrebuješ dva účty (oba majú free tier):

1. GitHub — github.com/signup
2. Railway — railway.app → 'Login with GitHub'

Máš oba? Daj vedieť keď si prihlásený."
```

### KROK 1B.2: Fork repa

```
"Teraz si forkneš repo Context Engine do svojho GitHubu:

1. Otvor URL repa (Jaro ti ju dal alebo: github.com/jarosatori/context-engine)
2. Klikni 'Fork' vpravo hore
3. Vyber svoj GitHub účet
4. Klikni 'Create fork'

Daj mi vedieť keď máš fork hotový — pošli mi URL."
```

### KROK 1B.3: Deploy na Railway

```
"Skvelé. Teraz nasadíme na Railway:

1. Otvor railway.app/new
2. Klikni 'Deploy from GitHub repo'
3. Autorizuj Railway (one-time)
4. Vyber tvoj forknutý 'context-engine' repo
5. Railway automaticky detekuje Dockerfile a začne build

Build trvá 2-5 minút. Daj mi vedieť keď je 'Deployed'."
```

### KROK 1B.4: Volume (KRITICKÉ)

```
"DÔLEŽITÉ — bez tohto kroku ti pri každom redeployi zmiznú dáta!

1. V Railway klikni na svoju službu (názov projektu)
2. Tab 'Settings' → scroll na 'Volumes'
3. Klikni '+ New Volume'
4. Mount path: /data
5. Size: 1 GB
6. Klikni 'Add'

Hotovo? Railway automaticky redeployne s volumom."
```

### KROK 1B.5: Environment variables

```
"Teraz nastav environment variables v Railway:

V projekte → tab 'Variables' → pridaj tieto:

CTX_DB=/data/context-engine.db
CTX_HOST=0.0.0.0
PORT=8000

Daj vedieť keď sú pridané."
```

### KROK 1B.6: Verejná doména

```
"Vygenerujme verejnú URL pre tvoj server:

1. Settings → scroll na 'Networking'
2. Klikni 'Generate Domain'
3. Skopíruj URL (typu: context-engine-production-xxx.up.railway.app)
4. Pošli mi ju — budem ju používať v ďalších krokoch."
```

### KROK 1B.7: OAuth (POVINNÉ pre bezpečnosť)

```
"Bez OAuth by tvoj endpoint bol otvorený celému internetu.
Nastavíme GitHub OAuth (najjednoduchšia možnosť):

1. Otvor github.com/settings/developers → OAuth Apps → New OAuth App
2. Vyplň:
   - Application name: Context Engine — moja inštancia
   - Homepage URL: https://[TVOJA_RAILWAY_URL]
   - Authorization callback URL: https://[TVOJA_RAILWAY_URL]/oauth/callback
3. Register application
4. Skopíruj 'Client ID' (zobrazí sa hneď)
5. Klikni 'Generate a new client secret' a skopíruj ho TERAZ
   (uvidíš ho len raz!)

Pošli mi Client ID a Secret — pridám ich do Railway.
(Alebo si ich pridaj sám: Railway → Variables:
   OAUTH_PROVIDER=github
   OAUTH_CLIENT_ID=...
   OAUTH_CLIENT_SECRET=...
   OAUTH_ALLOWED_USERS=tvoj_github_username
)"
```

### KROK 1B.8: Inicializácia DB

```
"Inicializujeme databázu na Railway. Najjednoduchšie cez Railway CLI:

1. Nainštaluj CLI: brew install railway (Mac)
   alebo: npm i -g @railway/cli

2. Prihlás sa: railway login
3. Linkni projekt: railway link → vyber svoj projekt
4. Spusti: railway run python3 -c \"from context_engine.db import init_db; print(init_db())\"

Mal by si dostať: {'status': 'ok', ...}"
```

### KROK 1B.9: Over server

```
"Posledná kontrola — otvor v prehliadači:
https://[TVOJA_RAILWAY_URL]/health

Mal by vrátiť: {\"status\": \"ok\"}

Funguje? Skvelé — máš production setup. Teraz pripojíme klientov."
```

### KROK 1B.10: Pripojenie MCP klientov

```
"Posledný krok — pripojíme klientov. Budeš ich pripájať postupne:

CLAUDE CODE (terminál):
   claude mcp add --transport sse context-engine https://[TVOJA_URL]/sse

   Otvorí prehliadač s GitHub OAuth prihlásením. Po autorizácii hotovo.
   Over: claude mcp list

COWORK (claude.ai web):
   1. claude.ai → Profile → Settings → Connectors
   2. Add custom connector
   3. Name: Context Engine
   4. URL: https://[TVOJA_URL]/sse
   5. Connect → GitHub OAuth login

INÉ ZARIADENIE / AGENT (mobil, druhý PC, Kyrilla...):
   Rovnaký postup s rovnakou URL. Každý klient si urobí svoj OAuth handshake,
   ale všetci pristupujú k tej istej DB.

Daj vedieť keď máš aspoň jedného klienta pripojeného — overím cez ctx_stats()."
```

Po pripojení:
```
ctx_init()   → Over že DB je inicializovaná
ctx_stats()  → Over že je prázdna a funkčná
```

Pokračuj na **KROK 4: Prvé naplnenie**.

---

## KROK 4: Prvé naplnenie — osobné údaje

```
"Context Engine je pripojený a funguje! Teraz ho naplníme tvojimi dátami.

Začneme s tebou. Povedz mi:
1. Tvoje celé meno
2. Tvoja firma (názov, čo robí)
3. Tvoja rola vo firme
4. V akom jazyku väčšinou komunikuješ? (sk/en/cs)
5. S väčšinou ľudí tykáš alebo vykáš?"
```

Po odpovedi:
```python
# Pridaj firmu
ctx_add_company(
    name="[FIRMA]",
    type="vlastna",
    industry="[ODVETVIE]",
    my_role="[ROLA]"
)

# Pridaj používateľa
ctx_add_person(
    name="[MENO]",
    company_name="[FIRMA]",
    role="[ROLA]",
    formality="ty",  # alebo "vy" podľa odpovede
    language="sk",
    relationship="ja",
    domain="work"
)
```

---

## KROK 5: Pravidlá komunikácie

```
"Teraz nastavíme pravidlá — toto je to, čo robí Context Engine výnimočným.
Pravidlá hovoria mne (Claude) ako sa správať keď píšem emaily a správy za teba.

Typické pravidlá:
- Komu tykáš / vykáš
- V akom jazyku píšeš (možno rôznym ľuďom rôzne)
- Aký tón preferuješ (formálny / priateľský / vecný)
- Špeciálne pravidlá (napr. 'faktúry vždy v EUR', 'nikdy neodosielaj bez schválenia')

Aké pravidlá chceš nastaviť?"
```

Pre každé pravidlo:
```python
ctx_add_rule(
    context="[KEDY PLATÍ]",
    rule="[ČO ROBIŤ]",
    priority="high",  # alebo medium/low
    category="komunikacia",
    domain="work"
)
```

**Odporúčané default pravidlá (navrhni ich):**
```
1. "Vždy len draft, nikdy neodosielaj priamo" (priority: high)
2. "Pred emailom vždy ctx_context()" (priority: high)
3. "Po odoslaní vždy ctx_log()" (priority: medium)
```

---

## KROK 6: Kľúčoví ľudia

```
"Kto sú ľudia, s ktorými komunikuješ najčastejšie? Stačí 5-10 na začiatok.

Pre každého povedz:
- Meno
- Email (ak vieš)
- Firma a rola
- Tykáte si? Aký tón?
- Niečo špeciálne? (napr. 'rýchle odpovede', 'vždy CC na šéfa')

Nemusíš to vedieť všetko — chýbajúce doplníme neskôr."
```

Pre každú osobu:
```python
# 1. Anti-duplicity check
ctx_find("[MENO]")

# 2. Ak neexistuje → pridaj
ctx_add_person(
    name="[MENO]",
    email="[EMAIL]",
    company_name="[FIRMA]",
    role="[ROLA]",
    relationship="[klient/partner/tim/kontakt]",
    formality="[ty/vy]",
    tone="[priatelsky/formalny/vecny]",
    language="[sk/en]",
    domain="work"
)

# 3. Ak má špeciálne pravidlo → pridaj rule
ctx_add_rule(
    context="Komunikacia s [MENO]",
    rule="[PRAVIDLO]",
    applies_to='["[MENO]"]',
    priority="medium"
)
```

---

## KROK 7: Projekty (voliteľné)

```
"Máš aktívne projekty na ktorých pracuješ? Napr. pre klientov, interné, osobné?

Pre každý povedz:
- Názov
- Pre akú firmu/klienta
- Kto je v tíme
- Deadline (ak je)
- Čo je tvoja rola"
```

---

## KROK 8: Verifikácia

Na konci vždy:

```python
# 1. Štatistiky
ctx_stats()

# 2. Zobraz sumár pre používateľa
"Hotovo! Tu je čo máme:
- [X] ľudí
- [X] firiem
- [X] pravidiel
- [X] projektov

# 3. Test
"Teraz to vyskúšame — povedz mi meno niekoho koho sme pridali a ja ti napíšem testovací email."
```

Po teste:
```
"Context Engine je nastavený a funguje!

Pár tipov na záver:
1. Keď povieš 'napíš email [meno]' — automaticky pozriem kontext
2. Keď povieš 'zapamätaj si...' — uložím do DB
3. Keď povieš 'čo vieme o [X]?' — prehľadám celú DB
4. Keď pridáš nový kontakt — pamätám si ho navždy

DÔLEŽITÉ pre Cowork:
- Server (context-engine --sse) musí bežať v Termináli
- Ngrok musí bežať v druhom Termináli
- Ak reštartuješ ngrok, URL sa zmení — musíš updatnúť v Cowork settings"
```

---

## FALLBACK — ak sa niečo pokazí

| Situácia | Čo robiť |
|----------|---------|
| ctx_* tools nevidno | Over MCP pripojenie v settings |
| "Connection refused" | Reštartni `context-engine --sse` |
| Ngrok expired | Reštartni ngrok, updatni URL v settings |
| Duplicitný záznam | Použi `ctx_update()` namiesto `ctx_add_*()` |
| Chyba v dátach | `ctx_update(table, id, {opravené dáta})` |
| Chcem začať odznova | Zmaž `~/.context-engine/context-engine.db` a spusti `ctx_init()` |
