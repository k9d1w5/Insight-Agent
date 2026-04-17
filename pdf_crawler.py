"""
pdf_crawler.py - PDF 자동 탐지·다운로드·텍스트 추출
"""
import os
import re
import json
import hashlib
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[경고] pdfplumber 미설치 - PDF 추출 불가")

KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

TRACKER_FILE = "web/data/downloaded_pdfs.json"
MAX_PDF_PAGES = 15      # 최대 추출 페이지 수
MAX_TEXT_CHARS = 4000   # Claude에 전달할 최대 텍스트 길이


def _load_tracker() -> dict:
    """이미 처리한 PDF 목록 로드"""
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": []}


def _save_tracker(tracker: dict):
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF 바이트에서 텍스트 추출"""
    if not PDF_AVAILABLE:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= MAX_PDF_PAGES:
                    break
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        os.unlink(tmp_path)
        full_text = "\n".join(text_parts)
        return full_text[:MAX_TEXT_CHARS]
    except Exception as e:
        print(f"    [PDF 추출 오류] {e}")
        return ""


def _find_pdf_links(html: str, base_url: str) -> list[dict]:
    """HTML에서 PDF 링크 탐지"""
    soup = BeautifulSoup(html, "html.parser")
    pdf_links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        full_url = urljoin(base_url, href)

        # PDF 링크 판별
        is_pdf = (
            full_url.lower().endswith(".pdf") or
            "pdf" in full_url.lower() or
            "download" in full_url.lower() and ".pdf" in full_url.lower()
        )

        if is_pdf and full_url not in seen:
            seen.add(full_url)
            title = tag.get_text(strip=True) or tag.get("title", "") or "PDF 문서"
            pdf_links.append({"url": full_url, "title": title[:100]})

    return pdf_links[:10]  # 최대 10개


async def crawl_pdf_source(client: httpx.AsyncClient, source: dict, tracker: dict) -> list[dict]:
    """단일 소스에서 PDF 탐지 및 처리"""
    results = []
    source_name = source["name"]

    try:
        # 인사이트 페이지 접속
        resp = await client.get(source["url"], timeout=20.0, follow_redirects=True)
        resp.raise_for_status()

        pdf_links = _find_pdf_links(resp.text, source["url"])

        if not pdf_links:
            print(f"  - {source_name}: PDF 링크 없음")
            return []

        print(f"  ○ {source_name}: PDF {len(pdf_links)}개 발견")

        for pdf_info in pdf_links:
            pdf_url = pdf_info["url"]
            url_id = _url_hash(pdf_url)

            # 이미 처리한 PDF 스킵
            if url_id in tracker["processed"]:
                continue

            try:
                pdf_resp = await client.get(pdf_url, timeout=30.0, follow_redirects=True)
                pdf_resp.raise_for_status()

                # Content-Type 확인
                content_type = pdf_resp.headers.get("content-type", "")
                if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
                    continue

                text = _extract_pdf_text(pdf_resp.content)
                if not text or len(text) < 100:
                    continue

                results.append({
                    "source": source_name,
                    "category": source["category"],
                    "title": pdf_info["title"],
                    "url": pdf_url,
                    "summary": text[:500],
                    "full_text": text,
                    "published": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                    "logo_domain": source.get("logo_domain", ""),
                    "type": "pdf",
                })

                tracker["processed"].append(url_id)
                print(f"    ✓ PDF 추출: {pdf_info['title'][:50]}")

            except Exception as e:
                print(f"    ✗ PDF 다운로드 실패 ({pdf_info['title'][:30]}): {e}")

    except Exception as e:
        print(f"  ✗ {source_name}: {e}")

    return results


async def fetch_pdf_sources(sources: list[dict]) -> list[dict]:
    """PDF 소스 전체 처리"""
    pdf_sources = [s for s in sources if s.get("type") in ("pdf", "web_pdf")]
    if not pdf_sources:
        return []

    print(f"\n[PDF 크롤링 시작] {len(pdf_sources)}개 소스")
    tracker = _load_tracker()
    all_results = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        for source in pdf_sources:
            results = await crawl_pdf_source(client, source, tracker)
            all_results.extend(results)

    _save_tracker(tracker)
    print(f"[PDF 크롤링 완료] 신규 {len(all_results)}개 추출\n")
    return all_results
