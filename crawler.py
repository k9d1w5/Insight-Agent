"""
crawler.py - 주요 컨설팅펌 및 테크 기업 RSS/웹 크롤러
Google News RSS를 활용해 안정적으로 수집
"""
import feedparser
import httpx
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import quote

# ── 직접 RSS가 있는 소스 ─────────────────────────────────
DIRECT_RSS = [
    {"name": "Naver D2",          "category": "플랫폼 테크", "url": "https://d2.naver.com/d2.atom"},
    {"name": "Kakao Tech",         "category": "플랫폼 테크", "url": "https://tech.kakao.com/feed"},
    {"name": "Toss Tech",          "category": "플랫폼 테크", "url": "https://toss.tech/rss.xml"},
    {"name": "우아한형제들(배민)",  "category": "플랫폼 테크", "url": "https://techblog.woowahan.com/feed/"},
    {"name": "당근마켓 Tech",      "category": "플랫폼 테크", "url": "https://medium.com/feed/daangn"},
    {"name": "라인 엔지니어링",    "category": "플랫폼 테크", "url": "https://engineering.linecorp.com/ko/feed/"},
    {"name": "Samsung Newsroom",   "category": "한국 대기업", "url": "https://news.samsung.com/kr/feed"},
    {"name": "LG CNS Blog",        "category": "한국 대기업", "url": "https://blog.lgcns.com/rss"},
    {"name": "SK Telecom Blog",    "category": "한국 대기업", "url": "https://blog.sktelecom.com/feed"},
    {"name": "전자신문",           "category": "IT 미디어",  "url": "https://www.etnews.com/rss/allArticleRss.xml"},
    {"name": "ZDNet Korea",        "category": "IT 미디어",  "url": "https://zdnet.co.kr/rss/"},
    {"name": "IT조선",             "category": "IT 미디어",  "url": "https://it.chosun.com/rss/allList.html"},
]

# ── Google News RSS 소스 (직접 RSS 없는 기업용) ──────────
def gnews(query: str) -> str:
    q = quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

GNEWS_SOURCES = [
    # 글로벌 컨설팅
    {"name": "McKinsey & Company", "category": "글로벌 컨설팅", "url": gnews("McKinsey 인사이트 리포트")},
    {"name": "BCG",                "category": "글로벌 컨설팅", "url": gnews("BCG 보스턴컨설팅 리포트")},
    {"name": "Deloitte",           "category": "글로벌 컨설팅", "url": gnews("딜로이트 Deloitte 인사이트")},
    {"name": "KPMG",               "category": "글로벌 컨설팅", "url": gnews("KPMG 리포트 트렌드")},
    {"name": "PwC",                "category": "글로벌 컨설팅", "url": gnews("PwC 삼일회계법인 인사이트")},
    {"name": "EY 한영",            "category": "글로벌 컨설팅", "url": gnews("EY 한영 인사이트")},
    {"name": "Accenture",          "category": "글로벌 컨설팅", "url": gnews("액센츄어 Accenture AI")},
    {"name": "Gartner",            "category": "글로벌 컨설팅", "url": gnews("Gartner 가트너 IT 트렌드")},
    # 한국 대기업
    {"name": "Samsung SDS",        "category": "한국 대기업",  "url": gnews("삼성SDS AI 클라우드")},
    {"name": "SK AX",              "category": "한국 대기업",  "url": gnews("SK AX SKAX AI 디지털")},
    {"name": "KT",                 "category": "한국 대기업",  "url": gnews("KT AI 클라우드 디지털")},
    {"name": "POSCO ICT",          "category": "한국 대기업",  "url": gnews("포스코ICT AI 스마트팩토리")},
    {"name": "LG CNS",             "category": "한국 대기업",  "url": gnews("LGCNS AI 클라우드 DX")},
    # 플랫폼
    {"name": "Naver",              "category": "플랫폼 테크",  "url": gnews("네이버 AI HyperCLOVA 기술")},
    {"name": "Kakao",              "category": "플랫폼 테크",  "url": gnews("카카오 AI 기술 개발")},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 기업별 도메인 (로고용)
LOGO_DOMAINS = {
    "McKinsey & Company": "mckinsey.com",
    "BCG": "bcg.com",
    "Deloitte": "deloitte.com",
    "KPMG": "kpmg.com",
    "PwC": "pwc.com",
    "EY 한영": "ey.com",
    "Accenture": "accenture.com",
    "Gartner": "gartner.com",
    "Samsung Newsroom": "samsung.com",
    "Samsung SDS": "samsungsds.com",
    "LG CNS": "lgcns.com",
    "LG CNS Blog": "lgcns.com",
    "SK Telecom Blog": "sktelecom.com",
    "SK AX": "skax.com",
    "KT": "kt.com",
    "POSCO ICT": "poscoict.com",
    "Naver D2": "naver.com",
    "Naver": "naver.com",
    "Kakao Tech": "kakao.com",
    "Kakao": "kakao.com",
    "Toss Tech": "toss.im",
    "우아한형제들(배민)": "baemin.com",
    "당근마켓 Tech": "daangn.com",
    "라인 엔지니어링": "linecorp.com",
    "전자신문": "etnews.com",
    "ZDNet Korea": "zdnet.co.kr",
    "IT조선": "it.chosun.com",
}


def _clean_text(html: str, max_len: int = 500) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(separator=" ")
    return " ".join(text.split())[:max_len]


async def _fetch_rss(client: httpx.AsyncClient, source: dict) -> list[dict]:
    articles = []
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        cutoff = datetime.now() - timedelta(days=7)

        for entry in feed.entries[:8]:
            pub_date = None
            if getattr(entry, "published_parsed", None):
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            if pub_date and pub_date < cutoff:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            raw = (entry.get("summary") or entry.get("description") or "")
            domain = LOGO_DOMAINS.get(source["name"], "")

            articles.append({
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": entry.get("link", ""),
                "summary": _clean_text(raw),
                "published": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else None,
                "logo_domain": domain,
            })

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개")
        else:
            print(f"  - {source['name']}: 최근 기사 없음")
    except Exception as e:
        print(f"  ✗ {source['name']}: {e}")

    return articles


async def fetch_all_sources() -> list[dict]:
    all_sources = DIRECT_RSS + GNEWS_SOURCES
    print(f"\n[크롤링 시작] {len(all_sources)}개 소스")
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [_fetch_rss(client, src) for src in all_sources]
        results = await asyncio.gather(*tasks)

    all_articles = [a for batch in results for a in batch]
    print(f"\n총 {len(all_articles)}개 아티클 수집 완료\n")
    return all_articles
