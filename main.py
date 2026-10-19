"""아침 뉴스 브리핑 실행 파일.

  python main.py build          뉴스 수집 → AI 정리 → 암호화 웹페이지 저장
  python main.py send --at 07:00  지정 시각(한국시간)까지 기다렸다가 카톡 발송
  python main.py notify-error   실패 알림 카톡 발송
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out" / "today.json"
KST = timezone(timedelta(hours=9))
WEEKDAYS = "월화수목금토일"


def load_env_file() -> None:
    """로컬 테스트용 .env 파일이 있으면 읽는다 (GitHub에서는 Secrets 사용)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def pages_url(date: str) -> str:
    base = os.environ.get("PAGES_URL", "").rstrip("/")
    return f"{base}/?d={date}"


def cmd_build() -> None:
    from briefing import collect, markets, publish, summarize

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    now = datetime.now(KST)
    date = now.strftime("%Y-%m-%d")
    date_label = f"{now.month}월 {now.day}일({WEEKDAYS[now.weekday()]})"

    articles, errors = collect.fetch_all(cfg)
    print(f"[정보] 기사 {len(articles)}건 수집 (실패한 출처 {len(errors)}곳)")
    for e in errors:
        print(f"  - 실패: {e}")
    if len(articles) < 20:
        raise RuntimeError("수집된 기사가 너무 적습니다. 뉴스 출처 주소를 확인하세요.")

    mk = markets.fetch(cfg)
    outlook_mk = markets.fetch(cfg, "outlook_markets")
    expiry = markets.option_expiry_note(now.date())
    from briefing import naver
    night = naver.night_futures()
    print(f"[정보] 야간선물 기사 문장 {len(night)}개")
    b = summarize.make_briefing(articles, mk, f"{now.year}년 {date_label}", cfg,
                                outlook_mk, expiry, night).model_dump()

    used = set()
    for sec in b["sections"]:
        for it in sec["items"]:
            used.update(it["article_ids"])
    for kw in b["keywords"]:
        for it in kw["items"]:
            used.update(it["article_ids"])
    for p in b["perspectives"]:
        used.update(p["article_ids"])
    used.update(b["market"]["article_ids"])
    by_id = {a["id"]: a for a in articles}
    page = {
        "date": date,
        "date_label": date_label,
        "generated_at": now.strftime("%H:%M"),
        "article_count": len(articles),
        "markets": mk,
        "outlook_markets": outlook_mk,
        "briefing": b,
        "articles": {str(i): {k: by_id[i][k] for k in ("title", "url", "source", "origin")}
                     for i in sorted(used) if i in by_id},
    }
    try:  # 카톡용 큰 카드 이미지 (실행마다 새 이름 → 카톡 캐시 방지)
        from briefing import image
        page["image"] = f"img/{date}-{now.strftime('%H%M')}.png"
        page["image_height"] = image.render(page, ROOT / "docs" / page["image"])
        page["market_image"] = f"img/{date}-{now.strftime('%H%M')}-market.png"
        page["market_image_height"] = image.render_market(page, ROOT / "docs" / page["market_image"])
    except Exception as e:
        print(f"[경고] 카드 이미지 생성 실패: {e}")
        page.pop("image", None)
        page.pop("image_height", None)
        page.pop("market_image", None)
    publish.save(page, date)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(page, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[완료] {date_label} 브리핑 저장")


def cmd_send(at: str | None) -> None:
    from briefing import kakao

    page = json.loads(OUT.read_text(encoding="utf-8"))
    if at:
        h, m = map(int, at.split(":"))
        target = datetime.now(KST).replace(hour=h, minute=m, second=0, microsecond=0)
        wait = (target - datetime.now(KST)).total_seconds()
        if 0 < wait < 3 * 3600:
            print(f"[정보] {at}까지 {int(wait // 60)}분 대기합니다.")
            time.sleep(wait)
    base = os.environ.get("PAGES_URL", "").rstrip("/")
    image_url = f"{base}/{page['image']}" if page.get("image") else None
    market_url = f"{base}/{page['market_image']}" if page.get("market_image") else None
    kakao.send_briefing(page, pages_url(page["date"]), image_url, market_url)
    print("[완료] 카톡 발송")


def cmd_notify_error() -> None:
    from briefing import kakao

    run = os.environ.get("RUN_URL", os.environ.get("PAGES_URL", "https://github.com"))
    kakao.send_text("⚠️ 오늘 아침 브리핑을 만들지 못했습니다.\n버튼을 눌러 GitHub 실행 기록을 확인하거나 Claude에게 문의하세요.", run)


def main() -> None:
    load_env_file()
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["build", "send", "notify-error"])
    p.add_argument("--at", help="발송 시각 HH:MM (한국시간)")
    args = p.parse_args()
    if args.command == "build":
        cmd_build()
    elif args.command == "send":
        cmd_send(args.at)
    else:
        cmd_notify_error()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
