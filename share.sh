#!/bin/bash
# report.html を GitHub Pages に公開する

cd "$(dirname "$0")"

echo "📤 report.html をアップロード中..."

# トークン経由でプッシュ
GH_TOKEN=$(gh auth token 2>/dev/null)
if [[ -z "$GH_TOKEN" ]]; then
    echo "❌ gh auth token が取得できません。'gh auth login' を実行してください。"
    exit 1
fi

git add report.html
git commit -m "update: report.html $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || {
    echo "⚠️  変更がありません。スキップします。"
    exit 0
}

GIT_REMOTE=$(git remote get-url origin 2>/dev/null | sed 's|https://[^@]*@||')
git remote set-url origin "https://x-access-token:${GH_TOKEN}@${GIT_REMOTE}"
git push origin main

echo ""
echo "✅ 公開完了！"
echo "🔗 URL: https://musou-insight.github.io/review-analyzer/report.html"
echo ""
echo "   ※ GitHub Pages の反映には最大 2〜3 分かかります"
