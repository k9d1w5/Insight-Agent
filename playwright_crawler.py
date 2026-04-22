"""
playwright_crawler.py - JavaScript 렌더링 사이트 전용 크롤러
httpx로 수집 불가능한 JS 렌더링 사이트를 Chromium 헤드리스 브라우저로 수집
"""
import asyncio
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
MAX_PER_SOURCE = 5

# ════════════════════════════════════════════════════════════
# JS 렌더링 수집 대상 사이트
# ════════════════════════════════════════════════════════════
PLAYWRIGHT_SOURCES = [
    {
        "name":            "Samsung SDS 인사이트",
        "category":        "한국 대기업",
        "url":             "https://www.samsungsds.com/kr/insights/index.html",
        "logo_domain":     "samsungsds.com",
        "link_pattern":    "/kr/insights/",
        "exclude_pattern": "index",
        "wait_for":        "networkidle",
        "extra_wait_ms":   2000,
    },
    {
        "name":            "SK AX",
        "category":        "한국 대기업",
        "url":             "https://www.skax.co.kr/insight/trends",
        "logo_domain":     "skax.co.kr",
        "link_pattern":    "/insight/",
        "exclude_pattern": "trends",
        "wait_for":        "networkidle",
        "extra_wait_ms":   2000,
    },
    {
        "name":            "현대오토에버",
        "category":        "한국 대기업",
        "url":             "https://www.hyundai-autoever.com/kor/about/pr/insights/list.do",
        "logo_domain":     "hyundai-autoever.com",
        "link_pattern":    "/insights/",
        "exclude_pattern": "list",
        "wait_for":        "networkidle",
        "extra_wait_ms":   2000,
    },
    {
        "name":            "LG CNS 인사이트",
        "category":        "한국 대기업",
        "url":             "https://www.lgcns.com/kr/moa/insight.page_1",
        "logo_domain":     "lgcns.com",
        "link_pattern":    "/kr/moa/insight",
        "exclude_pattern": "page_",           # 페이지네이션 링크 제외
        "wait_for":        "networkidle",
        "extra_wait_ms":   2000,
    },
    {
        "name":            "에커튼파트너스",
        "category":        "한국 대기업",
        "url":             "https://www.ackerton.com/insightReport",
        "logo_domain":     "ackerton.com",
        "link_pattern":    "/insightReport",
        "exclude_pattern": "",
        "wait_for":        "domcontentloaded",
        "extra_wait_ms":   500,
    },
]


def _extract_articles_from_html(html: str, source: dict) -> list[dict]:
    """
    렌더링된 HTML에서 아티클 추출
    — BeautifulSoup으로 링크 탐색 → 가장 긴 텍스트를 제목으로 사용
    """
    soup        = BeautifulSoup(html, "html.parser")
    base_url    = "https://" + source["url"].split("/")[2]
    pattern     = source.get("link_pattern", "")
    exclude     = source.get("exclude_pattern", "")
    articles    = []
    seen        = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # 절대 URL 처리
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = base_url + href
        elif not href.startswith("http"):
            continue

        # 패턴 필터링
        if pattern and pattern not in href:
            continue
        last_seg = href.rstrip("/").split("/")[-1].split("?")[0]
        if exclude and exclude in last_seg:
            continue
        if href in seen:
            continue

        # 제목 추출: 자식 요소 중 가장 긴 텍스트
        title = ""
        for tag in a_tag.find_all(["h1","h2","h3","h4","strong","p","span","div"]):
            t = tag.get_text(strip=True)
            if len(t) > len(title):
                title = t
        if not title:
            title = a_tag.get_text(strip=True)

        # 너무 짧거나 긴 제목 제외
        if len(title) < 10 or len(title) > 200:
            continue

        seen.add(href)
        articles.append({
            "source":      source["name"],
            "category":    source["category"],
            "title":       title,
            "url":         href,
            "summary":     "",
            "published":   datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "logo_domain": source.get("logo_domain", ""),
        })

        if len(articles) >= MAX_PER_SOURCE:
            break

    return articles


async def _fetch_one(source: dict) -> list[dict]:
    """단일 사이트 Playwright 수집"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(f"  ✗ Playwright 미설치 — {source['name']} 수집 불가")
        return []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],  # GitHub Actions 환경
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
            )
            page = await context.new_page()

            await page.goto(
                source["url"],
                wait_until=source.get("wait_for", "networkidle"),
                timeout=30_000,
            )

            # 추가 대기 (JS 렌더링 완료 보장)
            extra = source.get("extra_wait_ms", 1000)
            if extra:
                await page.wait_for_timeout(extra)

            html     = await page.content()
            articles = _extract_articles_from_html(html, source)

            await browser.close()

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개 (Playwright)")
        else:
            print(f"  - {source['name']}: 아티클 없음 (Playwright)")

        return articles

    except Exception as e:
        print(f"  ✗ {source['name']} (Playwright): {str(e)[:100]}")
        return []


async def fetch_playwright_sources() -> list[dict]:
    """JS 렌더링 사이트 전체 수집 — 순차 실행 (브라우저 메모리 절약)"""
    print(f"\n[Playwright 크롤링] {len(PLAYWRIGHT_SOURCES)}개 JS 렌더링 사이트")
    all_articles = []

    # 브라우저 메모리 이슈 방지를 위해 순차 실행
    for source in PLAYWRIGHT_SOURCES:
        articles = await _fetch_one(source)
        all_articles.extend(articles)
        await asyncio.sleep(1)  # 사이트 간 간격

    print(f"[Playwright 완료] {len(all_articles)}개 수집\n")
    return all_articles
