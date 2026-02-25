import asyncio
import random
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def scrape_tabelog(url: str) -> list[dict]:
    """食べログから口コミを全ページ取得する（10件/ページ）。"""
    print("🍽️  食べログ スクレイピング開始...")
    reviews = []

    # 口コミ一覧ページの URL に変換（末尾が / の場合も対応）
    base_url = url.rstrip("/")
    if "/dtlrvwlst/" not in base_url:
        base_url = base_url + "/dtlrvwlst/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = await context.new_page()

        page_num = 1
        while True:
            page_url = f"{base_url}?lc=2&rvw_cnt={(page_num - 1) * 20 + 1}" if page_num > 1 else base_url
            print(f"  📄 ページ {page_num} を取得中: {page_url}")

            try:
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"  ⚠️ ページ取得失敗: {e}")
                break

            soup = BeautifulSoup(await page.content(), "html.parser")
            new_reviews = _parse_tabelog_reviews(soup)

            if not new_reviews:
                print(f"  ✅ 終端ページに到達（ページ {page_num}）")
                break

            reviews.extend(new_reviews)
            print(f"    📥 ページ {page_num}: {len(new_reviews)}件 / 累計 {len(reviews)}件")

            # 次ページリンクを確認
            next_btn = soup.find("a", class_=re.compile(r"c-pagination__arrow--next|next"))
            if not next_btn:
                # 別パターン: ページネーションの最後
                pagination = soup.find("div", class_=re.compile(r"c-pagination"))
                if pagination:
                    links = pagination.find_all("a")
                    current_page_el = pagination.find("span", class_=re.compile(r"c-pagination__page--current|is-current"))
                    if not any("次" in l.get_text() or "next" in l.get("class", []) for l in links):
                        break
                else:
                    break

            page_num += 1
            await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    print(f"  ✅ 食べログ: {len(reviews)}件取得")
    return reviews


def _parse_tabelog_reviews(soup: BeautifulSoup) -> list[dict]:
    reviews = []
    # 食べログの口コミブロック
    blocks = soup.find_all("div", class_=re.compile(r"rvw-item|js-rvw-item-clickable-area"))
    if not blocks:
        blocks = soup.find_all("li", class_=re.compile(r"rvw-item"))

    for block in blocks:
        try:
            # テキスト
            text_el = (
                block.find(class_=re.compile(r"rvw-item__review-text|js-rvw-item-review-text"))
                or block.find("p", class_=re.compile(r"review-body"))
            )
            text = text_el.get_text(strip=True) if text_el else ""
            if not text:
                continue

            # 評点
            rating_el = block.find(class_=re.compile(r"rvw-item__score|c-rating__val"))
            rating = 0.0
            if rating_el:
                m = re.search(r"(\d\.\d|\d)", rating_el.get_text(strip=True))
                if m:
                    rating = float(m.group(1))

            # 日付
            date_el = block.find(class_=re.compile(r"rvw-item__visit-date|c-rating__time"))
            date_str = ""
            if date_el:
                date_str = date_el.get_text(strip=True)
            else:
                time_el = block.find("time")
                if time_el:
                    date_str = time_el.get("datetime", time_el.get_text(strip=True))

            # レビュアー名
            name_el = block.find(class_=re.compile(r"rvw-item__reviewer-name|reviewer-name"))
            reviewer_name = name_el.get_text(strip=True) if name_el else ""

            reviews.append({
                "source": "tabelog",
                "reviewer_name": reviewer_name,
                "rating": rating,
                "date": date_str,
                "text": text,
                "location": "",
            })
        except Exception:
            continue
    return reviews
