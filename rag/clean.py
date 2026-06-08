"""Convert raw HTML to substantive clean text: strip nav/footer/ads/boilerplate,
decode entities, normalize whitespace. Paragraph breaks are preserved as blank lines
so downstream recursive splitting can use them as semantic boundaries."""
import re
from bs4 import BeautifulSoup

# Tags that never contain substantive content.
# NOTE: <form> is intentionally NOT dropped — ASP.NET WebForms pages wrap the entire
# body in one <form runat="server">, so dropping it would discard all content.
_DROP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript",
              "button", "svg", "iframe"]

# Whole-word tokens in a class/id that mark boilerplate (ads, share bars, cookie
# banners, etc.). Matched against hyphen/underscore-split sub-tokens — NOT naive
# substrings — so a content container like id="wsite-content" class="wsite-not-footer"
# is not mistaken for a footer.
_DROP_TOKENS = {"cookie", "cookies", "ad", "ads", "advert", "advertisement",
                "share", "social", "newsletter", "subscribe", "breadcrumb",
                "breadcrumbs", "sidebar", "menu", "footer", "header", "banner",
                "popup", "modal", "related"}
# Negation words: a label like "not-footer" / "no-ads" is content, not boilerplate.
_NEGATIONS = {"not", "no", "non", "sans"}

# Link/anchor texts to drop (call-to-action boilerplate).
_DROP_LINK_TEXT = re.compile(r"^\s*(read more|share|apply now|sign up|subscribe|learn more)\s*$", re.I)


def _is_boilerplate(tag):
    if getattr(tag, "attrs", None) is None:
        return False
    classes = tag.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    for token in list(classes) + ([tag.get("id")] if tag.get("id") else []):
        subs = set(re.split(r"[^a-z0-9]+", token.lower()))
        if subs & _NEGATIONS:          # negated label (e.g. "wsite-not-footer") -> keep
            continue
        if subs & _DROP_TOKENS:
            return True
    return False


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(_DROP_TAGS):
        t.decompose()
    # Collect first, then decompose: decomposing a parent detaches children that may
    # still be in a live find_all list, so guard on parent before removing.
    for t in [t for t in soup.find_all(True) if _is_boilerplate(t)]:
        if t.parent is not None:
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
