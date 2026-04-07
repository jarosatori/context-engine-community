"""Slovak nickname dictionary and fuzzy search helpers for Context Engine.

Matchovanie mien je case-insensitive a bez diakritiky, takže "Frantisek",
"frantisek" aj "František" nájdu ten istý záznam v NICKNAMES dictionary.
"""

import json
import unicodedata
from difflib import SequenceMatcher


def _strip_diacritics(text: str) -> str:
    """Normalizuj text: lowercase + odstráň diakritiku.

    'František' → 'frantisek', 'Ľubomír' → 'lubomir', 'Katarína' → 'katarina'
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Slovak nickname dictionary — full name → common nicknames
NICKNAMES = {
    # Muži
    "Samuel": ["Samo", "Samko"],
    "Peter": ["Peťo", "Peto", "Peťko"],
    "Jakub": ["Kuba", "Kubo", "Kubko"],
    "Jaroslav": ["Jaro", "Jarko"],
    "Michal": ["Mišo", "Miško"],
    "Martin": ["Maťo", "Maťko"],
    "Ondrej": ["Ondro"],
    "Tomáš": ["Tomo", "Tomáško", "Tomi"],
    "Šimon": ["Šimo"],
    "Marek": ["Marko"],
    "Richard": ["Rišo", "Riško"],
    "Róbert": ["Robo", "Robko", "Robert"],
    "Lukáš": ["Luki", "Luky"],
    "Filip": ["Filo"],
    "Daniel": ["Dano", "Danko"],
    "Adrián": ["Ado", "Adrian"],
    "Norbert": ["Noro"],
    "Dalibor": ["Dali", "Dubec"],
    "Zoltán": ["Zoli"],
    "Vladimír": ["Vlado"],
    "Stanislav": ["Stano"],
    "Rastislav": ["Rasto"],
    "Miroslav": ["Miro"],
    "František": ["Fero", "Ferko"],
    "Jozef": ["Jožo", "Jožko"],
    "Ján": ["Janko", "Jano"],
    "Pavol": ["Paľo", "Paľko"],
    "Roman": ["Romo"],
    "Gregor": ["Grego"],
    "Marcel": ["Marco"],
    "Patrik": ["Paťo"],
    "Alexander": ["Alex", "Saňo"],
    "Matej": ["Maťo"],
    "Viktor": ["Viki"],
    # Rozšírenie — ďalšie bežné slovenské mená
    "Adam": ["Adamko", "Ado"],
    "Andrej": ["Ondrej", "Andy"],
    "Ivan": ["Ivo", "Ivko"],
    "Juraj": ["Juro", "Ďuro", "Jurko"],
    "Milan": ["Milo", "Milko"],
    "Karol": ["Karči", "Karolko"],
    "Kamil": ["Kamo"],
    "Dušan": ["Dušo", "Duško"],
    "Ladislav": ["Laco", "Laci", "Lacko"],
    "Ľubomír": ["Ľubo", "Lubo"],
    "Branislav": ["Brano", "Braňo"],
    "Erik": ["Eriček"],
    "Igor": ["Igorko"],
    "Matúš": ["Maťo", "Maťko"],
    "Dominik": ["Domi", "Dodo"],
    "Dávid": ["Dávidko", "Davo"],
    "Boris": ["Borisko"],
    "Vincent": ["Vinco", "Vinci"],
    "Rudolf": ["Rudo", "Rudko"],
    "Oliver": ["Oli", "Olko"],
    "Sebastián": ["Sebo", "Sebko"],
    "Emil": ["Emilko"],
    "Radoslav": ["Rado", "Radko"],
    "Ľuboš": ["Ľubo", "Lubos"],
    "Marián": ["Mario", "Marianko"],
    "Július": ["Julo", "Julko"],
    "Bohuš": ["Boho", "Bohušo"],
    "Anton": ["Tono", "Tonko"],
    "Vojtech": ["Vojto", "Vojo"],
    "Radovan": ["Rado"],
    "Vladislav": ["Vlado"],
    "Štefan": ["Števo", "Števko", "Pišta"],
    "Maroš": ["Maroško"],
    "Pavel": ["Paľo", "Pavlo"],
    "Tibor": ["Tibi", "Tiborko"],
    "Ernest": ["Erno"],
    # Ženy
    "Alexandra": ["Alex", "Saška"],
    "Karolína": ["Kaja", "Karolínka", "Karola"],
    "Dominika": ["Domi", "Domča"],
    "Patrícia": ["Paťka"],
    "Lenka": ["Lenôčka"],
    "Monika": ["Monča", "Moni"],
    "Zuzana": ["Zuza", "Zuzka"],
    "Katarína": ["Katka", "Kaťa"],
    "Jana": ["Janka", "Janči"],
    "Michaela": ["Miška", "Michi"],
    "Natália": ["Natka", "Naty"],
    "Barbora": ["Bára", "Barborka", "Barča"],
    "Simona": ["Simča"],
    "Veronika": ["Vera", "Verka"],
    "Kristína": ["Kristínka", "Kiki"],
    "Lucia": ["Lucka"],
    "Mária": ["Marika", "Maja", "Majka"],
    "Eva": ["Evka", "Evička"],
    "Soňa": ["Sonička"],
    "Ivana": ["Iva", "Ivka"],
    # Rozšírenie — ženy
    "Andrea": ["Andy", "Andrejka"],
    "Martina": ["Maťa", "Maťka"],
    "Anna": ["Anka", "Anča", "Anička"],
    "Petra": ["Peťa", "Peťka"],
    "Tatiana": ["Tanka", "Taňa"],
    "Viera": ["Vierka", "Vierika"],
    "Helena": ["Helenka", "Hela"],
    "Adriana": ["Ada", "Adka"],
    "Klaudia": ["Klaudi"],
    "Renáta": ["Rena", "Renka"],
    "Silvia": ["Silvi", "Silvinka"],
    "Beáta": ["Beatka", "Bea"],
    "Iveta": ["Ivetka"],
    "Emília": ["Ema", "Emka"],
    "Margita": ["Gita", "Magda"],
    "Magdaléna": ["Magda", "Majka"],
    "Terézia": ["Terka", "Tereza"],
    "Gabriela": ["Gabi", "Gabika"],
    "Júlia": ["Julka", "Julienka"],
    "Nikola": ["Nika", "Niki"],
    "Sára": ["Sárka"],
    "Ema": ["Emka", "Emička"],
    "Laura": ["Laurinka"],
    "Zuzka": ["Zuza", "Zuzanka"],
    "Klára": ["Klárka", "Klari"],
    "Daniela": ["Dana", "Danka"],
    "Dana": ["Danka", "Dadka"],
    "Ľubica": ["Ľuba", "Ľubka"],
}

# Reverse lookup: nickname → full name (case-sensitive, s diakritikou)
NICKNAME_REVERSE: dict[str, str] = {}
for _full, _nicks in NICKNAMES.items():
    for _nick in _nicks:
        # If collision (e.g. "Alex" for both Alexander and Alexandra), keep first
        if _nick not in NICKNAME_REVERSE:
            NICKNAME_REVERSE[_nick] = _full

# Normalizované lookupy (lowercase + bez diakritiky) — pre matchovanie mien bez diakritiky
# Kľúč: "frantisek", Hodnota: "František" (správny tvar s diakritikou)
NICKNAMES_NORM: dict[str, str] = {_strip_diacritics(full): full for full in NICKNAMES}

# Kľúč: "peto", Hodnota: "Peter" (plné meno s diakritikou)
NICKNAME_REVERSE_NORM: dict[str, str] = {
    _strip_diacritics(nick): full for nick, full in NICKNAME_REVERSE.items()
}


def _lookup_full_name(first_name: str) -> str | None:
    """Nájdi plné meno podľa krstného mena, tolerantné na diakritiku + case.

    'František', 'frantisek', 'FRANTISEK', 'Frantisek' → 'František'
    'Samo', 'samo' → None (toto je nickname, nie full name)
    """
    if first_name in NICKNAMES:
        return first_name
    return NICKNAMES_NORM.get(_strip_diacritics(first_name))


def _lookup_full_from_nickname(nick: str) -> str | None:
    """Nájdi plné meno podľa prezývky, tolerantné na diakritiku + case.

    'Peťo', 'peto', 'PETO' → 'Peter'
    'Peter' → None (toto je full name, nie nickname)
    """
    if nick in NICKNAME_REVERSE:
        return NICKNAME_REVERSE[nick]
    return NICKNAME_REVERSE_NORM.get(_strip_diacritics(nick))


def expand_query_names(query: str) -> list[str]:
    """Given a query like 'Samo Skovajsa', return alternative name forms.

    Returns list of alternative full names to try (NOT including original).
    Tolerantné na diakritiku — 'Frantisek Novak' aj 'František Novák' fungujú.

    E.g. 'Samo Skovajsa' → ['Samuel Skovajsa']
         'Samuel Skovajsa' → ['Samo Skovajsa', 'Samko Skovajsa']
    """
    parts = query.strip().split()
    if len(parts) < 2:
        # Single word — try expanding as first name only
        first = parts[0]
        results = []
        full = _lookup_full_from_nickname(first)
        if full:
            results.append(full)
            for nick in NICKNAMES.get(full, []):
                # Porovnaj normalizovane aby sme nepridali duplikát
                if _strip_diacritics(nick) != _strip_diacritics(first):
                    results.append(nick)
        full_direct = _lookup_full_name(first)
        if full_direct:
            results.extend(NICKNAMES[full_direct])
        return results

    first_name = parts[0]
    rest = " ".join(parts[1:])
    alternatives = []

    # If first name is a nickname → add full name variant
    full = _lookup_full_from_nickname(first_name)
    if full:
        alternatives.append(f"{full} {rest}")
        for nick in NICKNAMES.get(full, []):
            if _strip_diacritics(nick) != _strip_diacritics(first_name):
                alternatives.append(f"{nick} {rest}")

    # If first name is a full name → add nickname variants
    full_direct = _lookup_full_name(first_name)
    if full_direct:
        for nick in NICKNAMES[full_direct]:
            alternatives.append(f"{nick} {rest}")

    return alternatives


def surname_similarity(query_name: str, db_name: str) -> float:
    """Compare surnames using SequenceMatcher. Returns 0.0-1.0."""
    q_parts = query_name.strip().split()
    d_parts = db_name.strip().split()
    if len(q_parts) < 2 or len(d_parts) < 2:
        return 0.0
    q_surname = q_parts[-1].lower()
    d_surname = d_parts[-1].lower()
    return SequenceMatcher(None, q_surname, d_surname).ratio()


def generate_aliases(full_name: str) -> list[str]:
    """Generate aliases for a person based on NICKNAMES dictionary.

    Tolerantné na diakritiku — funguje aj pre 'Frantisek Novak' bez diakritiky.

    E.g. 'Samuel Skovajsa' → ['Samo Skovajsa', 'Samko Skovajsa']
         'Frantisek Novak' → ['Fero Novak', 'Ferko Novak', 'František Novak']
         'Peťo Ďurák' → ['Peter Ďurák'] (reverse: nickname → full name)
    """
    parts = full_name.strip().split()
    if len(parts) < 2:
        return []

    first_name = parts[0]
    rest = " ".join(parts[1:])
    aliases = []

    # If first name is in NICKNAMES (with diacritic tolerance) → add nickname variants
    full_direct = _lookup_full_name(first_name)
    if full_direct:
        for nick in NICKNAMES[full_direct]:
            aliases.append(f"{nick} {rest}")
        # Ak je meno bez diakritiky, pridaj aj správny tvar s diakritikou
        if full_direct != first_name:
            aliases.append(f"{full_direct} {rest}")

    # If first name is a nickname → add full name + other nicknames
    full_from_nick = _lookup_full_from_nickname(first_name)
    if full_from_nick:
        aliases.append(f"{full_from_nick} {rest}")
        for nick in NICKNAMES.get(full_from_nick, []):
            if _strip_diacritics(nick) != _strip_diacritics(first_name):
                aliases.append(f"{nick} {rest}")

    # Deduplikácia — zachová poradie
    seen = set()
    unique = []
    for a in aliases:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique


FUZZY_THRESHOLD = 0.75
