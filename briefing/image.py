"""카톡에 크게 보이는 브리핑 카드 이미지(900x1200)를 그린다."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 1200
PAD = 48
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
SECTION_COLORS = [(234, 88, 12), (124, 58, 237), (5, 150, 105), (219, 39, 119), (2, 132, 199), (202, 138, 4)]

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
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > max_w:
            lines.append(cur)
            cur = ch.lstrip()
            if len(lines) == max_lines:
                break
        else:
            cur += ch
    else:
        lines.append(cur)
    if len(lines) > max_lines or (len(lines) == max_lines and "".join(lines) != text.replace("\n", "")):
        lines = lines[:max_lines]
        lines[-1] = _fit(d, lines[-1] + "…", font, max_w) if not lines[-1].endswith("…") else lines[-1]
    return [l for l in lines if l]


def render(page: dict, path: Path) -> None:
    b = page["briefing"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    inner = W - PAD * 2

    # ── 상단 파란 띠 ──
    d.rectangle([0, 0, W, 130], fill=HEADER)
    d.text((PAD, 24), f"{page['date_label']} 아침 브리핑", font=_font("bold", 48), fill=(255, 255, 255))
    d.text((PAD, 86), f"국내외 기사 {page['article_count']}건 AI 요약", font=_font("regular", 24), fill=HEADER_SUB)

    # ── 지표 한 줄 ──
    y = 152
    mk = page["markets"][:5]
    gap = 10
    cw = (inner - gap * (len(mk) - 1)) / max(len(mk), 1)
    f_n, f_v, f_c = _font("regular", 20), _font("bold", 26), _font("bold", 20)
    arrows = {"up": "▲", "down": "▼", "flat": "-"}
    for i, m in enumerate(mk):
        x = PAD + i * (cw + gap)
        d.rounded_rectangle([x, y, x + cw, y + 108], radius=14, fill=CHIP_BG)
        d.text((x + 14, y + 10), m["name"], font=f_n, fill=SUB)
        d.text((x + 14, y + 38), _fit(d, m["text"], f_v, cw - 20), font=f_v, fill=TEXT)
        color = UP if m["direction"] == "up" else DOWN if m["direction"] == "down" else SUB
        d.text((x + 14, y + 74), f"{arrows[m['direction']]} {m['change']}", font=f_c, fill=color)

    # ── 오늘의 핵심 3줄 ──
    y = 290
    d.text((PAD, y), "오늘의 핵심", font=_font("bold", 30), fill=TEXT)
    y += 50
    f_hl, f_num = _font("bold", 32), _font("bold", 24)
    for i, h in enumerate(b["headlines"][:3], 1):
        d.ellipse([PAD, y + 6, PAD + 38, y + 44], fill=HEADER)
        d.text((PAD + 19, y + 25), str(i), font=f_num, fill=(255, 255, 255), anchor="mm")
        d.text((PAD + 54, y + 2), _fit(d, h, f_hl, inner - 54), font=f_hl, fill=TEXT)
        y += 56

    # ── 분야별 뉴스 2개씩 ──
    y += 14
    d.line([PAD, y, W - PAD, y], fill=LINE, width=2)
    y += 20
    f_tag, f_row = _font("bold", 23), _font("regular", 28)
    tag_col = 150
    for i, sec in enumerate(b["sections"][:4]):
        titles = [it["kakao_title"] or it["title"] for it in sec["items"]]
        picks = [t for t in titles if t not in b["headlines"]][:2] or titles[:2]
        if not picks:
            continue
        color = SECTION_COLORS[i % len(SECTION_COLORS)]
        tw = int(d.textlength(sec["name"], font=f_tag)) + 24
        d.rounded_rectangle([PAD, y + 2, PAD + tw, y + 40], radius=10, fill=color)
        d.text((PAD + 12, y + 21), sec["name"], font=f_tag, fill=(255, 255, 255), anchor="lm")
        for k, t in enumerate(picks):
            d.text((PAD + tag_col, y + 21 + k * 44), "· " + _fit(d, t, f_row, inner - tag_col - 30),
                   font=f_row, fill=TEXT, anchor="lm")
        y += 44 * len(picks) + 16

    # ── 오늘의 시사점 ──
    y += 6
    f_ins = _font("regular", 26)
    lines = _wrap(d, b.get("insight_kakao") or " ".join(b["insight"]), f_ins, inner - 48, 3)
    box_h = 64 + 40 * len(lines) + 12
    box_h = min(box_h, H - 24 - y)
    d.rounded_rectangle([PAD, y, W - PAD, y + box_h], radius=18, fill=INSIGHT_BG)
    d.text((PAD + 24, y + 16), "오늘의 시사점", font=_font("bold", 26), fill=INSIGHT_TX)
    for k, line in enumerate(lines):
        d.text((PAD + 24, y + 60 + k * 40), line, font=f_ins, fill=TEXT)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
