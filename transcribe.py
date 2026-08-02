#!/usr/bin/env python3
"""transcribe.py — audio file(s) -> plain-text transcript(s).

Engine ladder (first available wins):
  1. faster-whisper, local  (pip install faster-whisper; free, private, GPU if present)
  2. OpenAI Whisper API     (set OPENAI_API_KEY; audio leaves your machine)
  3. clear error telling you how to get 1 or 2

Usage:
  python transcribe.py note.m4a [more.ogg ...]     # writes note.txt next to the audio
  python transcribe.py note.m4a --stdout           # print instead of writing

Env:
  V2B_LANGUAGE   language hint, e.g. "en", "ru" (default: autodetect)
  V2B_MODEL      local model name (default: large-v3)
  V2B_GLOSSARY   path to glossary file (default: brain/glossary.txt)
"""
import os
import sys
from pathlib import Path

AUDIO_EXT = {".m4a", ".mp3", ".ogg", ".oga", ".wav", ".flac", ".webm", ".mp4", ".aac", ".opus"}


def load_glossary() -> str:
    """Glossary file -> one short paragraph used as the STT initial prompt.
    Missing/empty file = no biasing, which is always safe."""
    path = Path(os.environ.get("V2B_GLOSSARY", "brain/glossary.txt"))
    try:
        return " ".join(path.read_text(encoding="utf-8").split())
    except OSError:
        return ""


def transcribe_local(path: Path, glossary: str) -> str | None:
    """Local faster-whisper with bake-off-proven params. Returns None if not installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model_name = os.environ.get("V2B_MODEL", "large-v3")
    # Quality-first fallback chain: GPU fp16 -> GPU int8 -> CPU int8.
    model = None
    for device, ctype in (("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(model_name, device=device, compute_type=ctype)
            print(f"[transcribe] {model_name} on {device} {ctype}", file=sys.stderr)
            break
        except Exception:
            continue
    if model is None:
        raise RuntimeError(f"faster-whisper installed but no backend could load {model_name}")
    segments, _info = model.transcribe(
        str(path),
        language=os.environ.get("V2B_LANGUAGE") or None,
        beam_size=5,
        vad_filter=False,                     # VAD ate words on phone-mic recordings
        initial_prompt=glossary or None,      # name/domain biasing fixes proper nouns
        condition_on_previous_text=True,
        temperature=[0.0, 0.2, 0.4, 0.6],     # retry ladder against stuck repetition
        compression_ratio_threshold=1.35,     # anti-hallucination
        log_prob_threshold=-1.0,
        no_speech_threshold=0.3,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def transcribe_api(path: Path) -> str | None:
    """OpenAI Whisper API. Returns None if no key is configured."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError:
        print("[transcribe] OPENAI_API_KEY set but `pip install openai` missing", file=sys.stderr)
        return None
    client = OpenAI()
    with path.open("rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=os.environ.get("V2B_LANGUAGE") or None,
        )
    return result.text.strip()


def transcribe(path: Path) -> str:
    glossary = load_glossary()
    text = transcribe_local(path, glossary)
    if text is None:
        text = transcribe_api(path)
    if text is None:
        sys.exit(
            "No STT engine available. Either:\n"
            "  pip install faster-whisper   (local, private, recommended)\n"
            "  export OPENAI_API_KEY=...    (cloud Whisper API)"
        )
    return text


def main(argv: list[str]) -> None:
    to_stdout = "--stdout" in argv
    files = [Path(a) for a in argv if not a.startswith("--")]
    if not files:
        sys.exit(__doc__)
    for path in files:
        if path.suffix.lower() not in AUDIO_EXT:
            print(f"[transcribe] skip (not audio): {path}", file=sys.stderr)
            continue
        text = transcribe(path)
        if to_stdout:
            print(text)
        else:
            out = path.with_suffix(".txt")
            out.write_text(text + "\n", encoding="utf-8")
            print(f"[transcribe] {path.name} -> {out.name} ({len(text)} chars)")


if __name__ == "__main__":
    main(sys.argv[1:])
