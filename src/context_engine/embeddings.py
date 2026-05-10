"""Embedding layer for Context Engine — semantic search via Voyage AI + sqlite-vec.

Architektúra:
- Embeddings sa ukladajú do `embeddings` virtual table (sqlite-vec vec0)
- Mapping (table_name, row_id) → embedding_id v `embedding_index` tabuľke
- text_hash sleduje zmeny obsahu — re-embed len ak sa text zmenil

Voyage AI klient sa používa pre embedding generation. API key z env var VOYAGE_API
(fallback: VOYAGE_API_KEY).
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from typing import Iterable, Sequence


DEFAULT_MODEL = os.environ.get("VOYAGE_MODEL", "voyage-3-large")
EMBEDDING_DIM = 1024  # voyage-3-large = 1024, voyage-3 = 1024, voyage-3-lite = 512

# Sentinel — Voyage client je lazy
_voyage_client = None


_API_KEY_VARS = ("VOYAGE_API", "VOYAGE_API_KEY", "VOYAGE_KEY", "VOYAGEAI_API_KEY")


def _resolve_api_key() -> str | None:
    """Pokús sa nájsť API key vo viacerých štandardných env var názvoch."""
    for name in _API_KEY_VARS:
        v = os.environ.get(name)
        if v and v.strip():
            return v.strip()
    return None


def _get_client():
    """Lazy init Voyage client."""
    global _voyage_client
    if _voyage_client is not None:
        return _voyage_client

    api_key = _resolve_api_key()
    if not api_key:
        raise RuntimeError(
            f"Voyage API key not set. Tried env vars: {_API_KEY_VARS}. "
            "Sign up at https://www.voyageai.com/ and set on Railway."
        )

    try:
        import voyageai
    except ImportError:
        raise RuntimeError("voyageai package not installed. pip install voyageai")

    _voyage_client = voyageai.Client(api_key=api_key)
    return _voyage_client


def is_available() -> bool:
    """True ak je Voyage API key dostupný v ktoromkoľvek štandardnom env var."""
    return _resolve_api_key() is not None


def diagnostic_info() -> dict:
    """Diagnostika: ktoré env vars sú nastavené (bez odhalenia hodnoty)."""
    out = {"api_key_vars_checked": list(_API_KEY_VARS), "found_in": []}
    for name in _API_KEY_VARS:
        v = os.environ.get(name)
        if v:
            out["found_in"].append({
                "var": name,
                "length": len(v),
                "prefix": v[:6] + "...",
            })
    out["voyage_configured"] = bool(out["found_in"])
    out["model_default"] = DEFAULT_MODEL
    return out


def text_hash(text: str) -> str:
    """SHA256 hash textu — na detekciu zmien obsahu (re-embed trigger)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_texts(
    texts: Sequence[str],
    *,
    model: str = DEFAULT_MODEL,
    input_type: str = "document",
) -> list[list[float]]:
    """Embed batch textov cez Voyage. input_type: 'document' alebo 'query'."""
    if not texts:
        return []

    client = _get_client()
    # Voyage rate limit: 1k requests/min, 1M tokens/min for free tier — batch je OK
    # Max 128 texts per batch pre voyage-3 family
    BATCH = 128
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH):
        batch = list(texts[i : i + BATCH])
        result = client.embed(
            texts=batch,
            model=model,
            input_type=input_type,
            truncation=True,
        )
        all_embeddings.extend(result.embeddings)

    return all_embeddings


def embed_single(
    text: str,
    *,
    model: str = DEFAULT_MODEL,
    input_type: str = "document",
) -> list[float]:
    """Convenience — embed jeden text."""
    return embed_texts([text], model=model, input_type=input_type)[0]


def serialize_vector(embedding: Sequence[float]) -> bytes:
    """Serializuj vector na little-endian float32 bytes (formát pre vec0)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def deserialize_vector(blob: bytes) -> list[float]:
    """Deserializuj vec0 BLOB späť na list[float]."""
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


# ─────────────────────────────────────────────────────────────────────
# Embedding text generation per table
# ─────────────────────────────────────────────────────────────────────

def build_embedding_text(table: str, row: dict) -> str:
    """Skompiluje text pre embedding na základe typu záznamu.

    Cieľ: zachytiť čo najviac sémantického obsahu, vynechať irelevantné polia
    (id, dátumy, JSON metadata).
    """
    parts: list[str] = []

    if table == "notes":
        if row.get("title"):
            parts.append(row["title"])
        if row.get("content"):
            parts.append(row["content"])
        # Tags ako kontext (aj keď sú JSON, prepíšem na text)
        tags = _safe_json_list(row.get("tags"))
        if tags:
            parts.append(f"[tags: {', '.join(tags)}]")
        if row.get("category"):
            parts.append(f"[category: {row['category']}]")

    elif table == "interactions":
        if row.get("summary"):
            parts.append(row["summary"])
        if row.get("details"):
            parts.append(row["details"])
        topics = _safe_json_list(row.get("topics"))
        if topics:
            parts.append(f"[topics: {', '.join(topics)}]")
        kp = _safe_json_list(row.get("key_points"))
        if kp:
            parts.append(f"[key points: {' | '.join(kp)}]")
        if row.get("follow_up"):
            parts.append(f"[follow_up: {row['follow_up']}]")
        if row.get("person_name"):
            parts.append(f"[s {row['person_name']}]")
        if row.get("channel"):
            parts.append(f"[{row['channel']}]")

    elif table == "people":
        if row.get("name"):
            parts.append(row["name"])
        if row.get("role"):
            parts.append(f"role: {row['role']}")
        if row.get("company_name"):
            parts.append(f"@ {row['company_name']}")
        if row.get("relationship"):
            parts.append(f"vzťah: {row['relationship']}")
        if row.get("notes"):
            parts.append(row["notes"])
        if row.get("aliases"):
            aliases = _safe_json_list(row.get("aliases"))
            if aliases:
                parts.append(f"[tiež: {', '.join(aliases)}]")

    elif table == "companies":
        if row.get("name"):
            parts.append(row["name"])
        if row.get("type"):
            parts.append(f"type: {row['type']}")
        if row.get("industry"):
            parts.append(f"industry: {row['industry']}")
        if row.get("notes"):
            parts.append(row["notes"])

    elif table == "projects":
        if row.get("name"):
            parts.append(row["name"])
        if row.get("description"):
            parts.append(row["description"])
        if row.get("notes"):
            parts.append(row["notes"])

    return "\n".join(p for p in parts if p).strip()


def _safe_json_list(val) -> list[str]:
    """Tolerantný JSON list parser."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return [str(x) for x in v]
        except (json.JSONDecodeError, TypeError):
            pass
        return [t.strip() for t in s.split(",") if t.strip()]
    return []


# ─────────────────────────────────────────────────────────────────────
# Reciprocal Rank Fusion — kombinácia BM25 + semantic ranking
# ─────────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, int, float]]],
    *,
    k: int = 60,
) -> list[tuple[str, int, float]]:
    """RRF fusion (Cormack et al. 2009).

    Args:
        rankings: list of ranking lists, kde každý je [(table_name, row_id, original_score), ...]
                  ZORADENÝ od najlepšieho po najhorší.
        k: konstanta, default 60 (z papiera).

    Returns: zlúčený zoznam zoradený podľa RRF score, formát [(table, row_id, rrf_score), ...]
    """
    scores: dict[tuple[str, int], float] = {}
    for ranking in rankings:
        for rank, (table, row_id, _) in enumerate(ranking, start=1):
            key = (table, row_id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)

    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(table, row_id, score) for (table, row_id), score in fused]
