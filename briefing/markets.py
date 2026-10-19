"""환율·금리·원자재·코인 지표를 가져온다 (야후 파이낸스)."""
from datetime import date, timedelta

import yfinance as yf


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


def fetch(cfg: dict, key: str = "markets") -> list[dict]:
    out = []
    for m in cfg.get(key, []):
        row = {"name": m["name"], "value": None, "text": "-", "change": "", "direction": "flat"}
        try:
            hist = yf.Ticker(m["ticker"]).history(period="7d", interval="1d")["Close"].dropna()
            scale = m.get("scale", 1)
            last, prev = float(hist.iloc[-1]) * scale, float(hist.iloc[-2]) * scale
            diff = last - prev
            row["value"] = last
            row["text"] = _fmt(last, m["unit"])
            if m["unit"] == "%":  # 금리는 %p 변화
                row["change"] = f"{abs(diff):.2f}%p"
            elif m["unit"] == "원":
                row["change"] = f"{abs(diff):,.1f}"
            else:
                row["change"] = f"{abs(diff / prev * 100):.1f}%"
            row["direction"] = "up" if diff > 0 else "down" if diff < 0 else "flat"
        except Exception as e:
            row["error"] = str(e)
        out.append(row)
    return out
