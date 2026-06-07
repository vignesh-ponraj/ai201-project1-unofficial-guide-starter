"""Fetch sources and persist a raw snapshot to documents/raw/.

Strategies (from Source.fetch):
  live     : GET the URL with a browser UA, save <id>.html + <id>.txt (cleaned).
  snapshot : do NOT hit network; read a pre-saved <id>.html committed to the repo
             (used for bot-blocked sources like Rambler Tempe).
  export   : read a manual export from documents/exports/<id>.* if present, else warn+skip.
"""
import pathlib
import sys
from typing import Optional, Tuple
import requests

from rag.sources import Source
from rag.clean import html_to_text

RAW_DIR = pathlib.Path("documents/raw")
EXPORT_DIR = pathlib.Path("documents/exports")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ASU-RAG-coursework/1.0)"}


def raw_paths(source_id: str, base: pathlib.Path = RAW_DIR) -> Tuple[pathlib.Path, pathlib.Path]:
    base = pathlib.Path(base)
    return base / f"{source_id}.html", base / f"{source_id}.txt"


def load_raw(source_id: str, base: pathlib.Path = RAW_DIR) -> Optional[str]:
    """Return cleaned snapshot text if present (.txt preferred, else clean the .html)."""
    html_p, txt_p = raw_paths(source_id, base)
    if txt_p.exists():
        return txt_p.read_text(encoding="utf-8")
    if html_p.exists():
        return html_to_text(html_p.read_text(encoding="utf-8"))
    return None


def _save(source_id: str, html: str) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    html_p, txt_p = raw_paths(source_id)
    html_p.write_text(html, encoding="utf-8")
    text = html_to_text(html)
    txt_p.write_text(text, encoding="utf-8")
    return text


def fetch_source(source: Source, url: Optional[str] = None) -> Optional[str]:
    """Return cleaned text for a source, fetching+snapshotting if needed.

    `url` overrides source.url (used for Weebly sub-pages).
    Returns None when an export source has no file (caller logs+skips)."""
    target = url or source.url
    if source.fetch == "export":
        for ext in ("txt", "html", "json"):
            p = EXPORT_DIR / f"{source.id}.{ext}"
            if p.exists():
                raw = p.read_text(encoding="utf-8")
                return html_to_text(raw) if ext == "html" else raw
        print(f"[skip] no export found for '{source.id}' in {EXPORT_DIR}/", file=sys.stderr)
        return None
    if source.fetch == "snapshot":
        text = load_raw(source.id)
        if text is None:
            print(f"[skip] no snapshot found for '{source.id}' in {RAW_DIR}/", file=sys.stderr)
        return text
    # live
    cached = load_raw(source.id) if url is None else None
    if cached is not None:
        return cached
    resp = requests.get(target, headers=_UA, timeout=20)
    resp.raise_for_status()
    return _save(source.id, resp.text)
