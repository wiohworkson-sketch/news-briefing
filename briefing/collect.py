"""RSS 피드에서 최근 기사를 모은다."""
import calendar
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor

import feedparser
import requests

UA = "Mozilla/5.0 (compatible; MorningBriefingBot/1.0)"
KOREAN_OUTLETS = ("Korea", "Yonhap", "KED", "Chosun", "JoongAng", "Hankyoreh", "Maeil",
                  "조선", "중앙", "동아", "한겨레", "연합", "KBS", "MBC", "SBS", "Arirang")


def _clean(text: str, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def _fetch_feed(feed: dict, cutoff: float, max_items: int) -> tuple[dict, list[dict], str | None]:
    try:
        resp = requests.get(feed["url"], headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as e:  # 피드 하나가 실패해도 전체는 계속
        return feed, [], str(e)

    items = []
    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        ts = calendar.timegm(published) if published else None
        if ts and ts < cutoff:
            continue
        title = _clean(entry.get("title", ""), 200)
        if not title:
            continue
        source = feed["name"]
        # 구글 뉴스는 "제목 - 언론사" 형식이므로 언론사를 분리
        origin = feed["origin"]
        if "news.google.com" in feed["url"] and " - " in title:
            title, source = title.rsplit(" - ", 1)
            if any(k in source for k in KOREAN_OUTLETS):  # 국내 언론의 영문판은 국내로 분류
                origin = "국내"
        items.append({
            "title": title,
            "summary": _clean(entry.get("summary", ""), 280),
            "url": entry.get("link", ""),
            "source": source,
            "origin": origin,
            "ts": ts,
        })
        if len(items) >= max_items:
            break
    return feed, items, None


def fetch_all(cfg: dict) -> tuple[list[dict], list[str]]:
    """기사 목록과 실패한 피드 목록을 돌려준다. 기사에는 1부터 번호(id)를 붙인다."""
    cutoff = time.time() - cfg.get("lookback_hours", 26) * 3600
    max_items = cfg.get("max_per_feed", 15)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda f: _fetch_feed(f, cutoff, max_items), cfg["feeds"]))

    articles, seen, errors = [], set(), []
    for feed, items, err in results:
        if err:
            errors.append(f"{feed['name']} ({feed['url']}): {err}")
        for it in items:
            key = re.sub(r"\W", "", it["title"].lower())[:40]
            if key in seen:
                continue
            seen.add(key)
            articles.append(it)
    for i, a in enumerate(articles, 1):
        a["id"] = i
    return articles, errors
