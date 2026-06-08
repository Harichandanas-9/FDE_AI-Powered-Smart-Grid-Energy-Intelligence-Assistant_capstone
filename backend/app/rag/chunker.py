"""
Chunking strategies for the Smart Grid RAG pipeline.

Three strategies
----------------
sentence  — split on sentence boundaries with N-sentence window + overlap.
            Best for prose incident narratives. DEFAULT.
fixed     — fixed character window with character stride overlap.
            Useful for long concatenated maintenance logs / reports.
incident  — one chunk = one incident narrative (legacy / pass-through).

Public API
----------
    from app.rag.chunker import chunk_texts, ChunkStrategy

    # Single text → list of chunk dicts
    chunks = chunk_text(
        text, metadata, chunk_id_prefix,
        strategy=ChunkStrategy.SENTENCE, size=4, overlap=1
    )

    # Batch: list[{id, text, metadata}] → list[{id, text, metadata}]
    chunks = chunk_texts(records, strategy=ChunkStrategy.SENTENCE, size=4, overlap=1)

Each returned chunk dict: {"id": str, "text": str, "metadata": dict}
The metadata of sub-chunks is a shallow copy of the parent's metadata
with three extra keys injected: chunk_index, chunk_total, parent_id.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List


class ChunkStrategy(str, Enum):
    SENTENCE = "sentence"
    FIXED = "fixed"
    INCIDENT = "incident"


# Regex: split after sentence-ending punctuation (`.`, `!`, `?`) followed by
# whitespace. Works without NLTK — no runtime dependency.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    parts = _SENT_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Core single-text chunker
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    metadata: Dict[str, Any],
    chunk_id_prefix: str,
    *,
    strategy: ChunkStrategy = ChunkStrategy.SENTENCE,
    size: int = 4,      # sentences (sentence mode) | characters (fixed mode)
    overlap: int = 1,   # sentences | characters
) -> List[Dict[str, Any]]:
    """
    Split *text* into overlapping chunks.

    Parameters
    ----------
    text            : raw narrative string
    metadata        : incident metadata dict (shallow-copied per chunk)
    chunk_id_prefix : base ID string; sub-chunks get suffix ``_c0``, ``_c1``…
    strategy        : ChunkStrategy enum value
    size            : window width (sentences or chars depending on strategy)
    overlap         : overlap width (same unit as size)

    Returns
    -------
    List of chunk dicts: [{id, text, metadata}, ...]
    """
    if not text or not text.strip():
        return []

    if strategy == ChunkStrategy.INCIDENT:
        return [_make_chunk(chunk_id_prefix, text, metadata, 0, 1, chunk_id_prefix)]

    if strategy == ChunkStrategy.SENTENCE:
        return _sentence_chunks(text, metadata, chunk_id_prefix, size, overlap)

    if strategy == ChunkStrategy.FIXED:
        return _fixed_chunks(text, metadata, chunk_id_prefix, size, overlap)

    # Fallback — unknown strategy → treat as incident
    return [_make_chunk(chunk_id_prefix, text, metadata, 0, 1, chunk_id_prefix)]


def _make_chunk(
    chunk_id: str,
    text: str,
    metadata: Dict[str, Any],
    index: int,
    total: int,
    parent_id: str,
) -> Dict[str, Any]:
    meta = {
        **metadata,
        "chunk_index": index,
        "chunk_total": total,
        "parent_id": parent_id,
    }
    return {"id": chunk_id, "text": text, "metadata": meta}


def _sentence_chunks(
    text: str,
    metadata: Dict[str, Any],
    prefix: str,
    window: int,
    overlap: int,
) -> List[Dict[str, Any]]:
    sents = _split_sentences(text)

    if len(sents) <= window:
        # Incident text already fits in one window — no splitting needed
        return [_make_chunk(prefix, text, metadata, 0, 1, prefix)]

    stride = max(1, window - overlap)
    raw_chunks: List[str] = []
    i = 0
    while i < len(sents):
        window_sents = sents[i: i + window]
        raw_chunks.append(" ".join(window_sents))
        i += stride

    total = len(raw_chunks)
    return [
        _make_chunk(f"{prefix}_c{idx}", chunk_str, metadata, idx, total, prefix)
        for idx, chunk_str in enumerate(raw_chunks)
    ]


def _fixed_chunks(
    text: str,
    metadata: Dict[str, Any],
    prefix: str,
    size: int,
    overlap: int,
) -> List[Dict[str, Any]]:
    stride = max(1, size - overlap)
    raw_chunks: List[str] = []
    i = 0
    while i < len(text):
        segment = text[i: i + size].strip()
        if segment:
            raw_chunks.append(segment)
        i += stride

    if not raw_chunks:
        return [_make_chunk(prefix, text, metadata, 0, 1, prefix)]

    total = len(raw_chunks)
    return [
        _make_chunk(f"{prefix}_c{idx}", segment, metadata, idx, total, prefix)
        for idx, segment in enumerate(raw_chunks)
    ]


# ---------------------------------------------------------------------------
# Batch helper — operates on the canonical chunk-dict format
# ---------------------------------------------------------------------------

def chunk_texts(
    records: List[Dict[str, Any]],
    *,
    strategy: ChunkStrategy = ChunkStrategy.SENTENCE,
    size: int = 4,
    overlap: int = 1,
) -> List[Dict[str, Any]]:
    """
    Expand a list of incident dicts into sub-chunks.

    Input  : [{"id": str, "text": str, "metadata": dict}, ...]
    Output : same format, potentially more records if texts are long enough
             to be split.
    """
    out: List[Dict[str, Any]] = []
    for rec in records:
        sub = chunk_text(
            rec.get("text", ""),
            rec.get("metadata", {}),
            rec["id"],
            strategy=strategy,
            size=size,
            overlap=overlap,
        )
        out.extend(sub)
    return out
