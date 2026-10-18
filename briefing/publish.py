"""브리핑을 암호화해서 웹페이지(docs/)에 저장한다."""
import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
ITERATIONS = 310_000  # 웹페이지(index.html)의 값과 같아야 함


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _key_from_password(password: str) -> bytes:
    meta_path = DATA / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        DATA.mkdir(parents=True, exist_ok=True)
        meta = {"salt": _b64(os.urandom(16)), "iterations": ITERATIONS}
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=base64.b64decode(meta["salt"]), iterations=meta["iterations"])
    return kdf.derive(password.encode())


def encrypt(key: bytes, data: bytes) -> dict:
    iv = os.urandom(12)
    return {"iv": _b64(iv), "ct": _b64(AESGCM(key).encrypt(iv, data, None))}


def decrypt(key: bytes, blob: dict) -> bytes:
    return AESGCM(key).decrypt(base64.b64decode(blob["iv"]), base64.b64decode(blob["ct"]), None)


def save(page: dict, date: str, password: str) -> None:
    key = _key_from_password(password)
    blob = encrypt(key, json.dumps(page, ensure_ascii=False).encode())
    (DATA / f"{date}.json").write_text(json.dumps(blob), encoding="utf-8")

    index_path = DATA / "index.json"
    dates = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    if date not in dates:
        dates.append(date)
    dates.sort(reverse=True)
    index_path.write_text(json.dumps(dates), encoding="utf-8")
