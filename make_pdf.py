"""그날 브리핑을 A3 한 장짜리 PDF로 만든다 (docs/pdf/날짜.pdf).

내용이 많은 날에는 한 장에 들어갈 때까지 글씨 배율을 조금씩 줄인다.
사용: python make_pdf.py 2026-10-20 http://127.0.0.1:8799
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / "docs" / "pdf"
ZOOMS = ["1.1", "1.0", "0.92", "0.85", "0.78", "0.7"]
KEEP_DAYS = 14  # 저장소가 너무 커지지 않도록 최근 2주치만 보관

BROWSERS = ["google-chrome", "chromium", "chromium-browser",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]


def browser() -> str:
    for b in BROWSERS:
        if shutil.which(b) or Path(b).exists():
            return shutil.which(b) or b
    raise RuntimeError("PDF를 만들 브라우저(Chrome)를 찾지 못했습니다")


def render(url: str, out: Path) -> int:
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                        f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=20000",
                        f"--print-to-pdf={out}", url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)
    return len(PdfReader(out).pages) if out.exists() else 0


def main(date: str, base: str) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    out = PDF_DIR / f"{date}.pdf"
    for z in ZOOMS:
        pages = render(f"{base}/?d={date}&pz={z}", out)
        print(f"[정보] A3 PDF 배율 {z} → {pages}쪽")
        if pages == 1:
            break
    else:
        print("[경고] 가장 작은 배율에서도 한 장을 넘었습니다")
    for old in sorted(PDF_DIR.glob("*.pdf"))[:-KEEP_DAYS]:
        old.unlink()
    print(f"[완료] A3 PDF 저장: {out.name}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2].rstrip("/"))
