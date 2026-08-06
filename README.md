# voice2brain

**Voice → text → your personal knowledge base.** A primitive, not a platform.

You talk. It turns your voice notes into linked, tagged, searchable markdown — a second brain that grows every time you speak.

```
audio file ──▶ transcribe.py ──▶ ingest.py ──▶ notes/*.md ──▶ search.py
 (any source)    (Whisper)        (tags, links,      (plain        (ask your
                                   summary,           markdown)     own brain)
                                   embeddings)
```

No server. No database you can't open in a text editor. No framework. Four small Python scripts — `transcribe.py`, `ingest.py`, `search.py`, `watch.py` — that you can read in one sitting and fix with a hammer.

## Why a primitive?

DeFi has money legos. Personal knowledge needs the same: small, composable blocks. This is one block — **voice in, brain out** — deliberately kept so simple that:

- every note is a plain `.md` file you own forever (Obsidian/Logseq/anything opens it);
- every step runs standalone — `transcribe.py` without `ingest.py`, `ingest.py` without embeddings;
- every dependency is optional and degrades gracefully, via the ladders in `transcribe.py` and `search.py`.

We run this pipeline daily on our own voice notes (hundreds of them). This repo is the distilled, dependency-light version of that production setup.

## Prior art, and where this sits

Voice → markdown is a crowded shelf. We looked before building, and we are not claiming
to transcribe better than anyone — we use the same engine most of them do. What we
found, and the honest gap:

| What exists | Examples | What it gives you | Where it stops |
|---|---|---|---|
| **Obsidian plugins** | [whisper-obsidian-plugin](https://github.com/nikdanilov/whisper-obsidian-plugin), [obsidian-transcription](https://github.com/djmango/obsidian-transcription), [voice-md](https://github.com/denizokcu/voice-md), [obsidian-voice-notes](https://github.com/iahmedani/obsidian-voice-notes) | Record and transcribe inside the editor, insert at cursor or into daily notes | It is a plugin. It runs when Obsidian runs, in the language Obsidian speaks. You cannot put it in a cron job, a server, or someone else's pipeline |
| **Standalone transcribers** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win), dictation tools | Audio in, text out, very well | They stop at text. Tagging, linking, indexing and search are still your problem |
| **Single-source scripts** | Apple Voice Memos → daily journal gists | Turnkey for exactly one source and one output shape | Change the source or the output and you are rewriting it |

**voice2brain is the middle block nobody ships:** source-agnostic in (any audio file, any way it lands in a folder), and it keeps going *past* the transcript — note, frontmatter, auto-tags, wiki-links, full-text and vector index, search, all in `ingest.py` and `search.py`.
Four Python files, no editor, no server, no Docker, no framework.

**When you should not use this.** If you live inside Obsidian and just want to dictate into the note you have open, install a plugin — it is less work and it is right there.
If all you need is `audio → text`, use [faster-whisper](https://github.com/SYSTRAN/faster-whisper) directly; `transcribe.py` is a wrapper around it, not a replacement for it.
This repo earns its place only when you want the text to *become* something and stay yours afterwards.

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

### Repo-as-brain (zero infrastructure)

Fork this repo, remove `brain/` from `.gitignore`, and commit audio files into
`brain/inbox/` — the bundled [GitHub Action](.github/workflows/transcribe.yml)
transcribes them on push and commits the markdown notes back. No server, no
laptop left running: your git repo IS the brain, and its history is the changelog
of your thinking. Setup notes are at the top of the workflow file.

## What ingestion does

Each transcript becomes a markdown note. All five steps below are in `ingest.py`:

- **frontmatter** — date, source file, duration, tags;
- **auto-tags** — frequency-based keywords, 0 tokens and no LLM needed: repeated words rank first, and short notes are topped up so nothing lands untagged (`ingest.py`);
- **wiki-links** — `[[Other Note]]` when enough of another note's distinctive title words show up in this one: `MIN_LINK_COVERAGE = 0.6` and words of ≥3 characters in `ingest.py`, so the graph grows by itself without matching literal strings;
- **summary** — one-paragraph TL;DR (optional, needs an LLM key);
- **embeddings** — vector index in a single SQLite file for semantic search; optional, and `search.py` falls back to SQLite FTS5 full-text search, which needs nothing.

Everything optional is off by default and switched on by environment variables — the full list is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Transcription quality notes (hard-won)

The local engine defaults are not arbitrary — they came out of head-to-head bake-offs on real, messy phone-mic voice notes, and every value below is a literal in `transcribe.py`:

| Setting | Value | Why |
|---|---|---|
| model | `large-v3` | never downgrade your own voice for speed; small models mangle proper nouns |
| VAD | **off** | VAD ate words on phone recordings |
| `beam_size` | 5 | quality floor |
| `initial_prompt` | your glossary | biasing fixes names and domain terms ("OnlyFans" stops becoming "олифансе") |
| temperature ladder | 0.0→0.6 | retry ladder against stuck repetition |
| `compression_ratio_threshold` | 1.35 | anti-hallucination |

Put the words Whisper keeps mangling (names, products, jargon) into `brain/glossary.txt` — one short paragraph. `transcribe.py` passes it as the initial prompt, which is what stops the mangling shown in the table above.

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

1. **Plain files are the database.** SQLite is only a derived index; `notes/` is the source of truth, and `.index/` can be deleted and rebuilt by `ingest.py`.
2. **Post-then-mark.** A note is only marked done after it is written, so failures retry on the next run of `watch.py` and nothing is silently lost.
3. **Ladders, not requirements.** STT in `transcribe.py`: local Whisper → OpenAI API → clear error. Search in `search.py`: vectors → FTS5 → substring scan.
4. **Weakest-repairer rule.** Every file must be fixable by a non-programmer with a text editor — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). If a feature breaks that, it doesn't go in.

## Roadmap

**Now — [v0.1.0](https://github.com/Palo-Alto-AI-Research-Lab/voice2brain/releases/tag/v0.1.0).**
The four scripts end to end (`transcribe.py` → `ingest.py` → `notes/*.md` → `search.py`), the
`watch.py` folder poller, and repo-as-brain mode: push audio to `brain/inbox/` and the GitHub
Action transcribes it for you.

**Next**, in the order we would take them:

- **A self-test.** There is no test suite here yet. Everything above is verified by running it
  daily on our own notes, which is evidence of a kind but not the kind you can re-run.
- **Better linking on short notes.** `MIN_LINK_COVERAGE = 0.6` over distinctive title words means
  a two-word title has almost nothing to overlap on — measurement showed those notes stay
  unlinked by construction, and the limit is documented rather than hidden.
- **More source adapters** — see [docs/ADAPTERS.md](docs/ADAPTERS.md). Anything that can drop a
  file into a folder already works; the ask is for the sources that cannot.
- **Not planned:** a server, an editor plugin, or a schema you cannot open in a text editor. If
  you live inside Obsidian and want to dictate into the open note, install a plugin instead.

Every noticeable change ships as a new release, so the
[release feed](https://github.com/Palo-Alto-AI-Research-Lab/voice2brain/releases) is the honest
record of how far this primitive has actually come.

## Related

- [second-brain-starter-kit](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit) — the vault structure this feeds into
- [sqlite-graph-memory](https://github.com/Palo-Alto-AI-Research-Lab/sqlite-graph-memory) — heavier graph memory, same file-first philosophy

## License

MIT. Take it, fork it, wire it into your own stack. If you build an adapter for a new audio source, PRs are welcome — see [docs/ADAPTERS.md](docs/ADAPTERS.md).

---

Built at [Palo Alto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab). We're looking for engineer-testers — free seed access, DM [@tonydzi](https://t.me/tonydzi) or WhatsApp +13412229178.

---

<!--ecosystem-map:start-->

## 🧩 One piece of a working system

This repository is one piece lifted out of a live operation: one non-technical founder, an AI
cofounder, and a fleet of machines that reach consensus with each other and wake the human only
for money or the irreversible. It was extracted after it survived production, not written as a
demo — and it runs on its own: nothing here phones home to the rest.

**See how the whole thing fits together → [SYSTEM.md](https://github.com/Palo-Alto-AI-Research-Lab/Palo-Alto-AI-Research-Lab/blob/main/SYSTEM.md)**

Its closest neighbours in the **memory** layer: [`sqlite-graph-memory`](https://github.com/Palo-Alto-AI-Research-Lab/sqlite-graph-memory) · [`second-brain-starter-kit`](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit)

<!--ecosystem-map:end-->

## AI contributors

This project is built by a human + AI team, and the git log says so: Claude writes most of
the code, Codex and Grok review it, Gemini feeds the research. Each is credited on a commit
**only if its output changed that commit's content** — no decorative credits. Lab-wide
policy, one source for every repo: [AI-CONTRIBUTORS.md](https://github.com/Palo-Alto-AI-Research-Lab/.github/blob/main/AI-CONTRIBUTORS.md).
