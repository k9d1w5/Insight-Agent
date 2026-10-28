"""
trends.py - 누적 리포트에서 토픽별 트렌드를 계산해 web/data/trends.json 생성
실행: python trends.py  (main.py 실행 후)

- 이번 주: 기준일 포함 최근 7일
- 비교 기준: 그 직전 4주의 주평균
- 추이: 최근 12주 주간 건수
"""
import glob
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
REPORTS_DIR = os.path.join("web", "data", "reports")
OUT_PATH = os.path.join("web", "data", "trends.json")
TOPICS_PATH = "topics.json"

WEEK = 7
BASELINE_WEEKS = 4
SERIES_WEEKS = 12
NEW_KW_LOOKBACK_DAYS = 90
MIN_COUNT_FOR_GROWTH = 2
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_reports() -> list[dict]:
    reports = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json"))):
        if DATE_RE.match(os.path.splitext(os.path.basename(path))[0]):
            with open(path, encoding="utf-8") as f:
                reports.append(json.load(f))
    return reports


def compile_keywords(keywords: list[str]):
    out = []
    for kw in keywords:
        kw_l = kw.lower()
        if kw_l.isascii():
            out.append((kw, re.compile(r"(?<![a-z0-9])" + re.escape(kw_l) + r"(?![a-z0-9])")))
        else:
            out.append((kw, kw_l))
    return out


def find(text_l: str, pats) -> list[str]:
    return [kw for kw, p in pats if (p.search(text_l) if isinstance(p, re.Pattern) else p in text_l)]


def classify(text: str, matchers) -> dict[str, list[str]]:
    text_l = text.lower()
    hits = {}
    for tid, pats, _ in matchers:
        kws = find(text_l, pats)
        if kws:
            hits[tid] = kws
    if not hits:
        for tid, _, fallback in matchers:
            kws = find(text_l, fallback)
            if kws:
                hits[tid] = kws
    return hits


def parse_day(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s and len(s) >= 10 else None
    except ValueError:
        return None


def collect_articles(reports: list[dict], ref: date) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in reports:
        first_seen = parse_day(r.get("date"))
        for a in r.get("articles", []):
            key = a.get("url") or (a.get("source", "") + a.get("title", ""))
            if not key or key in seen:
                continue
            pub = parse_day(a.get("published"))
            # 게시일이 없거나 미래면 처음 수집된 날로 대체
            day = pub if pub and pub <= ref else first_seen
            if day:
                seen[key] = {**a, "_day": day}
    return list(seen.values())


def main():
    with open(TOPICS_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    topics = cfg["topics"]
    weights = cfg.get("source_weights", {})
    matchers = [(t["id"], compile_keywords(t["keywords"]), compile_keywords(t.get("fallback_keywords", [])))
                for t in topics]

    reports = load_reports()
    if not reports:
        print("[trends] 리포트가 없습니다.")
        return
    ref = parse_day(reports[-1]["date"])
    history_days = (ref - parse_day(reports[0]["date"])).days + 1

    week_start = ref - timedelta(days=WEEK - 1)
    base_start = week_start - timedelta(days=WEEK * BASELINE_WEEKS)
    series_start = ref - timedelta(days=WEEK * SERIES_WEEKS - 1)
    kw_start = week_start - timedelta(days=NEW_KW_LOOKBACK_DAYS)

    def week_index(d: date) -> int:
        return (d - series_start).days // WEEK

    stats = {t["id"]: {"week": [], "baseline": 0, "sources": set(), "weighted": 0.0,
                       "series": [0] * SERIES_WEEKS, "keywords": {}} for t in topics}
    kw_week: dict[str, int] = {}
    kw_before: set[str] = set()
    feed = []

    for a in collect_articles(reports, ref):
        day = a["_day"]
        hits = classify(f"{a.get('title', '')} {a.get('summary', '')}", matchers)
        a["_topics"] = list(hits)
        all_kws = {k for kws in hits.values() for k in kws}

        if day >= week_start:
            feed.append(a)
            for k in all_kws:
                kw_week[k] = kw_week.get(k, 0) + 1
        elif day >= kw_start:
            kw_before.update(all_kws)

        for tid, kws in hits.items():
            s = stats[tid]
            if day >= series_start:
                s["series"][week_index(day)] += 1
            if day >= week_start:
                s["week"].append(a)
                s["sources"].add(a.get("source", ""))
                s["weighted"] += weights.get(a.get("category"), 1.0)
                for k in kws:
                    s["keywords"][k] = s["keywords"].get(k, 0) + 1
            elif day >= base_start:
                s["baseline"] += 1

    def slim(a: dict) -> dict:
        return {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("source", ""),
            "category": a.get("category", ""),
            "summary": (a.get("summary") or "")[:220],
            "date": a["_day"].isoformat(),
            "logo_domain": a.get("logo_domain", ""),
            "topics": a["_topics"],
        }

    def rank(a: dict):
        return (a["_day"], weights.get(a.get("category"), 1.0))

    has_baseline = history_days >= WEEK * (BASELINE_WEEKS + 1)
    topic_out = []
    for t in topics:
        s = stats[t["id"]]
        count = len(s["week"])
        avg = s["baseline"] / BASELINE_WEEKS
        if not has_baseline or count < MIN_COUNT_FOR_GROWTH:
            growth = None
        elif avg < 0.5:
            growth = "new"
        else:
            growth = round((count - avg) / avg * 100)
        spread = len(s["sources"])
        g = 150 if growth == "new" else (growth or 0)
        score = s["weighted"] + 1.5 * spread + min(max(g, -100), 300) / 50 if count else 0
        topic_out.append({
            "id": t["id"],
            "name": t["name"],
            "count": count,
            "baseline_avg": round(avg, 1),
            "growth_pct": growth,
            "spread": spread,
            "sources": sorted(s["sources"]),
            "score": round(score, 2),
            "keywords": [k for k, _ in sorted(s["keywords"].items(), key=lambda kv: -kv[1])[:5]],
            "series": s["series"],
            "articles": [slim(a) for a in sorted(s["week"], key=rank, reverse=True)[:15]],
        })
    topic_out.sort(key=lambda x: -x["score"])
    rising = [t["id"] for t in topic_out
              if t["growth_pct"] == "new" or (isinstance(t["growth_pct"], int) and t["growth_pct"] >= 10)]
    top = (rising + [t["id"] for t in topic_out if t["count"] and t["id"] not in rising])[:3]

    new_keywords = []
    if history_days >= NEW_KW_LOOKBACK_DAYS:
        new_keywords = [k for k, c in sorted(kw_week.items(), key=lambda kv: -kv[1])
                        if k not in kw_before and c >= 2][:8]

    feed.sort(key=rank, reverse=True)
    series_labels = [(series_start + timedelta(days=WEEK * i)).strftime("%m/%d") for i in range(SERIES_WEEKS)]
    output = {
        "date": ref.isoformat(),
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "week_start": week_start.isoformat(),
        "history_days": history_days,
        "week_total": len(feed),
        "source_count": len({a.get("source") for a in feed}),
        "series_labels": series_labels,
        "top": top,
        "new_keywords": new_keywords,
        "topics": topic_out,
        "feed": [slim(a) for a in feed],
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)

    untagged = sum(1 for a in feed if not a["_topics"])
    print(f"[trends] {ref} 기준 · 이번 주 {len(feed)}건 (미분류 {untagged}) · 출처 {output['source_count']}곳")
    for t in topic_out[:6]:
        g = t["growth_pct"]
        g = "-" if g is None else ("신규" if g == "new" else f"{g:+d}%")
        print(f"  {t['name']:<12} {t['count']:>3}건  출처 {t['spread']}곳  {g:>6}  {t['keywords']}")


if __name__ == "__main__":
    main()
