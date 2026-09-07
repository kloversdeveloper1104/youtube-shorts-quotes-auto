"""名言テキスト+音声から、縦型(1080x1920)のYouTube Shorts動画を生成する。

素材はすべてコードで生成する(外部の画像/動画/音楽素材を使わない)ため、
著作権リスクとランニングコストをゼロに保つ。

- 背景: PILで生成したグラデーション画像 + ゆっくりズームするKen Burns風エフェクト
- 字幕: 単語(またはgTTSの場合は文字)をチャンクにまとめ、音声のタイムスタンプに同期して表示
- BGM: numpyで合成したシンプルなアンビエントパッド音(著作権フリー)
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# moviepy 1.0.3 の resize処理が古いPillow定数を参照しているため互換シムを当てる
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

W, H = 1080, 1920
FPS = 24

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]

PALETTES = [
    ((20, 24, 82), (255, 94, 98)),      # 紺 -> サンセットピンク
    ((10, 10, 30), (255, 153, 51)),     # 漆黒 -> オレンジ
    ((7, 41, 51), (0, 200, 180)),       # ティール系
    ((45, 10, 60), (255, 0, 128)),      # パープル -> マゼンタ
    ((5, 30, 20), (0, 180, 120)),       # フォレストグリーン
    ((15, 15, 15), (200, 30, 40)),      # ブラック -> レッド
]


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _make_gradient(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> Image.Image:
    base = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        base[y, :, :] = color
    img = Image.fromarray(base, "RGB")
    # 斜めの光の帯を軽く重ねて単調さを消す
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon(
        [(0, H * 0.15), (W, 0), (W, H * 0.05), (0, H * 0.35)],
        fill=(255, 255, 255, 18),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return img


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    mid = len(text) // 2
    for offset in range(0, mid):
        for i in (mid - offset, mid + offset):
            if 0 < i < len(text):
                left, right = text[:i], text[i:]
                if draw.textlength(left, font=font) <= max_width and draw.textlength(right, font=font) <= max_width:
                    return [left, right]
    return [text]


def _render_caption_image(text: str, font_size: int = 84) -> np.ndarray:
    """テキストを、その内容にちょうど収まる高さのRGBA画像として描画する。

    フル画面サイズのキャンバスに描くと(テキストが常に画像の縦中央に来るため)
    後段でmoviepyの set_position と組み合わせたときに意図した位置に置けない。
    ここではコンテンツの実サイズだけの画像を返し、配置は呼び出し側に委ねる。
    """
    font = _find_font(font_size)
    probe = Image.new("RGBA", (W, 10))
    probe_draw = ImageDraw.Draw(probe)
    lines = _wrap_text(text, font, int(W * 0.86), probe_draw)
    line_height = int(font_size * 1.35)
    pad_y = int(font_size * 0.3)
    img_h = line_height * len(lines) + pad_y * 2
    img = Image.new("RGBA", (W, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = pad_y
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (W - w) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=8, stroke_fill=(0, 0, 0, 255))
        y += line_height
    return np.array(img)


def _make_ambient_audio(duration: float, fps: int = 44100):
    t = np.linspace(0, duration, int(duration * fps), endpoint=False)
    freqs = random.choice([(110, 164.81, 220), (98, 146.83, 196), (130.81, 196, 261.63)])
    wave = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    fade = min(2.0, duration / 3)
    n_fade = int(fade * fps)
    envelope = np.ones_like(wave)
    if n_fade > 0:
        envelope[:n_fade] = np.linspace(0, 1, n_fade)
        envelope[-n_fade:] = np.linspace(1, 0, n_fade)
    wave = wave * envelope * 0.15
    stereo = np.column_stack([wave, wave]).astype(np.float32)
    return stereo, fps


def build_video(
    quote: str,
    title: str,
    audio_path: Path,
    captions: list[dict],
    audio_duration: float,
    out_path: Path,
) -> None:
    from moviepy.audio.AudioClip import AudioArrayClip
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
    )

    lead_in = 0.4
    tail = 1.0
    total_duration = audio_duration + lead_in + tail

    c1, c2 = random.choice(PALETTES)
    bg_img = _make_gradient(c1, c2)
    bg_clip = (
        ImageClip(np.array(bg_img))
        .set_duration(total_duration)
        .resize(lambda t: 1 + 0.06 * (t / max(total_duration, 0.1)))
        .set_position(("center", "center"))
    )

    layers = [bg_clip]

    # タイトル/カテゴリ帯(上部)
    title_img = _render_caption_image(title, font_size=56)
    title_clip = (
        ImageClip(title_img)
        .set_duration(total_duration)
        .set_position(("center", int(H * 0.08)))
    )
    layers.append(title_clip)

    for cap in captions:
        img = _render_caption_image(cap["text"])
        clip = (
            ImageClip(img)
            .set_start(lead_in + cap["start"])
            .set_duration(max(cap["duration"], 0.25))
            .set_position(("center", "center"))
        )
        layers.append(clip)

    video = CompositeVideoClip(layers, size=(W, H)).set_duration(total_duration)

    narration = AudioFileClip(str(audio_path)).set_start(lead_in)
    ambient_arr, afps = _make_ambient_audio(total_duration)
    ambient = AudioArrayClip(ambient_arr, fps=afps)
    final_audio = CompositeAudioClip([ambient, narration]).set_duration(total_duration)
    video = video.set_audio(final_audio)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="veryfast",
        threads=2,
        logger=None,
    )


if __name__ == "__main__":
    demo_captions = [
        {"text": "小さな一歩が、", "start": 0.0, "duration": 1.3},
        {"text": "大きな変化を", "start": 1.3, "duration": 1.2},
        {"text": "生む。", "start": 2.5, "duration": 0.6},
    ]
    build_video(
        quote="小さな一歩が、大きな変化を生む。",
        title="【努力】今日のひとこと",
        audio_path=Path("test_audio.mp3"),
        captions=demo_captions,
        audio_duration=3.1,
        out_path=Path("output/test.mp4"),
    )
