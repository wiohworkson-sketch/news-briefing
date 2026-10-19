"""시장 지표를 가져온다.

- 국내 지수(코스피·코스닥): 네이버 증권 (한국거래소 기준, 날짜별 종가)
  ※ 야후 파이낸스는 국내 지수가 하루 늦게 들어오는 경우가 있어 쓰지 않는다.
- 그 외(미국 지수·환율·금리·원자재·코인): 야후 파이낸스
"""
from datetime import date, timedelta

import requests
import yfinance as yf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def _fmt(value: float, unit: str) -> str:
    if unit == "pt":
        return f"{value:,.2f}" if value < 10000 else f"{value:,.0f}"
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "$":
        return f"${value:,.0f}" if value >= 1000 else f"${value:,.1f}"
    return f"{value:,.1f}{unit}"


def option_expiry_note(today: date) -> str:
    """국내 선물·옵션 만기일(매월 둘째 목요일, 3·6·9·12월은 동시만기) 안내."""
    def second_thursday(y: int, m: int) -> date:
        first = date(y, m, 1)
        return first + timedelta(days=(3 - first.weekday()) % 7 + 7)

    exp = second_thursday(today.year, today.month)
    if exp < today:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        exp = second_thursday(y, m)
    kind = "선물·옵션 동시만기(쿼드러플 위칭)" if exp.month in (3, 6, 9, 12) else "옵션 만기"
    days = (exp - today).days
    when = "오늘" if days == 0 else "내일" if days == 1 else f"{days}일 뒤"
    return f"{when}({exp.month}월 {exp.day}일 목) {kind}"


def _naver_index(code: str) -> tuple[date, float, float]:
    """네이버 증권 일별 시세: (거래일, 종가, 전일 종가)."""
    resp = requests.get(f"https://m.stock.naver.com/api/index/{code}/price",
                        params={"pageSize": 2, "page": 1}, headers={"User-Agent": UA}, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    num = lambda s: float(str(s).replace(",", ""))
    last = rows[0]
    close = num(last["closePrice"])
    return date.fromisoformat(last["localTradedAt"][:10]), close, close - num(last["compareToPreviousClosePrice"])


def _yahoo(ticker: str) -> tuple[date, float, float]:
    """야후 파이낸스 일별 종가: (거래일, 종가, 전일 종가)."""
    hist = yf.Ticker(ticker).history(period="7d", interval="1d")["Close"].dropna()
    return hist.index[-1].date(), float(hist.iloc[-1]), float(hist.iloc[-2])


def fetch(cfg: dict, key: str = "markets") -> list[dict]:
    out = []
    for m in cfg.get(key, []):
        row = {"name": m["name"], "value": None, "text": "-", "change": "", "direction": "flat", "date": ""}
        try:
            ticker = m["ticker"]
            if ticker.startswith("naver:"):
                day, last, prev = _naver_index(ticker.split(":", 1)[1])
            else:
                day, last, prev = _yahoo(ticker)
            scale = m.get("scale", 1)
            last, prev = last * scale, prev * scale
            diff = last - prev
            row["value"] = last
            row["date"] = day.isoformat()
            row["text"] = _fmt(last, m["unit"])
            if m["unit"] == "%":  # 금리는 %p 변화
                row["change"] = f"{abs(diff):.2f}%p"
            elif m["unit"] == "원":
                row["change"] = f"{abs(diff):,.1f}"
            elif m["unit"] == "pt":  # 지수는 공식 발표처럼 소수 둘째 자리
                row["change"] = f"{abs(diff / prev * 100):.2f}%"
            else:
                row["change"] = f"{abs(diff / prev * 100):.1f}%"
            row["direction"] = "up" if diff > 0 else "down" if diff < 0 else "flat"
        except Exception as e:
            row["error"] = str(e)
            print(f"[경고] 지표 {m['name']} 가져오기 실패: {e}")
        out.append(row)
    return out


def check_fresh(rows: list[dict], today: date) -> list[str]:
    """너무 오래된 데이터(주말·공휴일 감안 4일 초과)를 찾아 경고 문구를 돌려준다."""
    warnings = []
    for r in rows:
        if r.get("date") and (today - date.fromisoformat(r["date"])).days > 4:
            warnings.append(f"{r['name']} 데이터가 {r['date']} 기준입니다")
    return warnings
