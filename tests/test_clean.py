from rag.clean import html_to_text

SAMPLE = """
<html><head><style>.x{color:red}</style><script>var a=1;</script></head>
<body>
<nav>Home About Apply Now</nav>
<header>SiteName</header>
<div class="cookie-banner">We use cookies</div>
<main>
  <h2>Study Tips</h2>
  <p>Professor Smith&#39;s exams are based on lecture slides, not the textbook.</p>
  <a class="share" href="#">Share</a>
  <a href="#">Read more</a>
</main>
<footer>Copyright 2026</footer>
<aside class="ad">Buy now</aside>
</body></html>
"""


def test_strips_boilerplate_and_decodes_entities():
    text = html_to_text(SAMPLE)
    assert "Professor Smith's exams" in text          # apostrophe entity decoded
    assert "<" not in text and ">" not in text          # no tags
    assert "&#39;" not in text                           # no raw entities
    for junk in ("cookies", "Apply Now", "Copyright", "Buy now", "Share", "Read more", "var a"):
        assert junk not in text, junk


def test_collapses_whitespace():
    text = html_to_text("<p>a</p>\n\n\n<p>b</p>")
    assert "\n\n\n" not in text
