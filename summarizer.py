"""
summarizer.py - Claude AI를 사용한 아티클 요약 및 종합 리포트 생성
"""
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"


def _call_claude(prompt: str, max_tokens: int = 400) -> str:
    """Claude API 호출 헬퍼"""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def summarize_article(article: dict) -> dict:
    """단일 아티클을 IT 컨설턴트 관점에서 요약"""
    title = article.get("title", "")
    raw = article.get("summary", "")

    if not title and not raw:
        article["ai_summary"] = ""
        return article

    prompt = f"""당신은 IT 전략 컨설턴트입니다. 아래 아티클을 읽고 3문장으로 핵심 요약을 해주세요.
- 어떤 기술/트렌드인지
- 비즈니스 임팩트
- 한국 IT 시장에서의 시사점

출처: {article['source']} ({article['category']})
제목: {title}
내용: {raw[:800]}

요약 (3문장, 한국어):"""

    try:
        article["ai_summary"] = _call_claude(prompt, max_tokens=250)
    except Exception as e:
        print(f"    [요약 오류] {title[:40]}: {e}")
        article["ai_summary"] = raw[:200] if raw else title

    return article


def summarize_articles(articles: list[dict]) -> list[dict]:
    """전체 아티클 순차 요약 (API rate limit 고려)"""
    print(f"[AI 요약 시작] {len(articles)}개 아티클")
    result = []
    for i, article in enumerate(articles, 1):
        short_title = article["title"][:45]
        print(f"  [{i:02d}/{len(articles):02d}] {article['source']}: {short_title}...")
        result.append(summarize_article(article))
    print(f"[AI 요약 완료]\n")
    return result


def generate_final_report(articles: list[dict]) -> str:
    """오늘의 모든 인사이트를 종합한 최종 리포트 생성"""
    if not articles:
        return "오늘 수집된 인사이트가 없습니다."

    # 카테고리별 정리
    by_category: dict[str, list] = {}
    for a in articles:
        by_category.setdefault(a["category"], []).append(a)

    # 프롬프트에 넣을 요약 텍스트 구성
    lines = []
    for cat, items in by_category.items():
        lines.append(f"\n## {cat}")
        for item in items[:6]:  # 카테고리당 최대 6개
            lines.append(f"- [{item['source']}] {item['title']}")
            if item.get("ai_summary"):
                lines.append(f"  → {item['ai_summary'][:180]}")

    articles_text = "\n".join(lines)

    prompt = f"""당신은 IT 전략 컨설팅 전문가입니다.
오늘 수집된 글로벌/국내 주요 IT 인사이트를 바탕으로 IT 컨설턴트와 전략사업팀을 위한 일일 리포트를 작성하세요.

=== 오늘의 수집 인사이트 ===
{articles_text}

=== 리포트 작성 지침 ===
아래 형식으로 전문적이고 실용적인 리포트를 한국어로 작성하세요.

# 오늘의 IT 인사이트 리포트

## 1. 핵심 트렌드 Top 3
(오늘 가장 주목할 만한 기술/비즈니스 트렌드 3가지, 각 2-3문장)

## 2. 산업별 주요 동향
### 글로벌 컨설팅펌 동향
(맥킨지, BCG, 딜로이트 등이 강조하는 키 메시지)

### 한국 대기업 동향
(삼성, LG CNS, SK텔레콤 등의 움직임)

### 플랫폼/테크 기업 동향
(네이버, 카카오, 토스 등의 기술 트렌드)

## 3. IT 컨설턴트 시사점
(프로젝트 제안, 고객 미팅에서 활용할 수 있는 인사이트 3가지)

## 4. 오늘의 핵심 키워드
(콤마로 구분된 7-10개 키워드)"""

    try:
        return _call_claude(prompt, max_tokens=2000)
    except Exception as e:
        print(f"[최종 리포트 생성 오류]: {e}")
        return "최종 리포트 생성 중 오류가 발생했습니다. 개별 아티클 요약을 참고하세요."
