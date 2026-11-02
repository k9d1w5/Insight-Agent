"""
crawler.py - 국내(한글) IT 소스 RSS/웹 크롤러
* 한국 대기업·플랫폼 테크 → 회사 공식 사이트에서 직접 수집
* IT 미디어·국내 연구기관 → RSS/Google News
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


GUARANTEED_GROUPS = {
    # 컨설팅펌
    "삼일PwC":     {"삼일PwC"},
    "삼정KPMG":    {"삼정KPMG"},
    "딜로이트 안진": {"딜로이트 안진"},
    # 한국 대기업
    "Samsung SDS": {"Samsung SDS 인사이트", "Samsung SDS GN"},
    "LG CNS":      {"LG CNS 인사이트", "LG CNS GN"},
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
    {"name": "LG CNS GN", "category": "한국 대기업",
     "url": gnews("LG CNS AI 클라우드 DX"),
     "logo_domain": "lgcns.com"},
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

    # ── IT 미디어 (직접 RSS) ─────────────────────────────────
    {"name": "전자신문",           "category": "IT 미디어",
     "url": "https://rss.etnews.com/Section901.xml",
     "logo_domain": "etnews.com"},
    {"name": "AI타임즈",           "category": "IT 미디어",
     "url": "https://www.aitimes.com/rss/allArticle.xml",
     "logo_domain": "aitimes.com"},
    {"name": "바이라인네트워크",   "category": "IT 미디어",
     "url": "https://byline.network/feed/",
     "logo_domain": "byline.network"},
    {"name": "데이터넷",           "category": "IT 미디어",
     "url": "https://www.datanet.co.kr/rss/allArticle.xml",
     "logo_domain": "datanet.co.kr"},
]


# ════════════════════════════════════════════════════════════
# Google News RSS
# — RSS가 없는 매체는 site: 연산자로 해당 매체 기사만 수집
# ════════════════════════════════════════════════════════════
FIRM_EXCLUDE_TITLE = ["채용", "Newsletter", "뉴스레터", "뉴스룸", "| EY"]

GNEWS_SOURCES = [
    # 컨설팅펌 국내 법인 — 공식 사이트 글만 (site: 연산자)
    {"name": "삼일PwC", "category": "컨설팅펌",
     "url": gnews("site:pwc.com/kr when:14d"),
     "logo_domain": "pwc.com",
     "strip_suffix": "PwC", "exclude_title": FIRM_EXCLUDE_TITLE},
    {"name": "삼정KPMG", "category": "컨설팅펌",
     "url": gnews("site:kpmg.com/kr when:14d"),
     "logo_domain": "kpmg.com",
     "strip_suffix": "kpmg.com", "exclude_title": FIRM_EXCLUDE_TITLE},
    {"name": "딜로이트 안진", "category": "컨설팅펌",
     "url": gnews("site:deloitte.com/kr when:14d"),
     "logo_domain": "deloitte.com",
     "strip_suffix": "Deloitte", "exclude_title": FIRM_EXCLUDE_TITLE},

    # 국내 연구기관 — Google News (공식 사이트 위주)
    {"name": "IITP", "category": "국내 연구기관",
     "url": gnews("IITP 정보통신기획평가원 AI ICT 기술동향"),
     "logo_domain": "iitp.kr"},
    {"name": "NIA",  "category": "국내 연구기관",
     "url": gnews("NIA 한국지능정보사회진흥원 AI 디지털"),
     "logo_domain": "nia.or.kr"},

    # IT 미디어 — RSS가 없는 매체
    {"name": "지디넷코리아", "category": "IT 미디어",
     "url": gnews("site:zdnet.co.kr AI 클라우드"),
     "logo_domain": "zdnet.co.kr"},
    {"name": "IT조선",      "category": "IT 미디어",
     "url": gnews("site:it.chosun.com AI 디지털"),
     "logo_domain": "it.chosun.com"},
]


# ════════════════════════════════════════════════════════════
# 직접 웹 스크래핑 — 공식 인사이트 페이지
# ════════════════════════════════════════════════════════════
WEB_SOURCES = [
    # ── 서버사이드 렌더링 사이트만 httpx로 수집 ─────────────
    # JS 렌더링 사이트(삼성SDS·SK AX·현대오토에버·에커튼)는
    # playwright_crawler.py 에서 별도 처리
    {
        "name": "EY한영", "category": "컨설팅펌",
        "url": "https://www.ey.com/ko_kr/insights",
        "logo_domain": "ey.com",
        "link_pattern": "/ko_kr/insights/",
    },
    {
        "name": "KT Enterprise", "category": "한국 대기업",
        "url": "https://enterprise.kt.com/bt/dBoxing.do?tId=506",
        "logo_domain": "kt.com",
        "link_pattern": "enterprise.kt.com", "exclude_pattern": "dBoxing",
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

    suffix = source.get("strip_suffix")
    if suffix and title.endswith(f" - {suffix}"):
        title = title[:-len(suffix) - 3].strip()
    excludes = source.get("exclude_title")
    # 짧은 제목은 "세무자문"처럼 글이 아닌 서비스 소개 페이지
    if excludes and (len(title) < 10 or any(w in title for w in excludes)):
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

        # Google News는 관련도순이라 최신순으로 정렬해야 새 글이 잘리지 않는다
        entries = sorted(feed.entries, key=lambda e: tuple(e.get("published_parsed") or ()), reverse=True)
        for entry in entries[:30]:
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
        entries = sorted(feed.entries, key=lambda e: tuple(e.get("published_parsed") or ()), reverse=True)
        for entry in entries[:10]:
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
            if title.endswith("이동"): continue  # "메인 페이지로 이동" 같은 내비게이션 링크

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
