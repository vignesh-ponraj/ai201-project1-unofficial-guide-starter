from rag.preprocess import prepare_units


def test_weebly_homepage_keeps_substantial_drops_toc():
    # Homepage mixes tiny TOC link fragments with the real content blob. The blob is
    # kept (and chunked downstream); the nav fragments are dropped.
    home = ("Home\n\nFood & Fun\n\nHousing\n\n"
            + "Real content about stress relief stations with free food and coloring books. " * 6)
    units = prepare_units("weebly", home, is_homepage=True)
    assert any("stress relief" in u.lower() for u in units)
    assert "Home" not in units and "Housing" not in units


def test_weebly_subpage_kept():
    text = "Getting Around\n\nThere is a free intercampus shuttle every 30 minutes."
    units = prepare_units("weebly", text, is_homepage=False)
    assert any("shuttle" in u for u in units)


def test_quora_prepends_question():
    text = "QUESTION: Which professors do you recommend?\n\nDr. Lee is fantastic for stats."
    units = prepare_units("quora", text)
    assert all(u.startswith("Which professors do you recommend?") for u in units)


def test_reddit_keeps_text_units():
    text = "Go to office hours.\n\nUse the free tutoring center, it is underrated."
    units = prepare_units("reddit", text)
    assert len(units) == 2


def test_myprofreviews_pairs_name_with_review():
    text = ("1. Jane Doe\n\n"
            "Great professor, very clear lectures and fair grading throughout the semester.")
    units = prepare_units("myprofreviews", text)
    assert len(units) == 1
    assert units[0].startswith("1. Jane Doe")
    assert "clear lectures" in units[0]
