#!/usr/bin/env python3
"""ingest.py — transcript text -> a linked, tagged markdown note in your brain.

What it does (each step degrades gracefully):
  1. writes brain/notes/YYYY-MM-DD-<slug>.md with frontmatter
  2. auto-tags: frequency-based keywords, 0 tokens, no LLM
  3. wiki-links: [[Other Note]] for existing note titles mentioned in the text
  4. summary: one-paragraph TL;DR   (only if OPENAI_API_KEY is set)
  5. index: SQLite FTS5 always; vector embeddings if OPENAI_API_KEY is set

Usage:
  python ingest.py note.txt [more.txt ...]
  cat transcript.txt | python ingest.py -            # read from stdin

Env:
  V2B_BRAIN      brain directory (default: ./brain)
  V2B_SUMMARY    "off" to skip the LLM summary even when a key is present
  OPENAI_API_KEY enables summary + embeddings (optional)
"""
import datetime
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

BRAIN = Path(os.environ.get("V2B_BRAIN", "brain"))
NOTES = BRAIN / "notes"
INDEX = BRAIN / ".index"

# Minimal multilingual stopword list — enough to keep auto-tags meaningful.
STOP = set("""
a an the and or but if then this that these those i you he she it we they is are was were be been
being have has had do does did will would can could should of in on at to for with from by as not
no yes so very just about into over under out up down what which who whom when where why how all
и в не на я что он она оно мы вы они это как так но а же бы был была было были есть быть у к от
до по за из под над для при про без же ли то се его её их мой твой наш ваш свой этот тот такой
""".split())


def slugify(text: str, max_words: int = 6) -> str:
    # NFC, not NFKD: decomposition splits letters like Cyrillic "й" and mangles slugs
    text = unicodedata.normalize("NFC", text)
    words = re.findall(r"[\w]+", text.lower(), re.UNICODE)
    words = [w for w in words if w not in STOP][:max_words] or ["note"]
    return "-".join(words)[:60]


def auto_tags(text: str, n: int = 5, floor: int = 3) -> list[str]:
    """Frequency tags, with a top-up so short notes are not left bare.

    Measured on real voice notes: a spoken paragraph is 100-300 words and almost
    nothing repeats, so a strict "must appear twice" rule tagged most notes with
    one word and many with none. Repeated words still rank first; single-mention
    words only fill the remaining slots up to `floor`.
    """
    words = re.findall(r"[\w]{4,}", text.lower(), re.UNICODE)
    counts = Counter(w for w in words if w not in STOP)
    ranked = counts.most_common(n)
    tags = [w for w, c in ranked if c >= 2]
    if len(tags) < floor:
        tags += [w for w, c in ranked if c < 2][: floor - len(tags)]
    return tags[:n]


MIN_LINK_TOKENS = 3      # fewer shared words than this is a coincidence, not a reference
MIN_LINK_COVERAGE = 0.6  # ...and they must cover most of the other note's title


def existing_titles() -> dict[str, frozenset]:
    """note filename stem -> the distinctive words in its title, for wiki-linking."""
    titles = {}
    for p in NOTES.glob("*.md"):
        # strip the date prefix: 2026-08-02-audit-pricing-again -> {audit, pricing, again}
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", p.stem)
        words = frozenset(w for w in stem.split("-") if len(w) >= 3 and w not in STOP)
        if words:
            titles[p.stem] = words
    return titles


def wiki_links(text: str) -> list[str]:
    """Link when the text really refers to another note.

    Substring matching on the slug does not work and this was measured, not guessed:
    a slug is stopword-stripped ("audit-pricing-again") while prose is not
    ("the audit pricing again"), so the literal slug almost never occurs in a
    sentence and every note came out with zero links. Word-overlap survives the
    difference: enough of the other note's distinctive words, present in this text.
    """
    words = set(re.findall(r"[\w]{3,}", text.lower(), re.UNICODE))
    out = []
    for stem, title_words in existing_titles().items():
        hits = title_words & words
        if len(hits) >= MIN_LINK_TOKENS and len(hits) / len(title_words) >= MIN_LINK_COVERAGE:
            out.append(stem)
    return sorted(out)


def summarize(text: str) -> str:
    """One-paragraph TL;DR via the OpenAI API. Empty string when unavailable."""
    if os.environ.get("V2B_SUMMARY") == "off" or not os.environ.get("OPENAI_API_KEY"):
        return ""
    try:
        from openai import OpenAI
        resp = OpenAI().chat.completions.create(
            model=os.environ.get("V2B_SUMMARY_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content":
                       "Summarize this voice note in one short paragraph, "
                       "same language as the note:\n\n" + text[:8000]}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ingest] summary skipped ({e})", file=sys.stderr)
        return ""


def embed(text: str) -> list[float] | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        resp = OpenAI().embeddings.create(
            model="text-embedding-3-small", input=text[:8000])
        return resp.data[0].embedding
    except Exception as e:
        print(f"[ingest] embedding skipped ({e})", file=sys.stderr)
        return None


def index_note(stem: str, text: str, vector: list[float] | None) -> None:
    INDEX.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(INDEX / "brain.db")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(stem, body)")
    db.execute("CREATE TABLE IF NOT EXISTS vectors(stem TEXT PRIMARY KEY, vec TEXT)")
    db.execute("DELETE FROM fts WHERE stem = ?", (stem,))
    db.execute("INSERT INTO fts(stem, body) VALUES (?, ?)", (stem, text))
    if vector is not None:
        db.execute("INSERT OR REPLACE INTO vectors(stem, vec) VALUES (?, ?)",
                   (stem, json.dumps(vector)))
    db.commit()
    db.close()


def ingest(text: str, source: str) -> Path:
    if not text.strip():
        sys.exit(f"[ingest] refusing to create an empty note (source: {source})")
    NOTES.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    stem = f"{today}-{slugify(text)}"
    out = NOTES / f"{stem}.md"
    counter = 2
    while out.exists():
        out = NOTES / f"{stem}-{counter}.md"
        counter += 1
    stem = out.stem

    tags = auto_tags(text)
    links = wiki_links(text)
    summary = summarize(text)

    front = ["---", f"date: {today}", f"source: {source}",
             f"tags: [{', '.join(tags)}]", "type: voice-note", "---", ""]
    body = []
    if summary:
        body += ["> " + summary, ""]
    body += [text.strip(), ""]
    if links:
        body += ["Related: " + " ".join(f"[[{l}]]" for l in links), ""]
    out.write_text("\n".join(front + body), encoding="utf-8")

    index_note(stem, text, embed(text))
    print(f"[ingest] -> {out}  tags={tags or '-'} links={len(links)}")
    return out


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    if argv == ["-"]:
        ingest(sys.stdin.read(), source="stdin")
        return
    for arg in argv:
        path = Path(arg)
        ingest(path.read_text(encoding="utf-8"), source=path.name)


if __name__ == "__main__":
    main(sys.argv[1:])
