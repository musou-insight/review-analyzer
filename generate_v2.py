#!/usr/bin/env python3
"""FUTURE TRAIN v2 レポート生成スクリプト（ギャップ分析 + キーワード%表示）。"""

import json
import os
import sys
import shutil
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import analyze_reviews
from reporter import generate_report

RAW_JSON = "reviews_raw.json"
ANALYZED_JSON = "reviews_analyzed_v2.json"
OUTPUT_HTML = "report_v2.html"
STORE_NAME = "FUTURE TRAIN KYOTO DINER & CAFE"
PUBLIC_DIR = Path("public") / "FUTURE_TRAIN_v2"

if not os.path.exists(RAW_JSON):
    print(f"❌ {RAW_JSON} が見つかりません。")
    sys.exit(1)

print(f"📂 {RAW_JSON} を読み込み中...")
with open(RAW_JSON, encoding="utf-8") as f:
    reviews = json.load(f)
print(f"  {len(reviews)}件の口コミを読み込みました。")

print("\n🤖 v2 分析開始（ギャップ分析込み）...")
analysis = analyze_reviews(reviews, include_gap=True)

with open(ANALYZED_JSON, "w", encoding="utf-8") as f:
    json.dump(analysis, f, ensure_ascii=False, indent=2)
print(f"💾 分析結果: {ANALYZED_JSON}")

generate_report(STORE_NAME, analysis, output_path=OUTPUT_HTML)

# public/ ディレクトリにコピー
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
shutil.copy(OUTPUT_HTML, PUBLIC_DIR / "report.html")
print(f"✅ コピー完了: {PUBLIC_DIR / 'report.html'}")
