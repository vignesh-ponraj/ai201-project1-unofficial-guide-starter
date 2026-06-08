"""Embed all M3 chunks with BGE-M3 and build the persistent ChromaDB index.

Usage: python3 -m scripts.build_index
"""
from rag.corpus import load_chunks
from rag.embed import embed_texts, EMBED_DIM
from rag.store import build_index, PERSIST_DIR


def main():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks. Embedding with BGE-M3 (dim={EMBED_DIM})...")
    n = build_index(chunks, embedder=embed_texts)
    print(f"Indexed {n} chunks into ChromaDB at {PERSIST_DIR}/")


if __name__ == "__main__":
    main()
