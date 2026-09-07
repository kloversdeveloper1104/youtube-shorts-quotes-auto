"""パイプライン全体を実行するエントリーポイント。

1. 名言テキストを用意する
2. 読み上げ音声を合成する
3. 縦型Shorts動画を組み立てる
4. YouTubeへアップロードする

GitHub Actionsから `python src/main.py` として1日数回呼び出される想定。
アップロードに失敗しても他のステップの成果物(動画ファイル)は残るため、
ローカルでの動作確認にも使える。
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generate_audio import synthesize  # noqa: E402
from generate_quote import generate as generate_quote  # noqa: E402
from generate_video import build_video  # noqa: E402

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    audio_path = OUTPUT_DIR / "narration.mp3"
    video_path = OUTPUT_DIR / "short.mp4"

    quote_data = generate_quote()
    quote = quote_data["quote"]
    title = quote_data["title"]
    hashtags = quote_data["hashtags"]

    audio_data = synthesize(quote, audio_path)

    build_video(
        quote=quote,
        title=title,
        audio_path=audio_path,
        captions=audio_data["captions"],
        audio_duration=audio_data["duration"],
        out_path=video_path,
    )
    print(f"[main] 動画生成完了: {video_path}")

    skip_upload = os.environ.get("SKIP_UPLOAD") == "1"
    if skip_upload:
        print("[main] SKIP_UPLOAD=1 のためアップロードをスキップしました")
        return 0

    if not all(k in os.environ for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        print("[main] YouTube認証情報が未設定のためアップロードをスキップしました")
        return 0

    from upload_youtube import upload_short

    description = f"{quote}\n\n" + " ".join(hashtags) + "\n\n#shorts"
    tags = [h.lstrip("#") for h in hashtags]
    url = upload_short(video_path, title=f"{title} #shorts", description=description, tags=tags)
    print(f"[main] 投稿URL: {url}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
