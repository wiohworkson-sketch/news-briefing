"""카카오톡 '나에게 보내기'로 브리핑을 보낸다."""
import base64
import json
import os
import time
from pathlib import Path

import requests

from .publish import decrypt, encrypt

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "kakao.enc"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
SECTION_ICONS = ["📈", "🌏", "💻", "🏙️", "📰", "📰"]


def _state_key() -> bytes:
    return base64.b64decode(os.environ["STATE_KEY"])


def save_refresh_token(token: str, expires_in: int | None) -> None:
    STATE.parent.mkdir(exist_ok=True)
    data = {"refresh_token": token, "expires_at": int(time.time()) + (expires_in or 0)}
    STATE.write_text(json.dumps(encrypt(_state_key(), json.dumps(data).encode())), encoding="utf-8")


def _load_state() -> dict:
    return json.loads(decrypt(_state_key(), json.loads(STATE.read_text(encoding="utf-8"))))


def exchange_code(code: str, redirect_uri: str) -> dict:
    """최초 연결: 인가 코드를 토큰으로 교환한다."""
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": os.environ["KAKAO_REST_KEY"],
        "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
        "redirect_uri": redirect_uri,
        "code": code,
    }, timeout=20)
    resp.raise_for_status()
    tok = resp.json()
    save_refresh_token(tok["refresh_token"], tok.get("refresh_token_expires_in"))
    return tok


def access_token() -> str:
    state = _load_state()
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_KEY"],
        "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
        "refresh_token": state["refresh_token"],
    }, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"카카오 로그인 갱신 실패 ({resp.status_code}): {resp.text}")
    tok = resp.json()
    if tok.get("refresh_token"):  # 만료 1개월 전부터 새 토큰이 발급됨 → 저장
        save_refresh_token(tok["refresh_token"], tok.get("refresh_token_expires_in"))
        print("[정보] 카카오 로그인이 자동 연장되었습니다.")
    return tok["access_token"]


def send(template: dict, token: str) -> None:
    resp = requests.post(
        MEMO_URL,
        headers={"Authorization": f"Bearer {token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"카톡 전송 실패 ({resp.status_code}): {resp.text}")


def send_text(text: str, url: str, token: str | None = None) -> None:
    token = token or access_token()
    link = {"web_url": url, "mobile_web_url": url}
    send({"object_type": "text", "text": text[:200], "link": link, "button_title": "열어보기"}, token)


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def build_image_message(page: dict, url: str, image_url: str) -> dict:
    """큰 이미지 카드 1장 (카톡에서 화면 가득 보임)."""
    link = {"web_url": url, "mobile_web_url": url}
    insight = {"web_url": url + "#insight", "mobile_web_url": url + "#insight"}
    headlines = page["briefing"]["headlines"]
    return {
        "object_type": "feed",
        "content": {
            "title": f"📰 {_cut(headlines[0], 30)}" if headlines else f"{page['date_label']} 아침 브리핑",
            "description": f"{page['date_label']} 아침 브리핑",
            "image_url": image_url,
            "image_width": 900,
            "image_height": page.get("image_height", 1200),
            "link": link,
        },
        "buttons": [
            {"title": "전체 브리핑", "link": link},
            {"title": "시사점·일정", "link": insight},
        ],
    }


def build_messages(page: dict, url: str) -> list[dict]:
    """(예전 방식) 글자 카드 여러 개. 이미지를 만들 수 없을 때 대신 사용."""
    b = page["briefing"]
    link = lambda anchor="": {"web_url": url + anchor, "mobile_web_url": url + anchor}
    msgs = []

    # ① 지표 + 핵심 3줄 (피드형: 지표가 표로 정렬됨)
    arrows = {"up": "▲", "down": "▼", "flat": ""}
    items = [{"item": m["name"][:6], "item_op": f"{m['text']} {arrows[m['direction']]}{m['change']}".strip()}
             for m in page["markets"][:5]]
    msgs.append({
        "object_type": "feed",
        "content": {
            "title": f"☀️ {page['date_label']} 아침 브리핑",
            "description": "\n".join("▸ " + _cut(h, 25) for h in b["headlines"][:3]),
            "link": link(),
        },
        "item_content": {"items": items},
        "button_title": "전체 브리핑 보기",
    })

    # ②~⑤ 분야별 헤드라인 (리스트형: 제목 + 한 줄 설명)
    for i, sec in enumerate(b["sections"]):
        contents = []
        for it in sec["items"][:3]:
            src = page["articles"].get(str(it["article_ids"][0]), {}).get("source", "") if it["article_ids"] else ""
            desc = _cut(it["kakao_desc"], 22) + (f" · {src}" if src else "")
            contents.append({"title": _cut(it["kakao_title"], 22), "description": desc, "link": link(f"#sec-{i}")})
        if len(contents) < 2:
            continue
        msgs.append({
            "object_type": "list",
            "header_title": f"{SECTION_ICONS[i % len(SECTION_ICONS)]} {sec['name']}",
            "header_link": link(f"#sec-{i}"),
            "contents": contents,
            "button_title": "전체 브리핑 보기",
        })

    # ⑥ 시사점 + 일정 (텍스트형, 200자 제한)
    sched = "\n".join(f"⏰ {s['time']} {_cut(s['event'], 18)}" for s in b["schedule"][:4])
    text = f"💡 오늘의 시사점\n{_cut(b['insight_kakao'], 90)}"
    if sched:
        text += f"\n\n📅 오늘의 일정\n{sched}"
    msgs.append({"object_type": "text", "text": _cut(text, 200), "link": link("#insight"),
                 "button_title": "전체 브리핑 보기"})
    return msgs


def _wait_for(image_url: str, timeout: int = 420) -> bool:
    """웹페이지에 이미지가 올라올 때까지 기다린다 (GitHub 게시에 1~3분 소요)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.head(image_url, timeout=10).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(15)
    return False


def send_briefing(page: dict, url: str, image_url: str | None = None) -> None:
    token = access_token()
    if image_url and _wait_for(image_url):
        send(build_image_message(page, url, image_url), token)
        return
    print("[경고] 이미지를 사용할 수 없어 글자 카드로 보냅니다.")
    for i, msg in enumerate(build_messages(page, url)):
        try:
            send(msg, token)
        except RuntimeError:
            if msg["object_type"] != "feed":
                raise
            # 지표 칸은 숫자·기호만 허용될 수 있어, 거절되면 등락 표시 없이 재시도
            for it in msg["item_content"]["items"]:
                it["item_op"] = page["markets"][msg["item_content"]["items"].index(it)]["text"]
            send(msg, token)
        time.sleep(0.5)
