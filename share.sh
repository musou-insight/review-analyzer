#!/bin/bash
# 複数店舗レポートを Netlify に公開し、全店舗インデックスを自動生成する

SITE_ID="6546d685-7d7a-41cd-8450-3111ebeeb57f"
BASE_URL="https://stellar-cat-a3a906.netlify.app"

cd "$(dirname "$0")"

# ── 1. 店舗名を取得 ──────────────────────────────────────────────────────────
if [ -n "$1" ]; then
  STORE_DISPLAY="$1"
else
  echo ""
  echo "📝 店舗名を入力してください（例: 銀座 寿司田）:"
  read -r STORE_DISPLAY
fi

if [ -z "$STORE_DISPLAY" ]; then
  echo "❌ 店舗名が未入力です。終了します。"
  exit 1
fi

# スペースを _ に置換してディレクトリ名を生成
STORE_PATH="${STORE_DISPLAY// /_}"

# ── 2. public/<店舗名>/ に report.html をコピー ──────────────────────────────
mkdir -p "public/${STORE_PATH}"
cp report.html "public/${STORE_PATH}/report.html"
echo "📁 public/${STORE_PATH}/report.html を作成しました"

# ── 3. stores.json を更新 ────────────────────────────────────────────────────
STORES_JSON="public/stores.json"
DEPLOY_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# stores.json が存在しない場合は空配列で初期化
if [ ! -f "$STORES_JSON" ]; then
  echo "[]" > "$STORES_JSON"
fi

# Python で JSON を安全に更新（同名店舗は上書き、新規は追加、新しい順に並べ替え）
python3 - <<PYEOF
import json, sys

stores_file = "${STORES_JSON}"
with open(stores_file) as f:
    stores = json.load(f)

# 既存エントリを更新 or 新規追加
entry = {
    "display": "${STORE_DISPLAY}",
    "path": "${STORE_PATH}",
    "updatedAt": "${DEPLOY_TIME}"
}

updated = False
for i, s in enumerate(stores):
    if s["path"] == "${STORE_PATH}":
        stores[i] = entry
        updated = True
        break

if not updated:
    stores.append(entry)

# 新しい順にソート
stores.sort(key=lambda s: s["updatedAt"], reverse=True)

with open(stores_file, "w", encoding="utf-8") as f:
    json.dump(stores, f, ensure_ascii=False, indent=2)

print(f"✅ stores.json を更新しました（{'上書き' if updated else '新規追加'}）")
PYEOF

# ── 4. index.html を stores.json から自動生成 ─────────────────────────────────
python3 - <<PYEOF
import json
from datetime import datetime, timezone

with open("${STORES_JSON}", encoding="utf-8") as f:
    stores = json.load(f)

def fmt_time(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        jst = dt.astimezone(timezone.utc)  # UTC のまま表示（JST +9h）
        import zoneinfo
        jst = dt.astimezone(zoneinfo.ZoneInfo("Asia/Tokyo"))
        return jst.strftime("%Y年%m月%d日 %H:%M")
    except Exception:
        return iso

cards_html = ""
for s in stores:
    url = f"/{s['path']}/report.html"
    updated = fmt_time(s["updatedAt"])
    cards_html += f"""
    <div class="card">
      <div class="card-name">{s['display']}</div>
      <div class="card-time">更新: {updated}</div>
      <a class="card-link" href="{url}" target="_blank">レポートを開く →</a>
    </div>"""

if not cards_html:
    cards_html = '<p class="empty">まだ店舗がありません。</p>'

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>店舗レビュー分析 一覧</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic UI", sans-serif;
      background: #f0f2f5;
      color: #1a1a2e;
      min-height: 100vh;
      padding: 2rem 1rem;
    }}
    header {{
      text-align: center;
      margin-bottom: 2.5rem;
    }}
    header h1 {{
      font-size: 1.8rem;
      font-weight: 700;
      color: #2d3561;
    }}
    header p {{
      margin-top: 0.4rem;
      color: #666;
      font-size: 0.9rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.25rem;
      max-width: 960px;
      margin: 0 auto;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      padding: 1.4rem 1.6rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
      transition: box-shadow 0.2s;
    }}
    .card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.14); }}
    .card-name {{
      font-size: 1.1rem;
      font-weight: 600;
      color: #2d3561;
    }}
    .card-time {{
      font-size: 0.8rem;
      color: #888;
    }}
    .card-link {{
      display: inline-block;
      margin-top: 0.4rem;
      padding: 0.45rem 1rem;
      background: #4f46e5;
      color: #fff;
      border-radius: 8px;
      text-decoration: none;
      font-size: 0.88rem;
      font-weight: 500;
      align-self: flex-start;
      transition: background 0.2s;
    }}
    .card-link:hover {{ background: #4338ca; }}
    .empty {{ text-align: center; color: #999; padding: 2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>🏪 店舗レビュー分析 一覧</h1>
    <p>各店舗のAI分析レポートをまとめています</p>
  </header>
  <div class="grid">{cards_html}
  </div>
</body>
</html>"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ index.html を生成しました（{len(stores)} 店舗）")
PYEOF

# ── 5. public/ 全体を Netlify へデプロイ ─────────────────────────────────────
echo ""
echo "📤 Netlify へデプロイ中..."
netlify deploy --site "$SITE_ID" --dir "public" --prod --no-build 2>&1 | grep -E "✔|🚀|Error|Deploy"

# ── 6. URL を表示 ─────────────────────────────────────────────────────────────
echo ""
echo "✅ デプロイ完了！"
echo ""
echo "🔗 今回のレポート : ${BASE_URL}/${STORE_PATH}/report.html"
echo "📋 全店舗一覧     : ${BASE_URL}/"
echo ""
echo "   ※ URLに個人情報は含まれていません。第三者にそのまま渡せます。"
