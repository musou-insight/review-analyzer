#!/usr/bin/env python3
"""既存レポートHTMLのキーワードバーを100%基準に書き換えるスクリプト。"""

import re
from pathlib import Path

BASE = Path("public")

TARGETS = list(BASE.glob("*/report.html"))

def fix_report(path: Path):
    html = path.read_text(encoding="utf-8")
    original = html

    # --- 1. 総口コミ数を取得 ---
    m = re.search(r'総口コミ数[:：]\s*(\d+)件', html)
    if not m:
        print(f"  ⚠️ 総口コミ数が見つかりません: {path}")
        return
    total = int(m.group(1))
    print(f"  総口コミ数: {total}件")

    # --- 2. キーワードランキング テーブルのヘッダーを更新 ---
    # "頻度" → "出現率（100%基準）"、"回数" → "出現率"
    html = re.sub(
        r'(<thead><tr><th>#</th><th>キーワード</th><th>種別</th><th>)頻度(</th><th>)回数(</th></tr></thead>)',
        r'\1出現率（100%基準）\2出現率\3',
        html
    )

    # --- 3. キーワードランキング 各行のバー幅と末尾セルを更新 ---
    # パターン: width:XX%;background:COLOR;  ...  >N回</td>
    # キーワードランキングセクションのみ対象（時系列は別処理）
    # kw-rankセルを含む行を対象にする

    def replace_kw_row(match):
        full = match.group(0)
        # "N回" (未変換) または "X.X%" (変換済み) どちらも対応
        count_m = re.search(r'class="kw-count">(\d+)回</td>', full)
        rate_m  = re.search(r'class="kw-count">([0-9.]+)%</td>', full)

        if count_m:
            count = int(count_m.group(1))
            rate = round(count / total * 100, 1)
            bar_pct = min(rate, 100)
            full = re.sub(
                r'class="kw-count">\d+回</td>',
                f'class="kw-count">{rate}%</td>',
                full
            )
        elif rate_m:
            rate = float(rate_m.group(1))
            bar_pct = min(rate, 100)
        else:
            return full

        # バー幅を更新 (style="width:NN%;background:..." の形式)
        full = re.sub(
            r'(class="kw-bar" style="width:)\d+(%;)',
            f'\\g<1>{bar_pct:.0f}\\2',
            full
        )
        return full

    # kw-rank セルを含む <tr>...</tr> を対象に置換
    html = re.sub(
        r'<tr>\s*<td class="kw-rank">.*?</tr>',
        replace_kw_row,
        html,
        flags=re.DOTALL
    )

    # --- 4. キーワードランキングの説明テキストを追加（まだなければ）---
    legend_note = '<p style="color:var(--muted);font-size:0.85em;margin-bottom:12px;">出現率 = キーワードが含まれる口コミ件数 ÷ 総口コミ数。バーは100%を基準に表示。</p>'
    if '出現率 = キーワードが含まれる' not in html:
        html = html.replace(
            '<div class="kw-legend">',
            legend_note + '\n<div class="kw-legend">',
            1  # 最初の1つだけ（キーワードランキング箇所）
        )

    # --- 5. 時系列セクション テーブルのバー幅を出現率%直接指定に変更 ---
    # パターン: "N件 (X%)" → バー幅を X% に直接設定
    # 時系列のkw-bar-cell行: width:NN%;background:COLOR
    # kw-count が "N件 (X%)" の形式のものが時系列行

    def replace_ts_row(match):
        full = match.group(0)
        # kw-count に "件 (X%)" がある行が時系列
        rate_m = re.search(r'class="kw-count">\d+件 \(([0-9.]+)%\)', full)
        if not rate_m:
            return full
        rate = float(rate_m.group(1))
        bar_pct = min(rate, 100)
        # バー幅を更新 (style="width:NN%;background:..." の形式)
        full = re.sub(
            r'(class="kw-bar" style="width:)\d+(%;)',
            f'\\g<1>{bar_pct:.0f}\\2',
            full
        )
        return full

    html = re.sub(
        r'<tr>\s*<td class="kw-word">.*?</tr>',
        replace_ts_row,
        html,
        flags=re.DOTALL
    )

    if html == original:
        print(f"  ⚠️ 変更なし（すでに更新済みかもしれません）: {path}")
        return

    path.write_text(html, encoding="utf-8")
    print(f"  ✅ 更新完了: {path}")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent)
    for p in TARGETS:
        print(f"\n📄 {p}")
        fix_report(p)
