from rag.preprocess import prepare_units, weebly_is_homepage_blob


def test_weebly_homepage_blob_excluded():
    blob = ("Transportation light rail food dining housing tutoring finals stress relief "
            "bikes parking everything in one paragraph " * 5)
    assert weebly_is_homepage_blob(blob, is_homepage=True) is True
    units = prepare_units("weebly", blob, is_homepage=True)
    assert units == []   # homepage produces no units


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
