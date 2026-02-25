import asyncio
import random
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def scrape_tripadvisor(url: str) -> list[dict]:
    """TripAdvisor から口コミを全ページ取得する（15件/ページ）。"""
    print("✈️  TripAdvisor スクレイピング開始...")
    reviews = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        page = await context.new_page()

        # ページネーション用に URL ベースを解析
        # TripAdvisor のページは URL に or{offset}-Reviews を含む
        # 例: https://www.tripadvisor.jp/Restaurant_Review-g...d...-Reviews-RestaurantName.html
        #      → or15-Reviews で 2 ページ目
        base_url = url

        page_num = 1
        offset = 0
        while True:
            if page_num == 1:
                current_url = base_url
            else:
                # or{offset}-Reviews 形式に変換
                if "-Reviews-" in base_url:
                    current_url = base_url.replace("-Reviews-", f"-or{offset}-Reviews-")
                else:
                    break

            print(f"  📄 ページ {page_num} を取得中 (offset={offset})")
            try:
                await page.goto(current_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                print(f"  ⚠️ ページ取得失敗: {e}")
                break

            # 「続きを読む」ボタンをクリックして全文展開
            try:
                more_btns = await page.query_selector_all(
                    'button[data-test-target="expand-review"], button.taLnk.ulBlueLinks, span.taLnk'
                )
                for btn in more_btns[:20]:
                    try:
                        await btn.click()
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            soup = BeautifulSoup(await page.content(), "html.parser")
            new_reviews = _parse_tripadvisor_reviews(soup)

            if not new_reviews:
                print(f"  ✅ 終端ページに到達（ページ {page_num}）")
                break

            reviews.extend(new_reviews)
            print(f"    📥 ページ {page_num}: {len(new_reviews)}件 / 累計 {len(reviews)}件")

            # 次ページ確認
            next_btn = soup.find("a", attrs={"data-page-number": str(page_num + 1)})
            if not next_btn:
                # aria-label で確認
                next_btn = soup.find("a", attrs={"aria-label": re.compile(r"次|Next")})
            if not next_btn:
                break

            offset += 15
            page_num += 1
            await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    print(f"  ✅ TripAdvisor: {len(reviews)}件取得")
    return reviews


def _parse_tripadvisor_reviews(soup: BeautifulSoup) -> list[dict]:
    reviews = []
    # TripAdvisor の口コミブロック（複数パターンに対応）
    blocks = soup.find_all("div", attrs={"data-reviewid": True})
    if not blocks:
        blocks = soup.find_all("div", class_=re.compile(r"review-container|reviewSelector"))
    if not blocks:
        blocks = soup.find_all("div", class_=re.compile(r"_c|SvjLX"))  # 新 UI

    seen = set()
    for block in blocks:
        try:
            # テキスト
            text_el = (
                block.find(class_=re.compile(r"partial_entry|reviewText|biGQs"))
                or block.find("q")
                or block.find("p", class_=re.compile(r"review"))
            )
            text = text_el.get_text(strip=True) if text_el else ""
            if not text or text in seen:
                continue
            seen.add(text)

            # 評点
            rating_el = block.find(attrs={"class": re.compile(r"ui_bubble_rating|bubble_")})
            if not rating_el:
                rating_el = block.find(attrs={"aria-label": re.compile(r"\d.*5|★")})
            rating = 0.0
            if rating_el:
                # class="bubble_50" → 5.0 のような形式
                cls = " ".join(rating_el.get("class", []))
                m = re.search(r"bubble_(\d{2})", cls)
                if m:
                    rating = int(m.group(1)) / 10
                else:
                    aria = rating_el.get("aria-label", "")
                    m2 = re.search(r"(\d(?:\.\d)?)", aria)
                    if m2:
                        rating = float(m2.group(1))

            # 日付
            date_el = block.find(class_=re.compile(r"ratingDate|date_visited|biGQs.*date"))
            if not date_el:
                date_el = block.find(attrs={"data-prwidget-name": re.compile(r"date")})
            date_str = ""
            if date_el:
                date_str = date_el.get("title", date_el.get_text(strip=True))

            # レビュアー名・location（TripAdvisor は location を直接取得）
            name_el = block.find(class_=re.compile(r"username|member_info|memberOverlayLink"))
            reviewer_name = name_el.get_text(strip=True) if name_el else ""

            loc_el = block.find(class_=re.compile(r"userLocation|hometown"))
            location = loc_el.get_text(strip=True) if loc_el else ""

            reviews.append({
                "source": "tripadvisor",
                "reviewer_name": reviewer_name,
                "rating": rating,
                "date": date_str,
                "text": text,
                "location": location,
            })
        except Exception:
            continue
    return reviews
