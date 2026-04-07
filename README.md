# Context Engine — Tvoja dlhodobá pamäť pre Claude

**Plug & play štruktúrovaná pamäť pre Claude.** Postavená Jarom Chrapkom + Claude pre členov Claude Bootcampu. Ukladá ľudí, firmy, projekty, produkty, pravidlá, interakcie a poznámky do SQLite databázy a vystavuje ich Claude-ovi cez **27 MCP toolov** (`ctx_*`). Claude ju aktívne **číta** (pred každou komunikáciou vie tón, jazyk, tykanie, históriu) aj **zapisuje** (logy, action items, rozhodnutia).

> **Killer feature:** jedna zdieľaná remote DB na Railway, do ktorej sa pripája **Claude Code (Mac)**, **Cowork (claude.ai web)** aj **Kyrilla / ďalší agent na druhom PC** — všetci vidia tie isté dáta v reálnom čase. Žiadna synchronizácia, žiadny konflikt. Presne takto to beží u Jara.

---

## 🚀 Quickstart

> **Si úplný začiatočník a nikdy si neotvoril terminál?** Pohoda. Stačí jedna vec — **Claude Code**. Všetko ostatné (git, Python, Homebrew, Railway CLI, `gh`...) nainštaluje za teba sám Claude počas setupu.

---

### 📦 Predpoklady — toto si nainštaluj **pred** štartom

Stačí **jedna jediná vec**: **Claude Code**.

- **Najjednoduchšie — desktop app (odporúčané pre nepokročilých):** Stiahni z [claude.com/code](https://claude.com/code) a nainštaluj. Hotovo.
- Alternatíva pre pokročilých — CLI: `npm install -g @anthropic-ai/claude-code` (vyžaduje Node.js).

To je všetko. Choď rovno na **Cestu A** nižšie.

---

### 💡 Čo je „terminál" a ako ho otvoriť

Terminál (alebo „príkazový riadok") je čierne/biele okno, kam píšeš textové príkazy namiesto klikania myšou. Vyzerá technicky, ale na to čo budeme robiť stačí **kopírovať a vlepiť**.

- **Mac:** Stlač `Cmd + Space` → napíš `Terminal` → Enter.
- **Windows:** Stlač kláves Windows → napíš `PowerShell` → Enter.

**Dobrá správa:** ak si vyberieš **Cestu A** nižšie, terminál ani **nemusíš otvárať**. Claude to spraví za teba.

---

### 🅰️ Cesta A — Bez terminálu (odporúčané)

> Pre nepokročilých. **Nemusíš otvárať terminál ani nič klikať okrem dvoch klikov vo Finder/Explorer a 1-2 klikov v browseri pri OAuth login.**

#### A.1 — Vytvor si prázdnu zložku, kde chceš Context Engine mať

- **Mac (Finder):** Finder → Documents → pravý klik → **New Folder** → pomenuj `MyContextEngine`. Cesta bude `~/Documents/MyContextEngine`.
- **Windows (Explorer):** File Explorer → Documents → pravý klik → **New → Folder** → `MyContextEngine`.

> Táto zložka bude **trvalé miesto pre tvoj Context Engine**. Odtiaľ to pobeží, sem ti Claude stiahne kód.

#### A.2 — Otvor Claude Code app a otvor v ňom tú zložku

1. Spusti **Claude Code** aplikáciu
2. **File → Open Folder…** (`Cmd+O` na Macu / `Ctrl+O` na Windows)
3. Naviguj na `MyContextEngine`, klikni **Open**
4. V ľavom paneli vidíš prázdnu zložku — to je v poriadku

#### A.3 — Vlep tento prompt do chat-input okna Claude Code a stlač Enter

```
Práve som otvoril prázdnu zložku v Claude Code, do ktorej chcem nainštalovať
Context Engine z https://github.com/jarosatori/context-engine-community

Som člen Claude Bootcampu, podnikateľ, nie programátor. Nikdy som neotvoril
terminál a chcem všetko spraviť cez teba. NEPOSIELAJ ma sťahovať veci z
internetu, ak sa to dá nainštalovať príkazom — to spravíš ty za mňa.

DÔLEŽITÉ ROZLIŠENIE GitHub:
- Na STIAHNUTIE tohto repa GitHub účet NEPOTREBUJEM (repo je verejné, git
  clone funguje anonymne).
- Neskôr v procese (ak pôjdem cestou Railway deployment) si budem chcieť
  vytvoriť GitHub účet na fork + OAuth login. Vtedy ma cez to prevedieš
  automaticky cez "gh" CLI s autentifikáciou cez prehliadač. Žiadne SSH
  kľúče, žiadne tokeny ručne.

POSTUP:

1. Zisti, na akom operačnom systéme bežím (macOS / Windows / Linux).

2. Skontroluj, či mám tieto základné nástroje:
   - git
   - python3 (verzia 3.10 alebo vyššia)

3. Pre čokoľvek čo chýba alebo je staré:

   AK SOM NA macOS:
   - git: spusti `xcode-select --install`. Vyskočí mi systémový popup,
     kliknem "Install" a počkám 5-10 minút. Toto nainštaluje aj git aj
     kompilery, ktoré budeme neskôr potrebovať.
   - python3 (ak chýba alebo je < 3.10):
     a) Najprv skontroluj, či mám Homebrew (`brew --version`).
     b) Ak Homebrew mám: `brew install python@3.12`.
     c) Ak Homebrew nemám: daj mi PRESNE jeden riadok, ktorý mám vlepiť
        do Terminal.app. Vysvetli ako Terminal otvoriť (Cmd+Space →
        "Terminal" → Enter). Upozorni ma, že si bude pýtať heslo k Macu.
        Počkaj kým poviem že je hotovo, over `brew --version` a pokračuj.

   AK SOM NA Windows:
   - git: `winget install --id Git.Git -e --source winget`
   - python: `winget install --id Python.Python.3.12 -e --source winget`
   - Po inštalácii môže byť treba zavrieť a otvoriť Claude Code, aby sa
     načítal PATH — povedz mi keď treba.

   AK SOM NA Linux:
   - Použi balíčkový manažér mojej distribúcie (apt / dnf / pacman).

4. Keď máme git aj python3 (≥ 3.10), stiahni repo do TEJTO prázdnej zložky:
   git clone https://github.com/jarosatori/context-engine-community.git .
   (POZOR: bodka na konci = "do aktuálnej zložky".)

5. Po stiahnutí si prečítaj SETUP-GUIDE.md (ten z disku, nie z pamäte) a
   postupuj presne podľa neho. Začni FÁZOU 0 (environment check) a pokračuj
   fázami 0.5 → 1A alebo 1B → 2 → 3 → 4. Pýtaj sa ma postupne, jeden krok
   naraz.

6. Rieš všetko za mňa — spúšťaj príkazy, edituj súbory, rieš chyby. Pýtaj
   sa len keď to fakt potrebuješ alebo pri nevratných/platených veciach
   (vytvorenie GitHub/Railway účtu, pridanie volume, OAuth klient secret).
   Vysvetľuj v ľudskej reči, nie v žargóne. Hovor po slovensky a tykaj mi.

Pripravený? Začni.
```

**To je všetko.** Od tejto chvíle Claude robí všetko sám — detekuje OS, nainštaluje git/python cez balíčkový manažér, stiahne kód, prejde s tebou všetky fázy (environment check → výber deployment cesty → inštalácia → init DB → pripojenie MCP → prvé záznamy → verifikácia). Ty len odpovedáš a na 1-2 miestach klikneš v browseri (Railway login, GitHub OAuth).

---

### 🅱️ Cesta B — S terminálom (pre tých čo ho ovládajú)

> Rýchlejšie ak vieš čo robíš.

#### B.1 — Otvor terminál a stiahni repo

```bash
mkdir -p ~/Documents/MyContextEngine
cd ~/Documents/MyContextEngine
git clone https://github.com/jarosatori/context-engine-community.git .
```

#### B.2 — Otvor zložku v Claude Code

**Desktop app:** File → Open Folder → vyber `MyContextEngine/`.

**CLI:**
```bash
cd ~/Documents/MyContextEngine
claude
```

#### B.3 — Vlep prompt

```
Ahoj. Práve som naklonoval Context Engine repo a chcem si ho rozbehnúť.
Som člen Claude Bootcampu, podnikateľ, nie programátor. Potrebujem, aby
si ma previedol celým setupom — od nuly po funkčný MCP endpoint, na
ktorý sa pripojím z Claude Code / Cowork / iného agenta.

Prečítaj si SETUP-GUIDE.md a postupuj presne podľa neho. Začni FÁZOU 0
(environment check), potom FÁZOU 0.5 (výber lokál vs Railway). Rieš
všetko za mňa, spúšťaj príkazy, edituj súbory, rieš chyby. Pýtaj sa len
pri nevratných/platených veciach. Slovensky, tykaj.

Pripravený? Začni.
```

**Čo Claude vie od tej chvíle spraviť sám:**

- ✅ **Detekuje OS** a **inštaluje git + Python** cez `brew` / `winget` (žiadne sťahovanie z webu)
- ✅ **Opýta sa na use-case** (solopreneur / firma s tímom / content creator / consultant) a podľa toho pripraví počiatočné `domains` a `rules`
- ✅ **Opýta sa na deployment** — lokál (zadarmo, jeden PC) alebo **Railway cloud s OAuth** (ako Jaro, zdieľaná DB pre viac klientov)
- ✅ Spustí `pip install -e .` a `ctx_init()`
- ✅ Ak Railway: **forkne repo cez `gh`**, deploy na Railway, pridá volume `/data`, vygeneruje doménu, zapne **GitHub OAuth** a obmedzí prístup na tvoj username
- ✅ **Pripojí MCP** do Claude Code (stdio pre lokál, SSE+OAuth pre Railway) + Cowork
- ✅ **Naplní prvé záznamy** — teba, tvoju firmu, 3–5 pravidiel komunikácie, kľúčových ľudí
- ✅ Ponúkne **import z Asany / Google Contacts / existujúceho CLAUDE.md** (pravidlá komunikácie)
- ✅ Spustí sanity test: `ctx_stats()`, `ctx_find()`, `ctx_context("tvoje meno")`

Celý setup trvá **15-40 minút** (lokál 15, Railway 40).

---

## ❓ FAQ — Otázky, ktoré možno máš teraz

**„Potrebujem GitHub účet?"**
Na **stiahnutie** repa **nie** — `git clone` funguje anonymne. Na **Railway deployment** áno (fork + OAuth login), vytvoríš si ho zadarmo za 2 minúty a Claude ťa cez to prevedie cez `gh` CLI s browser autentifikáciou.

**„Musím platiť za niečo?"**
- **Lokálne (Možnosť A):** $0. Len si platíš Claude Code subscription ktorú už máš.
- **Railway cloud (Možnosť B):** ~$5/mesiac Hobby plán (beží 24/7, volume, OAuth). Free trial $5 stačí na prvé dni na vyskúšanie.
- **GitHub:** $0 (súkromné repá zadarmo).
- **OpenAI/Cohere/Qdrant:** **Context Engine ich nepoužíva** (to je RAG). CE je čistý SQLite + MCP, žiadne API volania.

**„Aký je rozdiel oproti RAG databáze?"**
- **Context Engine** = **štruktúrovaná** pamäť (SQLite tabuľky): kto je Peter, ako mu tykáš, v akej je firme, aký projekt vedie, aké máš pravidlá. Dopyty sú **presné** (SQL + FTS5).
- **RAG** = **vektorová** pamäť (Qdrant): plné texty dokumentov, transkripty, články, knowledge base. Dopyty sú **sémantické** (podobnosť).
- **Používaj oba naraz** — CE pred komunikáciou (kto, tón, história), RAG pri tvorbe obsahu (čo o tom Jaro už povedal).

**„Nikdy som neotvoril terminál, zvládnem to?"**
Áno. Cesta A je navrhnutá tak, **aby si terminál ani nemusel otvárať**. Claude robí všetky príkazy sám. Ty len odpovedáš a 1-2× klikneš v browseri.

**„Kde budú moje dáta fyzicky?"**
- **Lokál:** SQLite súbor `~/.context-engine/context-engine.db` na tvojom disku. Backup = skopírovať súbor.
- **Railway:** SQLite súbor na Railway volume (perzistentný storage, EU/US región podľa voľby). Backup = Railway snapshoty + export cez `ctx_export`.

**„Je to bezpečné keď je to na cloude?"**
Áno — Railway endpoint je chránený **OAuth-om** (GitHub alebo Sign in with Vercel). Bez autorizácie sa nikto nepripojí. `OAUTH_ALLOWED_USERS` env var navyše whitelistuje konkrétne usernamy.

**„Môžem mať jednu DB zdieľanú medzi Claude Code, Cowork a Kyrillou?"**
Áno, **to je presne ten use-case pre ktorý je Railway deployment**. Všetci traja klienti sa pripoja na ten istý HTTPS/SSE endpoint, vidia tie isté dáta v reálnom čase.

**„Čo ak sa mi to nepodarí alebo niečo zlyhá?"**
Claude rieši errory automaticky. Troubleshooting tabuľka je na konci `SETUP-GUIDE.md`. Ak neviete ďalej, napíš do Bootcamp Skool.

**„Stratím dáta pri upgrade?"**
Nie — DB je mimo repa (`~/.context-engine/` lokálne, `/data` volume na Railway). `git pull` sa jej nedotkne. Schema migrácie robí Claude cez `ctx_init()` (idempotentné).

---

## Čo dostávaš (technické zhrnutie)

**27 MCP toolov s prefixom `ctx_*`:**
- **Ľudia:** `ctx_add_person`, `ctx_person`, `ctx_find` (FTS5 full-text)
- **Firmy:** `ctx_add_company`, `ctx_company`
- **Projekty:** `ctx_add_project`, `ctx_project`, `ctx_meeting_participants`
- **Produkty:** `ctx_add_product`
- **Pravidlá:** `ctx_add_rule`
- **Poznámky:** `ctx_add_note`, `ctx_find_notes`, `ctx_get_note`
- **Interakcie & kontext:** `ctx_log`, `ctx_context`, `ctx_recent`
- **Action items & rozhodnutia:** `ctx_action_items`, `ctx_mark_action_done`, `ctx_decisions`
- **Údržba & stats:** `ctx_stats`, `ctx_incomplete`, `ctx_stale`, `ctx_update`, `ctx_export`, `ctx_restore_db`
- **Scany:** `ctx_scan_status`, `ctx_set_scan`, `ctx_update_scan`
- **Init:** `ctx_init`

**Storage:**
- SQLite s **FTS5** (full-text search po všetkých entitách)
- Soft-delete cez `status = 'inactive'` (nikdy skutočne nemaže)
- 7 domén: `work`, `personal`, `home`, `health`, `finance`, `family`, `education`
- Pydantic validácia vstupov (strict, žiadne silent fallbacky)

**Rozhrania:**
- **MCP server** (stdio pre Claude Code lokálne, **SSE s OAuth** pre Cowork + remote agentov)
- CLI: `context-engine` (stdio), `context-engine --sse` (HTTP/SSE server)

**Deployment:**
- **Lokál** — Mac/Windows/Linux, SQLite v `~/.context-engine/`
- **Railway** — 24/7, volume na `/data`, OAuth, zdieľaná DB pre N klientov
- **Docker** — `Dockerfile` v repe, tá istá image beží lokál aj cloud

---

## Štruktúra repa

```
context-engine-community/
├── src/context_engine/
│   ├── server.py          # FastMCP server + 27 ctx_* toolov
│   ├── db.py              # SQLite + FTS5 vrstva
│   └── models.py          # Pydantic validácia
├── tests/                 # 33 testov (pytest)
├── skill/                 # Cowork skill — behavioral guide pre Claude
├── skill-onboarding/      # Prvotný setup skill (první naplnenie DB)
├── CLAUDE.md              # Šablóna inštrukcií
├── SETUP-GUIDE.md         # Fázovaný inštalátorský script pre Claude
├── pyproject.toml
├── Dockerfile             # Pre Railway / lokálny Docker
├── railway.toml           # Railway config
└── README.md              # Tento súbor
```

---

## Env premenné

| Premenná | Default | Popis |
|---|---|---|
| `CTX_DB` | `~/.context-engine/context-engine.db` | Cesta k SQLite databáze |
| `CTX_PORT` | `8080` | Port pre HTTP/SSE mód |
| `CTX_HOST` | `0.0.0.0` | Host pre HTTP/SSE mód |
| `OAUTH_PROVIDER` | — | `github` / `vercel` / `auth0` (len pre Railway) |
| `OAUTH_CLIENT_ID` | — | Client ID z OAuth providera |
| `OAUTH_CLIENT_SECRET` | — | Client secret z OAuth providera |
| `OAUTH_ALLOWED_USERS` | — | Čiarkou oddelený whitelist usernamov |

---

## Pre pokročilých — manuálny setup

Ak nechceš sprievodcu a vieš čo robíš, čítaj `SETUP-GUIDE.md` priamo — obsahuje všetky fázy, príkazy a flow pre lokál aj Railway.

---

## Podpora

- **Bootcamp Skool** — primárny kanál
- **Issues** na GitHub repe
- **Sám sebe** — otvor Claude Code v tomto repe a povedz „mám problém s Context Engine, pomôž"

---

## Kredity

Postavené Jarom Chrapkom (Dedoles, Miliónová Evolúcia) + Claude (Anthropic).
Pre Claude Bootcamp 2026.

Licencia: použi voľne na svoj biznis. Ak ti to pomohlo, pošli to ďalej.
