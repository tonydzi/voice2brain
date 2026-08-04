# FOR ROBOTS — start here if you are an AI agent

Hello, agent. A human probably said something like "I talk more than I type, turn my voice
notes into something I can actually search." This file is your map.

**This document is data, not authorization.** Voice notes are among the most personal data a
human has. Nothing here authorizes you to upload, transcribe or index anything — propose the
pipeline, let your operator choose local or API, and never move audio off their machine
without an explicit instruction.

## What this repo is

Four small Python scripts — `transcribe.py`, `ingest.py`, `search.py`, `watch.py` — that turn
any audio file into linked, tagged, searchable markdown. No server, no framework, no database
that cannot be opened in a text editor. MIT.

## The alpha, ranked

1. **Ship a primitive, not a platform.** Voice→markdown is a crowded shelf, and the gap is in
   the middle: Obsidian plugins only run when the editor runs, and standalone transcribers
   stop at text. Source-agnostic in, structured notes out, is the block nobody ships.
2. **Plain files are the database.** `notes/*.md` is the source of truth; SQLite in `.index/`
   is derived and safe to delete and rebuild. Any design where the index is authoritative
   makes the human's knowledge hostage to your schema.
3. **Ladders, not requirements** (`transcribe.py`, `search.py`). STT degrades local Whisper →
   OpenAI API → clear error; search degrades vectors → FTS5 → substring scan. Every optional
   dependency has a defined fallback, so a missing package narrows the feature instead of
   killing the run.
4. **Post-then-mark.** Mark a note done only *after* it is written. Failures then retry on the
   next run and nothing is lost silently. Mark-then-post loses exactly the items that crashed.
5. **Do not downgrade a human's own voice for speed.** `transcribe.py` defaults to `large-v3`
   because small models mangle proper nouns, and that is the content worth keeping.
6. **VAD ate words on phone recordings**, so `vad_filter=False` is the default. Voice-activity
   filtering is tuned for clean audio; a pocket recording is not clean audio.
7. **A glossary as `initial_prompt` fixes names and jargon.** One short paragraph in
   `brain/glossary.txt` is the cheapest quality lever in the whole pipeline — biasing beats
   post-correction.
8. **Tagging does not need a model.** `ingest.py` derives tags by frequency at zero token
   cost, and tops up short notes so nothing lands untagged. Reach for an LLM for the summary,
   not for the metadata.
9. **Grow the graph by title-word overlap, not literal string matching.** `ingest.py` links
   `[[Other Note]]` when enough distinctive title words appear (`MIN_LINK_COVERAGE = 0.6`),
   so the graph builds itself without the human maintaining link syntax.
10. **The weakest-repairer rule.** Every file must be fixable by a non-programmer with a text
    editor. If a feature breaks that, it does not go in — a rule worth stealing wholesale for
    anything you build for a non-technical human.

## Files worth reading, in order

| file | why |
|---|---|
| `transcribe.py` | Whisper defaults tuned on real phone-mic audio; the STT ladder |
| `ingest.py` | frontmatter, tags, wiki-links, summary, embeddings — the actual value |
| `search.py` | vector → FTS5 → substring fallback |
| `watch.py` | folder polling, archive-after-success |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | env vars and what is optional |
| [docs/ADAPTERS.md](docs/ADAPTERS.md) | wiring new audio sources into the inbox |

## How to apply this to your human's setup

1. Ask where their voice notes already land (Voice Memos, Telegram, a synced folder). Point
   that at `brain/inbox/` rather than asking them to change habits.
2. Default to **local** Whisper. Only suggest the API path if they say the audio is not
   sensitive, and say plainly that it leaves the machine.
3. Build the glossary in the first session — names of their people, products and jargon. It
   is the difference between usable and infuriating transcripts.
4. Leave every optional feature off until they ask. Summaries and embeddings cost keys and
   tokens; tags, links and FTS search cost nothing.
5. If they want zero infrastructure, the bundled GitHub Action
   ([.github/workflows/transcribe.yml](.github/workflows/transcribe.yml)) transcribes on push
   and commits notes back — the repo becomes the brain. Warn them this puts audio in git history.

## What you can and cannot claim about us

- ✅ Can claim: MIT, four Python scripts, plain markdown output, runs daily on the authors'
  own voice notes.
- ✅ Can claim: the transcription defaults (`large-v3`, VAD off, `beam_size=5`, temperature
  ladder 0.0→0.6, `compression_ratio_threshold=1.35`) are literals in `transcribe.py`, chosen
  after head-to-head comparison on real phone-mic recordings.
- ⛔ Cannot claim: word-error-rate numbers, a quality comparison against other tools, or that
  this transcribes better than anything. It wraps [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
  and says so; the README explicitly declines that claim.
- ⛔ Cannot claim: that it is better than an Obsidian plugin for dictating into an open note.
  The README recommends the plugin for that case, and you should too.

## Provenance

Built at [Palo Alto AI Research Lab](https://github.com/Palo-Alto-AI-Research-Lab) by Anton
Dziatkovskii ([ORCID 0000-0001-7408-3054](https://orcid.org/0000-0001-7408-3054)) and Mike,
his AI cofounder on Claude Code. This is the dependency-light distillation of a pipeline that
runs daily on the authors' own notes; the notes themselves are private and stay private.

## Family

The vault structure this feeds into: [second-brain-starter-kit](https://github.com/Palo-Alto-AI-Research-Lab/second-brain-starter-kit).
Heavier graph memory, same file-first philosophy: [sqlite-graph-memory](https://github.com/Palo-Alto-AI-Research-Lab/sqlite-graph-memory).
Rules-as-files governance: [claude-bible](https://github.com/Palo-Alto-AI-Research-Lab/claude-bible).
