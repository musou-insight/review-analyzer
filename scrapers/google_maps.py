import asyncio
import random
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def scrape_google_maps(url: str, max_reviews: int | None = None) -> list[dict]:
    """Google マップから口コミを取得する。max_reviews 指定時はその件数で打ち切る。"""
    limit_msg = f"（上限 {max_reviews} 件）" if max_reviews else "（全件）"
    print(f"🗺️  Google マップ スクレイピング開始... {limit_msg}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,900",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
            java_script_enabled=True,
        )
        # webdriver フラグを隠してボット検知を回避
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US'] });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Cookie 同意ダイアログを閉じる
        for selector in ['button[aria-label*="同意"]', 'button[aria-label*="Accept"]']:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass

        # 口コミタブをクリック
        for selector in [
            'button[aria-label*="クチコミ"]',
            'button[aria-label*="Reviews"]',
            '[data-tab-index="1"]',
        ]:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    print("  ✅ 口コミタブをクリックしました")
                    break
            except Exception:
                pass

        # 口コミ要素が出現するまで待つ（最大20秒）
        print("  ⏳ 口コミの読み込みを待機中...")
        try:
            await page.wait_for_selector('[data-review-id]', timeout=20000)
            print("  ✅ 口コミ要素を検出しました")
        except Exception:
            print("  ⚠️ 口コミ要素の待機タイムアウト。そのまま続行します。")
        await asyncio.sleep(2)

        # スクロール可能なコンテナを JS で特定
        scroll_js = """
            () => {
                const review = document.querySelector('[data-review-id]');
                if (!review) return null;
                let el = review.parentElement;
                for (let i = 0; i < 10; i++) {
                    if (!el) break;
                    const style = window.getComputedStyle(el);
                    const ov = style.overflowY;
                    if ((ov === 'auto' || ov === 'scroll') && el.scrollHeight > el.clientHeight + 50) {
                        return el.className.split(' ')[0];
                    }
                    el = el.parentElement;
                }
                return null;
            }
        """
        scroll_container_class = await page.evaluate(scroll_js)
        if scroll_container_class:
            print(f"  📌 スクロールコンテナ: .{scroll_container_class}")
        else:
            print("  ⚠️ スクロールコンテナが特定できません")

        print("  ⏳ 口コミをスクロール取得中...")
        last_count = 0
        stuck = 0

        for i in range(150):
            # スクロール（特定できたクラス優先、fallback は mouse.wheel）
            try:
                scrolled = await page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('[data-review-id]');
                        if (!el) return false;
                        let c = el.parentElement;
                        for (let i = 0; i < 10; i++) {{
                            if (!c) break;
                            const ov = window.getComputedStyle(c).overflowY;
                            if ((ov === 'auto' || ov === 'scroll') && c.scrollHeight > c.clientHeight + 50) {{
                                c.scrollTop += 3000;
                                return true;
                            }}
                            c = c.parentElement;
                        }}
                        return false;
                    }}
                """)
                if not scrolled:
                    await page.mouse.wheel(0, 3000)
            except Exception:
                await page.mouse.wheel(0, 3000)

            await asyncio.sleep(random.uniform(0.8, 1.5))

            # 「もっと見る」ボタンを展開
            try:
                await page.evaluate("""
                    document.querySelectorAll('button.w8nwRe, button[jsaction*="expandReview"]').forEach(b => b.click());
                """)
            except Exception:
                pass

            soup = BeautifulSoup(await page.content(), "html.parser")
            reviews_now = _parse_google_reviews(soup)
            count = len(reviews_now)

            if (i + 1) % 10 == 0 or count != last_count:
                print(f"    📥 取得件数: {count}件（試行 {i+1}）")

            if max_reviews and count >= max_reviews:
                print(f"  ✅ 取得上限 {max_reviews} 件に到達（試行 {i+1}）")
                break

            if count <= last_count:
                stuck += 1
                if stuck >= 8:
                    print(f"  ✅ スクロール終端に到達（試行 {i+1}）")
                    break
            else:
                stuck = 0
            last_count = count

        soup = BeautifulSoup(await page.content(), "html.parser")
        reviews = _parse_google_reviews(soup)
        if max_reviews:
            reviews = reviews[:max_reviews]
        await browser.close()

    print(f"  ✅ Google マップ: {len(reviews)}件取得")
    return reviews


def _clean_review_text(text: str) -> str:
    """Google マップが付加するメタデータ（食事の種類・料金・評点など）を除去する。"""
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


def _parse_google_reviews(soup: BeautifulSoup) -> list[dict]:
    reviews = []

    # data-review-id がある div を優先
    blocks = soup.find_all("div", {"data-review-id": True})
    if not blocks:
        blocks = soup.find_all("div", class_=re.compile(r"jftiEf"))

    seen = set()
    for block in blocks:
        try:
            # テキスト（複数のクラス名パターンに対応）
            text_el = block.find(class_=re.compile(r"wiI7pd|MyEned|review-full-text"))
            if not text_el:
                # span や div の中で最も長いテキストを探す
                candidates = block.find_all(["span", "p"], string=True)
                text_el = max(candidates, key=lambda x: len(x.get_text()), default=None)
            raw_text = text_el.get_text(strip=True) if text_el else ""
            text = _clean_review_text(raw_text)
            if len(text) < 5 or text in seen:
                continue
            seen.add(text)

            # 評点（aria-label="星5つ中4つ" のような形式）
            rating = 0.0
            for el in block.find_all(attrs={"aria-label": True}):
                label = el.get("aria-label", "")
                m = re.search(r"(\d)(?:\.\d)?(?:つ|星| star)", label)
                if m:
                    rating = float(m.group(1))
                    break

            # 日付
            date_el = block.find(class_=re.compile(r"rsqaWe|xRkPPb|review-date"))
            date_str = date_el.get_text(strip=True) if date_el else ""

            # レビュアー名
            name_el = block.find(class_=re.compile(r"d4r55|reviewer|al6Kxe"))
            reviewer_name = name_el.get_text(strip=True) if name_el else ""

            reviews.append({
                "source": "google_maps",
                "reviewer_name": reviewer_name,
                "rating": rating,
                "date": date_str,
                "text": text,
                "location": "",
            })
        except Exception:
            continue
    return reviews
