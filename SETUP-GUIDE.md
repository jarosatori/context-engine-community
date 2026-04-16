---
name: Context Engine — Interactive Setup Guide for Claude
description: Master setup script that Claude Code follows to walk a Bootcamp member through end-to-end installation, configuration, deployment (local or Railway+OAuth), and first-run population of their Context Engine.
type: setup-guide
audience: claude-code
language: sk
version: 2.0
---

# Context Engine — Interactive Setup Guide (pre Claude)

> **Tento dokument je inštruktážny script pre teba (Claude Code).** Používateľ ti dal prompt typu „nainštaluj mi Context Engine". Tvoja úloha je previesť ho **krok za krokom** od nuly po funkčný MCP endpoint, na ktorý sa pripojí z Claude Code / Cowork / iného agenta. Hovor po slovensky, tykaj, buď proaktívny, nečakaj kým sa pýta.

---

## Kontext a princípy

**Kto je používateľ:** Člen Claude Bootcampu. Podnikateľ, **nie programátor**. Vie spustiť terminál a klikať. Neočakávaj že rozumie Pythonu, Dockeru, MCP, OAuth alebo Railway. Vysvetľuj len keď treba a v ľudskej reči.

**Cieľ:** Na konci sessionu má používateľ:
1. Nainštalovaný Context Engine (lokálne **alebo** na Railway s OAuth)
2. Inicializovanú DB a funkčné `ctx_*` tooly v Claude
3. Prvé záznamy: seba, svoju firmu, 3–5 pravidiel komunikácie, kľúčových ľudí
4. Sanity-tested retrieval (`ctx_stats`, `ctx_context`, `ctx_find`)

**Tvoja DNA:**
- ✅ **Plug & play** — všetko rieš za neho. Spúšťaj príkazy, edituj súbory, riešiš chyby. Pýtaj sa len pri nevratných/platených akciách (GitHub/Railway účet, volume, OAuth secret, `--force` akcie).
- ✅ **Discovery najprv, potom akcia** — nasleduj fázy v poradí.
- ✅ **Jeden krok naraz** — neukazuj 10 príkazov naraz. Spusti, počkaj, vysvetli, ďalej.
- ✅ **Vždy povedz prečo** — v 1 vete pred každým krokom prečo to robíš.
- ❌ **Nikdy nevypisuj long-form teóriu** ak sa nepýta. Toto je inštalátor, nie kurz.
- ❌ **Nenechávaj ho čítať dokumentáciu** — TY si prečítaj všetko a zhrň mu len to podstatné.
- ❌ **Nikdy ho nepošli stiahnuť installer z webu**, ak sa to dá vyriešiť príkazom cez `brew` / `winget` / `apt`.

---

## FÁZA 0: Privítanie + environment check + auto-install nástrojov

Hneď ako prečítaš tento súbor, povedz:

> „Ahoj 👋 Som tvoj inštalátor Context Engine. Za 15-40 minút ti rozbehnem štruktúrovanú pamäť pre Claude — bude vedieť kto je kto, ako s kým hovoríš, a bude si pamätať všetko dôležité. Začnem krátkym skenom prostredia, nech viem čo už máš a čo ti doinštalujem."

### 0.1 — Detekuj OS a stav prostredia

Spusti **paralelne**:
- `uname -s` (Mac → "Darwin", Linux → "Linux", Windows → zlyhá)
- `pwd`
- `ls -la`
- `python3 --version` (musí byť ≥ 3.10)
- `git --version`

**Zapamätaj si OS** (macOS / Windows / Linux). Použiješ ho ďalej.

### 0.2 — Inštalácia chýbajúcich nástrojov

> **PRAVIDLO:** nikdy ho nepošli stiahnuť installer z webu, ak sa to dá príkazom.

#### macOS

**git** (ak chýba): `xcode-select --install` — vyskočí GUI popup, povedz mu: *„Vyskočil ti systémový popup, klikni 'Install' a počkaj 5-10 minút."* Over `git --version` v slučke.

**python3 ≥ 3.10** (ak chýba alebo je starší):
1. Skontroluj `brew --version`
2. **Ak má Homebrew** → `brew install python@3.12`
3. **Ak nemá Homebrew** → potrebuje ho najprv. Homebrew install script vyžaduje sudo, čo Bash tool neutiahne interaktívne. Povedz mu:

   > „Aby som ti vedel nainštalovať Python, potrebujeme jednorázovo Homebrew (balíčkový manažér pre Mac, bezpečný a oficiálny). Prosím:
   > 1. Otvor aplikáciu **Terminal** (`Cmd+Space` → `Terminal` → Enter)
   > 2. Vlep tento jeden riadok a stlač Enter:
   >
   > ```
   > /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   > ```
   >
   > Bude si pýtať heslo k Macu (rovnaké ako login). Povedz mi keď bude hotovo."

   Keď potvrdí → `brew --version` → `brew install python@3.12`.

#### Windows

- **git:** `winget install --id Git.Git -e --source winget`
- **python:** `winget install --id Python.Python.3.12 -e --source winget`
- Po inštalácii môže byť treba zavrieť a otvoriť Claude Code (PATH refresh). Povedz mu.
- Ak `winget` nefunguje (starý Windows), navrhni Chocolatey.

#### Linux

Použi balíčkový manažér distribúcie: `apt install python3 python3-pip git` / `dnf install …` / `pacman -S …`.

### 0.3 — Stiahni repo (ak v zložke ešte nie je)

Skontroluj `ls -la` — ak nevidíš `pyproject.toml` a `src/context_engine/`, spusti:

```bash
git clone https://github.com/jarosatori/context-engine-produkt.git .
```

(Bodka na konci = do aktuálnej zložky.)

Ak už repo **je** stiahnuté (napr. user si urobil `git clone` sám cestou B), preskoč a choď na FÁZU 0.5.

---

## FÁZA 0.5: Discovery — use-case a výber deployment cesty

Pred akoukoľvek inštaláciou potrebuješ vedieť **na čo** Context Engine bude a **kde** pobeží. Spýtaj sa používateľa (jeden quick rozhovor, nie dlhý dotazník):

**Otázka 1 — use-case (1 veta odpoveď stačí):**
> „Na čo ideš Context Engine používať? Solopreneur workflow (ja + moji ľudia + moje pravidlá)? Firma s tímom? Content creator (zdroje + spolupracovníci)? Consultant (klienti + projekty)? Niečo iné?"

Podľa odpovede si poznač:
- Ktoré **domains** budú aktívne (`work`, `personal`, `home`, `health`, `finance`, `family`, `education`)
- Aké **rules** pravdepodobne chce (tykanie/vykanie, formálny/neformálny, jazyk)
- Či chce **import** z existujúcich zdrojov (Asana projekty, Google Contacts, CLAUDE.md pravidlá)

**Otázka 2 — deployment:** prečítaj mu zhrnutie dvoch ciest (A lokál / B Railway) nižšie a pomôž mu vybrať. Ak má **jeden PC a chce to len skúsiť** → A. Ak chce **zdieľanú DB medzi Claude Code + Cowork + agentom / mobilom / druhým PC** → B.

---

## FÁZA 0.5 detail: Vyber si kde to bude bežať

Context Engine môžeš spustiť **dvomi spôsobmi**. Vyber si podľa svojich potrieb:

### Možnosť A — Lokálne na tvojom PC (jednoduchšie, free)

**Pre koho:** Začiatočníci, jeden používateľ, jeden počítač.

**Ako to funguje:**
- Server beží na tvojom Macu/PC
- Databáza je lokálny SQLite súbor (`~/.context-engine/context-engine.db`)
- Funguje len keď máš PC zapnutý
- Backup = skopírovať `.db` súbor

**Plusy:**
- ✅ Zadarmo
- ✅ Dáta sú fyzicky u teba
- ✅ Žiadny cloud, žiadne účty
- ✅ Inštalácia za 10 minút

**Mínusy:**
- ❌ Funguje len na jednom PC (žiadne zdieľanie medzi zariadeniami)
- ❌ Cowork (Claude.ai web) potrebuje navyše ngrok tunel
- ❌ Ak vypneš PC, Context Engine nebeží
- ❌ Žiadna autentifikácia — kto má prístup k PC, má prístup k DB

→ Pokračuj na **FÁZA 1A: Lokálna inštalácia**

---

### Možnosť B — Railway cloud s OAuth (production setup, ako Jaro)

**Pre koho:** Pokročilí používatelia, viac zariadení, viac MCP klientov, alebo ak chceš pristupovať z mobilu/iného PC/agentov.

**Ako to funguje:**
- Server beží na **Railway** ako remote MCP server (HTTP/SSE)
- Databáza je SQLite súbor na Railway volume (perzistentný storage)
- Beží 24/7, prístupný odkiaľkoľvek
- Zabezpečené cez **OAuth** — len ty (alebo koho pustíš) sa môže pripojiť
- Tá istá inštancia obsluhuje **všetkých klientov naraz**: Claude Code (Mac), Cowork (web), Kyrilla/iný agent (druhý PC), mobil...

**Plusy:**
- ✅ Beží 24/7, nezávislé od tvojho PC
- ✅ Viac zariadení a klientov vidí tie isté dáta v reálnom čase
- ✅ OAuth zabezpečenie (žiadne zdieľané heslá)
- ✅ Žiadny ngrok, žiadne tunely — natívne HTTPS
- ✅ Automatický backup cez Railway snapshoty

**Mínusy:**
- ❌ Stojí ~5 USD/mesiac za Railway hosting (Hobby plan)
- ❌ Treba GitHub účet a Railway účet
- ❌ Inštalácia trvá 20-30 minút (ale jednorázovo)
- ❌ Dáta sú v cloude (Railway, EU/US region)

→ Pokračuj na **FÁZA 1B: Railway deployment**

---

## FÁZA 1A: Lokálna inštalácia (5-10 minút)

> Tento postup je pre **Možnosť A — lokálne na PC**. Ak ideš cez Railway, preskoč na **FÁZA 1B**.

### Krok 1.1 — Over Python

Otvor Terminál a napíš:
```bash
python3 --version
```

Potrebuješ Python 3.10 alebo novší. Ak nemáš, nainštaluj cez:
- **Mac:** `brew install python3` (ak máš Homebrew) alebo stiahni z python.org
- **Windows:** stiahni z python.org, pri inštalácii zaškrtni "Add to PATH"

### Krok 1.2 — Stiahni Context Engine

Skopíruj folder `context-engine-produkt` niekam na disk. Odporúčanie:
```bash
# Mac/Linux
~/context-engine/

# Windows
C:\Users\TVOJE_MENO\context-engine\
```

### Krok 1.3 — Nainštaluj

```bash
cd ~/context-engine
pip install -e .
```

Ak dostaneš "permission denied":
```bash
pip install -e . --user
```

### Krok 1.4 — Over inštaláciu

```bash
context-engine --help
```

Mal by sa zobraziť help text. Ak nie, skús:
```bash
python3 -m context_engine.server --help
```

### Krok 1.5 — Inicializuj databázu

```bash
python3 -c "from context_engine.db import init_db; print(init_db())"
```

Malo by sa zobraziť:
```
{'status': 'ok', 'message': 'Database initialized', 'path': '/Users/TVOJE_MENO/.context-engine/context-engine.db'}
```

Databáza je prázdna a čaká na tvoje dáta.

→ Pokračuj na **FÁZA 2A: Pripojenie do Claude (lokálne)**

---

## FÁZA 1B: Railway deployment s OAuth (20-30 minút)

> Tento postup je pre **Možnosť B — Railway cloud**. Ak ideš lokálne, použi **FÁZA 1A**.

Toto je presne ten setup, ktorý používa Jaro: Context Engine beží na Railway, zabezpečený OAuth-om, a pripája sa k nemu Claude Code (Mac), Cowork (web) aj Kyrilla (agent na druhom PC) — všetci vidia tie isté dáta.

### Krok 1B.1 — Vytvor si účty (ak ešte nemáš)

1. **GitHub:** [github.com/signup](https://github.com/signup) — free
2. **Railway:** [railway.app](https://railway.app) → "Login with GitHub" — free trial $5, potom Hobby $5/mesiac

### Krok 1B.2 — Forkni repo do svojho GitHubu

1. Otvor [github.com/jarosatori/context-engine](https://github.com/jarosatori/context-engine) (alebo URL ktorú ti dal Jaro)
2. Klikni **Fork** vpravo hore
3. Vyber svoj GitHub účet ako destination
4. Klikni **Create fork**

Teraz máš vlastnú kópiu repa na `github.com/TVOJ_USERNAME/context-engine`.

### Krok 1B.3 — Nasaď na Railway

1. Otvor [railway.app/new](https://railway.app/new)
2. Klikni **Deploy from GitHub repo**
3. Autorizuj Railway na čítanie tvojich repov (one-time)
4. Vyber `context-engine` repo
5. Railway automaticky detekuje `Dockerfile` a začne build

### Krok 1B.4 — Pridaj perzistentný volume (DÔLEŽITÉ)

Bez tohto kroku ti pri každom redeployi zmiznú dáta!

1. V Railway projekte → klikni na svoju službu (`context-engine`)
2. Tab **Settings** → scroll na **Volumes**
3. Klikni **+ New Volume**
4. **Mount path:** `/data`
5. **Size:** 1 GB (stačí, môžeš zväčšiť neskôr)
6. Klikni **Add**

### Krok 1B.5 — Nastav environment variables

V Railway projekte → tab **Variables** → pridaj:

```
CTX_DB=/data/context-engine.db
CTX_HOST=0.0.0.0
PORT=8000
```

(`PORT` Railway nastaví automaticky, ale pre istotu ho daj na 8000.)

### Krok 1B.6 — Vygeneruj verejnú doménu

1. V Railway → tab **Settings** → scroll na **Networking**
2. Klikni **Generate Domain**
3. Dostaneš URL typu: `context-engine-production-abc123.up.railway.app`
4. Skopíruj túto URL — budeš ju potrebovať

### Krok 1B.7 — Zapni OAuth zabezpečenie

Bez OAuth je tvoj endpoint **otvorený celému internetu** — ktokoľvek s URL by mohol čítať tvoje dáta. OAuth zabezpečí, že sa pripojí len autorizovaný klient.

**Možnosti OAuth providera:**

| Provider | Pre koho | Náročnosť |
|----------|---------|----------|
| **Sign in with Vercel** | Najjednoduchšie, free | ⭐ Easy |
| **GitHub OAuth App** | Ak už používaš GitHub | ⭐⭐ Medium |
| **Auth0 / Clerk** | Enterprise, viac userov | ⭐⭐⭐ Advanced |

**Odporúčaný setup (GitHub OAuth) — krok za krokom:**

1. Otvor [github.com/settings/developers](https://github.com/settings/developers) → **OAuth Apps** → **New OAuth App**
2. Vyplň:
   - **Application name:** `Context Engine — moja inštancia`
   - **Homepage URL:** `https://TVOJA-RAILWAY-URL.up.railway.app`
   - **Authorization callback URL:** `https://TVOJA-RAILWAY-URL.up.railway.app/oauth/callback`
3. Klikni **Register application**
4. Skopíruj **Client ID** a vygeneruj **Client Secret**
5. V Railway → **Variables** pridaj:
   ```
   OAUTH_PROVIDER=github
   OAUTH_CLIENT_ID=tvoj_client_id
   OAUTH_CLIENT_SECRET=tvoj_client_secret
   OAUTH_ALLOWED_USERS=tvoj_github_username
   ```
6. Railway automaticky redeployne s OAuth ochranou

> **Tip:** `OAUTH_ALLOWED_USERS` je čiarkou oddelený zoznam GitHub usernamov, ktorí sa môžu pripojiť. Ak chceš prístup pre tím, pridaj viac.

### Krok 1B.8 — Inicializuj databázu na Railway

Najjednoduchšie cez Railway CLI:
```bash
brew install railway  # alebo: npm i -g @railway/cli
railway login
railway link  # vyber svoj projekt
railway run python3 -c "from context_engine.db import init_db; print(init_db())"
```

Mal by si vidieť `{'status': 'ok', ...}`.

### Krok 1B.9 — Over že server beží

Otvor v prehliadači:
```
https://TVOJA-RAILWAY-URL.up.railway.app/health
```
Mal by vrátiť `{"status": "ok"}`.

→ Pokračuj na **FÁZA 2B: Pripojenie do Claude (Railway)**

---

## FÁZA 2A: Pripojenie do Claude (lokálne)

Vyber si jednu z dvoch ciest:

### Cesta A: Claude Code (terminál) — jednoduchšie

1. Otvor/vytvor súbor `~/.claude/settings.json` (alebo `.mcp.json` v projekte)
2. Pridaj:

```json
{
  "mcpServers": {
    "context-engine": {
      "command": "context-engine",
      "env": {
        "CTX_DB": "/Users/TVOJE_MENO/.context-engine/context-engine.db"
      }
    }
  }
}
```

3. Reštartuj Claude Code
4. Napíš: `ctx_init()` — mal by odpovedať "Database initialized"

### Cesta B: Cowork (desktop app) — cez ngrok

> **Pozor:** Toto je workaround pre lokálnu inštaláciu. Ak chceš stabilný prístup z viacerých zariadení, použi **FÁZA 1B: Railway deployment** namiesto tohto.

Cowork nepodporuje lokálne príkazy, takže musíš server vystaviť cez HTTP tunel.

**Krok B.1 — Nainštaluj ngrok**
```bash
brew install ngrok  # Mac
# Alebo stiahni z https://ngrok.com/download
```

Registrácia na ngrok.com je free. Po registrácii:
```bash
ngrok config add-authtoken TVOJ_TOKEN
```

**Krok B.2 — Spusti server + tunel**
```bash
# Tab 1
context-engine --sse

# Tab 2
ngrok http 8080
```

Ngrok ti dá URL `https://abc-123-xyz.ngrok-free.app`.

**Krok B.3 — Pridaj MCP konektor v Cowork**

1. Cowork → Settings → MCP Connectors → Add
2. Name: `context-engine`, Type: `SSE`, URL: `https://abc-123.ngrok-free.app/sse`
3. Connect

**Krok B.4 — Over:** napíš v Cowork `ctx_stats()`.

---

## FÁZA 2B: Pripojenie do Claude (Railway s OAuth)

Toto je postup pre Railway deployment z **FÁZA 1B**. Tvoj endpoint je `https://TVOJA-RAILWAY-URL.up.railway.app/sse` a je chránený OAuth-om.

### Pripojenie z Claude Code (Mac/PC terminál)

```bash
claude mcp add --transport sse context-engine https://TVOJA-RAILWAY-URL.up.railway.app/sse
```

Pri prvom pripojení sa otvorí prehliadač s OAuth prihlásením (GitHub login). Po autorizácii Claude Code uloží OAuth token a pripája sa automaticky.

Over:
```bash
claude mcp list
# context-engine: https://...up.railway.app/sse (HTTP) - ✓ Connected
```

### Pripojenie z Cowork (Claude.ai web)

1. Otvor [claude.ai](https://claude.ai) → klikni na svoj profil → **Settings** → **Connectors**
2. Klikni **Add custom connector**
3. Vyplň:
   - **Name:** `Context Engine`
   - **URL:** `https://TVOJA-RAILWAY-URL.up.railway.app/sse`
   - **Auth type:** OAuth (auto-detekované)
4. Klikni **Connect** → otvorí sa GitHub OAuth login
5. Po autorizácii uvidíš connector ako "Connected"

### Pripojenie z iného zariadenia / agenta (Kyrilla, OpenClaw, mobil...)

Rovnaký postup — použi tú istú Railway URL. OAuth zabezpečí, že každý klient sa musí samostatne autorizovať, ale všetci pristupujú k tej istej databáze.

### Over že všetko funguje

V ktoromkoľvek pripojenom klientovi napíš:
```
Zavolaj ctx_stats()
```

Mal by si dostať štatistiky (na začiatku všetko 0, lebo DB je prázdna).

---

## FÁZA 3: Prvé naplnenie (15-20 minút)

Teraz máš prázdnu databázu. Claude ťa prevedie naplnením.

### Krok 3.1 — Pridaj seba

Povedz Claude:
```
Pridaj ma do Context Engine. Volám sa [TVOJE MENO], moja firma je [FIRMA].
```

Claude zavolá `ctx_add_person()` a `ctx_add_company()`.

### Krok 3.2 — Pridaj pravidlá komunikácie

Povedz Claude:
```
Zapamätaj si tieto pravidlá:
- S klientmi vykám
- Interným ľuďom tykám
- Emaily píšem po slovensky, niekedy anglicky
- Vždy najprv draft, nikdy neodosielaj priamo
```

Claude vytvorí `ctx_add_rule()` záznamy.

### Krok 3.3 — Pridaj kľúčových ľudí

Povedz Claude:
```
Pridaj tieto kontakty:
- Peter Horváth, peter@firma.sk, CEO vo FirmaXY — tykáme si, priateľský tón
- Jana Nová, jana@klient.sk, marketing manager v KlientABC — vykáme si, formálny tón
- Marek z tímu, marek@moja-firma.sk, developer — tykáme si
```

Claude pre každého zavolá `ctx_add_person()` so správnymi parametrami.

### Krok 3.4 — Pridaj projekty (voliteľné)

```
Mám tieto aktívne projekty:
- Rebrand (pre KlientABC, deadline jún 2026, tím: ja + Jana + Marek)
- Nový e-shop (interný projekt, tím: ja + Marek)
```

### Krok 3.5 — Over si stav

```
Daj mi štatistiky Context Engine
```

Claude zavolá `ctx_stats()` a ukáže koľko záznamov máš.

---

## FÁZA 4: Denné používanie

### Email workflow
```
Ty: "Napíš email Petrovi ohľadom faktúry"
Claude: (automaticky) ctx_context("Peter") → zistí tykanie, tón, jazyk, pravidlá
Claude: (napíše draft podľa kontextu)
Claude: (automaticky) ctx_log() → zaloguje interakciu
```

### Zapamätanie
```
Ty: "Zapamätaj si že Peter zmenil pozíciu na COO"
Claude: ctx_update("people", peter_id, {"role": "COO"})
```

### Vyhľadávanie
```
Ty: "Čo vieme o firme KlientABC?"
Claude: ctx_company("KlientABC") → ľudia, projekty, pravidlá
```

### Poznámky (osobné veci)
```
Ty: "Zapamätaj si — termín u lekára 20. marca o 14:00"
Claude: ctx_add_note(title="Lekár", content="20.3. 14:00", domain="health")
```

---

## FÁZA 5: Rozšírené použitie (keď budeš ready)

### Scan emailov
Ak máš Gmail konektor, Claude môže automaticky:
- Prejsť posledné emaily
- Extrahovať nových ľudí do DB
- Doplniť chýbajúce údaje z email podpisov

### Meeting notes
Po meetingu:
```
"Spracuj tieto meeting notes: [prilepíš poznámky]"
```
Claude extrahuje action items, rozhodnutia a účastníkov.

### Údržba
Raz za čas povedz:
```
"Daj mi prehľad Context Engine — neúplné záznamy, zastarané kontakty"
```
Claude zavolá `ctx_incomplete()` + `ctx_stale()` a navrhne doplnenia.

---

## Troubleshooting

**Lokálne (Možnosť A):**

| Problém | Riešenie |
|---------|---------|
| `Module not found: context_engine` | Spusti `pip install -e .` v root foldri |
| `Connection refused` v Cowork | Over či `context-engine --sse` beží a ngrok je aktívny |
| `ctx_* tools not showing` | Reštartni Claude Code / reconnectni MCP v Cowork |
| Ngrok URL nefunguje | URL sa mení pri reštarte — updatni v Cowork settings |
| `UNIQUE constraint failed` | Osoba/firma už existuje — použi `ctx_update()` |
| Server spadne po chvíli | Terminál s `context-engine --sse` musí zostať otvorený |

**Railway (Možnosť B):**

| Problém | Riešenie |
|---------|---------|
| Build na Railway zlyhá | Skontroluj Logs tab v Railway, často chýba `Dockerfile` v gite — commitni ho |
| Po redeployi zmizli dáta | Zabudol si pridať volume na `/data` (Krok 1B.4) |
| OAuth login končí chybou | Skontroluj že callback URL v GitHub OAuth App matchuje presne tvoju Railway URL |
| `401 Unauthorized` v MCP klientovi | OAuth token expiroval — odpoj a znovu pripoj konektor |
| `Connection refused` na Railway URL | Skontroluj že si vygeneroval Public Domain (Krok 1B.6) |
| Iný user sa nemôže pripojiť | Pridaj jeho GitHub username do `OAUTH_ALLOWED_USERS` env var |
| Chcem zmeniť OAuth providera | Stačí zmeniť `OAUTH_PROVIDER` env var v Railway, redeploy je automatický |

---

## Checklist — "Mám všetko?"

**Spoločné:**
- [ ] Vybral som si deployment (Lokálne / Railway)
- [ ] `ctx_init()` vrátil "ok"
- [ ] Claude vidí `ctx_*` tooly
- [ ] Moja osoba je v DB
- [ ] Moja firma je v DB
- [ ] Aspoň 1 pravidlo komunikácie pridané
- [ ] Aspoň 3 kľúčoví ľudia pridaní
- [ ] `ctx_stats()` ukazuje správne počty
- [ ] Skúsil som "napíš email [meno]" a Claude použil ctx_context()

**Pre Lokálne (Možnosť A):**
- [ ] Python 3.10+ nainštalovaný
- [ ] `pip install -e .` prebehol bez chýb
- [ ] (Cowork) ngrok beží a URL je v Cowork settings

**Pre Railway (Možnosť B):**
- [ ] GitHub fork repa hotový
- [ ] Railway projekt vytvorený a build prešiel
- [ ] Volume na `/data` pridaný (DB sa nestratí pri redeployi)
- [ ] Environment variables nastavené (`CTX_DB`, `CTX_HOST`, OAuth)
- [ ] Verejná doména vygenerovaná
- [ ] OAuth provider nakonfigurovaný (GitHub OAuth App + callback URL)
- [ ] `OAUTH_ALLOWED_USERS` obsahuje môj username
- [ ] `/health` endpoint vracia `{"status": "ok"}`
- [ ] Aspoň jeden klient (Claude Code alebo Cowork) sa úspešne pripojil cez OAuth

---

*Ak sa zasekneš, povedz Claude: "Pomôž mi s nastavením Context Engine — kde som sa zasekol?"*
*Claude prečíta tento guide a navrhne ďalší krok.*
