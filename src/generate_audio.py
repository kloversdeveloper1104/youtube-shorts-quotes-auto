"""名言テキストを読み上げ音声(mp3)に変換し、字幕表示用のタイムスタンプを取得する。

優先: edge-tts (無料・APIキー不要・高品質な日本語ニューラル音声)
失敗時: gTTS (無料・APIキー不要) にフォールバックし、均等割りで疑似タイムスタンプを作る。

注意: edge-ttsは日本語(スペース区切りが無い言語)では単語単位のWordBoundaryを
返さず、文単位のSentenceBoundaryのみを返す。そのため、取得できた境界情報の
テキストを文字数ベースでさらに細かい字幕チャンク(表示用)に分割し、
時間は文字数に比例して按分することで、実用上十分な同期精度を得る。
"""
from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

VOICES = ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"]
MAX_CHARS_PER_CAPTION = 9


def _subdivide(text: str, start: float, duration: float, max_chars: int = MAX_CHARS_PER_CAPTION) -> list[dict]:
    chars = list(text)
    n = len(chars)
    if n == 0 or duration <= 0:
        return []
    per = duration / n
    captions: list[dict] = []
    buf = ""
    buf_start_idx = 0
    for i, c in enumerate(chars):
        if not buf:
            buf_start_idx = i
        buf += c
        if len(buf) >= max_chars or i == n - 1:
            cap_start = start + buf_start_idx * per
            cap_end = start + (i + 1) * per
            captions.append({"text": buf, "start": cap_start, "duration": cap_end - cap_start})
            buf = ""
    return captions


async def _edge_tts(text: str, out_mp3: Path, voice: str) -> list[dict]:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate="+0%")
    boundaries: list[dict] = []
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                boundaries.append(
                    {
                        "type": chunk["type"],
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10_000_000,  # 100ns -> sec
                        "duration": chunk["duration"] / 10_000_000,
                    }
                )

    # WordBoundaryが取れていればそれを優先、無ければSentenceBoundaryを使う
    words = [b for b in boundaries if b["type"] == "WordBoundary"]
    source = words if words else [b for b in boundaries if b["type"] == "SentenceBoundary"]

    captions: list[dict] = []
    for b in source:
        captions.extend(_subdivide(b["text"], b["start"], b["duration"]))
    return captions


def _gtts_fallback(text: str, out_mp3: Path) -> list[dict]:
    from gtts import gTTS
    from mutagen.mp3 import MP3

    gTTS(text=text, lang="ja").save(str(out_mp3))
    audio = MP3(str(out_mp3))
    total = audio.info.length
    return _subdivide(text, 0.0, total)


def synthesize(text: str, out_mp3: Path) -> dict:
    voice = random.choice(VOICES)
    try:
        captions = asyncio.run(_edge_tts(text, out_mp3, voice))
        if not out_mp3.exists() or out_mp3.stat().st_size == 0 or not captions:
            raise RuntimeError("edge-tts produced empty audio or no timing data")
        engine = "edge-tts"
    except Exception as e:  # noqa: BLE001
        print(f"[generate_audio] edge-tts失敗、gTTSへ切替: {e}")
        captions = _gtts_fallback(text, out_mp3)
        engine = "gtts"
        voice = "ja(gTTS)"

    duration = (captions[-1]["start"] + captions[-1]["duration"]) if captions else 0.0
    print(f"[generate_audio] engine={engine} voice={voice} captions={len(captions)} duration={duration:.2f}s")
    return {"engine": engine, "voice": voice, "captions": captions, "duration": duration}


if __name__ == "__main__":
    result = synthesize("小さな一歩が、大きな変化を生む。", Path("test_audio.mp3"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
