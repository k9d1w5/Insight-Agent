"""
crawler.py - 주요 컨설팅펌 및 테크 기업 RSS/웹 크롤러
"""
import feedparser
import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

KST = timezone(timedelta(hours=9))

# ── 직접 RSS가 있는 소스 ─────────────────────────────────
DIRECT_RSS = [
    {"name": "Naver D2",          "category": "플랫폼 테크", "url": "https://d2.naver.com/d2.atom"},
    {"name": "Kakao Tech",         "category": "플랫폼 테크", "url": "https://tech.kakao.com/feed"},
    {"name": "Toss Tech",          "category": "플랫폼 테크", "url": "https://toss.tech/rss.xml"},
    {"name": "우아한형제들(배민)",  "category": "플랫폼 테크", "url": "https://techblog.woowahan.com/feed/"},
    {"name": "당근마켓 Tech",      "category": "플랫폼 테크", "url": "https://medium.com/feed/daangn"},
    {"name": "라인 엔지니어링",    "category": "플랫폼 테크", "url": "https://engineering.linecorp.com/ko/feed/"},
    {"name": "LG CNS Blog",        "category": "한국 대기업", "url": "https://blog.lgcns.com/rss"},
]

# ── Google News RSS 소스 ──────────────────────────────────
def gnews(query: str) -> str:
    q = quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

GNEWS_SOURCES = [
    # 글로벌 컨설팅
    {"name": "McKinsey & Company", "category": "글로벌 컨설팅", "url": gnews("McKinsey 인사이트 리포트 AI"), "logo_domain": "mckinsey.com"},
    {"name": "BCG",                "category": "글로벌 컨설팅", "url": gnews("BCG 보스턴컨설팅 리포트 AI"), "logo_domain": "bcg.com"},
    {"name": "Deloitte",           "category": "글로벌 컨설팅", "url": gnews("딜로이트 Deloitte 인사이트"), "logo_domain": "deloitte.com"},
    {"name": "KPMG",               "category": "글로벌 컨설팅", "url": gnews("KPMG 리포트 AI 트렌드"), "logo_domain": "kpmg.com"},
    {"name": "PwC",                "category": "글로벌 컨설팅", "url": gnews("PwC 삼일회계법인 인사이트"), "logo_domain": "pwc.com"},
    {"name": "EY 한영",            "category": "글로벌 컨설팅", "url": gnews("EY 한영 인사이트 AI"), "logo_domain": "ey.com"},
    {"name": "Accenture",          "category": "글로벌 컨설팅", "url": gnews("액센츄어 Accenture AI DX"), "logo_domain": "accenture.com"},
    {"name": "Gartner",            "category": "글로벌 컨설팅", "url": gnews("Gartner 가트너 IT 트렌드"), "logo_domain": "gartner.com"},
    # 한국 대기업
    {"name": "SK AX",              "category": "한국 대기업",  "url": gnews("SK AX AI 디지털 클라우드"), "logo_domain": "skax.co.kr"},
    {"name": "KT",                 "category": "한국 대기업",  "url": gnews("KT AI 클라우드 디지털전환"), "logo_domain": "kt.com"},
    {"name": "현대오토에버",       "category": "한국 대기업",  "url": gnews("현대오토에버 AI IT 클라우드"), "logo_domain": "hyundai-autoever.com"},
    {"name": "LG CNS",             "category": "한국 대기업",  "url": gnews("LGCNS LG CNS AI 클라우드 DX"), "logo_domain": "lgcns.com"},
    # 플랫폼
    {"name": "Naver",              "category": "플랫폼 테크",  "url": gnews("네이버 AI HyperCLOVA 기술"), "logo_domain": "naver.com"},
    {"name": "Kakao",              "category": "플랫폼 테크",  "url": gnews("카카오 AI 기술 개발"), "logo_domain": "kakao.com"},
    # IT 미디어
    {"name": "IT조선",             "category": "IT 미디어",   "url": gnews("IT조선 인공지능 AI 디지털"), "logo_domain": "it.chosun.com"},
    {"name": "ZDNet Korea",        "category": "IT 미디어",   "url": gnews("ZDNet Korea AI 소프트웨어 IT"), "logo_domain": "zdnet.co.kr"},
    {"name": "전자신문",           "category": "IT 미디어",   "url": gnews("전자신문 AI 클라우드 IT"), "logo_domain": "etnews.com"},
    {"name": "인공지능신문",       "category": "IT 미디어",   "url": gnews("인공지능신문 AI LLM"), "logo_domain": "aitimes.kr"},
    {"name": "AI타임즈",           "category": "IT 미디어",   "url": gnews("AI타임즈 인공지능 기술"), "logo_domain": "aitimes.com"},
]

# ── 직접 웹 스크래핑 소스 ────────────────────────────────
WEB_SOURCES = [
    {
        "name": "Samsung SDS",
        "category": "한국 대기업",
        "url": "https://www.samsungsds.com/kr/insights/index.html",
        "logo_domain": "samsungsds.com",
        "link_pattern": "/kr/insights/",   # 이 패턴 포함된 링크만
        "exclude_pattern": "index",        # 인덱스 페이지 자체 제외
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
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
    "Samsung SDS": "samsungsds.com",
    "LG CNS": "lgcns.com",
    "LG CNS Blog": "lgcns.com",
    "SK AX": "skax.co.kr",
    "KT": "kt.com",
    "현대오토에버": "hyundai-autoever.com",
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
    "인공지능신문": "aitimes.kr",
    "AI타임즈": "aitimes.com",
}


def _clean_text(html: str, max_len: int = 500) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(separator=" ")
    return " ".join(text.split())[:max_len]


async def _fetch_rss(client: httpx.AsyncClient, source: dict) -> list[dict]:
    """RSS 피드 수집"""
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
            domain = source.get("logo_domain") or LOGO_DOMAINS.get(source["name"], "")

            articles.append({
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": entry.get("link", ""),
                "summary": _clean_text(raw),
                "published": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else datetime.now().strftime("%Y-%m-%d %H:%M"),
                "logo_domain": domain,
            })

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개")
        else:
            print(f"  - {source['name']}: 최근 기사 없음")
    except Exception as e:
        print(f"  ✗ {source['name']}: {e}")

    return articles


async def _fetch_web(client: httpx.AsyncClient, source: dict) -> list[dict]:
    """웹 페이지 직접 스크래핑 (인사이트 목록 페이지용)"""
    articles = []
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen = set()
        link_pattern  = source.get("link_pattern", "")
        exclude_pattern = source.get("exclude_pattern", "")
        base = "https://" + source["url"].split("/")[2]

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("/"):
                href = base + href
            elif not href.startswith("http"):
                continue

            # 패턴 필터
            if link_pattern and link_pattern not in href:
                continue
            if exclude_pattern and exclude_pattern in href.split("/")[-1]:
                continue
            if href in seen:
                continue

            # 제목 추출: 태그 내부 텍스트 또는 가장 긴 자식 텍스트
            title = ""
            for tag in a_tag.find_all(["h2", "h3", "h4", "strong", "p", "span"]):
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
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": href,
                "summary": "",
                "published": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "logo_domain": source.get("logo_domain", ""),
            })

            if len(articles) >= 8:
                break

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개 (웹 스크래핑)")
        else:
            print(f"  - {source['name']}: 아티클 없음 (웹 스크래핑)")

    except Exception as e:
        print(f"  ✗ {source['name']}: {e}")

    return articles


async def fetch_all_sources() -> list[dict]:
    all_rss = DIRECT_RSS + GNEWS_SOURCES
    print(f"\n[크롤링 시작] RSS {len(all_rss)}개 + 웹 {len(WEB_SOURCES)}개 소스")

    async with httpx.AsyncClient(headers=HEADERS) as client:
        rss_tasks = [_fetch_rss(client, src) for src in all_rss]
        web_tasks = [_fetch_web(client, src) for src in WEB_SOURCES]
        all_results = await asyncio.gather(*(rss_tasks + web_tasks))

    all_articles = [a for batch in all_results for a in batch]
    print(f"\n총 {len(all_articles)}개 아티클 수집 완료\n")
    return all_articles
