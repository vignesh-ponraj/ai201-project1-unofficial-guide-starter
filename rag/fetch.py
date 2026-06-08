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
# Full browser-like headers — some sources (e.g. Rambler Tempe) 403 a bare UA.
_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def raw_paths(source_id: str, base: pathlib.Path = RAW_DIR) -> Tuple[pathlib.Path, pathlib.Path]:
    base = pathlib.Path(base)
    return base / f"{source_id}.html", base / f"{source_id}.txt"


def load_raw(source_id: str, base: pathlib.Path = RAW_DIR) -> Optional[str]:
    """Return cleaned text for a saved snapshot.

    Prefer re-cleaning the raw .html (so cleaner changes propagate on re-run); fall
    back to a .txt-only snapshot (manual exports/snapshots that have no raw HTML)."""
    html_p, txt_p = raw_paths(source_id, base)
    if html_p.exists():
        return html_to_text(html_p.read_text(encoding="utf-8"))
    if txt_p.exists():
        return txt_p.read_text(encoding="utf-8")
    return None


def _save(save_id: str, html: str) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    html_p, txt_p = raw_paths(save_id)
    html_p.write_text(html, encoding="utf-8")
    text = html_to_text(html)
    txt_p.write_text(text, encoding="utf-8")
    return text


def fetch_source(source: Source, url: Optional[str] = None,
                 save_id: Optional[str] = None) -> Optional[str]:
    """Return cleaned text for a source, fetching+snapshotting if needed.

    `url` overrides source.url (used for Weebly sub-pages).
    `save_id` overrides the raw-snapshot filename (so each Weebly sub-page is saved
    separately instead of overwriting one file).
    Returns None when an export source has no file (caller logs+skips)."""
    sid = save_id or source.id
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
        text = load_raw(sid)
        if text is None:
            print(f"[skip] no snapshot found for '{sid}' in {RAW_DIR}/", file=sys.stderr)
        return text
    # live — reuse a committed raw snapshot if present, else fetch and save one
    cached = load_raw(sid)
    if cached is not None:
        return cached
    resp = requests.get(target, headers=_UA, timeout=20)
    resp.raise_for_status()
    # requests defaults to ISO-8859-1 when the charset is absent from the header,
    # which mangles UTF-8 punctuation (’ — etc). Trust the detected encoding instead.
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return _save(sid, resp.text)
