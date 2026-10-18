"""Claude로 기사 목록을 브리핑으로 정리한다."""
from typing import Literal

import anthropic
from pydantic import BaseModel, Field


class Item(BaseModel):
    title: str = Field(description="웹페이지용 한국어 제목, 40자 이내")
    summary: str = Field(description="핵심을 1~2문장 개조식으로. 왜 중요한지 포함")
    kakao_title: str = Field(description="카톡용 초간단 제목, 공백 포함 20자 이내")
    kakao_desc: str = Field(description="카톡용 한 줄 부연, 공백 포함 22자 이내")
    article_ids: list[int] = Field(description="근거 기사 번호 목록 (입력의 [번호])")


class Section(BaseModel):
    name: str
    items: list[Item]


class Perspective(BaseModel):
    topic: str = Field(description="비교 주제, 20자 이내")
    domestic: str = Field(description="국내 언론의 시각 한 문장")
    foreign: str = Field(description="외신의 시각 한 문장")
    article_ids: list[int]


class ScheduleItem(BaseModel):
    time: str = Field(description="한국시간 기준 'HH:MM' 또는 '종일'")
    region: Literal["한국", "미국", "기타"]
    event: str = Field(description="일정 내용, 30자 이내")


class KeywordHit(BaseModel):
    keyword: str
    items: list[Item] = Field(description="해당 키워드 관련 뉴스. 없으면 빈 목록")


class Briefing(BaseModel):
    headlines: list[str] = Field(description="오늘의 핵심 3개, 각 25자 이내")
    insight: list[str] = Field(description="오늘의 시사점 3줄. 여러 뉴스를 엮어 '그래서 무엇이 중요한가'")
    insight_kakao: str = Field(description="시사점을 카톡용으로 압축, 90자 이내")
    market_comment: str = Field(description="지표 흐름 한 줄 해설, 40자 이내")
    sections: list[Section]
    perspectives: list[Perspective] = Field(description="같은 사안에 대한 국내 vs 외신 시각 비교 2~3개")
    schedule: list[ScheduleItem] = Field(description="오늘 주목할 일정 3~6개, 시간순")
    keywords: list[KeywordHit]


SYSTEM = """당신은 한국 독자를 위한 아침 뉴스 브리핑 편집장입니다.
- 한국 독자 관점에서 중요도를 판단하고, 외신 기사는 자연스러운 한국어로 옮깁니다.
- 말투는 간결한 개조식입니다. (예: "한은, 기준금리 2.50% 동결 — 가계부채 부담 고려")
- 반드시 입력으로 받은 기사에 근거해서만 쓰고, 근거 기사 번호(article_ids)를 정확히 답니다. 추측이나 지어낸 수치는 쓰지 않습니다.
- 같은 사건을 다룬 여러 기사는 하나의 항목으로 묶습니다.
- 카톡용 글자 수 제한을 꼭 지킵니다."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=4)


def find_schedule(date_str: str, model: str) -> str:
    """웹 검색으로 오늘 일정을 찾는다. 실패하면 빈 문자열."""
    client = _client()
    messages = [{
        "role": "user",
        "content": (
            f"오늘은 {date_str}(한국시간)입니다. 오늘 한국시간 기준으로 예정된 주요 일정을 웹에서 찾아 "
            "목록으로만 답하세요: 한국·미국 경제지표 발표, 중앙은행 회의/발언, 주요 기업 실적 발표, "
            "국내외 주요 정치·외교 일정. 각 줄은 'HH:MM(한국시간) | 지역 | 내용' 형식, 최대 8줄."
        ),
    }]
    try:
        for _ in range(4):  # pause_turn 이면 이어서 진행
            resp = client.messages.create(
                model=model,
                max_tokens=8000,
                output_config={"effort": "low"},
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
                messages=messages,
            )
            if resp.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": resp.content})
        return "\n".join(b.text for b in resp.content if b.type == "text").strip()
    except anthropic.APIError as e:
        print(f"[경고] 일정 검색 실패: {e}")
        return ""


def make_briefing(articles: list[dict], markets: list[dict], schedule_text: str,
                  date_str: str, cfg: dict) -> Briefing:
    client = _client()
    lines = [
        f"[{a['id']}] ({a['source']}|{a['origin']}) {a['title']} — {a['summary']}"
        for a in articles
    ]
    market_lines = [
        f"{m['name']}: {m['text']} ({'▲' if m['direction'] == 'up' else '▼' if m['direction'] == 'down' else '-'}{m['change']})"
        for m in markets
    ]
    prompt = f"""오늘은 {date_str}입니다. 아래 자료로 아침 브리핑을 만드세요.

## 작성 규칙
- 분야(sections)는 정확히 이 순서와 이름으로: {", ".join(cfg["sections"])}
- 분야별 항목은 {cfg.get("items_per_section", 4)}개 내외, 중요한 순서대로.
- 국내 뉴스를 중심으로 하되 미국 등 외신의 중요한 뉴스도 반드시 포함하세요.
- 관심 키워드(keywords)는 정확히 이 순서로: {", ".join(cfg["keywords"])} — 관련 뉴스가 없으면 items를 빈 목록으로.
- 일정(schedule)은 아래 '오늘의 일정 검색 결과'를 우선 참고하고, 없으면 기사에서 찾으세요. 확실하지 않으면 넣지 마세요.

## 시장 지표 (전일 대비)
{chr(10).join(market_lines)}

## 오늘의 일정 검색 결과
{schedule_text or "(검색 결과 없음)"}

## 기사 목록 ({len(articles)}건)
{chr(10).join(lines)}
"""
    with client.beta.messages.stream(
        model=cfg.get("model", "claude-opus-5-5"),
        max_tokens=64000,
        system=SYSTEM,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
        output_format=Briefing,
    ) as stream:
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        raise RuntimeError(f"AI가 브리핑 작성을 거절했습니다: {final.stop_details}")
    if final.stop_reason == "max_tokens":
        raise RuntimeError("AI 응답이 너무 길어 잘렸습니다.")
    u = final.usage
    cost = (u.input_tokens * 4 + u.output_tokens * 20) / 1_000_000
    print(f"[정보] 토큰 입력 {u.input_tokens:,} / 출력 {u.output_tokens:,} (약 ${cost:.2f})")
    return final.parsed_output
