"""Gemini による口コミ分析モジュール。"""

import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

from google import genai
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
MODEL = "gemini-2.5-flash"

KANDO_TYPES = ["threshold", "surprise", "resonance", "rescue", "awe", "participation", "growth"]
KANDO_LABELS = {
    "threshold":    "①しきい値突破",
    "surprise":     "②意外性",
    "resonance":    "③共鳴・共感",
    "rescue":       "④救済",
    "awe":          "⑤崇高",
    "participation":"⑥参加",
    "growth":       "⑦成長",
}


def _generate(prompt: str) -> str:
    response = _client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


# ---------------------------------------------------------------------------
# メインエントリ
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Google マップが付加するメタデータ（食事の種類・料金・評点など）を本文から除去する。"""
    metadata_markers = [
        r'食事の種類',
        r'1\s*人あたりの料金',
        r'食事[:：]\s*\d',
        r'サービス[:：]\s*\d',
        r'雰囲気[:：]\s*\d',
        r'予約\n',
        r'グループの人数',
    ]
    pattern = '|'.join(f'(?:{m})' for m in metadata_markers)
    m = re.search(pattern, text)
    if m:
        text = text[:m.start()].strip()
    return text


def analyze_reviews(reviews: list[dict]) -> dict:
    # 保存済みデータ内のメタデータを除去（--skip-scrape 時も対応）
    reviews = [dict(r, text=_clean_text(r.get("text", ""))) for r in reviews]
    print(f"\n🤖 Gemini 分析開始（{len(reviews)}件）...")

    keywords = _extract_keywords(reviews)
    experience = _analyze_experience(reviews, keywords)
    timeseries_keywords = _analyze_timeseries_keywords(reviews, keywords)
    kando = _analyze_kando(reviews)

    return {
        "reviews": reviews,
        "keywords": keywords,
        "experience": experience,
        "timeseries_keywords": timeseries_keywords,
        "kando": kando,
    }


# ---------------------------------------------------------------------------
# キーワード抽出（Gemini バッチ）
# ---------------------------------------------------------------------------

BATCH_SIZE = 20

def _extract_keywords(reviews: list[dict]) -> list[dict]:
    """Gemini でキーワードを特定し、実テキスト検索で出現件数を集計する。"""
    print("  🔑 キーワード抽出中...")
    word_sentiments: dict[str, list[str]] = defaultdict(list)
    total_batches = (len(reviews) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(reviews), BATCH_SIZE):
        batch = reviews[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"    📦 バッチ {batch_num}/{total_batches}...")
        texts = "\n".join(f"[{j}] {r['text'][:200]}" for j, r in enumerate(batch))

        prompt = f"""以下の飲食店口コミから、顧客心理・顧客価値を表すキーワードを抽出してください。

【抽出する言葉】
- 顧客の感情・評価・体験価値を表す言葉（例：美味しい、感動、映え、最高、残念、また来たい、コスパ、非日常、待ちすぎ、雰囲気抜群）
- 形容詞・評価動詞・印象・満足度を表す表現を優先

【除外する言葉】
- 「料理」「食事」「スタッフ」「ドリンク」「席」「店内」「お店」「メニュー」「注文」「テーブル」「ランチ」「ディナー」「飲み物」「食べ物」「店員」「店舗」など、飲食店として当たり前の物・場所・人を表す一般名詞
- 助詞・接続詞・語尾

【統一ルール】
- 類似表現は代表的な表記に統一（例:「美味しい」「おいしい」→「美味しい」）
- 各キーワードのポジネガも判定

口コミ:
{texts}

出力形式（JSONのみ）:
[{{"word":"キーワード","sentiment":"positive|negative|neutral"}}]"""

        try:
            response_text = _generate(prompt)
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                for item in json.loads(json_match.group()):
                    w = item.get("word", "").strip()
                    s = item.get("sentiment", "neutral")
                    if w and len(w) >= 2:
                        word_sentiments[w].append(s)
            time.sleep(2)
        except Exception as e:
            print(f"    ⚠️ エラー（バッチ {batch_num}）: {e}")

    # 一般名詞除外リスト
    GENERIC_WORDS = {
        "料理", "食事", "スタッフ", "ドリンク", "席", "店内", "お店", "メニュー",
        "注文", "テーブル", "ランチ", "ディナー", "飲み物", "食べ物", "店員", "店舗",
        "お料理", "飲食", "朝食", "昼食", "夕食", "夜ご飯", "昼ご飯", "朝ご飯",
        "入口", "出口", "入り口", "トイレ", "駐車場", "予約", "会計", "レジ",
        "店", "方", "人", "時", "方々", "皆さん", "皆様", "こちら", "こと",
    }

    # ポジネガを多数決で決定し、実テキスト検索で出現件数を集計
    all_texts = [r.get("text", "") for r in reviews]
    ranked = []
    for word, sents in word_sentiments.items():
        if word in GENERIC_WORDS:
            continue
        pos, neg = sents.count("positive"), sents.count("negative")
        sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"
        count = sum(1 for t in all_texts if word in t)
        if count > 0:
            ranked.append({"word": word, "count": count, "sentiment": sentiment})

    ranked.sort(key=lambda x: -x["count"])
    return ranked[:50]


# ---------------------------------------------------------------------------
# 顧客体験価値分析
# ---------------------------------------------------------------------------

def _analyze_experience(reviews: list[dict], keywords: list[dict]) -> dict:
    print("  ✨ 顧客体験価値を分析中...")
    total = len(reviews)

    # ポジ・ネガキーワードを分離
    pos_kws = [k for k in keywords if k.get("sentiment") == "positive"]
    neg_kws = [k for k in keywords if k.get("sentiment") == "negative"]
    pos_summary = "、".join(f"{k['word']}({k['count']}件)" for k in pos_kws[:15])
    neg_summary = "、".join(f"{k['word']}({k['count']}件)" for k in neg_kws[:15])

    # 低評価・ネガティブ口コミを優先してサンプルに含める
    low_rated = [r for r in reviews if r.get("rating") is not None and float(r.get("rating", 5)) <= 3]
    high_rated = [r for r in reviews if r not in low_rated]
    # 低評価を最大15件 + 高評価から15件
    sample = low_rated[:15] + high_rated[:15]
    sample_text = "\n".join(f"[★{r.get('rating','?')}] {r['text'][:200]}" for r in sample)

    prompt = f"""以下の飲食店口コミデータを分析し、客観的なデータに基づいて記述してください。

【基本情報】総口コミ数:{total}件
【ポジティブキーワード Top15】{pos_summary}
【ネガティブキーワード Top15】{neg_summary}
【代表的な口コミ（低評価優先サンプル）】
{sample_text}

## 記述ルール（厳守）
- 主観的な評価語（「強い」「優れている」「課題」「人気」「支持されている」など）は使わない
- 必ず口コミ件数・キーワード出現件数・割合などの数値を根拠として示す
  - 良い例：「〇〇を評価する声が△件みられる」「□□というキーワードが△件の口コミに出現している」
  - 良い例：「〇〇を指摘する声が△件あり、改善することで顧客体験が向上する可能性がある」
  - 悪い例：「〇〇が高く評価されている」「〇〇が課題です」
- headline は「〇〇の声が多い飲食体験」など、データから言える事実ベースの表現にする
- summary は口コミ全体の傾向を件数・割合ベースで要約する（150文字程度）
- strengths は主要なポジティブ評価を2〜3件にまとめる（網羅的にしなくてよい）
- weaknesses は改善の余地がある点を網羅的に列挙する（件数が少なくても改善価値のある指摘は必ず含める）
  - 例：アクセス・わかりにくさ・待ち時間・価格・情報不足なども対象
- strengths の description は「〇〇というキーワードが△件出現」「〇〇を評価する口コミが△件」など件数を含める
- weaknesses の description は「〇〇を指摘する声が△件みられる」など件数を含める

以下の形式でJSONのみ出力（前置き不要）:
{{"headline":"20文字以内","summary":"150文字程度","strengths":[{{"title":"観点","description":"件数を含む客観的説明"}}],"weaknesses":[{{"title":"観点","description":"件数を含む客観的説明"}}]}}"""

    try:
        json_match = re.search(r"\{.*\}", _generate(prompt), re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"    ⚠️ 顧客体験価値分析エラー: {e}")
    return {"headline": "分析エラー", "summary": "", "strengths": [], "weaknesses": []}


# ---------------------------------------------------------------------------
# 時系列キーワード変化分析
# ---------------------------------------------------------------------------

def _is_recent(date_str: str) -> bool | None:
    """直近3ヶ月かどうか判定。None = 判定不能（どちらにも含めない）。"""
    if not date_str:
        return None
    # 「最終編集: X か月前」などのプレフィックスを除去
    s = re.sub(r'^最終編集[:：]\s*', '', date_str.strip())
    # 日・時間・分・週間前 → 直近3ヶ月以内
    if re.search(r'\d+\s*(日|時間|分|週間)前', s):
        return True
    # か月前 / ヶ月前 / ヵ月前
    m = re.search(r'(\d+)\s*[かヶヵ]月前', s)
    if m:
        return int(m.group(1)) <= 3
    # 年前 → それ以前
    if re.search(r'\d+\s*年前', s):
        return False
    # 絶対日付
    ym = _extract_year_month(s)
    if ym:
        try:
            d = datetime.strptime(ym, "%Y-%m")
            cutoff = datetime(2025, 11, 24)
            return d >= cutoff
        except Exception:
            pass
    return None


def _analyze_timeseries_keywords(reviews: list[dict], all_keywords: list[dict]) -> dict:
    """直近3ヶ月 vs それ以前のキーワード出現率を比較。"""
    print("  📅 時系列キーワード変化を分析中...")
    recent = [r for r in reviews if _is_recent(r.get("date", "")) is True]
    older  = [r for r in reviews if _is_recent(r.get("date", "")) is False]

    def count_rate(word: str, review_list: list) -> tuple[int, float]:
        c = sum(1 for r in review_list if word in r.get("text", ""))
        rate = round(c / len(review_list) * 100, 1) if review_list else 0.0
        return c, rate

    changes = []
    for kw in all_keywords[:30]:
        word = kw["word"]
        rc, rr = count_rate(word, recent)
        oc, or_ = count_rate(word, older)
        diff = round(rr - or_, 1)
        changes.append({
            "word": word,
            "sentiment": kw.get("sentiment", "neutral"),
            "recent_count": rc,
            "recent_rate": rr,
            "older_count": oc,
            "older_rate": or_,
            "change": diff,
        })

    changes.sort(key=lambda x: abs(x["change"]), reverse=True)
    return {
        "recent_count": len(recent),
        "older_count": len(older),
        "keywords": changes,
    }


# ---------------------------------------------------------------------------
# 感動の7類型分析
# ---------------------------------------------------------------------------

KANDO_BATCH = 15

def _analyze_kando(reviews: list[dict]) -> dict:
    """感動の7類型でスコアリングし、レーダーチャートデータを生成。"""
    print("  🎭 感動の7類型を分析中...")

    all_scores: dict[str, list[int]] = {t: [] for t in KANDO_TYPES}
    detection: dict[str, int] = {t: 0 for t in KANDO_TYPES}
    total_batches = (len(reviews) + KANDO_BATCH - 1) // KANDO_BATCH

    for i in range(0, len(reviews), KANDO_BATCH):
        batch = reviews[i: i + KANDO_BATCH]
        batch_num = i // KANDO_BATCH + 1
        print(f"    📦 感動分析バッチ {batch_num}/{total_batches}...")

        rows = "\n".join(f"[{j}] {r['text'][:200]}" for j, r in enumerate(batch))
        prompt = f"""以下の飲食店口コミを「感動の7類型」で評価し、JSON配列のみを出力してください。

## 7類型（各0〜5点）
① threshold（しきい値突破）: 期待を超える圧倒的体験・最上級表現
② surprise（意外性）: 予期しなかった嬉しい体験・サプライズ
③ resonance（共鳴・共感）: 記憶・人生・物語との共鳴・懐かしさ
④ rescue（救済）: 困った時の助け・スタッフの気遣い・対応
⑤ awe（崇高）: 非日常・世界観・異空間への圧倒・畏敬
⑥ participation（参加）: 体験への参加・一体感・主体的関与
⑦ growth（成長）: リピート・時間変化・成長・季節変化

スコア基準: 0=言及なし / 1=曖昧 / 2=明確だが弱い / 3=明確+感情 / 4=強い感情+具体例 / 5=圧倒的

口コミ:
{rows}

出力（JSON配列のみ、idは0始まり）:
[{{"id":0,"threshold":0,"surprise":0,"resonance":0,"rescue":0,"awe":0,"participation":0,"growth":0}}]"""

        try:
            json_match = re.search(r'\[.*\]', _generate(prompt), re.DOTALL)
            if json_match:
                for item in json.loads(json_match.group()):
                    idx = item.get("id", 0)
                    if 0 <= idx < len(batch):
                        for t in KANDO_TYPES:
                            score = int(item.get(t, 0))
                            all_scores[t].append(score)
                            if score > 0:
                                detection[t] += 1
            time.sleep(2)
        except Exception as e:
            print(f"    ⚠️ エラー（バッチ {batch_num}）: {e}")
            for _ in batch:
                for t in KANDO_TYPES:
                    all_scores[t].append(0)

    total = len(reviews)
    aggregated = {}
    for t in KANDO_TYPES:
        scores = all_scores[t]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        aggregated[t] = {
            "label": KANDO_LABELS[t],
            "score": avg,
            "detection_rate": round(detection[t] / total * 100, 1) if total else 0.0,
            "review_count": detection[t],
            "is_reliable": detection[t] >= 3,
        }

    sorted_types = sorted(KANDO_TYPES, key=lambda t: aggregated[t]["score"], reverse=True)
    strengths  = sorted_types[:2]
    weaknesses = sorted_types[-2:]

    # AI コンサルコメント生成
    radar_summary = "\n".join(
        f"- {aggregated[t]['label']}: {aggregated[t]['score']:.1f}/5 (検出率{aggregated[t]['detection_rate']}%)"
        for t in KANDO_TYPES
    )
    top_reviews_text = "\n".join(f"「{r['text'][:100]}」" for r in reviews[:10] if r.get("text"))

    comment_prompt = f"""以下の口コミ分析データをもとに、感動の7類型ごとの分析結果を客観的に記述してください。

## 分析データ
{radar_summary}

## 代表的な口コミ
{top_reviews_text}

## 記述ルール
1. 主観的な評価語（「強い」「優れている」「課題です」など）は使わない
2. データを根拠にした客観的な表現のみ使う
   - 良い例: 「〇〇のスコアが最も高く、〇〇を評価する声が複数みられる」
   - 良い例: 「〇〇を指摘する声が複数あり、改善することで顧客体験が向上する可能性がある」
   - 悪い例: 「〇〇が強く支持されている」「〇〇が課題です」
3. スコアと検出率の数値を積極的に引用する
4. 口コミの具体的な表現を引用して根拠を示す
5. 全体で300〜500文字

分析結果テキストのみ出力（前置き不要）:"""

    try:
        ai_comment = _generate(comment_prompt)
    except Exception as e:
        ai_comment = f"コメント生成エラー: {e}"

    return {
        "aggregated": aggregated,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "ai_comment": ai_comment,
        "total_analyzed": total,
    }


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _extract_year_month(date_str: str) -> str | None:
    if not date_str:
        return None
    patterns = [
        (r"(\d{4})[/-](\d{1,2})", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}"),
        (r"(\d{4})年\s*(\d{1,2})月", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}"),
        (
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})",
            lambda m: f"{m.group(2)}-{_month_to_num(m.group(1)):02d}",
        ),
    ]
    for pattern, formatter in patterns:
        m = re.search(pattern, date_str, re.IGNORECASE)
        if m:
            try:
                return formatter(m)
            except Exception:
                continue
    return None


def _month_to_num(abbr: str) -> int:
    return {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
            "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}.get(abbr.lower()[:3], 1)
