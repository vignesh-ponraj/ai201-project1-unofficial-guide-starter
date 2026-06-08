from rag.generate import build_prompt, SYSTEM_PROMPT


def _hits():
    return [
        {"text": "Free intercampus shuttle every 30 min.", "source_type": "editorial",
         "source_url": "http://weebly", "source_id": "weebly", "commercial_bias": False},
        {"text": "Our apartments are the best near campus.", "source_type": "editorial",
         "source_url": "http://rambler", "source_id": "rambler_tempe", "commercial_bias": True},
    ]


def test_build_prompt_includes_text_type_url_and_question():
    system, user = build_prompt("How do I get between campuses?", _hits())
    assert system == SYSTEM_PROMPT
    assert "Free intercampus shuttle" in user
    assert "editorial" in user
    assert "http://weebly" in user
    assert "How do I get between campuses?" in user


def test_build_prompt_marks_commercial_bias():
    _, user = build_prompt("housing?", _hits())
    assert "http://rambler" in user
    assert "commercial" in user.lower()   # the biased source block is flagged


def test_system_prompt_states_three_rules():
    s = SYSTEM_PROMPT.lower()
    assert "couldn't find" in s or "could not find" in s   # rule 1 refusal phrase
    assert "cite" in s                                       # rule 2
    assert "user_opinion" in s and "commercial" in s         # rule 3


from unittest.mock import MagicMock
import rag.generate as gen


def test_answer_uses_retrieved_sources_and_client(monkeypatch):
    fake_hits = [{"text": "Shuttle every 30 min.", "source_type": "editorial",
                  "source_url": "http://weebly", "source_id": "weebly", "commercial_bias": False}]
    monkeypatch.setattr(gen, "retrieve", lambda q, k=5: fake_hits)

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Take the free shuttle. Sources: http://weebly"))
    ]

    out = gen.answer("how to get between campuses?", k=5, client=fake_client)
    assert out["answer"].startswith("Take the free shuttle")
    assert out["sources"] == fake_hits
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == gen.MODEL
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
