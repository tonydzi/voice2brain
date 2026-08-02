# Architecture

## The pipeline

```
           ┌────────────┐    ┌───────────┐    ┌──────────────────┐
 audio ──▶ │ transcribe │ ─▶ │  ingest   │ ─▶ │  brain/notes/*.md │ ◀── search
           └────────────┘    └───────────┘    └──────────────────┘
             STT ladder        tags, links,     source of truth
                               summary, index
```

Four scripts, one shared contract: **plain markdown files are the database.**
Everything else (SQLite index, embeddings) is derived and can be deleted and rebuilt.

## Script contracts

### transcribe.py
- Input: audio file(s). Output: `.txt` next to the audio (or stdout).
- Engine ladder: local faster-whisper → OpenAI Whisper API → explicit error.
- Local params are bake-off-proven on real phone-mic voice notes (see README table).
- The glossary (`brain/glossary.txt`) is passed as `initial_prompt` — the single
  biggest quality lever for proper nouns and domain jargon.

### ingest.py
- Input: transcript text (file or stdin). Output: one markdown note + index rows.
- Deterministic parts run always and cost 0 tokens: slug, frontmatter, auto-tags
  (frequency-based, topped up so short notes are never bare), wiki-links, FTS index.
- Wiki-links match on WORD OVERLAP, not on the literal slug. A slug is stopword-stripped
  ("audit-pricing-again") and prose is not ("the audit pricing again"), so substring
  matching found nothing on real notes. A link is written when ≥3 of another note's
  distinctive title words appear here and they cover ≥60% of that title
  (`MIN_LINK_TOKENS` / `MIN_LINK_COVERAGE` in `ingest.py` — the two numbers to tune
  if you get too many or too few links). A title shorter than 3 distinctive words is
  asked for all of them instead, so short notes stay linkable; one-word titles are
  skipped entirely.
- Known limits of word overlap, so you can judge whether they matter to you:
  - **Generic titles over-link.** A note called `machine-learning-model-evaluation`
    will link from any text that happens to mention machine learning and model
    evaluation. Raise `MIN_LINK_COVERAGE` if your notes share a lot of vocabulary.
  - **No stemming.** "customers' risks" does not match a `customer-risk` title, and
    inflected languages (Russian, German, Finnish) lose links this way. Stemming per
    language is more machinery than this repo is willing to carry; if you need it,
    swap `wiki_links()` — it is 12 lines and has no other callers.
- LLM parts are opt-in via `OPENAI_API_KEY`: one-paragraph summary, vector embedding.
- Collision-safe: same-day same-slug notes get `-2`, `-3` suffixes, never overwritten.

### search.py
- Ladder: vectors (cosine over the SQLite `vectors` table) → FTS5 → substring scan.
- The engine actually used is printed, so a degraded search never masquerades as a
  semantic one.

### watch.py
- Glue loop over `brain/inbox/`. **Post-then-mark:** audio is moved to `archive/`
  only after the note is written; any failure leaves the file in the inbox for retry.
- Poison-pill guard: one corrupt file logs and skips, it cannot kill the run.
- `--once` mode is designed for cron / Windows Task Scheduler.

## Why SQLite and not a vector DB

One file (`brain/.index/brain.db`), zero servers, FTS5 ships inside Python's stdlib
sqlite3. At personal-knowledge scale (thousands of notes, not billions) brute-force
cosine over JSON-stored vectors is milliseconds. When you outgrow it you will know,
and the notes — the actual brain — port anywhere because they are just markdown.

## Failure philosophy

- Every optional dependency degrades to a working (if weaker) path, loudly.
- Nothing is marked done before its output exists on disk.
- Derived state is disposable; source-of-truth state is human-readable.
