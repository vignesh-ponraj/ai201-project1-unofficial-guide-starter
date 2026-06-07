"""Convert raw HTML to substantive clean text: strip nav/footer/ads/boilerplate,
decode entities, normalize whitespace. Paragraph breaks are preserved as blank lines
so downstream recursive splitting can use them as semantic boundaries."""
import re
from bs4 import BeautifulSoup

# Tags that never contain substantive content.
_DROP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript",
              "form", "button", "svg", "iframe"]

# class/id substrings that mark boilerplate (ads, share bars, cookie banners, etc.).
_DROP_HINTS = ("cookie", "ad-", "ads", "advert", "share", "social", "newsletter",
               "subscribe", "breadcrumb", "sidebar", "menu", "nav-", "footer",
               "header", "banner", "popup", "modal", "related", "comment-count")

# Link/anchor texts to drop (call-to-action boilerplate).
_DROP_LINK_TEXT = re.compile(r"^\s*(read more|share|apply now|sign up|subscribe|learn more)\s*$", re.I)


def _is_boilerplate(tag):
    attr = " ".join(tag.get("class", []) + [tag.get("id", "")]).lower()
    return any(h in attr for h in _DROP_HINTS)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(_DROP_TAGS):
        t.decompose()
    for t in soup.find_all(True):
        if _is_boilerplate(t):
            t.decompose()
    for a in soup.find_all("a"):
        if _DROP_LINK_TEXT.match(a.get_text(strip=True)):
            a.decompose()
    text = soup.get_text(separator="\n")
    # normalize: trim lines, drop empties, collapse to single blank-line paragraph breaks
    lines = [ln.strip() for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip()
