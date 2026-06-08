"""End-to-end generation eval: 5 questions + a refusal probe + an attribution probe.

Usage: python3 -m scripts.eval_generate   (needs GROQ_API_KEY in .env + built index)
"""
from rag.generate import answer

EVAL = [
    "How long should a single study session be before a break?",
    "What makes William Martin a popular professor?",
    "What transportation options does ASU provide between campuses?",
    "What resources are at ASU libraries during finals week?",
    "What common mistakes do students make on exams and how can I avoid them?",
]
REFUSAL_PROBE = "What is ASU's football schedule this season?"
ATTRIBUTION_PROBE = "What should I know about freshman housing near ASU?"


def _show(q):
    out = answer(q, k=5)
    urls = sorted({h.get("source_url") for h in out["sources"]})
    print(f"\nQ: {q}\nA: {out['answer']}\n   sources: {urls}")


def main():
    print("=== 5 eval questions ===")
    for q in EVAL:
        _show(q)
    print("\n=== refusal probe (off-domain — expect a 'not in sources' style answer) ===")
    _show(REFUSAL_PROBE)
    print("\n=== attribution probe (housing — expect a commercial-bias caveat if Rambler is used) ===")
    _show(ATTRIBUTION_PROBE)


if __name__ == "__main__":
    main()
