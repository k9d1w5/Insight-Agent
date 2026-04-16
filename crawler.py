"""
crawler.py - 주요 컨설팅펌 및 테크 기업 RSS/웹 크롤러
"""
import feedparser
import httpx
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

SOURCES = [
    # ─── 글로벌 컨설팅펌 ───────────────────────────────────────
    {"name": "McKinsey & Company", "category": "글로벌 컨설팅",
     "url": "https://www.mckinsey.com/insights/rss"},
    {"name": "BCG", "category": "글로벌 컨설팅",
     "url": "https://www.bcg.com/rss/insights"},
    {"name": "Deloitte Insights", "category": "글로벌 컨설팅",
     "url": "https://www2.deloitte.com/us/en/insights/rss.html"},
    {"name": "KPMG", "category": "글로벌 컨설팅",
     "url": "https://kpmg.com/rss/rss.xml"},
    {"name": "PwC", "category": "글로벌 컨설팅",
     "url": "https://www.pwc.com/gx/en/insights/rss.html"},
    {"name": "EY", "category": "글로벌 컨설팅",
     "url": "https://www.ey.com/en_gl/rss/insights-feed"},
    {"name": "Accenture", "category": "글로벌 컨설팅",
     "url": "https://newsroom.accenture.com/rss/all-news.rss"},

    # ─── 한국 대기업 ───────────────────────────────────────────
    {"name": "Samsung Newsroom KR", "category": "한국 대기업",
     "url": "https://news.samsung.com/kr/feed"},
    {"name": "LG CNS Blog", "category": "한국 대기업",
     "url": "https://blog.lgcns.com/rss"},
    {"name": "SK Telecom Blog", "category": "한국 대기업",
     "url": "https://blog.sktelecom.com/feed"},
    {"name": "KT Enterprise", "category": "한국 대기업",
     "url": "https://enterprise.kt.com/bt/rss.do"},

    # ─── 플랫폼 테크 ───────────────────────────────────────────
    {"name": "Naver D2", "category": "플랫폼 테크",
     "url": "https://d2.naver.com/d2.atom"},
    {"name": "Kakao Tech", "category": "플랫폼 테크",
     "url": "https://tech.kakao.com/feed"},
    {"name": "Toss Tech", "category": "플랫폼 테크",
     "url": "https://toss.tech/rss.xml"},
    {"name": "우아한형제들 (배민)", "category": "플랫폼 테크",
     "url": "https://techblog.woowahan.com/feed/"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _clean_text(html: str, max_len: int = 600) -> str:
    """HTML 태그 제거 후 텍스트 정리"""
    text = BeautifulSoup(html or "", "html.parser").get_text(separator=" ")
    text = " ".join(text.split())
    return text[:max_len]


async def _fetch_rss(client: httpx.AsyncClient, source: dict) -> list[dict]:
    """단일 RSS 소스 크롤링"""
    articles = []
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        cutoff = datetime.now() - timedelta(days=2)  # 최근 48시간

        for entry in feed.entries[:15]:
            # 발행일 파싱
            pub_date = None
            if getattr(entry, "published_parsed", None):
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            # 48시간 이내 또는 날짜 미상 모두 포함
            if pub_date and pub_date < cutoff:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            raw_summary = (
                entry.get("summary")
                or entry.get("description")
                or entry.get("content", [{}])[0].get("value", "")
            )

            articles.append({
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": entry.get("link", ""),
                "summary": _clean_text(raw_summary),
                "published": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else None,
            })

        print(f"  ✓ {source['name']}: {len(articles)}개 수집")
    except Exception as e:
        print(f"  ✗ {source['name']}: {e}")

    return articles


async def fetch_all_sources() -> list[dict]:
    """전체 소스 병렬 크롤링"""
    print(f"\n[크롤링 시작] {len(SOURCES)}개 소스")
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [_fetch_rss(client, src) for src in SOURCES]
        results = await asyncio.gather(*tasks)

    all_articles = [article for batch in results for article in batch]
    print(f"\n총 {len(all_articles)}개 아티클 수집 완료\n")
    return all_articles
