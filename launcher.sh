#!/bin/bash
# 口コミ分析 ランチャースクリプト

cd /home/unamu349/review-analyzer
source venv/bin/activate

echo ""
echo "========================================"
echo "  🍽️  飲食店 口コミ分析ツール"
echo "========================================"
echo ""

# 既存データから再分析するか確認
read -p "既存データから再分析しますか？（スクレイピングをスキップ）[y/N]: " skip
if [[ "$skip" =~ ^[Yy]$ ]]; then
    read -p "店舗名を入力してください: " store_name
    python main.py --name "$store_name" --skip-scrape
    exit 0
fi

# 店舗名
read -p "店舗名を入力してください: " store_name

echo ""
echo "収集するサイトのURLを入力してください（不要な場合はそのままEnter）"
echo ""

read -p "Google マップ URL: " google_url
read -p "食べログ URL: " tabelog_url
read -p "TripAdvisor URL: " tripadvisor_url

# 引数を組み立て
args=(--name "$store_name")
[[ -n "$google_url" ]]    && args+=(--google-maps "$google_url")
[[ -n "$tabelog_url" ]]   && args+=(--tabelog "$tabelog_url")
[[ -n "$tripadvisor_url" ]] && args+=(--tripadvisor "$tripadvisor_url")

# いずれも未入力の場合
if [[ ${#args[@]} -eq 2 ]]; then
    echo ""
    echo "❌ URLが1つも入力されていません。終了します。"
    exit 1
fi

echo ""
echo "🚀 分析を開始します..."
echo ""
python main.py "${args[@]}"
