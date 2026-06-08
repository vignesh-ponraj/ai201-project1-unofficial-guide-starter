"""Attach the 9 required metadata fields to every chunk."""
from typing import Optional
from rag.sources import Source

REQUIRED_FIELDS = (
    "chunk_id", "source_url", "source_title", "source_type",
    "author", "date", "chunk_index", "section_title", "source_id",
)


def chunk_id(source_id: str, index: int) -> str:
    return f"{source_id}::{index}"


def build_chunk(source: Source, chunk_index: int, text: str,
                section_title: Optional[str] = None) -> dict:
    return {
        "chunk_id": chunk_id(source.id, chunk_index),
        "source_id": source.id,
        "source_url": source.url,
        "source_title": source.title,
        "source_type": source.source_type,
        "author": source.author,
        "date": source.date,
        "chunk_index": chunk_index,
        "section_title": section_title,
        "commercial_bias": source.commercial_bias,
        "text": text,
    }
