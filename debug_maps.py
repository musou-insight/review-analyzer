"""Google マップのHTML構造をデバッグ確認するスクリプト。"""
import asyncio
import random
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

URL = 'https://www.google.com/maps/place/FUTURE+TRAIN+KYOTO+DINER+%26+CAFE/@34.9883402,135.740253,17z/data=!3m1!4b1!4m15!1m8!3m7!1s0x6001071edcc74405:0x75e17e849b89ba5a!2sFUTURE+TRAIN+KYOTO+DINER+%26+CAFE!8m2!3d34.9883402!4d135.7428279!10e9!16s%2Fg%2F11yh6dx_09!3m5!1s0x6001071edcc74405:0x75e17e849b89ba5a!8m2!3d34.9883402!4d135.7428279!16s%2Fg%2F11yh6dx_09?entry=ttu&g_ep=EgoyMDI2MDIxOC4wIKXMDSoASAFQAw%3D%3D'

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1280,900",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US'] });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        print("ページ読み込み中...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)

        # 口コミタブクリック
        for selector in ['button[aria-label*="クチコミ"]', 'button[aria-label*="Reviews"]', '[data-tab-index="1"]']:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    print(f"タブクリック: {selector}")
                    await asyncio.sleep(3)
                    break
            except Exception:
                pass

        # スクロール数回
        for i in range(5):
            await page.evaluate("""
                const feed = document.querySelector('div[role="feed"]');
                if (feed) feed.scrollTop += 3000;
            """)
            await asyncio.sleep(1.5)
            print(f"スクロール {i+1}/5")

        html = await page.content()

        # HTMLを保存
        with open("debug_maps.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("debug_maps.html に保存しました")

        # セレクタ試験
        soup = BeautifulSoup(html, "html.parser")

        tests = {
            "data-review-id": len(soup.find_all("div", {"data-review-id": True})),
            "role=listitem": len(soup.find_all(attrs={"role": "listitem"})),
            "role=feed": len(soup.find_all(attrs={"role": "feed"})),
            "jftiEf class": len(soup.find_all("div", class_="jftiEf")),
            "wiI7pd class": len(soup.find_all(class_="wiI7pd")),
            "class*=review": len(soup.find_all(class_=lambda c: c and "review" in c.lower() if c else False)),
        }

        print("\n=== セレクタ試験結果 ===")
        for k, v in tests.items():
            print(f"  {k}: {v}件")

        # data-review-id の親要素を調べる
        first_review = soup.find("div", {"data-review-id": True})
        if first_review:
            print(f"\ndata-review-id の親要素を遡る:")
            el = first_review
            for i in range(6):
                el = el.parent
                if el is None:
                    break
                cls = el.get("class", [])
                role = el.get("role", "")
                jslog = el.get("jslog", "")
                print(f"  祖先{i+1}: <{el.name}> class={cls[:3]} role={role}")

        # スクロール可能なコンテナを JS で調べる
        scroll_info = await page.evaluate("""
            () => {
                const results = [];
                // data-review-id を持つ要素の祖先でスクロール可能なものを探す
                const review = document.querySelector('[data-review-id]');
                if (!review) return ['no review found'];
                let el = review;
                for (let i = 0; i < 10; i++) {
                    el = el.parentElement;
                    if (!el) break;
                    const style = window.getComputedStyle(el);
                    const overflow = style.overflow + ' ' + style.overflowY;
                    const scrollable = el.scrollHeight > el.clientHeight;
                    results.push({
                        tag: el.tagName,
                        class: el.className.slice(0, 60),
                        role: el.getAttribute('role') || '',
                        overflow: overflow,
                        scrollable: scrollable,
                        scrollHeight: el.scrollHeight,
                        clientHeight: el.clientHeight,
                    });
                }
                return results;
            }
        """)
        print("\n=== スクロール可能なコンテナ調査 ===")
        for item in scroll_info:
            print(f"  {item}")

        # aria-label に "星" を含む要素
        star_els = soup.find_all(attrs={"aria-label": lambda x: x and ("星" in x or "star" in x.lower()) if x else False})
        print(f"\n星評点 aria-label 要素数: {len(star_els)}")
        if star_els:
            print(f"  例: {star_els[0].get('aria-label','')}")

        await browser.close()

asyncio.run(debug())
