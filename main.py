#!/usr/bin/env python3
"""飲食店口コミ収集・分析ツール エントリポイント。"""

import argparse
import asyncio
import json
import os
import sys

import nest_asyncio

nest_asyncio.apply()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="飲食店口コミ収集・分析ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""使用例:
  python main.py --name "テスト食堂" --tripadvisor "https://www.tripadvisor.jp/..."
  python main.py --name "テスト食堂" --google-maps "https://www.google.com/maps/..." --tabelog "https://tabelog.com/..."
  python main.py --name "テスト食堂" --skip-scrape   # 既存JSONから分析のみ再実行
""",
    )
    parser.add_argument("--name", default="店舗", help="店舗名（レポートのタイトルに使用）")
    parser.add_argument("--google-maps", dest="google_maps", metavar="URL", help="Google マップ URL")
    parser.add_argument("--tabelog", metavar="URL", help="食べログ URL")
    parser.add_argument("--tripadvisor", metavar="URL", help="TripAdvisor URL")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="スクレイピングをスキップし、既存の reviews_raw.json から分析のみ実行",
    )
    parser.add_argument("--output", default="report.html", help="出力 HTML ファイル名（デフォルト: report.html）")
    return parser.parse_args()


async def run_scrapers(args: argparse.Namespace) -> list[dict]:
    """指定された URL からスクレイピングを実行し、全口コミを返す。"""
    from scrapers import scrape_google_maps, scrape_tabelog, scrape_tripadvisor

    all_reviews: list[dict] = []

    if args.google_maps:
        try:
            reviews = await scrape_google_maps(args.google_maps)
            all_reviews.extend(reviews)
        except Exception as e:
            print(f"⚠️ Google マップ スクレイピングエラー: {e}")

    if args.tabelog:
        try:
            reviews = await scrape_tabelog(args.tabelog)
            all_reviews.extend(reviews)
        except Exception as e:
            print(f"⚠️ 食べログ スクレイピングエラー: {e}")

    if args.tripadvisor:
        try:
            reviews = await scrape_tripadvisor(args.tripadvisor)
            all_reviews.extend(reviews)
        except Exception as e:
            print(f"⚠️ TripAdvisor スクレイピングエラー: {e}")

    return all_reviews


def main() -> None:
    args = parse_args()

    # URL もスキップフラグも指定なし
    if not args.skip_scrape and not any([args.google_maps, args.tabelog, args.tripadvisor]):
        print("❌ エラー: --google-maps / --tabelog / --tripadvisor のいずれかを指定してください。")
        print("   既存 JSON から再分析する場合は --skip-scrape を指定してください。")
        sys.exit(1)

    raw_json_path = "reviews_raw.json"
    analyzed_json_path = "reviews_analyzed.json"

    # ---- スクレイピング ----
    if args.skip_scrape:
        if not os.path.exists(raw_json_path):
            print(f"❌ エラー: {raw_json_path} が見つかりません。先にスクレイピングを実行してください。")
            sys.exit(1)
        print(f"⏭️  スクレイピングをスキップ。{raw_json_path} を読み込みます...")
        with open(raw_json_path, encoding="utf-8") as f:
            all_reviews = json.load(f)
        print(f"  📂 {len(all_reviews)}件の口コミを読み込みました。")
    else:
        print(f"\n🚀 口コミ収集を開始します（店舗名: {args.name}）\n")
        all_reviews = asyncio.run(run_scrapers(args))

        if not all_reviews:
            print("⚠️ 口コミが1件も取得できませんでした。URL を確認してください。")
            sys.exit(1)

        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump(all_reviews, f, ensure_ascii=False, indent=2)
        print(f"\n💾 {len(all_reviews)}件の口コミを {raw_json_path} に保存しました。")

    # ---- Gemini 分析 ----
    from analyzer import analyze_reviews

    analysis = analyze_reviews(all_reviews)

    with open(analyzed_json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"💾 分析結果を {analyzed_json_path} に保存しました。")

    # ---- HTML レポート生成 ----
    from reporter import generate_report

    generate_report(args.name, analysis, output_path=args.output)


if __name__ == "__main__":
    main()
