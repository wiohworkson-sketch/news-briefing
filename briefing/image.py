"""카톡에 크게 보이는 브리핑 카드 이미지(900x1200)를 그린다."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 1200
PAD = 48
BG = (250, 249, 245)
CARD = (255, 255, 255)
TEXT = (31, 30, 28)
SUB = (110, 108, 102)
LINE = (227, 225, 217)
UP = (208, 59, 59)
DOWN = (37, 99, 201)
HEADER = (24, 32, 56)
SECTION_COLORS = [(216, 90, 48), (83, 74, 183), (29, 158, 117), (186, 117, 23), (153, 53, 86), (24, 95, 165)]

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


def _fit(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    """한 줄에 들어가도록 자르고, 넘치면 … 을 붙인다."""
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def render(page: dict, path: Path) -> None:
    b = page["briefing"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    inner = W - PAD * 2

    # 상단 제목 띠
    d.rectangle([0, 0, W, 150], fill=HEADER)
    d.text((PAD, 34), f"{page['date_label']} 아침 브리핑", font=_font("bold", 50), fill=(255, 255, 255))
    d.text((PAD, 100), f"국내외 기사 {page['article_count']}건 AI 요약", font=_font("regular", 26), fill=(190, 198, 220))

    # 지표 카드 (3 + 2)
    y = 178
    mk = page["markets"][:5]
    f_name, f_val, f_chg = _font("regular", 24), _font("bold", 36), _font("bold", 24)
    arrows = {"up": "▲", "down": "▼", "flat": ""}
    for row in (mk[:3], mk[3:]):
        if not row:
            continue
        gap = 14
        cw = (inner - gap * 2) // 3
        for i, m in enumerate(row):
            x = PAD + i * (cw + gap)
            d.rounded_rectangle([x, y, x + cw, y + 128], radius=16, fill=CARD, outline=LINE, width=2)
            d.text((x + 20, y + 14), m["name"], font=f_name, fill=SUB)
            d.text((x + 20, y + 44), _fit(d, m["text"], f_val, cw - 30), font=f_val, fill=TEXT)
            color = UP if m["direction"] == "up" else DOWN if m["direction"] == "down" else SUB
            d.text((x + 20, y + 90), f"{arrows[m['direction']]} {m['change']}".strip(), font=f_chg, fill=color)
        y += 128 + 14

    # 오늘의 핵심 3줄
    y += 14
    d.text((PAD, y), "오늘의 핵심", font=_font("bold", 34), fill=TEXT)
    y += 56
    f_hl = _font("bold", 34)
    for i, h in enumerate(b["headlines"][:3], 1):
        d.ellipse([PAD, y + 4, PAD + 42, y + 46], fill=HEADER)
        d.text((PAD + 21, y + 25), str(i), font=_font("bold", 26), fill=(255, 255, 255), anchor="mm")
        d.text((PAD + 60, y), _fit(d, h, f_hl, inner - 60), font=f_hl, fill=TEXT)
        y += 62

    # 분야별 대표 뉴스 1줄씩
    y += 16
    d.line([PAD, y, W - PAD, y], fill=LINE, width=2)
    y += 26
    f_tag, f_row = _font("bold", 26), _font("regular", 31)
    for i, sec in enumerate(b["sections"][:4]):
        if not sec["items"]:
            continue
        color = SECTION_COLORS[i % len(SECTION_COLORS)]
        tag_w = int(d.textlength(sec["name"], font=f_tag)) + 28
        d.rounded_rectangle([PAD, y, PAD + tag_w, y + 44], radius=10, fill=color)
        d.text((PAD + 14, y + 22), sec["name"], font=f_tag, fill=(255, 255, 255), anchor="lm")
        # 오늘의 핵심과 겹치지 않는 뉴스를 고른다
        titles = [it["kakao_title"] or it["title"] for it in sec["items"]]
        title = next((t for t in titles if t not in b["headlines"]), titles[0])
        d.text((PAD + tag_w + 18, y + 22), _fit(d, title, f_row, inner - tag_w - 18), font=f_row, fill=TEXT, anchor="lm")
        y += 80

    # 하단 안내
    d.rectangle([0, H - 86, W, H], fill=(239, 237, 230))
    d.text((W // 2, H - 43), "아래 [전체 브리핑 보기]에서 시사점·일정·키워드 확인",
           font=_font("regular", 26), fill=SUB, anchor="mm")

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
