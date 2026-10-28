"""
teams_notify.py - trends.json을 Adaptive Card로 만들어 Teams 워크플로 웹훅에 전송
환경변수: TEAMS_WEBHOOK_URL (필수), SITE_URL (선택, '전체 브리핑 보기' 버튼 링크)
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

TRENDS_PATH = os.path.join("web", "data", "trends.json")
WEEKDAYS = "월화수목금토일"


def growth_label(g) -> str:
    if g is None:
        return ""
    if g == "new":
        return "신규"
    return f"▲ {g}%" if g > 0 else (f"▼ {abs(g)}%" if g < 0 else "보합")


def growth_color(g) -> str:
    if g == "new" or (isinstance(g, int) and g > 0):
        return "Good"
    if isinstance(g, int) and g < 0:
        return "Attention"
    return "Default"


def topic_block(rank: int, t: dict) -> dict:
    items = [{
        "type": "ColumnSet",
        "columns": [
            {"type": "Column", "width": "stretch", "items": [{
                "type": "TextBlock", "text": f"{rank}. {t['name']}", "weight": "Bolder", "size": "Medium", "wrap": True,
            }]},
            {"type": "Column", "width": "auto", "verticalContentAlignment": "Center", "items": [{
                "type": "TextBlock", "text": growth_label(t["growth_pct"]), "color": growth_color(t["growth_pct"]),
                "weight": "Bolder", "size": "Small",
            }]},
        ],
    }, {
        "type": "TextBlock", "isSubtle": True, "size": "Small", "spacing": "None", "wrap": True,
        "text": f"이번 주 {t['count']}건 · 출처 {t['spread']}곳 · " + ", ".join(t["keywords"][:3]),
    }]
    for a in t["articles"][:2]:
        title = a["title"].replace("[", "(").replace("]", ")")
        text = f"[{title}]({a['url']})" if a.get("url") else title
        items.append({
            "type": "TextBlock", "wrap": True, "size": "Small", "spacing": "Small",
            "text": f"- {text}  \n  {a['source']}",
        })
    return {"type": "Container", "separator": rank > 1, "spacing": "Medium", "items": items}


def build_card(d: dict, site_url: str) -> dict:
    by_id = {t["id"]: t for t in d["topics"]}
    ref = date.fromisoformat(d["date"])
    body = [
        {"type": "TextBlock", "text": "IT 트렌드 브리핑", "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock", "spacing": "None", "isSubtle": True, "wrap": True,
         "text": f"{ref.month}월 {ref.day}일 ({WEEKDAYS[ref.weekday()]}) · 이번 주 {d['week_total']}건 · 출처 {d['source_count']}곳"},
    ]
    body += [topic_block(i + 1, by_id[tid]) for i, tid in enumerate(d["top"]) if tid in by_id]
    if d.get("new_keywords"):
        body.append({"type": "TextBlock", "separator": True, "spacing": "Medium", "wrap": True, "size": "Small",
                     "text": "**새로 등장한 키워드**  " + " · ".join(d["new_keywords"][:6])})
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "msteams": {"width": "Full"},
        "body": body,
    }
    if site_url:
        card["actions"] = [{"type": "Action.OpenUrl", "title": "전체 브리핑 보기",
                            "url": site_url.rstrip("/") + "/v2"}]
    return card


def main():
    webhook = os.environ.get("TEAMS_WEBHOOK_URL", "").strip()
    if not webhook:
        print("[teams] TEAMS_WEBHOOK_URL이 없어 전송을 건너뜁니다.")
        return
    with open(TRENDS_PATH, encoding="utf-8") as f:
        d = json.load(f)
    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": build_card(d, os.environ.get("SITE_URL", "").strip()),
        }],
    }
    req = urllib.request.Request(
        webhook, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            print(f"[teams] 전송 완료 ({res.status})")
    except urllib.error.HTTPError as e:
        print(f"[teams] 전송 실패 {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
        sys.exit(1)


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        with open(TRENDS_PATH, encoding="utf-8") as f:
            print(json.dumps(build_card(json.load(f), os.environ.get("SITE_URL", "")), ensure_ascii=False, indent=1))
    else:
        main()
