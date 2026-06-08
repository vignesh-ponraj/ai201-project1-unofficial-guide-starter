"""Run the 5 eval questions through retrieval and report whether the expected
source lands in top-k, and at what rank. Verifies embedding dim + retrieval quality.

Usage: python3 -m scripts.eval_retrieval
"""
from rag.embed import embed_texts, EMBED_DIM
from rag.retrieve import retrieve

# (question, set of acceptable expected source_ids)
EVAL = [
    ("How long should a single study session be before a break?",
     {"asuonline_finals", "heysunny"}),
    ("What makes William Martin a popular professor?",
     {"myprofreviews"}),
    ("What transportation options does ASU provide between campuses?",
     {"weebly"}),
    ("What resources are at ASU libraries during finals week?",
     {"weebly"}),
    ("What common mistakes do students make on exams and how to avoid them?",
     {"asunews_miceli"}),
]


def main():
    assert embed_texts(["dim check"]).shape[1] == EMBED_DIM, "unexpected embedding dim"
    passed = 0
    for q, expected in EVAL:
        hits = retrieve(q, k=5)
        ranks = [i + 1 for i, h in enumerate(hits) if h["source_id"] in expected]
        ok = bool(ranks)
        passed += ok
        rank = ranks[0] if ranks else "—"
        top = hits[0]
        print(f"[{'PASS' if ok else 'MISS'}] rank={rank} | {q[:48]!r}")
        print(f"        top: ({top['source_id']}, score={top['score']:.3f}) {top['text'][:70]!r}")
    print(f"\n{passed}/{len(EVAL)} eval questions retrieved their expected source in top-5")


if __name__ == "__main__":
    main()
