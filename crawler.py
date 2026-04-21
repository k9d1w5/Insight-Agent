"""
crawler.py - 주요 컨설팅펌 및 테크 기업 RSS/웹 크롤러
* 글로벌 컨설팅·한국 대기업·플랫폼 테크 → 회사 공식 사이트에서 직접 수집
* IT 미디어 → RSS/Google News
"""
import feedparser
import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import quote

KST = timezone(timedelta(hours=9))

MAX_PER_SOURCE = 5   # 소스당 최대 아티클

# ════════════════════════════════════════════════════════════
# 보장 소스: 날짜에 관계없이 매일 최소 1개 반드시 포함
# 같은 회사의 소스가 여러 개면 하나라도 있으면 OK
# ════════════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

def gnews(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"

def gnews_en(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en&gl=US&ceid=US:en"


GUARANTEED_GROUPS = {
    # 글로벌 컨설팅
    "McKinsey":   {"McKinsey & Company"},
    "Deloitte":   {"Deloitte Insights"},
    "BCG":        {"BCG"},
    "PwC":        {"PwC"},
    "KPMG":       {"KPMG"},
    "EY":         {"EY"},
    "Accenture":  {"Accenture"},
    "Gartner":    {"Gartner"},
    "Forrester":  {"Forrester"},
    # 한국 대기업
    "Samsung SDS": {"Samsung SDS 인사이트", "Samsung SDS GN"},
    "LG CNS":      {"LG CNS Blog"},
    "SK AX":       {"SK AX", "SK AX GN"},
    "KT":          {"KT Enterprise"},
    "현대오토에버": {"현대오토에버", "현대오토에버 GN"},
    "에커튼":       {"에커튼파트너스"},
}

# JS 렌더링으로 웹 스크래핑이 안 될 경우를 위한 Google News 폴백 소스
GNEWS_CORP_FALLBACK = [
    {"name": "Samsung SDS GN", "category": "한국 대기업",
     "url": gnews("삼성SDS 인사이트 AI 클라우드 DX 기술"),
     "logo_domain": "samsungsds.com"},
    {"name": "SK AX GN", "category": "한국 대기업",
     "url": gnews("SK AX SKAX AI 디지털전환 인사이트"),
     "logo_domain": "skax.co.kr"},
    {"name": "현대오토에버 GN", "category": "한국 대기업",
     "url": gnews("현대오토에버 AI IT 기술 인사이트"),
     "logo_domain": "hyundai-autoever.com"},
]


# ════════════════════════════════════════════════════════════
# 직접 RSS — 회사 공식 RSS 피드
# ════════════════════════════════════════════════════════════
DIRECT_RSS = [
    # ── 글로벌 컨설팅 (공식 RSS) ────────────────────────────
    {"name": "McKinsey & Company", "category": "글로벌 컨설팅",
     "url": "https://www.mckinsey.com/insights/rss",
     "logo_domain": "mckinsey.com"},
    {"name": "Deloitte Insights",  "category": "글로벌 컨설팅",
     "url": "https://www2.deloitte.com/us/en/insights/rss.xml",
     "logo_domain": "deloitte.com"},
    {"name": "BCG",                "category": "글로벌 컨설팅",
     "url": "https://www.bcg.com/rss/publications.xml",
     "logo_domain": "bcg.com"},
    {"name": "Accenture",          "category": "글로벌 컨설팅",
     "url": "https://newsroom.accenture.com/rss/rss.rss",
     "logo_domain": "accenture.com"},
    {"name": "Gartner",            "category": "글로벌 컨설팅",
     "url": "https://www.gartner.com/en/newsroom/press-releases.xml",
     "logo_domain": "gartner.com"},
    {"name": "Forrester",          "category": "글로벌 컨설팅",
     "url": "https://www.forrester.com/blogs/feed/",
     "logo_domain": "forrester.com"},
    {"name": "HBR 디지털·IT",      "category": "글로벌 컨설팅",
     "url": "https://hbr.org/feeds/topics/information-technology.rss",
     "logo_domain": "hbr.org"},
    {"name": "MIT Sloan Review",   "category": "글로벌 컨설팅",
     "url": "https://sloanreview.mit.edu/topic/technology-innovation/feed/",
     "logo_domain": "sloanreview.mit.edu"},

    # ── 한국 대기업 (공식 블로그 RSS) ───────────────────────
    {"name": "LG CNS Blog",        "category": "한국 대기업",
     "url": "https://blog.lgcns.com/rss",
     "logo_domain": "lgcns.com"},

    # ── 플랫폼 테크 (공식 기술 블로그 RSS) ──────────────────
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
    {"name": "쿠팡 Engineering",    "category": "플랫폼 테크",
     "url": "https://medium.com/feed/coupang-engineering",
     "logo_domain": "coupang.com"},

    # ── IT 미디어 (직접 RSS) ─────────────────────────────────
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
# Google News RSS
# — RSS가 없는 컨설팅사는 site: 연산자로 공식 사이트 글만 수집
# — IT 미디어는 일반 뉴스 검색
# ════════════════════════════════════════════════════════════
GNEWS_SOURCES = [
    # 글로벌 컨설팅 — 공식 사이트 글만 (site: 연산자)
    {"name": "PwC",  "category": "글로벌 컨설팅",
     "url": gnews_en("site:pwc.com AI technology insights"),
     "logo_domain": "pwc.com"},
    {"name": "KPMG", "category": "글로벌 컨설팅",
     "url": gnews_en("site:kpmg.com AI digital transformation insights"),
     "logo_domain": "kpmg.com"},
    {"name": "EY",   "category": "글로벌 컨설팅",
     "url": gnews_en("site:ey.com AI technology insights"),
     "logo_domain": "ey.com"},

    # 국내 연구기관 — Google News (공식 사이트 위주)
    {"name": "IITP", "category": "국내 연구기관",
     "url": gnews("IITP 정보통신기획평가원 AI ICT 기술동향"),
     "logo_domain": "iitp.kr"},
    {"name": "NIA",  "category": "국내 연구기관",
     "url": gnews("NIA 한국지능정보사회진흥원 AI 디지털"),
     "logo_domain": "nia.or.kr"},

    # IT 미디어 — 뉴스 기사 수집
    {"name": "IT조선",      "category": "IT 미디어",
     "url": gnews("IT조선 인공지능 AI 디지털"),
     "logo_domain": "it.chosun.com"},
    {"name": "인공지능신문", "category": "IT 미디어",
     "url": gnews("인공지능신문 AI LLM 생성형"),
     "logo_domain": "aitimes.kr"},
    {"name": "AI타임즈",    "category": "IT 미디어",
     "url": gnews("AI타임즈 인공지능 기술"),
     "logo_domain": "aitimes.com"},
    {"name": "TechCrunch",  "category": "IT 미디어",
     "url": gnews_en("TechCrunch AI startup technology enterprise"),
     "logo_domain": "techcrunch.com"},
]


# ════════════════════════════════════════════════════════════
# 직접 웹 스크래핑 — 공식 인사이트 페이지
# ════════════════════════════════════════════════════════════
WEB_SOURCES = [
    # ── 한국 대기업 인사이트 페이지 직접 스크래핑 ────────────
    # ※ JS 렌더링 사이트(삼성SDS·SK AX·현대오토에버)는 정적 HTML만
    #   가져오므로 아티클이 없을 수 있음 → GUARANTEED_GROUPS 폴백 적용
    {
        "name": "Samsung SDS 인사이트", "category": "한국 대기업",
        "url": "https://www.samsungsds.com/kr/insights/index.html",
        "logo_domain": "samsungsds.com",
        "link_pattern": "/kr/insights/", "exclude_pattern": "index",
    },
    {
        "name": "SK AX", "category": "한국 대기업",
        "url": "https://www.skax.co.kr/insight/trends",
        "logo_domain": "skax.co.kr",
        "link_pattern": "/insight/", "exclude_pattern": "",
    },
    {
        "name": "KT Enterprise", "category": "한국 대기업",
        "url": "https://enterprise.kt.com/bt/dBoxing.do?tId=506",
        "logo_domain": "kt.com",
        "link_pattern": "enterprise.kt.com", "exclude_pattern": "dBoxing",
    },
    {
        "name": "현대오토에버", "category": "한국 대기업",
        "url": "https://www.hyundai-autoever.com/kor/about/pr/insights/list.do",
        "logo_domain": "hyundai-autoever.com",
        "link_pattern": "/insights/", "exclude_pattern": "list",
    },
    {
        "name": "에커튼파트너스", "category": "한국 대기업",
        "url": "https://www.ackerton.com/insightReport",
        "logo_domain": "ackerton.com",
        "link_pattern": "/insightReport", "exclude_pattern": "",
    },
]


# ════════════════════════════════════════════════════════════
# 크롤링 함수
# ════════════════════════════════════════════════════════════

def _clean_text(html: str, max_len: int = 500) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(separator=" ")
    return " ".join(text.split())[:max_len]


def _parse_entry(entry, source: dict, cutoff=None) -> dict | None:
    """RSS 엔트리 → 아티클 dict. cutoff 이전이면 None."""
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
        cutoff = datetime.now() - timedelta(days=14)

        for entry in feed.entries[:30]:
            art = _parse_entry(entry, source, cutoff=cutoff)
            if art:
                articles.append(art)
                if len(articles) >= MAX_PER_SOURCE:
                    break

        if articles:
            print(f"  ✓ {source['name']}: {len(articles)}개")
        else:
            print(f"  - {source['name']}: 최근 기사 없음 (14일 내)")
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
                "source":      source["name"],
                "category":    source["category"],
                "title":       title,
                "url":         href,
                "summary":     "",
                "published":   datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
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

    # ── JS 렌더링 대기업 폴백: 웹 스크래핑 실패 시 Google News 사용 ──
    web_src_names   = {s["name"] for s in WEB_SOURCES}
    present_sources = {a["source"] for a in all_articles}
    gn_fallback_needed = [
        src for src in GNEWS_CORP_FALLBACK
        # GN 폴백 이름의 "원본 소스"가 수집 안 됐을 때만 실행
        if src["name"].replace(" GN", " 인사이트") not in present_sources
        and src["name"].replace(" GN", "") not in present_sources
        and src["name"] not in present_sources
    ]
    if gn_fallback_needed:
        names = [s["name"].replace(" GN", "") for s in gn_fallback_needed]
        print(f"\n[대기업 GN 폴백] JS 렌더링으로 스크래핑 실패 → Google News 대체: {', '.join(names)}")
        async with httpx.AsyncClient(headers=HEADERS) as client_gn:
            gn_results = await asyncio.gather(
                *[_fetch_rss(client_gn, src) for src in gn_fallback_needed]
            )
        for batch in gn_results:
            all_articles.extend(batch)

    # ── 보장 소스 최종 폴백 (RSS 소스용 — 날짜 무관 최신 1개) ───
    present_sources = {a["source"] for a in all_articles}
    rss_src_map = {s["name"]: s for s in all_rss}

    fallback_targets = []
    missing_groups   = []
    for group_name, source_names in GUARANTEED_GROUPS.items():
        if not source_names & present_sources:
            missing_groups.append(group_name)
            # RSS 소스만 날짜 무관 폴백 가능
            for sname in source_names:
                if sname in rss_src_map:
                    fallback_targets.append(rss_src_map[sname])
                    break

    if fallback_targets:
        print(f"\n[보장 소스 RSS 폴백] 누락: {', '.join(missing_groups)}")
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
    print(f"\n총 {len(all_articles)}개 아티클 수집")
    for cat, cnt in sorted(cat_counts.items()):
        print(f"  {cat}: {cnt}개")
    print(f"\n소스별:")
    for src, cnt in sorted(src_counts.items(), key=lambda x: -x[1]):
        mark = " ★" if any(src in v for v in GUARANTEED_GROUPS.values()) else ""
        print(f"  {src}: {cnt}개{mark}")
    print()
    return all_articles
