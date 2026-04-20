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

MAX_PER_SOURCE = 5   # 소스당 최대 아티클 (한 소스가 지배하지 않도록)

# ════════════════════════════════════════════════════════════
# 보장 소스: 날짜에 관계없이 매일 최소 1개 반드시 포함
# 같은 회사의 소스가 여러 개면 하나라도 있으면 OK (그룹 단위 체크)
# ════════════════════════════════════════════════════════════
GUARANTEED_GROUPS = {
    # 글로벌 컨설팅 — 각 펌마다 최소 1개
    "McKinsey":   {"McKinsey & Company"},
    "Deloitte":   {"Deloitte Insights"},
    "BCG":        {"BCG"},
    "PwC":        {"PwC"},
    "KPMG":       {"KPMG"},
    "EY":         {"EY"},
    "Accenture":  {"Accenture"},
    "Gartner":    {"Gartner"},
    "Forrester":  {"Forrester"},
    # 한국 대기업 — 각 회사마다 최소 1개
    "Samsung SDS":  {"Samsung SDS", "Samsung SDS 인사이트"},
    "LG CNS":       {"LG CNS Blog", "LG CNS"},
    "SK":           {"SK C&C 기술블로그", "SK AX"},
    "KT":           {"KT Enterprise"},
    "현대오토에버":  {"현대오토에버"},
    "롯데이노베이트": {"롯데이노베이트"},
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ── Google News RSS 헬퍼 ──────────────────────────────────
def gnews(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"

def gnews_en(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en&gl=US&ceid=US:en"

# ════════════════════════════════════════════════════════════
# 직접 RSS 소스 — 안정적으로 작동하는 피드만
# ════════════════════════════════════════════════════════════
DIRECT_RSS = [
    # ── 글로벌 컨설팅 ─────────────────────────────────────
    {"name": "McKinsey & Company", "category": "글로벌 컨설팅",
     "url": "https://www.mckinsey.com/insights/rss",
     "logo_domain": "mckinsey.com"},
    {"name": "Deloitte Insights",  "category": "글로벌 컨설팅",
     "url": "https://www2.deloitte.com/us/en/insights/rss.xml",
     "logo_domain": "deloitte.com"},
    {"name": "HBR 디지털·IT",      "category": "글로벌 컨설팅",
     "url": "https://hbr.org/feeds/topics/information-technology.rss",
     "logo_domain": "hbr.org"},
    {"name": "MIT Sloan Review",   "category": "글로벌 컨설팅",
     "url": "https://sloanreview.mit.edu/topic/technology-innovation/feed/",
     "logo_domain": "sloanreview.mit.edu"},
    {"name": "World Economic Forum","category": "글로벌 컨설팅",
     "url": "https://www.weforum.org/agenda/feed/",
     "logo_domain": "weforum.org"},

    # ── 한국 대기업 기술 블로그 ───────────────────────────
    {"name": "LG CNS Blog",        "category": "한국 대기업",
     "url": "https://blog.lgcns.com/rss",
     "logo_domain": "lgcns.com"},
    {"name": "SK C&C 기술블로그",   "category": "한국 대기업",
     "url": gnews("SK C&C AI 클라우드 DX 기술"),
     "logo_domain": "skcc.com"},

    # ── 플랫폼·테크 기업 블로그 ──────────────────────────
    {"name": "Naver D2",           "category": "플랫폼 테크",
     "url": "https://d2.naver.com/d2.atom",
     "logo_domain": "naver.com"},
    {"name": "Kakao Tech",         "category": "플랫폼 테크",
     "url": "https://tech.kakao.com/feed",
     "logo_domain": "kakao.com"},
    {"name": "Toss Tech",          "category": "플랫폼 테크",
     "url": "https://toss.tech/rss.xml",
     "logo_domain": "toss.im"},
    {"name": "당근마켓 Tech",       "category": "플랫폼 테크",
     "url": "https://medium.com/feed/daangn",
     "logo_domain": "daangn.com"},
    {"name": "라인 엔지니어링",     "category": "플랫폼 테크",
     "url": "https://engineering.linecorp.com/ko/feed/",
     "logo_domain": "linecorp.com"},
    {"name": "쿠팡 Engineering",    "category": "플랫폼 테크",
     "url": "https://medium.com/feed/coupang-engineering",
     "logo_domain": "coupang.com"},
    {"name": "우아한형제들",        "category": "플랫폼 테크",
     "url": "https://techblog.woowahan.com/feed/",
     "logo_domain": "woowahan.com"},
    {"name": "뱅크샐러드 Tech",     "category": "플랫폼 테크",
     "url": "https://blog.banksalad.com/feed.xml",
     "logo_domain": "banksalad.com"},
    {"name": "29CM 기술블로그",     "category": "플랫폼 테크",
     "url": "https://medium.com/feed/29cm",
     "logo_domain": "29cm.co.kr"},

    # ── IT 미디어 ─────────────────────────────────────────
    {"name": "블로터",             "category": "IT 미디어",
     "url": "https://www.bloter.net/feed",
     "logo_domain": "bloter.net"},
    {"name": "전자신문",           "category": "IT 미디어",
     "url": "https://www.etnews.com/rss/allArticleRss.xml",
     "logo_domain": "etnews.com"},
    {"name": "아이뉴스24",         "category": "IT 미디어",
     "url": "https://www.inews24.com/rss/allArticle.xml",
     "logo_domain": "inews24.com"},
    {"name": "디지털타임스",       "category": "IT 미디어",
     "url": "https://www.dt.co.kr/rss/all.xml",
     "logo_domain": "dt.co.kr"},
    {"name": "지디넷코리아",       "category": "IT 미디어",
     "url": "https://zdnet.co.kr/rss/",
     "logo_domain": "zdnet.co.kr"},
]

# ════════════════════════════════════════════════════════════
# Google News RSS — 직접 RSS가 없는 소스
# ════════════════════════════════════════════════════════════
GNEWS_SOURCES = [
    # 글로벌 컨설팅 (영문 쿼리가 더 잘 됨)
    {"name": "BCG",      "category": "글로벌 컨설팅",
     "url": gnews_en("BCG Boston Consulting Group AI strategy report"),
     "logo_domain": "bcg.com"},
    {"name": "KPMG",     "category": "글로벌 컨설팅",
     "url": gnews_en("KPMG AI digital transformation report"),
     "logo_domain": "kpmg.com"},
    {"name": "PwC",      "category": "글로벌 컨설팅",
     "url": gnews_en("PwC AI technology report insights"),
     "logo_domain": "pwc.com"},
    {"name": "EY",       "category": "글로벌 컨설팅",
     "url": gnews_en("EY Ernst Young AI digital transformation"),
     "logo_domain": "ey.com"},
    {"name": "Accenture","category": "글로벌 컨설팅",
     "url": gnews_en("Accenture AI generative technology report"),
     "logo_domain": "accenture.com"},
    {"name": "Gartner",  "category": "글로벌 컨설팅",
     "url": gnews_en("Gartner AI technology trend 2025"),
     "logo_domain": "gartner.com"},
    {"name": "Forrester","category": "글로벌 컨설팅",
     "url": gnews_en("Forrester AI digital enterprise report"),
     "logo_domain": "forrester.com"},

    # 한국 대기업
    {"name": "Samsung SDS", "category": "한국 대기업",
     "url": gnews("삼성SDS AI 클라우드 인사이트"),
     "logo_domain": "samsungsds.com"},
    {"name": "SK AX",       "category": "한국 대기업",
     "url": gnews("SK AX SKAX AI 디지털"),
     "logo_domain": "skax.co.kr"},
    {"name": "KT Enterprise","category": "한국 대기업",
     "url": gnews("KT AI 클라우드 디지털전환 기업"),
     "logo_domain": "kt.com"},
    {"name": "LG CNS",      "category": "한국 대기업",
     "url": gnews("LG CNS AI DX 클라우드"),
     "logo_domain": "lgcns.com"},
    {"name": "현대오토에버", "category": "한국 대기업",
     "url": gnews("현대오토에버 AI IT 클라우드"),
     "logo_domain": "hyundai-autoever.com"},
    {"name": "롯데이노베이트","category": "한국 대기업",
     "url": gnews("롯데이노베이트 AI DX 클라우드"),
     "logo_domain": "lotteinnovate.com"},

    # 플랫폼
    {"name": "Naver AI",    "category": "플랫폼 테크",
     "url": gnews("네이버 HyperCLOVA AI 기술 서비스"),
     "logo_domain": "naver.com"},
    {"name": "Kakao",       "category": "플랫폼 테크",
     "url": gnews("카카오 AI 기술 서비스 개발"),
     "logo_domain": "kakao.com"},

    # IT 미디어
    {"name": "IT조선",      "category": "IT 미디어",
     "url": gnews("IT조선 인공지능 AI 디지털"),
     "logo_domain": "it.chosun.com"},
    {"name": "인공지능신문", "category": "IT 미디어",
     "url": gnews("인공지능신문 AI LLM 생성형"),
     "logo_domain": "aitimes.kr"},
    {"name": "AI타임즈",    "category": "IT 미디어",
     "url": gnews("AI타임즈 인공지능 기술"),
     "logo_domain": "aitimes.com"},
    {"name": "테크크런치",  "category": "IT 미디어",
     "url": gnews_en("TechCrunch AI startup funding"),
     "logo_domain": "techcrunch.com"},
    {"name": "The Verge AI","category": "IT 미디어",
     "url": gnews_en("The Verge AI technology news"),
     "logo_domain": "theverge.com"},
]

# ── 직접 웹 스크래핑 소스 ────────────────────────────────
WEB_SOURCES = [
    {
        "name": "Samsung SDS 인사이트",
        "category": "한국 대기업",
        "url": "https://www.samsungsds.com/kr/insights/index.html",
        "logo_domain": "samsungsds.com",
        "link_pattern": "/kr/insights/",
        "exclude_pattern": "index",
    },
]


def _clean_text(html: str, max_len: int = 500) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(separator=" ")
    return " ".join(text.split())[:max_len]


def _parse_entry(entry: dict, source: dict, cutoff=None) -> dict | None:
    """RSS 엔트리 → 아티클 dict 변환. cutoff 이전이면 None 반환."""
    title = entry.get("title", "").strip()
    if not title:
        return None

    pub_date = None
    if getattr(entry, "published_parsed", None):
        try:
            pub_date = datetime(*entry.published_parsed[:6])
        except Exception:
            pass

    if cutoff and pub_date and pub_date < cutoff:
        return None

    raw = entry.get("summary") or entry.get("description") or ""
    return {
        "source":      source["name"],
        "category":    source["category"],
        "title":       title,
        "url":         entry.get("link", ""),
        "summary":     _clean_text(raw),
        "published":   pub_date.strftime("%Y-%m-%d %H:%M") if pub_date
                       else datetime.now().strftime("%Y-%m-%d %H:%M"),
        "logo_domain": source.get("logo_domain", ""),
    }


async def _fetch_rss(client: httpx.AsyncClient, source: dict) -> list[dict]:
    articles = []
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        feed   = feedparser.parse(resp.text)
        cutoff = datetime.now() - timedelta(days=14)  # 14일 컷오프

        for entry in feed.entries[:30]:
            art = _parse_entry(entry, source, cutoff=cutoff)
            if art:
                articles.append(art)
                if len(articles) >= MAX_PER_SOURCE:
                    break

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개")
        else:
            print(f"  - {source['name']}: 최근 기사 없음")
    except Exception as e:
        print(f"  ✗ {source['name']}: {str(e)[:80]}")

    return articles


async def _fetch_rss_fallback(client: httpx.AsyncClient, source: dict) -> list[dict]:
    """날짜 제한 없이 최신 글 1개 — 보장 소스 폴백 전용"""
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:10]:
            art = _parse_entry(entry, source, cutoff=None)
            if art:
                print(f"  ↩ {source['name']}: 폴백 1개 (날짜 무관 최신)")
                return [art]
    except Exception as e:
        print(f"  ✗ {source['name']} 폴백 실패: {str(e)[:80]}")
    return []


async def _fetch_web(client: httpx.AsyncClient, source: dict) -> list[dict]:
    articles = []
    try:
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        soup    = BeautifulSoup(resp.text, "html.parser")
        seen    = set()
        base    = "https://" + source["url"].split("/")[2]
        pattern = source.get("link_pattern", "")
        exclude = source.get("exclude_pattern", "")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("/"): href = base + href
            elif not href.startswith("http"): continue
            if pattern and pattern not in href: continue
            if exclude and exclude in href.split("/")[-1]: continue
            if href in seen: continue

            title = ""
            for tag in a_tag.find_all(["h2","h3","h4","strong","p","span"]):
                t = tag.get_text(strip=True)
                if len(t) > len(title): title = t
            if not title: title = a_tag.get_text(strip=True)
            if len(title) < 10 or len(title) > 200: continue

            seen.add(href)
            articles.append({
                "source":     source["name"],
                "category":   source["category"],
                "title":      title,
                "url":        href,
                "summary":    "",
                "published":  datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "logo_domain": source.get("logo_domain", ""),
            })
            if len(articles) >= MAX_PER_SOURCE: break

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개 (웹)")
        else:
            print(f"  - {source['name']}: 아티클 없음 (웹)")
    except Exception as e:
        print(f"  ✗ {source['name']}: {str(e)[:80]}")
    return articles


async def fetch_all_sources() -> list[dict]:
    all_rss = DIRECT_RSS + GNEWS_SOURCES
    print(f"\n[크롤링 시작] RSS {len(all_rss)}개 + 웹 {len(WEB_SOURCES)}개 소스")

    async with httpx.AsyncClient(headers=HEADERS) as client:
        results = await asyncio.gather(
            *[_fetch_rss(client, src) for src in all_rss],
            *[_fetch_web(client, src) for src in WEB_SOURCES],
        )

    all_articles = [a for batch in results for a in batch]

    # ── 보장 소스 폴백 ────────────────────────────────────────
    # 수집된 소스 이름 집합
    present_sources = {a["source"] for a in all_articles}

    # 그룹별로 하나도 없는 경우 폴백 대상 선정
    # (같은 회사 소스가 여러 개면 하나라도 있으면 OK)
    src_map = {s["name"]: s for s in all_rss + WEB_SOURCES}
    fallback_targets = []
    missing_groups   = []

    for group_name, source_names in GUARANTEED_GROUPS.items():
        if not source_names & present_sources:          # 그룹 내 소스가 하나도 없음
            missing_groups.append(group_name)
            # 그룹 내 소스 중 RSS/Web 정의가 있는 첫 번째를 폴백 대상으로
            for sname in source_names:
                if sname in src_map:
                    fallback_targets.append(src_map[sname])
                    break

    if fallback_targets:
        print(f"\n[보장 소스 폴백] 누락 그룹: {', '.join(missing_groups)}")
        print(f"  → {len(fallback_targets)}개 소스 날짜 무관 재시도...")
        async with httpx.AsyncClient(headers=HEADERS) as client2:
            fb_results = await asyncio.gather(
                *[_fetch_rss_fallback(client2, src) for src in fallback_targets]
            )
        for batch in fb_results:
            all_articles.extend(batch)
    else:
        print(f"\n[보장 소스] 모든 그룹 정상 수집 ✓")

    # ── 수집 요약 ─────────────────────────────────────────────
    from collections import Counter
    cat_counts = Counter(a["category"] for a in all_articles)
    src_counts = Counter(a["source"]   for a in all_articles)
    print(f"\n총 {len(all_articles)}개 아티클 수집 완료")
    for cat, cnt in sorted(cat_counts.items()):
        print(f"  {cat}: {cnt}개")
    print(f"\n소스별 수집 현황:")
    for src, cnt in sorted(src_counts.items(), key=lambda x: -x[1]):
        guaranteed_mark = " ★" if any(src in v for v in GUARANTEED_GROUPS.values()) else ""
        print(f"  {src}: {cnt}개{guaranteed_mark}")
    print()
    return all_articles
