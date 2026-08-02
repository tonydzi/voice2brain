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
  (frequency-based), wiki-links (existing note titles found in the text), FTS index.
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
