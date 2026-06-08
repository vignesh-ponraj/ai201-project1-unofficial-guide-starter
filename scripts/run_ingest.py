"""CLI: run the full ingestion + chunking pipeline and print the verification report.

Usage: python3 -m scripts.run_ingest
"""
from rag.ingest import ingest_all, verification_report


def main():
    chunks = ingest_all()
    print(verification_report(chunks))
    print(f"\nWrote {len(chunks)} chunks to data/chunks.jsonl")


if __name__ == "__main__":
    main()
