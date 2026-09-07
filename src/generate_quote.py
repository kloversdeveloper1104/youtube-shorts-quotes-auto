"""名言・モチベーション系Shortsのテキスト(引用文・タイトル・ハッシュタグ)を用意する。

優先順位:
  1. GEMINI_API_KEY があれば Gemini (無料枠) でオリジナルの名言を新規生成する。
  2. 失敗した/キーが無い場合は quotes_fallback.json からランダムに選ぶ。

直近使った名言は state/used_topics.json に記録し、なるべく重複を避ける。
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

SRC_DIR = Path(__file__).parent
FALLBACK_PATH = SRC_DIR / "quotes_fallback.json"
STATE_PATH = SRC_DIR / "state" / "used_topics.json"
HISTORY_LIMIT = 25  # 直近何件を「使用済み」として避けるか

CATEGORIES = ["努力", "挑戦", "継続", "自己肯定", "失敗と学び", "夢と目標", "感謝", "勇気と行動"]

HASHTAG_POOL = [
    "名言", "モチベーション", "自己啓発", "格言", "前向き", "頑張る", "努力",
    "成長", "メンタル", "shorts",
]


def _load_history() -> list[str]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_history(history: list[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    trimmed = history[-HISTORY_LIMIT:]
    STATE_PATH.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def _pick_hashtags(category: str) -> list[str]:
    tags = ["#" + category.replace("と", "")] if category else []
    extra = random.sample(HASHTAG_POOL, k=4)
    for t in extra:
        tag = "#" + t
        if tag not in tags:
            tags.append(tag)
    return tags[:5]


def _from_fallback(history: list[str]) -> dict:
    quotes = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    candidates = [q for q in quotes if q["text"] not in history] or quotes
    chosen = random.choice(candidates)
    return {
        "quote": chosen["text"],
        "title": f"【{chosen['category']}】今日のひとこと",
        "hashtags": _pick_hashtags(chosen["category"]),
        "category": chosen["category"],
        "source": "fallback",
    }


def _from_gemini(history: list[str]) -> dict | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
        category = random.choice(CATEGORIES)
        avoid = "\n".join(f"- {h}" for h in history[-15:]) or "(なし)"
        prompt = f"""あなたはYouTube Shorts向けの日本語モチベーション名言クリエイターです。
テーマ「{category}」で、以下の条件を満たすオリジナルの名言を1つ作ってください。

条件:
- 実在の人物の名言やその引用・意訳ではなく、完全にオリジナルの文章にすること
- 20〜40文字程度、1〜2文で、心に刺さる前向きな言葉にすること
- 説明的すぎず、短く余韻のある表現にすること
- 次の直近使用済みリストとは異なる内容にすること:
{avoid}

出力は次のJSON形式のみ。説明文やコードブロックは付けないこと:
{{"quote": "ここに名言", "title": "動画タイトル(20文字以内、絵文字1つ程度可)"}}
"""
        response = client.models.generate_content(model=model_name, contents=prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        quote = data["quote"].strip()
        title = data.get("title", "").strip() or f"【{category}】今日のひとこと"
        if not quote or quote in history:
            return None
        return {
            "quote": quote,
            "title": title,
            "hashtags": _pick_hashtags(category),
            "category": category,
            "source": "gemini",
        }
    except Exception as e:  # noqa: BLE001
        print(f"[generate_quote] Gemini生成に失敗、フォールバックへ切替: {e}")
        return None


def generate() -> dict:
    history = _load_history()
    result = _from_gemini(history)
    if result is None:
        result = _from_fallback(history)
    history.append(result["quote"])
    _save_history(history)
    print(f"[generate_quote] source={result['source']} category={result['category']}")
    print(f"[generate_quote] quote={result['quote']}")
    return result


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
