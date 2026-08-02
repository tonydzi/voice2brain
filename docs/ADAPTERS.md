# Adapters — getting audio into the inbox

voice2brain deliberately does NOT bundle source integrations. The contract is one
folder: **get your audio into `brain/inbox/` and the pipeline does the rest.**
Here are the recipes we actually use.

## macOS Voice Memos

Voice Memos stores recordings as `.m4a` on disk:

```
~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/*.m4a
```

Simplest adapter is a copy loop (new files only):

```bash
rsync -av --ignore-existing \
  ~/Library/Group\ Containers/group.com.apple.VoiceMemos.shared/Recordings/ \
  /path/to/brain/inbox/
```

Put it in a LaunchAgent or just run it before `watch.py --once`. On recent macOS
you may need to grant Full Disk Access to your terminal for that folder.

## Telegram

Record voice messages into a private "notes" chat, then pull them with a small
[Telethon](https://docs.telethon.dev) script:

```python
# pip install telethon; get api_id/api_hash at my.telegram.org
import asyncio
from pathlib import Path
from telethon import TelegramClient

CHAT = "me"                      # Saved Messages, or your notes-chat id
INBOX = Path("brain/inbox")
LEDGER = Path("brain/.index/tg_done.txt")   # msg ids only, so we never re-download

async def main():
    done = set(LEDGER.read_text().split()) if LEDGER.exists() else set()
    async with TelegramClient("v2b", API_ID, API_HASH) as client:
        async for m in client.iter_messages(CHAT, limit=50):
            if m.voice and str(m.id) not in done:
                await client.download_media(m, file=str(INBOX / f"tg-{m.id}.oga"))
                LEDGER.parent.mkdir(parents=True, exist_ok=True)
                with LEDGER.open("a") as f:
                    f.write(f"{m.id}\n")

asyncio.run(main())
```

Ledger-of-ids (never transcript text) + download-then-mark is the same
post-then-mark idiom the rest of the pipeline uses.

## n8n / any workflow tool

If you already run n8n, Zapier, or similar: end your flow with a "write binary
file" node pointing at `brain/inbox/`. That's the whole integration. We migrated
OFF an n8n-centric version of this pipeline to the folder contract precisely
because a folder survives every tool change.

## Syncthing / Dropbox / iCloud

Sync `brain/inbox/` across devices and record on your phone with any app that
saves audio files. The watcher on your always-on machine picks them up.

## Writing your own

An adapter is anything that ends with an audio file in the inbox. Rules of thumb:

1. keep a ledger of source ids, not content, for dedup;
2. mark a source item done only AFTER the file is fully written;
3. never delete the source until the note exists (the pipeline archives, you decide
   when to purge).

PRs with new adapter recipes are welcome.
