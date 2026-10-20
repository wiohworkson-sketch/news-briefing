"""카톡에 크게 보이는 브리핑 카드 이미지(가로 900px, 내용에 맞춰 세로 자름)를 그린다."""
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 1360
PAD = 44
BG = (255, 255, 255)
TEXT = (28, 32, 40)
SUB = (100, 108, 122)
LINE = (226, 232, 240)
UP = (220, 50, 50)
DOWN = (37, 99, 235)
HEADER = (37, 99, 235)        # 밝은 파란색
HEADER_SUB = (205, 222, 255)
CHIP_BG = (241, 245, 252)
INSIGHT_BG = (235, 243, 255)
INSIGHT_TX = (30, 64, 175)
INSIGHT_LINE = (200, 216, 245)
SECTION_COLORS = [(234, 88, 12), (124, 58, 237), (5, 150, 105), (220, 38, 38), (219, 39, 119), (2, 132, 199)]
# 분야 이름별 고정 색 (분야를 추가·순서 변경해도 색이 바뀌지 않게)
SECTION_COLOR_BY_NAME = {"증시·경제": (234, 88, 12), "부동산": (161, 98, 7), "정치·국제": (124, 58, 237),
                         "IT·AI": (5, 150, 105), "바이오·제약": (220, 38, 38), "사회·생활": (219, 39, 119)}

FONT_CANDIDATES = {
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/malgunbd.ttf"],
    "regular": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/malgun.ttf"],
}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[weight]:
        if Path(path).exists():
            # .ttc 파일의 1번 = 한국어(KR) 글꼴
            return ImageFont.truetype(path, size, index=1 if path.endswith(".ttc") else 0)
    raise RuntimeError("한글 글꼴을 찾을 수 없습니다 (fonts-noto-cjk 설치 필요)")


def _fit(d: ImageDraw.ImageDraw, text: str, font, max_w: float) -> str:
    """한 줄에 들어가도록 자르고, 넘치면 … 을 붙인다."""
    if d.textlength(text, font=font) <= max_w:
        return text
    while text and d.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: float, max_lines: int) -> list[str]:
    """띄어쓰기(단어) 단위로 줄바꿈. 한 단어가 너무 길 때만 글자 단위로 자른다."""
    words = text.split()
    lines, cur = [], ""
    i = 0
    while i < len(words):
        w = words[i]
        cand = f"{cur} {w}" if cur else w
        if d.textlength(cand, font=font) <= max_w:
            cur, i = cand, i + 1
        elif cur:
            lines.append(cur)
            cur = ""
        else:  # 단어 하나가 한 줄보다 긴 경우
            cut = len(w)
            while cut > 1 and d.textlength(w[:cut], font=font) > max_w:
                cut -= 1
            lines.append(w[:cut])
            words[i] = w[cut:]
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
        cur = ""
    if (i < len(words) or cur) and lines:  # 남은 글자가 있으면 … 표시
        lines[-1] = _fit(d, lines[-1] + "…", font, max_w)
    return lines


def render(page: dict, path: Path) -> int:
    """이미지를 저장하고 실제 높이(px)를 돌려준다."""
    b = page["briefing"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    inner = W - PAD * 2

    # ── 상단 파란 띠 ──
    d.rectangle([0, 0, W, 108], fill=HEADER)
    d.text((PAD, 16), f"{page['date_label']} 아침 브리핑", font=_font("bold", 44), fill=(255, 255, 255))
    d.text((PAD, 70), f"국내외 기사 {page['article_count']}건 AI 요약", font=_font("regular", 22), fill=HEADER_SUB)

    # ── 지표 한 줄 ──
    y = 122
    mk = page["markets"][:6]
    gap = 8
    cw = (inner - gap * (len(mk) - 1)) / max(len(mk), 1)
    f_n, f_v, f_c = _font("regular", 17), _font("bold", 22), _font("bold", 17)
    arrows = {"up": "▲", "down": "▼", "flat": "-"}
    for i, m in enumerate(mk):
        x = PAD + i * (cw + gap)
        d.rounded_rectangle([x, y, x + cw, y + 86], radius=12, fill=CHIP_BG)
        d.text((x + 10, y + 6), _fit(d, m["name"], f_n, cw - 14), font=f_n, fill=SUB)
        d.text((x + 10, y + 29), _fit(d, m["text"], f_v, cw - 14), font=f_v, fill=TEXT)
        color = UP if m["direction"] == "up" else DOWN if m["direction"] == "down" else SUB
        d.text((x + 10, y + 59), f"{arrows[m['direction']]} {m['change']}", font=f_c, fill=color)

    # ── 오늘의 핵심 3줄 ──
    y = 222
    d.text((PAD, y), "오늘의 핵심", font=_font("bold", 25), fill=TEXT)
    y += 38
    f_hl, f_num = _font("bold", 28), _font("bold", 21)
    for i, h in enumerate(b["headlines"][:3], 1):
        d.ellipse([PAD, y + 5, PAD + 33, y + 38], fill=HEADER)
        d.text((PAD + 16, y + 21), str(i), font=f_num, fill=(255, 255, 255), anchor="mm")
        d.text((PAD + 46, y + 1), _fit(d, h, f_hl, inner - 46), font=f_hl, fill=TEXT)
        y += 46

    # ── 분야별 뉴스 2개씩 ──
    y += 6
    d.line([PAD, y, W - PAD, y], fill=LINE, width=2)
    y += 12
    f_tag, f_row = _font("bold", 20), _font("regular", 23)
    tag_col = 136
    for i, sec in enumerate(b["sections"][:6]):
        titles = [it["kakao_title"] or it["title"] for it in sec["items"]]
        picks = [t for t in titles if t not in b["headlines"]][:2] or titles[:2]
        if not picks:
            continue
        color = SECTION_COLOR_BY_NAME.get(sec["name"], SECTION_COLORS[i % len(SECTION_COLORS)])
        tw = int(d.textlength(sec["name"], font=f_tag)) + 20
        d.rounded_rectangle([PAD, y + 2, PAD + tw, y + 32], radius=9, fill=color)
        d.text((PAD + 10, y + 17), sec["name"], font=f_tag, fill=(255, 255, 255), anchor="lm")
        for k, t in enumerate(picks):
            d.text((PAD + tag_col, y + 17 + k * 33), "· " + _fit(d, t, f_row, inner - tag_col - 26),
                   font=f_row, fill=TEXT, anchor="lm")
        y += 33 * len(picks) + 9

    # ── 오늘의 시사점 (쉽게 풀어보기 + IT·AI + 증시) ──
    y += 4
    f_ins, f_lab = _font("regular", 22), _font("bold", 22)
    easy = b.get("insight_easy")
    if easy:
        rows = [("무슨 일?", easy["what"]), ("어떤 영향?", easy["impact"]), ("그래서?", easy["result"])]
    else:  # 예전 데이터
        rows = [("", t) for t in _wrap(d, b.get("insight_kakao", ""), f_ins, inner - 48, 3)]
    extra = [(lab, b[key]) for lab, key in (("IT·AI", "insight_it"), ("증시", "insight_market")) if b.get(key)]
    lab_w = 118
    line_h = 29
    wrap = lambda txt: _wrap(d, txt, f_ins, inner - 40 - lab_w, 2)
    w_rows = [(lab, wrap(txt) if lab else [txt]) for lab, txt in rows]
    w_extra = [(lab, wrap(txt)) for lab, txt in extra]
    box_h = 48 + sum(len(ls) * line_h + 7 for _, ls in w_rows)
    if w_extra:
        box_h += 12 + sum(len(ls) * line_h + 7 for _, ls in w_extra)
    box_h = min(box_h + 6, H - 10 - y)
    d.rounded_rectangle([PAD, y, W - PAD, y + box_h], radius=16, fill=INSIGHT_BG)
    d.text((PAD + 20, y + 11), "오늘의 시사점 · 쉽게 풀어보기", font=_font("bold", 23), fill=INSIGHT_TX)
    yy = y + 48

    def draw_rows(items, label_color):
        nonlocal yy
        for lab, ls in items:
            if lab:
                d.text((PAD + 20, yy), lab, font=f_lab, fill=label_color)
            for k, line in enumerate(ls):
                d.text((PAD + 20 + (lab_w if lab else 0), yy + k * line_h), line, font=f_ins, fill=TEXT)
            yy += len(ls) * line_h + 7

    draw_rows(w_rows, INSIGHT_TX)
    if w_extra:
        d.line([PAD + 20, yy + 2, W - PAD - 20, yy + 2], fill=INSIGHT_LINE, width=2)
        yy += 12
        draw_rows(w_extra, (5, 150, 105))

    # 내용이 끝나는 곳까지만 남겨 아래 빈 공간을 없앤다
    bottom = min(H, y + box_h + 28)
    img = img.crop((0, 0, W, bottom))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return bottom


# ───────────── 오늘 장 전망 카드 ─────────────
NAVY = (17, 24, 39)
OPEN_STYLE = {  # 시초가 예상별 색 (국내 관례: 상승=빨강, 하락=파랑)
    "갭상승": ((220, 38, 38), (255, 255, 255)), "강보합": ((254, 226, 226), (185, 28, 28)),
    "보합": ((229, 231, 235), (55, 65, 81)),
    "약보합": ((219, 234, 254), (29, 78, 216)), "갭하락": ((37, 99, 235), (255, 255, 255)),
}
UP_BG, DOWN_BG = (254, 242, 242), (239, 246, 255)


def render_market(page: dict, path: Path) -> int:
    """오늘 장 전망 카드를 저장하고 실제 높이(px)를 돌려준다."""
    m = page["briefing"]["market"]
    img = Image.new("RGB", (W, 1500), BG)
    d = ImageDraw.Draw(img)
    inner = W - PAD * 2

    # 헤더
    d.rectangle([0, 0, W, 108], fill=NAVY)
    d.text((PAD, 16), "오늘 장 전망", font=_font("bold", 44), fill=(255, 255, 255))
    d.text((PAD, 70), f"{page['date_label']} · 밤사이 시장과 야간선물 반영", font=_font("regular", 22),
           fill=(190, 198, 215))

    # 밤사이 시장 (3 x 2) — 모두 '전일 마감' 값 (예상치 아님)
    mk = page.get("outlook_markets", [])[:6]
    days = sorted({x["date"] for x in mk if x.get("date")})
    when = ""
    if days:
        y_, m_, d_ = map(int, days[-1].split("-"))
        when = f" · {m_}월 {d_}일({'월화수목금토일'[date(y_, m_, d_).weekday()]}) 기준"
    d.text((PAD, 120), f"전일 마감{when}", font=_font("bold", 22), fill=SUB)
    y = 156
    cols, gap = 3, 10
    cw = (inner - gap * (cols - 1)) / cols
    f_n, f_v, f_c = _font("regular", 21), _font("bold", 30), _font("bold", 21)
    arrows = {"up": "▲", "down": "▼", "flat": "-"}
    for i, x_m in enumerate(mk):
        r, c = divmod(i, cols)
        x, yy = PAD + c * (cw + gap), y + r * 104
        d.rounded_rectangle([x, yy, x + cw, yy + 94], radius=14, fill=CHIP_BG)
        stale = x_m.get("date") and days and x_m["date"] < days[-1]
        d.text((x + 14, yy + 8), x_m["name"] + (" (지연)" if stale else ""), font=f_n,
               fill=UP if stale else SUB)
        d.text((x + 14, yy + 34), _fit(d, x_m["text"], f_v, cw * 0.62), font=f_v, fill=TEXT)
        color = UP if x_m["direction"] == "up" else DOWN if x_m["direction"] == "down" else SUB
        d.text((x + cw - 12, yy + 50), f"{arrows[x_m['direction']]}{x_m['change']}", font=f_c, fill=color,
               anchor="rm")
    y += ((len(mk) + cols - 1) // cols) * 104 + 6

    # 야간선물
    f_txt = _font("regular", 25)
    d.rounded_rectangle([PAD, y, W - PAD, y + 56], radius=14, fill=(255, 247, 237))
    d.text((PAD + 18, y + 28), "야간선물", font=_font("bold", 24), fill=(194, 65, 12), anchor="lm")
    d.text((PAD + 140, y + 28), _fit(d, m["night_futures"], f_txt, inner - 160), font=f_txt, fill=TEXT, anchor="lm")
    y += 72

    # 시초가 예상 (코스피 / 코스닥)
    d.text((PAD, y), "시초가 예상", font=_font("bold", 28), fill=TEXT)
    y += 44
    f_badge, f_why = _font("bold", 28), _font("regular", 24)
    for name, key, why in (("코스피", "kospi_open", "kospi_reason"), ("코스닥", "kosdaq_open", "kosdaq_reason")):
        label = m[key].strip()
        bg, fg = OPEN_STYLE.get(label, OPEN_STYLE["보합"])
        d.text((PAD, y + 24), name, font=_font("bold", 27), fill=TEXT, anchor="lm")
        bw = int(d.textlength(label, font=f_badge)) + 32
        d.rounded_rectangle([PAD + 100, y + 2, PAD + 100 + bw, y + 46], radius=12, fill=bg)
        d.text((PAD + 116, y + 24), label, font=f_badge, fill=fg, anchor="lm")
        d.text((PAD + 116 + bw, y + 24), _fit(d, m[why], f_why, inner - 130 - bw), font=f_why, fill=SUB,
               anchor="lm")
        y += 58
    y += 4

    # 밤사이 변수
    d.line([PAD, y, W - PAD, y], fill=LINE, width=2)
    y += 14
    d.text((PAD, y), "밤사이 주요 변수", font=_font("bold", 26), fill=TEXT)
    y += 40
    for t in m["overnight"][:4]:
        d.text((PAD + 4, y), "· " + _fit(d, t, f_txt, inner - 24), font=f_txt, fill=TEXT)
        y += 37
    y += 8

    # 강세 / 약세 섹터
    f_sec, f_stk = _font("bold", 25), _font("regular", 22)
    for title, calls, bg, fg in (("강세 예상", m["sectors_up"], UP_BG, UP), ("약세 예상", m["sectors_down"], DOWN_BG, DOWN)):
        calls = calls[:3]
        if not calls:
            continue
        box_h = 50 + len(calls) * 66
        d.rounded_rectangle([PAD, y, W - PAD, y + box_h], radius=16, fill=bg)
        d.text((PAD + 18, y + 12), ("▲ " if fg == UP else "▼ ") + title, font=_font("bold", 25), fill=fg)
        yy = y + 50
        for c in calls:
            d.text((PAD + 18, yy), c["sector"], font=f_sec, fill=TEXT)
            d.text((PAD + 150, yy + 2), _fit(d, c["reason"], f_stk, inner - 170), font=f_stk, fill=SUB)
            stocks = ", ".join(c["stocks"][:3])
            if stocks:
                d.text((PAD + 150, yy + 31), _fit(d, stocks, f_stk, inner - 170), font=_font("bold", 22), fill=fg)
            yy += 66
        y += box_h + 12

    # 이벤트
    if m["events"]:
        d.text((PAD, y), "이벤트", font=_font("bold", 25), fill=TEXT)
        d.text((PAD + 100, y + 2), _fit(d, " · ".join(m["events"][:3]), f_stk, inner - 100), font=f_stk, fill=TEXT)
        y += 40

    # 안내 문구
    d.text((W // 2, y + 14), "AI가 기사로 예상한 내용이며 투자 권유가 아닙니다", font=_font("regular", 20),
           fill=SUB, anchor="mm")
    bottom = min(1500, y + 40)
    img = img.crop((0, 0, W, bottom))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return bottom
