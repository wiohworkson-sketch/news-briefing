"""네이버 뉴스 검색 결과의 본문 미리보기에서 야간선물 등 숫자가 담긴 문장을 찾는다.

뉴스 제목에는 야간선물 등락률이 잘 안 나오고 본문에만 있어서, 검색 결과 미리보기를 활용한다.
"""
import html
import json
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
BS = chr(92)  # 역슬래시
FIELD = re.compile('"content":"((?:[^"' + BS + BS + ']|' + BS + BS + '.)*)"')
SENTENCE_END = re.compile(r"(?<=[다요])\.\s")


def snippets(query: str, keyword: str, limit: int = 6) -> list[str]:
    """최근 1일 뉴스 검색 결과에서 keyword가 들어간 문장만 모은다. 실패하면 빈 목록."""
    try:
        resp = requests.get(
            "https://search.naver.com/search.naver",
            params={"where": "news", "query": query, "sort": "1", "pd": "4"},
            headers={"User-Agent": UA}, timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[경고] 네이버 검색 실패 ({query}): {e}")
        return []

    found: list[str] = []
    for m in FIELD.finditer(resp.text):
        try:
            text = json.loads('"' + m.group(1) + '"')
        except ValueError:
            continue
        text = re.sub(r"<[^>]+>", "", html.unescape(text))
        for sent in SENTENCE_END.split(text):
            sent = sent.strip()
            if keyword in sent and "%" in sent and sent not in found:
                found.append(sent[:200])
        if len(found) >= limit:
            break
    return found


def night_futures() -> list[str]:
    """코스피 야간선물 등락이 적힌 문장들 (최신순)."""
    out = snippets("코스피 야간선물", "야간선물")
    if len(out) < 2:
        out += [s for s in snippets("코스피200 야간선물", "야간선물") if s not in out]
    return out[:6]
