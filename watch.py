#!/usr/bin/env python3
"""watch.py — the whole loop on a folder: inbox audio -> transcript -> note -> archive.

Drop audio files into brain/inbox/ (by hand, synced folder, Telegram bot, Voice Memos
export — see docs/ADAPTERS.md). This script polls the inbox and for each new file:

  1. transcribe            (transcribe.py engine ladder)
  2. ingest                (ingest.py: note + tags + links + index)
  3. move audio to brain/archive/

Post-then-mark: audio is only archived AFTER the note is written. A crash mid-way
means the file stays in the inbox and is retried next cycle — nothing is lost.

Usage:
  python watch.py              # poll every 60s, forever
  python watch.py --once       # single pass (put it in cron / Task Scheduler)

Env:
  V2B_BRAIN      brain directory (default: ./brain)
  V2B_INTERVAL   poll seconds (default: 60)
"""
import os
import sys
import time
from pathlib import Path

import ingest
import transcribe

BRAIN = Path(os.environ.get("V2B_BRAIN", "brain"))
INBOX = BRAIN / "inbox"
ARCHIVE = BRAIN / "archive"


def run_once() -> int:
    INBOX.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    done = 0
    for audio in sorted(INBOX.iterdir()):
        if audio.suffix.lower() not in transcribe.AUDIO_EXT:
            continue
        try:
            text = transcribe.transcribe(audio)
            if not text:
                print(f"[watch] {audio.name}: empty transcript, will retry", file=sys.stderr)
                continue
            ingest.ingest(text, source=audio.name)
            audio.rename(ARCHIVE / audio.name)   # archive only after the note exists
            done += 1
        except SystemExit:
            raise                                # no STT engine at all — stop loudly
        except Exception as e:                   # poison-pill guard: one bad file
            print(f"[watch] {audio.name}: FAILED ({e}) -> kept in inbox", file=sys.stderr)
    return done


def main(argv: list[str]) -> None:
    if "--once" in argv:
        n = run_once()
        print(f"[watch] processed {n} file(s)")
        return
    interval = int(os.environ.get("V2B_INTERVAL", "60"))
    print(f"[watch] polling {INBOX} every {interval}s (Ctrl+C to stop)")
    while True:
        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    main(sys.argv[1:])
