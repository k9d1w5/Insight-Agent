"""
main.py - 인사이트 리포트 생성 메인 오케스트레이터
실행: python main.py
"""
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from crawler import fetch_all_sources
from summarizer import summarize_articles, generate_final_report
from pdf_crawler import fetch_pdf_sources
from playwright_crawler import fetch_playwright_sources
from sources_config import ALL_SOURCES

KST = timezone(timedelta(hours=9))  # 한국 시간대

REPORTS_DIR = os.path.join("web", "data", "reports")


def save_report(articles: list[dict], final_report: str) -> str:
    """리포트를 JSON으로 저장하고 파일 경로 반환"""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    today = datetime.now(KST).strftime("%Y-%m-%d")
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    # 카테고리별 통계
    categories = {}
    for a in articles:
        categories[a["category"]] = categories.get(a["category"], 0) + 1

    output = {
        "date": today,
        "generated_at": now_str,
        "total_articles": len(articles),
        "categories": categories,
        "final_report": final_report,
        "articles": articles,
    }

    # 날짜별 파일 저장
    dated_path = os.path.join(REPORTS_DIR, f"{today}.json")
    with open(dated_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # latest.json 갱신
    latest_path = os.path.join(REPORTS_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # index.json 갱신 (과거 리포트 목록)
    index_path = os.path.join(REPORTS_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"reports": []}

    existing_dates = [r["date"] for r in index["reports"]]
    if today not in existing_dates:
        index["reports"].insert(0, {
            "date": today,
            "file": f"{today}.json",
            "total_articles": len(articles),
            "categories": categories,
        })
        index["reports"] = index["reports"][:60]  # 최근 60일

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return dated_path


def main():
    start = datetime.now(KST)
    print("=" * 60)
    print(f"  IT 인사이트 리포트 생성 시작")
    print(f"  {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. RSS/웹 크롤링 (정적 사이트)
    articles = asyncio.run(fetch_all_sources())

    # 1b. Playwright 크롤링 (JS 렌더링 사이트)
    pw_articles = asyncio.run(fetch_playwright_sources())
    if pw_articles:
        print(f"[Playwright] {len(pw_articles)}개 아티클 추가")
        articles = articles + pw_articles

    # 1c. PDF 크롤링 (web_pdf / pdf 타입 소스)
    pdf_articles = asyncio.run(fetch_pdf_sources(ALL_SOURCES))
    if pdf_articles:
        print(f"[PDF] {len(pdf_articles)}개 아티클 추가")
        articles = articles + pdf_articles

    if not articles:
        print("\n수집된 아티클이 없습니다. 종료합니다.")
        return

    # 2. AI 요약
    summarized = summarize_articles(articles)

    # 3. 종합 리포트 생성
    print("[종합 리포트 생성 중...]")
    final_report = generate_final_report(summarized)

    # 4. 저장
    saved_path = save_report(summarized, final_report)

    elapsed = (datetime.now(KST) - start).seconds
    print("\n" + "=" * 60)
    print(f"  완료! ({elapsed}초 소요)")
    print(f"  저장 경로: {saved_path}")
    print(f"  수집 아티클: {len(summarized)}개")
    print("=" * 60)
    print("\n[오늘의 종합 리포트 미리보기]")
    print(final_report[:800])
    print("...")


if __name__ == "__main__":
    main()
