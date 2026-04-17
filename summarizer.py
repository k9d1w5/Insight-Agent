"""
summarizer.py - Claude AI 아티클 요약 + 중요도 점수 + 영문 번역
"""
import os
import re
import time
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL_FAST   = "claude-3-haiku-20240307"     # 개별 요약·번역 (구버전, 전 플랜 지원)
MODEL_STRONG = "claude-3-5-sonnet-20241022"  # 종합 리포트


# ── 헬퍼 ─────────────────────────────────────────────────

def _is_english(text: str) -> bool:
    """텍스트가 주로 영문인지 판별"""
    if not text:
        return False
    alpha      = sum(1 for c in text if c.isalpha())
    ascii_alph = sum(1 for c in text if c.isascii() and c.isalpha())
    return alpha > 0 and (ascii_alph / alpha) > 0.65


def _call_claude(prompt: str, max_tokens: int = 300,
                 model: str = MODEL_FAST, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
        except anthropic.RateLimitError:
            wait = 5 * (2 ** attempt)
            print(f"    [RateLimit] {wait}초 대기...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if "credit" in str(e).lower():
                raise
            wait = 3 * (2 ** attempt)
            print(f"    [API 오류] {wait}초 후 재시도 ({e})")
            time.sleep(wait)
        except Exception as e:
            print(f"    [예외] {e}")
            if attempt == retries - 1:
                raise
            time.sleep(3)
    raise RuntimeError("최대 재시도 초과")


def _parse_response(text: str) -> dict:
    """Claude 응답에서 요약/점수/번역 파싱"""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("요약:"):
            result["ai_summary"] = line[3:].strip()
        elif line.startswith("점수:"):
            nums = re.findall(r'\d+', line[3:])
            if nums:
                result["importance_score"] = min(10, max(1, int(nums[0])))
        elif line.startswith("번역:"):
            result["title_ko"] = line[3:].strip()
    return result


# ── 단일 아티클 요약 ──────────────────────────────────────

def summarize_article(article: dict) -> dict:
    """요약 + 중요도 점수 + 영문 번역 (단일 API 호출)"""
    title = article.get("title", "")
    raw   = article.get("summary", "")

    if not title and not raw:
        article.setdefault("ai_summary", "")
        article.setdefault("importance_score", 0)
        return article

    is_eng = _is_english(title + " " + raw[:100])
    trans_line = "\n번역: [위 기사 제목의 자연스러운 한국어 번역]" if is_eng else ""

    prompt = (
        f"IT 전략 컨설턴트 관점에서 아래 기사를 분석하세요.\n"
        f"출처: {article['source']} | 제목: {title}\n"
        f"내용: {raw[:400]}\n\n"
        f"아래 형식으로 정확히 답하세요 (다른 말 금지):\n"
        f"요약: [IT 컨설팅 관점 2문장 한국어 요약]\n"
        f"점수: [IT 전략적 중요도 1~10 숫자만]"
        f"{trans_line}"
    )

    try:
        raw_resp = _call_claude(prompt, max_tokens=220, model=MODEL_FAST)
        parsed   = _parse_response(raw_resp)

        article["ai_summary"]       = parsed.get("ai_summary", raw[:150] if raw else "")
        article["importance_score"] = parsed.get("importance_score", 5)
        if is_eng and "title_ko" in parsed:
            article["title_ko"] = parsed["title_ko"]

        time.sleep(0.5)

    except Exception as e:
        print(f"    [요약 오류] {title[:40]}: {e}")
        article.setdefault("ai_summary", raw[:150] if raw else "")
        article.setdefault("importance_score", 0)

    return article


# ── 전체 아티클 요약 ──────────────────────────────────────

def summarize_articles(articles: list[dict]) -> list[dict]:
    """상위 30개 AI 요약 후, 전체를 중요도 순 정렬"""
    TOP_N = 30
    print(f"[AI 요약 시작] 전체 {len(articles)}개 중 상위 {TOP_N}개 요약")
    result = []
    consecutive_failures = 0

    for i, article in enumerate(articles, 1):
        if i <= TOP_N:
            print(f"  [{i:02d}] {article['source']}: {article['title'][:45]}...")
            prev_score = article.get("importance_score")
            summarize_article(article)
            if article.get("importance_score", 0) > 0:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    print("  ⚠ API 연속 실패 5회 — 크레딧/키 확인 필요")
        else:
            article.setdefault("ai_summary", "")
            article.setdefault("importance_score", 0)
        result.append(article)

    # 중요도 점수 높은 순 정렬
    result.sort(key=lambda a: a.get("importance_score", 0), reverse=True)

    print(f"[AI 요약 완료]\n")
    return result


# ── 종합 리포트 ───────────────────────────────────────────

def generate_final_report(articles: list[dict]) -> str:
    if not articles:
        return "오늘 수집된 인사이트가 없습니다."

    # 카테고리별 상위 5개 (점수 높은 순)
    by_category: dict[str, list] = {}
    for a in sorted(articles, key=lambda x: x.get("importance_score", 0), reverse=True):
        cat = a["category"]
        if len(by_category.get(cat, [])) < 5:
            by_category.setdefault(cat, []).append(a)

    lines = []
    for cat, items in by_category.items():
        lines.append(f"\n[{cat}]")
        for item in items:
            ai_sum = item.get("ai_summary", "")
            score  = item.get("importance_score", 0)
            title  = item.get("title_ko") or item.get("title", "")
            score_str = f" [중요도 {score}/10]" if score else ""
            summ_str  = f" → {ai_sum[:80]}" if ai_sum else ""
            lines.append(f"- {item['source']}: {title}{score_str}{summ_str}")

    articles_text = "\n".join(lines)

    prompt = f"""당신은 20년 경력의 IT 전략 컨설팅 파트너입니다. 글로벌 컨설팅펌·대기업 IT·플랫폼·미디어 등 다양한 채널에서 수집한 오늘의 인사이트를 종합 분석하여, 컨설팅사업부 소속 IT 컨설턴트와 전략기획·사업전략 담당자가 즉시 활용할 수 있는 고품질 일일 인사이트 리포트를 작성하세요.

[오늘 수집된 인사이트 (중요도 순)]
{articles_text}

**작성 원칙:**
- Executive Summary: 오늘 IT 시장 전반의 거시적 흐름, 핵심 이슈, 전략적 시사점을 전문 컨설턴트 문체로 5문장 이상 작성
- 핵심 트렌드: 특정 기업에 국한하지 않고 여러 출처를 종합해 IT 시장 전체에서 나타나는 거시 트렌드 도출
- 기관별 동향: 개별 기사 나열 금지 — 카테고리 전체에서 나타나는 공통 패턴·화두·전략 방향을 분석
- 액션 포인트: IT 컨설턴트 또는 전략기획·사업전략 담당자 입장에서 제안서·고객미팅·사업기획에 즉시 쓸 수 있는 구체적 인사이트

아래 형식으로 한국어 리포트를 작성하세요:

# 📊 오늘의 IT 인사이트 리포트

## 🔍 Executive Summary
(IT 시장 거시 흐름 + 핵심 이슈 + 전략적 시사점을 전문 컨설턴트 문체로 5문장 이상. 구체적 수치·기업명·기술명을 포함해 깊이 있게 작성)

---

## 1. 핵심 트렌드 Top 3
(여러 출처를 종합한 IT 시장 거시 트렌드. 특정 기업 단독 사례가 아닌 산업 전반의 움직임으로 기술)

### 🥇 [트렌드 제목: 명사구로 간결하게]
(배경·현황·전망·전략적 의미를 5문장 이상 심층 분석. 관련 기업·사례를 복수로 언급)

### 🥈 [트렌드 제목: 명사구로 간결하게]
(배경·현황·전망·전략적 의미를 5문장 이상 심층 분석. 관련 기업·사례를 복수로 언급)

### 🥉 [트렌드 제목: 명사구로 간결하게]
(배경·현황·전망·전략적 의미를 5문장 이상 심층 분석. 관련 기업·사례를 복수로 언급)

---

## 2. 기관별 동향
(각 카테고리 전체의 공통 패턴·전략 방향 분석. 개별 기사 단순 나열 금지)

### 🌐 글로벌 컨설팅펌
(맥킨지·BCG·딜로이트·KPMG·PwC·EY·가트너 등이 공통으로 강조하는 화두, 시장 전망, 권고 방향)

### 🏢 한국 대기업 IT
(삼성SDS·LG CNS·SK AX·KT 등에서 공통으로 나타나는 투자 방향·전략·기술 선택)

### 📱 플랫폼·테크 기업
(네이버·카카오·토스·당근·라인 등에서 나타나는 공통 기술 트렌드·서비스 방향성)

### 📰 IT 미디어 핵심 이슈
(언론이 집중 조명하는 이슈와 배경, 업계 파급효과)

---

## 3. IT 컨설턴트 액션 포인트
(IT 컨설턴트 또는 전략기획·사업전략 담당자가 오늘 바로 활용할 수 있는 인사이트 3가지)

1. **[인사이트 제목]**: (제안서·고객미팅에 활용할 수 있는 구체적 논점과 접근법. 2-3문장)
2. **[인사이트 제목]**: (신규 사업 기회 또는 시장 진입 타이밍과 근거. 2-3문장)
3. **[인사이트 제목]**: (반드시 모니터링해야 할 리스크·경쟁 동향과 대응 방향. 2-3문장)

---

## 4. 오늘의 핵심 키워드
(오늘 IT 시장을 관통하는 키워드 10개를 중요도 순으로, 각각 한 줄 설명 포함)"""

    # 1차: Sonnet
    try:
        print("[종합 리포트 생성 중... Sonnet]")
        result = _call_claude(prompt, max_tokens=2500, model=MODEL_STRONG, retries=2)
        print("[종합 리포트 완료]")
        return result
    except Exception as e:
        print(f"[Sonnet 실패] {e}")

    # 2차: Haiku (프롬프트 축약)
    try:
        short_lines = []
        for cat, items in by_category.items():
            short_lines.append(f"[{cat}]")
            for item in items[:3]:
                title = item.get("title_ko") or item.get("title", "")
                short_lines.append(f"- {item['source']}: {title}")
        short_prompt = prompt.replace(articles_text, "\n".join(short_lines))
        print("[종합 리포트 재시도... Haiku]")
        result = _call_claude(short_prompt, max_tokens=1500, model=MODEL_FAST, retries=2)
        print("[종합 리포트 Haiku 완료]")
        return result
    except Exception as e2:
        print(f"[종합 리포트 최종 실패] {e2}")
        # 폴백: 기사 목록만
        fallback = ["# 📊 오늘의 IT 인사이트 리포트\n",
                    "## ⚠ AI 리포트 생성 실패 — 수집된 기사 목록\n"]
        for cat, items in by_category.items():
            fallback.append(f"## {cat}")
            for item in items:
                title = item.get("title_ko") or item.get("title", "")
                fallback.append(f"- **{item['source']}**: {title}")
            fallback.append("")
        return "\n".join(fallback)
