"""무료 Google Gemini로 기사 목록을 브리핑으로 정리한다."""
import time

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field


class Item(BaseModel):
    title: str = Field(description="웹페이지용 한국어 제목, 40자 이내")
    summary: str = Field(description="핵심을 짧은 개조식 1문장으로, 휴대폰 2줄(약 45자) 이내. 왜 중요한지 포함")
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


class EasyInsight(BaseModel):
    what: str = Field(description="무슨 일이 있었나: 초등학생도 알아듣게 쉬운 말로, 40자 이내")
    impact: str = Field(description="어떤 영향이 있나: 우리 생활·용돈·물가·일자리 등에 미치는 영향, 40자 이내")
    result: str = Field(description="그래서 어떻게 되나: 앞으로 예상되는 결과, 40자 이내")


class SectorCall(BaseModel):
    sector: str = Field(description="섹터 이름, 8자 이내 (예: 반도체, 2차전지, 로봇, 원전, 조선, 방산, 바이오, 자동차)")
    reason: str = Field(description="그렇게 보는 이유 한 줄, 25자 이내")
    stocks: list[str] = Field(description="관련 종목 1~3개. 기사에 이름이 나온 국내 상장 종목만")


class MarketOutlook(BaseModel):
    night_futures: str = Field(description="전일 코스피200 야간선물 결과 한 줄(등락률 포함, 30자 이내). 기사에 없으면 '야간선물 기사 없음'")
    overnight: list[str] = Field(description="밤사이 주요 변수 3~5개: 미국 증시, 전쟁·지정학, 유가, 금리·CPI 등 발표. 각 30자 이내")
    kospi_open: str = Field(description="코스피 시초가 예상: 갭상승 / 강보합 / 보합 / 약보합 / 갭하락 중 하나")
    kospi_reason: str = Field(description="코스피 시초가 예상 근거, 35자 이내")
    kosdaq_open: str = Field(description="코스닥 시초가 예상: 갭상승 / 강보합 / 보합 / 약보합 / 갭하락 중 하나")
    kosdaq_reason: str = Field(description="코스닥 시초가 예상 근거, 35자 이내")
    sectors_up: list[SectorCall] = Field(description="오늘 강세가 예상되는 섹터 2~3개")
    sectors_down: list[SectorCall] = Field(description="오늘 약세가 예상되는 섹터 1~3개")
    events: list[str] = Field(description="오늘·이번 주 시장 이벤트 0~4개(금리결정, CPI, 실적, 선물옵션 만기 등), 각 25자 이내")
    article_ids: list[int] = Field(description="근거 기사 번호")


class Briefing(BaseModel):
    market: MarketOutlook = Field(description="오늘 국내 증시 장 전망")
    headlines: list[str] = Field(description="오늘의 핵심 3개, 각 25자 이내")
    insight: list[str] = Field(description="오늘의 시사점 3줄. 여러 뉴스를 엮어 '그래서 무엇이 중요한가'")
    insight_easy: EasyInsight = Field(description="오늘 가장 중요한 흐름을 초등학생도 이해하게 풀어쓴 설명")
    insight_it: str = Field(description="IT·AI 분야 시사점: 쉬운 말 '~해요'체 한 문장, 32자 이내")
    insight_market: str = Field(description="증시 시사점: 오늘 주식시장에서 눈여겨볼 점을 쉬운 말 '~해요'체 한 문장, 32자 이내")
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


def make_briefing(articles: list[dict], markets: list[dict], date_str: str, cfg: dict,
                  outlook_markets: list[dict] | None = None, expiry_note: str = "",
                  night_lines: list[str] | None = None) -> Briefing:
    client = genai.Client()  # GEMINI_API_KEY 환경변수 사용
    lines = [
        f"[{a['id']}] ({a['source']}|{a['origin']}){' [키워드 후보: ' + a['keyword'] + ']' if a.get('keyword') else ''} {a['title']} — {a['summary']}"
        for a in articles
    ]
    fmt = lambda m: (f"{m['name']}: {m['text']} "
                     f"({'▲' if m['direction'] == 'up' else '▼' if m['direction'] == 'down' else '-'}{m['change']})")
    market_lines = [fmt(m) for m in markets]
    outlook_lines = [fmt(m) + (f" [{m['date']} 마감]" if m.get("date") else "") for m in (outlook_markets or [])]
    kw_lines = chr(10).join(
        f"  · {k['name']} — {k.get('hint', '')}" if isinstance(k, dict) else f"  · {k}" for k in cfg["keywords"])
    prompt = f"""오늘은 {date_str}입니다. 아래 자료로 아침 브리핑을 만드세요.

## 오늘 장 전망(market) 작성 규칙 — 가장 중요
- 기사 목록의 야간선물·뉴욕증시 마감·증시 전망·특징주 기사와 아래 '밤사이 시장' 숫자를 근거로 씁니다.
- night_futures: 아래 '야간선물 관련 기사 문장'(최신 문장 우선)과 기사 목록에서 간밤 코스피200 야간선물 결과를 찾아
  등락률과 함께 씁니다(예: "코스피200 야간선물 0.13% 하락"). 근거가 없으면 지어내지 말고 '야간선물 기사 없음'.
- overnight: 밤사이 미국 증시, 전쟁·지정학, 유가, 금리 결정·CPI 등 발표 중 오늘 국내 증시에 영향이 큰 것만.
- kospi_open / kosdaq_open: 위 근거를 종합해 갭상승 / 강보합 / 보합 / 약보합 / 갭하락 중 하나로 예상합니다.
  (참고: 미국 반도체지수·나스닥·한국 ETF(EWY) 등락이 국내 시초가와 관련이 큽니다.)
- sectors_up / sectors_down: 반도체, 2차전지, 로봇, 원전, 조선, 방산, 바이오, 자동차 등에서 고르고,
  종목(stocks)은 반드시 기사에 이름이 나온 국내 상장 종목만 씁니다. 근거 없으면 빈 목록으로 둡니다.
- events: 아래 '선물·옵션 만기' 정보와 기사 속 금리 결정·CPI·실적 발표 일정을 넣습니다.
- 확정된 사실처럼 쓰지 말고 '예상'임이 드러나게 씁니다.

## 전일 마감 시장 (각 지표의 마감 날짜 표시, 전일 대비 등락)
{chr(10).join(outlook_lines) or "(데이터 없음)"}
선물·옵션 만기: {expiry_note or "정보 없음"}

## 야간선물 관련 기사 문장 (최신순 — 첫 문장이 가장 최근, 날짜가 지난 문장은 무시)
{chr(10).join("- " + s for s in (night_lines or [])) or "(없음)"}

## 작성 규칙
- 분야(sections)는 정확히 이 순서와 이름으로: {", ".join(cfg["sections"])}
- 분야별 항목은 정확히 {cfg.get("items_per_section", 3)}개, 중요한 순서대로.
- 국내 뉴스를 중심으로 하되 미국 등 외신의 중요한 뉴스도 반드시 포함하세요.
- 관심 키워드(keywords)는 정확히 이 순서와 이름(keyword)으로 쓰고, 설명을 참고해 관련 뉴스를 0~3개 고르세요.
  기사 목록에 '[키워드 후보: 이름]' 표시가 붙은 기사는 그 키워드 전용 검색으로 모은 기사이니 우선 살펴보고,
  설명에 맞는 기사는 꼭 넣으세요. 다른 키워드나 무관한 기사(예: 항공 키워드에 선박 기사, 스포츠 기사)는 넣지 마세요.
  관련 뉴스가 없으면 items를 빈 목록으로 둡니다:
{kw_lines}
- 쉬운 시사점(insight_easy)은 초등학생도 이해할 수 있게 쓰세요. 어려운 경제·정치 용어는 쓰지 말고 풀어서 말하고,
  필요하면 비유를 쓰세요. (예: "환율이 오르면 → 해외 물건값이 비싸져요 → 수입 과자·여행비가 오를 수 있어요")
  IT·AI 시사점(insight_it)과 증시 시사점(insight_market)도 같은 쉬운 말로 한 문장씩 씁니다.
  이 항목들만은 개조식 대신 "~해요"체로 친절하게 씁니다.
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
            except Exception as e:  # 연결 끊김·시간 초과 등 네트워크 오류 → 잠시 후 재시도
                last_error = e
                print(f"[경고] {model} 연결 오류 ({type(e).__name__}): {e}")
                time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"AI 브리핑 작성 실패: {last_error}")
