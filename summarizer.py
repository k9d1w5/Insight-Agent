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

    prompt = f"""당신은 15년 경력의 IT 전략 컨설팅 전문가입니다.
오늘 수집된 글로벌/국내 주요 IT 인사이트를 분석하여, IT 컨설턴트와 전략사업팀이 실무에 즉시 활용할 수 있는 고품질 일일 리포트를 작성하세요.

=== 오늘의 수집 인사이트 ===
{articles_text}

=== 리포트 작성 지침 ===
- 단순 요약이 아닌, 트렌드 간 연결고리와 전략적 함의를 도출할 것
- 구체적인 수치, 사례, 기업명을 적극 활용할 것
- IT 컨설턴트가 고객사 미팅에서 바로 꺼낼 수 있는 수준으로 작성할 것
- 각 섹션은 충분한 깊이로 작성할 것 (섹션당 최소 3-5문장)

아래 형식으로 작성하세요:

# 📊 오늘의 IT 인사이트 리포트

## 🔍 Executive Summary
(오늘 가장 중요한 메시지 2-3문장. 바쁜 임원이 이것만 읽어도 핵심을 파악할 수 있게)

---

## 1. 오늘의 핵심 트렌드 (Top 3)

### 🥇 트렌드 1: [트렌드명]
- **배경**: 왜 지금 이 트렌드가 부상하는지
- **주요 동향**: 어떤 기업/기관이 무엇을 하고 있는지 구체적으로
- **전망**: 향후 6-12개월 내 어떻게 전개될지

### 🥈 트렌드 2: [트렌드명]
- **배경**:
- **주요 동향**:
- **전망**:

### 🥉 트렌드 3: [트렌드명]
- **배경**:
- **주요 동향**:
- **전망**:

---

## 2. 기관별 포지션 분석

### 🌐 글로벌 컨설팅펌 (McKinsey·BCG·Deloitte·KPMG·PwC·EY·Accenture)
(각 펌이 오늘 강조한 메시지와 공통 화두, 차별점)

### 🏢 한국 대기업 IT (삼성·LG CNS·SK텔레콤·SK AX·KT·POSCO ICT)
(국내 대기업들의 기술 투자 방향과 시장 움직임)

### 📱 플랫폼·테크 기업 (네이버·카카오·토스·배민 등)
(실제 서비스 현장에서 적용 중인 기술 트렌드와 혁신 사례)

---

## 3. IT 컨설턴트 액션 포인트

### 💼 즉시 활용 가능한 고객 미팅 소재
1. [구체적인 소재와 활용법]
2. [구체적인 소재와 활용법]
3. [구체적인 소재와 활용법]

### 📈 신규 사업 기회
(오늘 인사이트에서 발견한 컨설팅/SI 수요 기회)

### ⚠️ 리스크 & 주의 동향
(시장에서 주의 깊게 봐야 할 변화나 위험 신호)

---

## 4. 오늘의 핵심 키워드
(10-15개, 중요도 순으로)

---

## 5. 내일 주목할 이슈
(오늘 트렌드를 바탕으로 내일/이번 주 follow-up 해야 할 사항)"""

    try:
        return _call_claude(prompt, max_tokens=2000)
    except Exception as e:
        print(f"[최종 리포트 생성 오류]: {e}")
        return "최종 리포트 생성 중 오류가 발생했습니다. 개별 아티클 요약을 참고하세요."
