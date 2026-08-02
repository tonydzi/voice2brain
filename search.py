#!/usr/bin/env python3
"""search.py — ask your brain a question.

Ladder (first available wins):
  1. vector search        (if notes were embedded — needs OPENAI_API_KEY at ingest AND query time)
  2. SQLite FTS5          (always built by ingest.py, needs nothing)
  3. substring scan       (if the index is missing entirely)

Usage:
  python search.py "what did I say about pricing"
  python search.py --top 10 "pricing"

Env:
  V2B_BRAIN   brain directory (default: ./brain)
"""
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path

BRAIN = Path(os.environ.get("V2B_BRAIN", "brain"))
DB = BRAIN / ".index" / "brain.db"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def search_vectors(query: str, top: int) -> list[tuple[float, str]] | None:
    if not DB.exists() or not os.environ.get("OPENAI_API_KEY"):
        return None
    db = sqlite3.connect(DB)
    try:
        rows = db.execute("SELECT stem, vec FROM vectors").fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        db.close()
    if not rows:
        return None
    try:
        from openai import OpenAI
        qvec = OpenAI().embeddings.create(
            model="text-embedding-3-small", input=query).data[0].embedding
    except Exception as e:
        print(f"[search] vector search unavailable ({e})", file=sys.stderr)
        return None
    scored = [(cosine(qvec, json.loads(vec)), stem) for stem, vec in rows]
    scored.sort(reverse=True)
    return scored[:top]


def search_fts(query: str, top: int) -> list[tuple[float, str]] | None:
    if not DB.exists():
        return None
    db = sqlite3.connect(DB)
    try:
        # quote each term (punctuation can't break FTS syntax) and join with OR:
        # recall over precision — bm25 ranking still puts all-term matches first
        terms = " OR ".join(f'"{t}"' for t in re.findall(r"\w+", query, re.UNICODE))
        rows = db.execute(
            "SELECT stem, rank FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
            (terms or query, top)).fetchall()
        return [(-rank, stem) for stem, rank in rows]
    except sqlite3.OperationalError:
        return None
    finally:
        db.close()


def search_scan(query: str, top: int) -> list[tuple[float, str]]:
    words = [w for w in re.findall(r"\w+", query.lower(), re.UNICODE)]
    scored = []
    for p in (BRAIN / "notes").glob("*.md"):
        body = p.read_text(encoding="utf-8").lower()
        hits = sum(body.count(w) for w in words)
        if hits:
            scored.append((float(hits), p.stem))
    scored.sort(reverse=True)
    return scored[:top]


def main(argv: list[str]) -> None:
    top = 5
    if "--top" in argv:
        i = argv.index("--top")
        top = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        sys.exit(__doc__)
    query = " ".join(argv)

    for engine, fn in (("vectors", search_vectors), ("fts", search_fts)):
        results = fn(query, top)
        if results:
            break
    else:
        engine, results = "scan", search_scan(query, top)

    if not results:
        print("nothing found")
        return
    print(f"[search] engine={engine}")
    for score, stem in results:
        path = BRAIN / "notes" / f"{stem}.md"
        first_line = ""
        if path.exists():
            body = path.read_text(encoding="utf-8")
            body = re.sub(r"^---.*?---\s*", "", body, flags=re.S)  # drop frontmatter
            first_line = body.strip().splitlines()[0][:100] if body.strip() else ""
        print(f"  {score:10.4g}  {stem}\n              {first_line}")


if __name__ == "__main__":
    main(sys.argv[1:])
