# voice2brain

**Voice → text → your personal knowledge base.** A primitive, not a platform.

You talk. It turns your voice notes into linked, tagged, searchable markdown — a second brain that grows every time you speak.

```
audio file ──▶ transcribe.py ──▶ ingest.py ──▶ notes/*.md ──▶ search.py
 (any source)    (Whisper)        (tags, links,      (plain        (ask your
                                   summary,           markdown)     own brain)
                                   embeddings)
```

No server. No database you can't open in a text editor. No framework. Four small Python scripts you can read in one sitting and fix with a hammer.

## Why a primitive?

DeFi has money legos. Personal knowledge needs the same: small, composable blocks. This is one block — **voice in, brain out** — deliberately kept so simple that:

- every note is a plain `.md` file you own forever (Obsidian/Logseq/anything opens it),
- every step runs standalone (`transcribe` without `ingest`, `ingest` without embeddings),
- every dependency is optional and degrades gracefully.

We run this pipeline daily on our own voice notes (hundreds of them). This repo is the distilled, dependency-light version of that production setup.

## Quick start

```bash
git clone https://github.com/Palo-Alto-AI-Research-Lab/voice2brain
cd voice2brain
pip install faster-whisper        # local STT (or set OPENAI_API_KEY to use the API instead)

python transcribe.py my-note.m4a          # → my-note.txt
python ingest.py my-note.txt              # → brain/notes/2026-08-02-my-note.md
python search.py "what did I say about pricing"
```

Or run the whole loop on a folder:

```bash
python watch.py                   # polls brain/inbox/, transcribes + ingests, archives audio
```

Drop audio into `brain/inbox/` from anywhere — a synced folder, a Telegram bot, macOS Voice Memos (see [docs/ADAPTERS.md](docs/ADAPTERS.md)).

## What ingestion does

Each transcript becomes a markdown note with:

- **frontmatter** — date, source file, duration, tags;
- **auto-tags** — frequency-based keywords (0 tokens, no LLM needed);
- **wiki-links** — `[[Other Note]]` links to existing notes whose titles appear in the text, so the graph grows by itself;
- **summary** — one-paragraph TL;DR (optional, needs an LLM key);
- **embeddings** — vector index in a single SQLite file for semantic search (optional; falls back to SQLite FTS5 full-text search, which needs nothing).

Everything optional is off by default and switched on by environment variables. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Transcription quality notes (hard-won)

The local engine defaults are not arbitrary — they came out of head-to-head bake-offs on real, messy phone-mic voice notes:

| Setting | Value | Why |
|---|---|---|
| model | `large-v3` | never downgrade your own voice for speed; small models mangle proper nouns |
| VAD | **off** | VAD ate words on phone recordings |
| `beam_size` | 5 | quality floor |
| `initial_prompt` | your glossary | biasing fixes names and domain terms ("OnlyFans" stops becoming "олифансе") |
| temperature ladder | 0.0→0.6 | retry ladder against stuck repetition |
| `compression_ratio_threshold` | 1.35 | anti-hallucination |

Put the words Whisper keeps mangling (names, products, jargon) into `brain/glossary.txt` — one short paragraph. It is passed as the initial prompt and dramatically improves proper nouns.

## Layout

```
brain/
  inbox/        drop audio here (watch.py polls it)
  archive/      audio moved here after successful ingestion
  notes/        your brain: one markdown file per voice note
  .index/       SQLite (FTS + optional vectors) — derived, safe to delete & rebuild
  glossary.txt  words Whisper should know (optional)
```

## Design rules

1. **Plain files are the database.** SQLite is only a derived index; `notes/` is the source of truth.
2. **Post-then-mark.** A note is only marked done after it is written; failures retry on the next run, nothing is silently lost.
3. **Ladders, not requirements.** STT: local Whisper → OpenAI API → clear error. Search: vectors → FTS5 → substring scan.
4. **Weakest-repairer rule.** Every file must be fixable by a non-programmer with a text editor. If a feature breaks that, it doesn't go in.

## Related

- [second-brain-starter-kit](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit) — the vault structure this feeds into
- [sqlite-graph-memory](https://github.com/Palo-Alto-AI-Research-Lab/sqlite-graph-memory) — heavier graph memory, same file-first philosophy

## License

MIT. Take it, fork it, wire it into your own stack. If you build an adapter for a new audio source, PRs are welcome — see [docs/ADAPTERS.md](docs/ADAPTERS.md).

---

Built at [Palo Alto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab). We're looking for engineer-testers — free seed access, DM [@tonydzi](https://t.me/tonydzi) or WhatsApp +13412229178.
