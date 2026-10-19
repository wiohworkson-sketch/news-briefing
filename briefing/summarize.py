"""무료 Google Gemini로 기사 목록을 브리핑으로 정리한다."""
import time

from google import genai
from google.genai import errors, types
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
    region: str = Field(description="한국 / 미국 / 기타 중 하나")
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
    schedule: list[ScheduleItem] = Field(description="기사에 언급된 오늘 예정 일정 0~6개, 시간순")
    keywords: list[KeywordHit]


SYSTEM = """당신은 한국 독자를 위한 아침 뉴스 브리핑 편집장입니다.
- 한국 독자 관점에서 중요도를 판단하고, 외신 기사는 자연스러운 한국어로 옮깁니다.
- 말투는 간결한 개조식입니다. "~습니다/~했다" 대신 명사형·개조식으로 끝냅니다.
  (예: "한은, 기준금리 2.50% 동결 — 가계부채 부담 고려", "외국인 4일째 순매수, 반도체 중심 매수세 지속")
- 반드시 입력으로 받은 기사에 근거해서만 쓰고, 근거 기사 번호(article_ids)를 정확히 답니다. 추측이나 지어낸 수치는 쓰지 않습니다.
- 같은 사건을 다룬 여러 기사는 하나의 항목으로 묶습니다.
- 카톡용 글자 수 제한을 꼭 지킵니다."""

# 앞의 모델이 무료 한도 초과·장애일 때 다음 모델로 넘어감
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]


def make_briefing(articles: list[dict], markets: list[dict], date_str: str, cfg: dict) -> Briefing:
    client = genai.Client()  # GEMINI_API_KEY 환경변수 사용
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
- 일정(schedule)은 기사에 '오늘' 예정으로 언급된 것만 넣으세요(경제지표 발표, 회의, 실적 발표 등). 확실하지 않으면 넣지 마세요.

## 시장 지표 (전일 대비)
{chr(10).join(market_lines)}

## 기사 목록 ({len(articles)}건)
{chr(10).join(lines)}
"""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        response_mime_type="application/json",
        response_schema=Briefing,
    )
    models = [cfg.get("model", "gemini-3.8-flash")] + FALLBACK_MODELS
    last_error = None
    for model in models:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
                result = resp.parsed or Briefing.model_validate_json(resp.text)
                u = resp.usage_metadata
                print(f"[정보] {model} 사용 · 토큰 입력 {u.prompt_token_count:,} / 출력 {u.candidates_token_count:,} (무료)")
                return result
            except errors.APIError as e:
                last_error = e
                print(f"[경고] {model} 오류 ({e.code}): {e.message}")
                if e.code in (429, 500, 503):  # 한도 초과·일시 장애 → 잠시 후 재시도
                    time.sleep(20 * (attempt + 1))
                    continue
                break  # 그 외 오류는 다음 모델로
            except ValueError as e:  # 응답 형식 오류 → 재시도
                last_error = e
                print(f"[경고] {model} 응답 형식 오류: {e}")
    raise RuntimeError(f"AI 브리핑 작성 실패: {last_error}")
