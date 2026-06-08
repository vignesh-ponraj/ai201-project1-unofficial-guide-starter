"""Groq-backed answer generation grounded in retrieved chunks."""
import os
from typing import List, Tuple

from rag.retrieve import retrieve

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are an assistant helping Arizona State University (ASU) freshmen. "
    "Answer using ONLY the numbered sources provided in the user message.\n"
    "Rules:\n"
    "1. If the sources do not contain the answer, reply exactly: "
    "\"I couldn't find that in the sources.\" Do not use outside knowledge or guess.\n"
    "2. Cite the sources you use by their name (the quoted title), e.g. "
    "\"According to MyProfReviews, ...\". Do NOT write out URLs and do NOT add your own "
    "'Sources:' list — the app shows clickable source links separately.\n"
    "3. Signal lower confidence and add a brief caveat when your support comes from a "
    "user_opinion source (anonymous, unverified) or an editorial source flagged "
    "commercial (the author has a financial stake).\n"
    "Be concise and specific."
)


def _format_hit(i: int, hit: dict) -> str:
    bias = " [commercial-bias]" if hit.get("commercial_bias") else ""
    title = hit.get("source_title") or hit.get("source_id")
    return (f'[Source {i}] "{title}" (source_type: {hit.get("source_type")}{bias})\n'
            f'{hit.get("text", "")}')


def build_prompt(query: str, hits: List[dict]) -> Tuple[str, str]:
    """Return (system, user) messages grounding the answer in `hits`."""
    blocks = "\n\n".join(_format_hit(i + 1, h) for i, h in enumerate(hits))
    user = f"Sources:\n{blocks}\n\nQuestion: {query}"
    return SYSTEM_PROMPT, user


_client = None


def get_client():
    """Lazy Groq client; reads GROQ_API_KEY from environment / .env."""
    global _client
    if _client is None:
        from dotenv import load_dotenv
        load_dotenv()
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set — copy .env.example to .env and add your key.")
        _client = Groq(api_key=key)
    return _client


def answer(query: str, k: int = 5, client=None) -> dict:
    """Retrieve k chunks, build a grounded prompt, and generate a cited answer."""
    hits = retrieve(query, k=k)
    system, user = build_prompt(query, hits)
    client = client or get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2,
    )
    return {"answer": resp.choices[0].message.content, "sources": hits}
