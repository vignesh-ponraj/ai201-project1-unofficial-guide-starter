"""Load the M3 chunk corpus from JSONL."""
import json
import pathlib
from typing import List

CHUNKS_PATH = pathlib.Path("data/chunks.jsonl")


def load_chunks(path=CHUNKS_PATH) -> List[dict]:
    path = pathlib.Path(path)
    chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks
