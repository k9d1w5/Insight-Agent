"""
summarizer.py - Claude AI를 사용한 아티클 요약 및 종합 리포트 생성
"""
import os
import time
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"


def _call_claude(prompt: str, max_tokens: int = 400) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def summarize_article(article: dict) -> dict:
    """단일 아티클 AI 요약 (오류 시 원문 요약 사용)"""
    title = article.get("title", "")
    raw = article.get("summary", "")

    if not title and not raw:
        article["ai_summary"] = ""
        return article

    prompt = f"""IT 전략 컨설턴트 관점에서 아래 기사를 2문장으로 요약해주세요.
출처: {article['source']} | 제목: {title}
내용: {raw[:500]}

요약 (한국어, 2문장):"""

    try:
        article["ai_summary"] = _call_claude(prompt, max_tokens=150)
        time.sleep(0.3)  # rate limit 방지
    except Exception as e:
        print(f"    [요약 오류] {title[:40]}: {e}")
        article["ai_summary"] = raw[:150] if raw else ""

    return article


def summarize_articles(articles: list[dict]) -> list[dict]:
    """상위 20개만 AI 요약 (속도·비용 최적화)"""
    print(f"[AI 요약 시작] 전체 {len(articles)}개 중 상위 20개 요약")
    result = []
    for i, article in enumerate(articles, 1):
        if i <= 20:
            print(f"  [{i:02d}] {article['source']}: {article['title'][:45]}...")
            result.append(summarize_article(article))
        else:
            article["ai_summary"] = ""
            result.append(article)
    print(f"[AI 요약 완료]\n")
    return result


def generate_final_report(articles: list[dict]) -> str:
    """오늘의 모든 인사이트를 종합한 최종 리포트"""
    if not articles:
        return "오늘 수집된 인사이트가 없습니다."

    # 카테고리별 정리 (카테고리당 최대 4개)
    by_category: dict[str, list] = {}
    for a in articles:
        cat = a["category"]
        if len(by_category.get(cat, [])) < 4:
            by_category.setdefault(cat, []).append(a)

    # 프롬프트용 텍스트 구성
    lines = []
    for cat, items in by_category.items():
        lines.append(f"\n[{cat}]")
        for item in items:
            lines.append(f"- {item['source']}: {item['title']}")

    articles_text = "\n".join(lines)

    prompt = f"""당신은 15년 경력의 IT 전략 컨설팅 전문가입니다.
오늘 수집된 IT 인사이트를 분석해 IT 컨설턴트와 전략사업팀을 위한 일일 리포트를 작성하세요.

[오늘 수집된 인사이트]
{articles_text}

아래 형식으로 한국어 리포트를 작성하세요:

# 📊 오늘의 IT 인사이트 리포트

## 🔍 Executive Summary
(오늘 가장 중요한 메시지 2-3문장)

---

## 1. 핵심 트렌드 Top 3

### 🥇 트렌드 1: [제목]
배경·동향·전망을 3-4문장으로

### 🥈 트렌드 2: [제목]
배경·동향·전망을 3-4문장으로

### 🥉 트렌드 3: [제목]
배경·동향·전망을 3-4문장으로

---

## 2. 기관별 동향

### 🌐 글로벌 컨설팅펌
(맥킨지·BCG·딜로이트 등의 공통 화두와 핵심 메시지)

### 🏢 한국 대기업 IT
(삼성·LG CNS·SK텔레콤·KT 등의 움직임)

### 📱 플랫폼·테크 기업
(네이버·카카오·토스·배민 등의 기술 트렌드)

---

## 3. IT 컨설턴트 액션 포인트
1. [고객 미팅 소재 및 활용법]
2. [신규 사업 기회]
3. [주의 동향]

---

## 4. 오늘의 핵심 키워드
(10개, 중요도 순)"""

    try:
        print("[종합 리포트 생성 중...]")
        result = _call_claude(prompt, max_tokens=3000)
        print("[종합 리포트 생성 완료]")
        return result
    except Exception as e:
        print(f"[종합 리포트 오류] {type(e).__name__}: {e}")
        # 프롬프트 축약 후 재시도
        try:
            short_lines = []
            for cat, items in by_category.items():
                short_lines.append(f"[{cat}]")
                for item in items[:2]:
                    short_lines.append(f"- {item['source']}: {item['title']}")
            short_prompt = prompt.replace(articles_text, "\n".join(short_lines))
            print("[종합 리포트 재시도 중...]")
            return _call_claude(short_prompt, max_tokens=2000)
        except Exception as e2:
            print(f"[종합 리포트 재시도 오류] {e2}")
            return "최종 리포트 생성 중 오류가 발생했습니다. 개별 아티클 요약을 참고하세요."
