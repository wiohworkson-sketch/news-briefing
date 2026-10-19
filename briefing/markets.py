"""환율·금리·원자재·코인 지표를 가져온다 (야후 파이낸스)."""
import yfinance as yf


def _fmt(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "$":
        return f"${value:,.0f}" if value >= 1000 else f"${value:,.1f}"
    return f"{value:,.1f}{unit}"


def fetch(cfg: dict) -> list[dict]:
    out = []
    for m in cfg["markets"]:
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
