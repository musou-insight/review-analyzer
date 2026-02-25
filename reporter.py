"""HTML レポート生成モジュール。"""

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime


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


def generate_report(store_name: str, analysis: dict, output_path: str = "report.html") -> str:
    reviews              = analysis.get("reviews", [])
    keywords             = analysis.get("keywords", [])
    experience           = analysis.get("experience", {})
    timeseries_keywords  = analysis.get("timeseries_keywords", {})
    kando                = analysis.get("kando", {})

    site_stats = _calc_site_stats(reviews)
    html = _build_html(store_name, reviews, keywords, experience, timeseries_keywords, kando, site_stats)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    abs_path = os.path.abspath(output_path)
    print(f"\n✅ レポート生成完了: {abs_path}")
    try:
        subprocess.run(["garcon-url-handler", f"file://{abs_path}"])
    except Exception:
        try:
            subprocess.Popen(["xdg-open", abs_path])
        except Exception:
            print("  ブラウザの自動起動に失敗しました。上記パスを開いてください。")
    return abs_path


def _calc_site_stats(reviews):
    stats = defaultdict(lambda: {"count": 0})
    for r in reviews:
        stats[r.get("source", "unknown")]["count"] += 1
    return dict(stats)


def _site_label(src):
    return {"google_maps": "Google マップ", "tabelog": "食べログ", "tripadvisor": "TripAdvisor"}.get(src, src)


def _site_color(src):
    return {"google_maps": "#4285F4", "tabelog": "#e23b2a", "tripadvisor": "#34e0a1"}.get(src, "#888")


# ---------------------------------------------------------------------------
# HTML 全体構築
# ---------------------------------------------------------------------------

def _build_html(store_name, reviews, keywords, experience, timeseries_keywords, kando, site_stats):
    today = datetime.now().strftime("%Y年%m月%d日")
    total = len(reviews)
    recent_n = timeseries_keywords.get("recent_count", 0)
    older_n  = timeseries_keywords.get("older_count", 0)

    site_cards_html      = _build_site_cards(site_stats)
    experience_html      = _build_experience_section(experience)
    keyword_table_html   = _build_keyword_table(keywords)
    timeseries_html      = _build_timeseries_section(timeseries_keywords)
    kando_html           = _build_kando_section(kando)
    reviews_json         = json.dumps(reviews, ensure_ascii=False)
    kando_radar_json     = _build_kando_radar_json(kando)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{store_name} 口コミ分析レポート</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --primary: #1a73e8;
      --bg: #f0f4f9;
      --card: #ffffff;
      --border: #e0e0e0;
      --text: #2c2c2c;
      --muted: #666;
      --pos: #0d6e3b; --pos-bg: #d1fae5;
      --neg: #991b1b; --neg-bg: #fee2e2;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Segoe UI", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .container {{ max-width: 1080px; margin: 0 auto; padding: 28px 16px; }}
    .section {{ background: var(--card); border-radius: 14px; padding: 28px; margin-bottom: 24px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }}
    h1 {{ font-size: 1.9em; font-weight: 700; }}
    h2 {{ font-size: 1.25em; font-weight: 700; padding-bottom: 10px; border-bottom: 2px solid var(--primary); margin-bottom: 18px; color: var(--primary); }}
    h3 {{ font-size: 1.05em; font-weight: 600; margin-bottom: 6px; }}
    .meta {{ color: var(--muted); font-size: 0.88em; margin-top: 4px; margin-bottom: 20px; }}

    /* サイトカード */
    .site-cards {{ display: flex; gap: 14px; flex-wrap: wrap; }}
    .site-card {{ flex:1; min-width:140px; border-radius:10px; padding:14px 18px; color:white; }}
    .site-card .s-label {{ font-size:0.82em; opacity:0.9; }}
    .site-card .s-count {{ font-size:2.1em; font-weight:700; line-height:1.2; }}

    /* 体験価値 */
    .headline {{ font-size:1.3em; font-weight:700; color:var(--primary); margin:10px 0 6px; }}
    .summary-text {{ font-size:0.97em; margin-bottom:16px; }}
    .value-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px; }}
    @media(max-width:600px){{.value-grid{{grid-template-columns:1fr;}}}}
    .value-box {{ border-radius:10px; padding:14px 16px; }}
    .value-box.positive {{ background:var(--pos-bg); border-left:4px solid var(--pos); }}
    .value-box.negative {{ background:var(--neg-bg); border-left:4px solid var(--neg); }}
    .value-box.positive h3 {{ color:var(--pos); }}
    .value-box.negative h3 {{ color:var(--neg); }}
    .value-desc {{ font-size:0.9em; margin-top:4px; }}
    .target-box {{ background:#eff6ff; border-radius:10px; padding:14px 18px; margin-top:10px; }}
    .target-box p {{ font-size:0.92em; margin-top:4px; }}

    /* キーワードテーブル共通 */
    .kw-legend {{ display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap; }}
    .legend-item {{ display:flex; align-items:center; gap:5px; font-size:0.85em; color:var(--muted); }}
    .legend-dot {{ display:inline-block; width:12px; height:12px; border-radius:50%; }}
    .kw-table {{ width:100%; border-collapse:collapse; font-size:0.92em; }}
    .kw-table thead th {{ text-align:left; padding:8px 10px; background:#f8faff; border-bottom:2px solid var(--border); font-size:0.85em; color:var(--muted); }}
    .kw-table tbody tr:hover {{ background:#f8faff; }}
    .kw-table td {{ padding:7px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }}
    .kw-rank {{ width:36px; color:var(--muted); font-size:0.85em; text-align:center; }}
    .kw-word {{ font-weight:600; min-width:90px; }}
    .kw-badge {{ width:55px; }}
    .kw-bar-cell {{ width:100%; }}
    .kw-bar-wrap {{ background:#f1f5f9; border-radius:4px; height:14px; width:100%; }}
    .kw-bar {{ height:14px; border-radius:4px; }}
    .kw-count {{ width:55px; text-align:right; color:var(--muted); font-size:0.88em; white-space:nowrap; }}

    /* 時系列キーワード */
    .ts-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
    @media(max-width:700px){{.ts-grid{{grid-template-columns:1fr;}}}}
    .ts-panel h3 {{ font-size:1em; margin-bottom:10px; padding:6px 10px; border-radius:6px; }}
    .ts-panel.recent h3 {{ background:#dbeafe; color:#1d4ed8; }}
    .ts-panel.older  h3 {{ background:#f3f4f6; color:#374151; }}
    .change-up   {{ color:#059669; font-weight:700; }}
    .change-down {{ color:#dc2626; font-weight:700; }}
    .change-zero {{ color:var(--muted); }}
    .ts-change-table {{ width:100%; border-collapse:collapse; font-size:0.88em; margin-top:16px; }}
    .ts-change-table th {{ background:#f8faff; padding:7px 10px; border-bottom:2px solid var(--border); text-align:left; color:var(--muted); font-size:0.83em; }}
    .ts-change-table td {{ padding:6px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }}
    .ts-count-cell {{ text-align:center; font-size:0.88em; }}

    /* 感動の7類型注釈 */
    .kando-note {{ background:#f0f7ff; border-radius:10px; padding:16px 18px; margin-top:16px; border:1px solid #c7dcf7; }}
    .kando-note-intro {{ font-size:0.92em; line-height:1.75; margin-bottom:10px; }}
    details.kando-expand summary {{ cursor:pointer; list-style:none; display:inline-flex; align-items:center; gap:6px; font-size:0.88em; color:var(--primary); font-weight:600; padding:4px 0; user-select:none; }}
    details.kando-expand summary::-webkit-details-marker {{ display:none; }}
    details.kando-expand summary .expand-icon {{ font-size:0.8em; transition:transform 0.2s; display:inline-block; }}
    details.kando-expand[open] summary .expand-icon {{ transform:rotate(90deg); }}
    .kando-types {{ margin-top:14px; display:grid; gap:10px; }}
    .kando-type-item {{ background:white; border-radius:8px; padding:12px 14px; border-left:3px solid var(--primary); }}
    .kando-type-item h4 {{ font-size:0.9em; font-weight:700; color:var(--primary); margin-bottom:5px; }}
    .kando-type-item p {{ font-size:0.87em; line-height:1.75; color:var(--text); }}
    .kando-citation {{ margin-top:14px; font-size:0.8em; color:var(--muted); line-height:1.7; border-top:1px solid var(--border); padding-top:10px; }}
    .kando-citation a {{ color:var(--primary); text-decoration:none; word-break:break-all; }}

    /* 感動レーダー */
    .kando-layout {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; align-items:start; }}
    @media(max-width:700px){{.kando-layout{{grid-template-columns:1fr;}}}}
    .kando-chart-wrap {{ position:relative; height:360px; }}
    .kando-detail {{ display:grid; gap:8px; }}
    .kando-row {{ display:flex; align-items:center; gap:8px; padding:6px 10px; border-radius:8px; background:#f8faff; }}
    .kando-row.strength {{ background:#dbeafe; }}
    .kando-row.weakness {{ background:#fee2e2; }}
    .kando-label {{ font-size:0.88em; font-weight:600; min-width:110px; }}
    .kando-bar-wrap {{ flex:1; background:#e5e7eb; border-radius:4px; height:10px; }}
    .kando-bar {{ height:10px; border-radius:4px; background:var(--primary); }}
    .kando-score {{ font-size:0.85em; color:var(--muted); width:32px; text-align:right; }}
    .kando-rate {{ font-size:0.78em; color:var(--muted); width:55px; text-align:right; }}
    .kando-dot {{ font-size:0.7em; color:var(--muted); }}
    .ai-comment {{ background:#f8faff; border-left:4px solid var(--primary); border-radius:8px; padding:16px 18px; margin-top:16px; font-size:0.93em; line-height:1.75; white-space:pre-wrap; }}

    /* 口コミ一覧 */
    .filter-bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; align-items:center; }}
    .filter-bar select {{ padding:6px 10px; border:1px solid var(--border); border-radius:6px; font-size:0.88em; }}
    .filter-label {{ font-size:0.82em; color:var(--muted); }}
    #review-count {{ font-size:0.88em; color:var(--muted); margin-bottom:10px; }}
    #review-list {{ display:grid; gap:10px; }}
    .rc {{ border:1px solid var(--border); border-radius:8px; padding:12px 14px; }}
    .rc-meta {{ font-size:0.78em; color:var(--muted); margin-bottom:6px; }}
    .rc-text {{ font-size:0.91em; line-height:1.65; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.75em; background:#e8f0fe; color:var(--primary); margin-bottom:4px; }}
  </style>
</head>
<body>
<div class="container">

  <!-- ヘッダー -->
  <div class="section">
    <h1>📊 {store_name}</h1>
    <p class="meta">口コミ分析レポート ／ 収集日: {today} ／ 総口コミ数: {total}件（直近3ヶ月: {recent_n}件 ／ それ以前: {older_n}件）</p>
    <div class="site-cards">{site_cards_html}</div>
  </div>

  <!-- 顧客体験価値 -->
  <div class="section">
    <h2>顧客体験価値分析</h2>
    {experience_html}
  </div>

  <!-- 感動の7類型レーダー -->
  <div class="section">
    <h2>感動の7類型分析</h2>
    {kando_html}
  </div>

  <!-- キーワードランキング -->
  <div class="section">
    <h2>キーワード頻度ランキング（Top 30）</h2>
    {keyword_table_html}
  </div>

  <!-- 時系列キーワード変化 -->
  <div class="section">
    <h2>時系列キーワード変化（直近3ヶ月 vs それ以前）</h2>
    {timeseries_html}
  </div>

  <!-- 口コミ一覧 -->
  <div class="section">
    <h2>口コミ一覧</h2>
    <div class="filter-bar">
      <span class="filter-label">絞り込み:</span>
      <select id="f-source" onchange="filterReviews()">
        <option value="">すべてのサイト</option>
        <option value="google_maps">Google マップ</option>
        <option value="tabelog">食べログ</option>
        <option value="tripadvisor">TripAdvisor</option>
      </select>
    </div>
    <div id="review-count"></div>
    <div id="review-list"></div>
  </div>

</div>
<script>
const REVIEWS = {reviews_json};
const KANDO_DATA = {kando_radar_json};
const SITE_LABELS = {{google_maps:"Google マップ",tabelog:"食べログ",tripadvisor:"TripAdvisor"}};

// 感動レーダーチャート
(function(){{
  const el = document.getElementById('kandoChart');
  if(!el || !KANDO_DATA.labels) return;
  new Chart(el, {{
    type: 'radar',
    data: {{
      labels: KANDO_DATA.labels,
      datasets: [{{
        label: '感動スコア',
        data: KANDO_DATA.scores,
        backgroundColor: 'rgba(26,115,232,0.15)',
        borderColor: '#1a73e8',
        borderWidth: 2,
        pointBackgroundColor: '#1a73e8',
        pointRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        r: {{
          min: 0, max: 5,
          ticks: {{ stepSize: 1, font: {{ size: 11 }} }},
          pointLabels: {{ font: {{ size: 12 }}, color: '#2c2c2c' }},
        }}
      }}
    }}
  }});
}})();

// 口コミ一覧
function filterReviews(){{
  const fSource = document.getElementById('f-source').value;
  const filtered = REVIEWS.filter(r => !fSource || r.source === fSource);
  document.getElementById('review-count').textContent = filtered.length + '件表示';
  document.getElementById('review-list').innerHTML = filtered.slice(0,300).map(r => `
    <div class="rc">
      <div class="rc-meta">
        <span class="badge">${{SITE_LABELS[r.source]||r.source}}</span>
        ${{r.reviewer_name||'匿名'}}${{r.date?' · '+r.date:''}}
      </div>
      <div class="rc-text">${{(r.text||'').slice(0,500)}}${{r.text&&r.text.length>500?'…':''}}</div>
    </div>
  `).join('');
}}
filterReviews();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 各セクション HTML ビルダー
# ---------------------------------------------------------------------------

def _build_experience_section(exp: dict) -> str:
    if not exp:
        return "<p>分析データなし</p>"
    headline   = exp.get("headline", "")
    summary    = exp.get("summary", "")
    strengths  = exp.get("strengths", [])
    weaknesses = exp.get("weaknesses", [])

    s_html = "".join(f'<div class="value-box positive"><h3>✅ {s.get("title","")}</h3><p class="value-desc">{s.get("description","")}</p></div>' for s in strengths)
    w_html = "".join(f'<div class="value-box negative"><h3>⚠️ {w.get("title","")}</h3><p class="value-desc">{w.get("description","")}</p></div>' for w in weaknesses)

    return f"""
    <p class="headline">「{headline}」</p>
    <p class="summary-text">{summary}</p>
    <div class="value-grid">{s_html}{w_html}</div>"""


def _build_keyword_table(keywords: list[dict]) -> str:
    if not keywords:
        return "<p>キーワードデータなし</p>"
    max_count = keywords[0]["count"] if keywords else 1
    rows = []
    for i, kw in enumerate(keywords[:30], 1):
        word = kw["word"]
        count = kw["count"]
        sentiment = kw.get("sentiment", "neutral")
        pct = round(count / max_count * 100)
        if sentiment == "positive":
            bar_color, badge_style, label = "#34d399", "background:#d1fae5;color:#065f46;", "ポジ"
        elif sentiment == "negative":
            bar_color, badge_style, label = "#f87171", "background:#fee2e2;color:#991b1b;", "ネガ"
        else:
            bar_color, badge_style, label = "#94a3b8", "background:#f1f5f9;color:#475569;", "中立"
        rows.append(f"""
  <tr>
    <td class="kw-rank">{i}</td>
    <td class="kw-word">{word}</td>
    <td class="kw-badge"><span style="{badge_style}padding:2px 7px;border-radius:10px;font-size:0.78em;">{label}</span></td>
    <td class="kw-bar-cell"><div class="kw-bar-wrap"><div class="kw-bar" style="width:{pct}%;background:{bar_color};"></div></div></td>
    <td class="kw-count">{count}回</td>
  </tr>""")
    return f"""
<div class="kw-legend">
  <span class="legend-item"><span class="legend-dot" style="background:#34d399;"></span>ポジティブ</span>
  <span class="legend-item"><span class="legend-dot" style="background:#f87171;"></span>ネガティブ</span>
  <span class="legend-item"><span class="legend-dot" style="background:#94a3b8;"></span>中立</span>
</div>
<table class="kw-table">
  <thead><tr><th>#</th><th>キーワード</th><th>種別</th><th>頻度</th><th>回数</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""


def _build_timeseries_section(ts: dict) -> str:
    if not ts:
        return "<p>データなし</p>"
    recent_n = ts.get("recent_count", 0)
    older_n  = ts.get("older_count", 0)
    kws = ts.get("keywords", [])

    # 直近3ヶ月 上位キーワード
    recent_top = sorted(kws, key=lambda x: -x["recent_rate"])[:15]
    older_top  = sorted(kws, key=lambda x: -x["older_rate"])[:15]

    def kw_rows(items, rate_key, count_key, max_rate):
        rows = []
        for kw in items:
            word = kw["word"]
            rate = kw[rate_key]
            count = kw[count_key]
            s = kw.get("sentiment", "neutral")
            bar_color = "#34d399" if s == "positive" else "#f87171" if s == "negative" else "#94a3b8"
            pct = round(rate / max_rate * 100) if max_rate else 0
            rows.append(f"""
      <tr>
        <td class="kw-word">{word}</td>
        <td class="kw-bar-cell"><div class="kw-bar-wrap"><div class="kw-bar" style="width:{pct}%;background:{bar_color};"></div></div></td>
        <td class="kw-count">{count}件 ({rate}%)</td>
      </tr>""")
        return "".join(rows)

    recent_max = max((k["recent_rate"] for k in recent_top), default=1) or 1
    older_max  = max((k["older_rate"] for k in older_top), default=1) or 1

    # 変化ランキング（上位・下位5件）
    increased = sorted(kws, key=lambda x: -x["change"])[:5]
    decreased = sorted(kws, key=lambda x: x["change"])[:5]

    def change_rows(items, direction):
        rows = []
        for kw in items:
            arrow = "▲" if direction == "up" else "▼"
            cls   = "change-up" if direction == "up" else "change-down"
            rows.append(f"""
      <tr>
        <td class="kw-word">{kw['word']}</td>
        <td class="ts-count-cell">{kw['older_rate']}%</td>
        <td class="ts-count-cell">{kw['recent_rate']}%</td>
        <td class="ts-count-cell"><span class="{cls}">{arrow} {abs(kw['change'])}pt</span></td>
      </tr>""")
        return "".join(rows)

    return f"""
<p style="color:var(--muted);font-size:0.88em;margin-bottom:16px;">
  直近3ヶ月: <strong>{recent_n}件</strong> ／ それ以前: <strong>{older_n}件</strong>
</p>
<div class="ts-grid">
  <div class="ts-panel recent">
    <h3>📅 直近3ヶ月（{recent_n}件）の頻出キーワード</h3>
    <table class="kw-table">
      <thead><tr><th>キーワード</th><th>頻度</th><th>出現率</th></tr></thead>
      <tbody>{kw_rows(recent_top,"recent_rate","recent_count",recent_max)}</tbody>
    </table>
  </div>
  <div class="ts-panel older">
    <h3>🗂️ それ以前（{older_n}件）の頻出キーワード</h3>
    <table class="kw-table">
      <thead><tr><th>キーワード</th><th>頻度</th><th>出現率</th></tr></thead>
      <tbody>{kw_rows(older_top,"older_rate","older_count",older_max)}</tbody>
    </table>
  </div>
</div>

<h3 style="margin-top:24px;margin-bottom:10px;">変化の大きいキーワード</h3>
<div class="ts-grid">
  <div>
    <p style="font-size:0.85em;color:#1d4ed8;margin-bottom:6px;">▲ 直近3ヶ月で増加</p>
    <table class="ts-change-table">
      <thead><tr><th>キーワード</th><th>以前</th><th>直近</th><th>変化</th></tr></thead>
      <tbody>{change_rows(increased,"up")}</tbody>
    </table>
  </div>
  <div>
    <p style="font-size:0.85em;color:#dc2626;margin-bottom:6px;">▼ 直近3ヶ月で減少</p>
    <table class="ts-change-table">
      <thead><tr><th>キーワード</th><th>以前</th><th>直近</th><th>変化</th></tr></thead>
      <tbody>{change_rows(decreased,"down")}</tbody>
    </table>
  </div>
</div>"""


def _build_kando_section(kando: dict) -> str:
    if not kando or not kando.get("aggregated"):
        return "<p>感動分析データなし</p>"

    aggregated = kando["aggregated"]
    strengths  = kando.get("strengths", [])
    weaknesses = kando.get("weaknesses", [])
    ai_comment = kando.get("ai_comment", "")
    total      = kando.get("total_analyzed", 0)

    max_score = max((aggregated[t]["score"] for t in KANDO_TYPES), default=5) or 5
    rows = []
    for t in KANDO_TYPES:
        d = aggregated[t]
        pct = round(d["score"] / 5 * 100)
        extra_cls = "strength" if t in strengths else "weakness" if t in weaknesses else ""
        badge = " 💪" if t in strengths else " ⚠️" if t in weaknesses else ""
        reliable = "" if d["is_reliable"] else ' <span class="kando-dot" title="口コミ数3件未満">●</span>'
        rows.append(f"""
  <div class="kando-row {extra_cls}">
    <span class="kando-label">{d['label']}{badge}</span>
    <div class="kando-bar-wrap"><div class="kando-bar" style="width:{pct}%;"></div></div>
    <span class="kando-score">{d['score']:.1f}</span>
    <span class="kando-rate">{d['detection_rate']}%{reliable}</span>
  </div>""")

    return f"""
<p style="color:var(--muted);font-size:0.85em;margin-bottom:16px;">
  分析口コミ数: {total}件 ／ スコア: 0〜5点 ／ 出現率: 各類型に言及のある口コミの割合<br>
  <span style="color:#1a73e8">💪 強み上位2類型</span>　<span style="color:#dc2626">⚠️ 弱み下位2類型</span>　<span style="color:var(--muted)">● 信頼度低（件数3件未満）</span>
</p>
<div class="kando-layout">
  <div class="kando-chart-wrap">
    <canvas id="kandoChart"></canvas>
  </div>
  <div class="kando-detail">{"".join(rows)}</div>
</div>
<div class="kando-note">
  <p class="kando-note-intro">テーマパークは感動を提供する場。感動には７種類あり、テーマパークではこれらを組み合わせて感動を生み出している。</p>
  <details class="kando-expand">
    <summary><span class="expand-icon">▶</span> 感動の７類型とは？（クリックして展開）</summary>
    <div class="kando-types">
      <div class="kando-type-item">
        <h4>① しきい値突破型</h4>
        <p>消費者の基準（しきい値）を真正面から超えるもの。「過去に食べたものより美味しい」、「他のどの体験よりも楽しい」など。五感を刺激して体験価値を上げたり、いろいろな手段がありますが、シンプルに本業に力を入れることでもある。消費者の価値基準が高まってきている現代では、なかなかしきい値を突破しないことが多くなっている。とことん突き抜ける覚悟が必要になります。</p>
      </div>
      <div class="kando-type-item">
        <h4>② 意外性型</h4>
        <p>スケジュールに書いていない時間や場所でキャラクターが登場したり、アトラクションが予想外の動きをしたりして、「予測の裏切り」がもたらす感動。即効性がある。「消費者がまったく期待していない部分（裏側の対応や、ちょっとした気遣いなど）」に圧倒的な力を注ぐと、この意外性は強烈なフックになります。</p>
      </div>
      <div class="kando-type-item">
        <h4>③ 共鳴・共感型</h4>
        <p>ディズニーランドのパレードやショーの登場人物に自分を重ね合わせるもの。辛い境遇や困難を乗り越える姿に涙する。これが共鳴の力。いかに相手に「これは自分のことだ」と自分事に感じてもらうかが大事。</p>
      </div>
      <div class="kando-type-item">
        <h4>④ 救済型</h4>
        <p>ディズニーランドで例えると、迷子対応、ポップコーンをこぼしてしまったときのリフィルや清掃が該当。不安なとき、困ったときに助けてくれたことは記憶に残る。上級者はあえて不便な状況を残して、スタッフが手を差し伸べやすい環境を作ったりします。</p>
      </div>
      <div class="kando-type-item">
        <h4>⑤ 崇高型</h4>
        <p>世界的スターであるミッキーマウスに会える。シンデレラ城など圧倒的な造形美。日常では絶対にお目にかかれない「憧れ」や「神聖さ」に触れたときの、畏敬の念に近い感動。ブランドのカリスマ性だったり、歴史の深さなども該当します。</p>
      </div>
      <div class="kando-type-item">
        <h4>⑥ 参加型</h4>
        <p>外側よりも内側から参加した方が何倍にも感動は増幅するもの。カチューシャなどを一緒に着けたりするのは、その準備に当たる。一人で達成するよりも、チームで達成した方が感動につながります。</p>
      </div>
      <div class="kando-type-item">
        <h4>⑦ 成長型</h4>
        <p>消費者の成長と共に歩み、人生のフェーズに合わせて新たな価値を提供し続けることで感動を生むもの。以前は身長制限で乗れなかった乗り物が大人になって乗れるようになったなど。最初から消費者の成長に合わせた設計がなされ、「できるようになった」という自己効力感の積み重ねに心が動きます。</p>
      </div>
    </div>
    <p class="kando-citation">出典：<a href="https://x.com/smileguardian/status/2026050568658341967" target="_blank">https://x.com/smileguardian/status/2026050568658341967</a>　株式会社スマイルガーディアン代表取締役　清水群　※ディズニーランドとUSJ出身のテーマパークコンサルタント</p>
  </details>
</div>
<div class="ai-comment">📊 分析結果

{ai_comment}</div>"""


def _build_kando_radar_json(kando: dict) -> str:
    if not kando or not kando.get("aggregated"):
        return "null"
    aggregated = kando["aggregated"]
    labels = [aggregated[t]["label"] for t in KANDO_TYPES]
    scores = [aggregated[t]["score"] for t in KANDO_TYPES]
    return json.dumps({"labels": labels, "scores": scores}, ensure_ascii=False)


def _build_site_cards(site_stats: dict) -> str:
    cards = []
    for src, s in site_stats.items():
        cards.append(f"""
    <div class="site-card" style="background:{_site_color(src)};">
      <div class="s-label">{_site_label(src)}</div>
      <div class="s-count">{s['count']}</div>
    </div>""")
    return "".join(cards)
