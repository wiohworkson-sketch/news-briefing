"""카톡에 크게 보이는 브리핑 카드 이미지(900x1200)를 그린다."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 1200
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
    """글자 단위로 줄바꿈 (마지막 줄은 넘치면 … 처리)."""
    lines, cur, truncated = [], "", False
    for i, ch in enumerate(text):
        # 문장부호는 줄 끝에 붙여서 혼자 다음 줄로 넘어가지 않게 한다
        if d.textlength(cur + ch, font=font) > max_w and ch not in ".,!?…)'\"":
            lines.append(cur)
            cur = ch.lstrip()
            if len(lines) == max_lines:
                truncated = bool(text[i:].strip())  # 남은 글자가 있을 때만 … 표시
                break
        else:
            cur += ch
    else:
        lines.append(cur)
    if truncated:
        lines[-1] = _fit(d, lines[-1] + "…", font, max_w)
    return [l for l in lines if l]


def render(page: dict, path: Path) -> None:
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
    for i, sec in enumerate(b["sections"][:5]):
        titles = [it["kakao_title"] or it["title"] for it in sec["items"]]
        picks = [t for t in titles if t not in b["headlines"]][:2] or titles[:2]
        if not picks:
            continue
        color = SECTION_COLORS[i % len(SECTION_COLORS)]
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

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
