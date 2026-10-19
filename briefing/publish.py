"""브리핑을 웹페이지(docs/) 데이터로 저장한다. 카카오 로그인 정보 암호화 도구도 여기 있다."""
import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def encrypt(key: bytes, data: bytes) -> dict:
    iv = os.urandom(12)
    return {"iv": _b64(iv), "ct": _b64(AESGCM(key).encrypt(iv, data, None))}


def decrypt(key: bytes, blob: dict) -> bytes:
    return AESGCM(key).decrypt(base64.b64decode(blob["iv"]), base64.b64decode(blob["ct"]), None)


def save(page: dict, date: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"{date}.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")

    index_path = DATA / "index.json"
    dates = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    if date not in dates:
        dates.append(date)
    dates.sort(reverse=True)
    index_path.write_text(json.dumps(dates), encoding="utf-8")
