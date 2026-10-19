"""최초 설정 도우미 — 터미널에서 `python setup.py` 실행.

입력한 키와 비밀번호는 화면에 표시되지 않으며, GitHub의 암호화된 Secrets에만 저장됩니다.
(로컬 테스트용으로 이 폴더의 .env 파일에도 저장되며, 이 파일은 GitHub에 올라가지 않습니다.)
"""
import base64
import getpass
import http.server
import os
import secrets
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 5678
REDIRECT = f"http://localhost:{PORT}/kakao"


def ask(label: str, hidden: bool = True) -> str:
    while True:
        v = (getpass.getpass if hidden else input)(f"  {label}: ").strip()
        if v:
            return v
        print("    값을 입력하세요.")


def gh_secret(name: str, value: str) -> None:
    subprocess.run(["gh", "secret", "set", name], input=value.encode(), check=True,
                   stdout=subprocess.DEVNULL)


def kakao_login(rest_key: str) -> str:
    code_box = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_box["code"] = q.get("code", [""])[0]
            code_box["error"] = q.get("error_description", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "카카오 연결 완료! 이 창을 닫고 터미널로 돌아가세요." if code_box["code"] else "연결 실패: " + code_box["error"]
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    url = ("https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode(
        {"client_id": rest_key, "redirect_uri": REDIRECT, "response_type": "code", "scope": "talk_message"}))
    print("\n  브라우저에서 카카오 로그인 → '카카오톡 메시지 전송' 동의를 눌러주세요.")
    print(f"  (창이 안 열리면 이 주소를 복사해 브라우저에 붙여넣기)\n  {url}\n")
    webbrowser.open(url)
    while "code" not in code_box:
        threading.Event().wait(0.5)
    server.server_close()
    if not code_box["code"]:
        sys.exit(f"  카카오 연결 실패: {code_box['error']}")
    return code_box["code"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n=== 아침 뉴스 브리핑 최초 설정 ===")
    print("입력하는 내용은 화면에 보이지 않습니다. 붙여넣기(마우스 오른쪽 클릭) 후 Enter를 누르세요.\n")

    print("[1/4] Google Gemini 무료 키 (aistudio.google.com 에서 발급, AIza로 시작)")
    gemini_key = ask("Gemini 키")
    print("[2/4] 카카오 앱 키 (카카오 개발자 > 내 애플리케이션 > 앱 키)")
    rest_key = ask("REST API 키")
    client_secret = ask("Client Secret 코드 (카카오 로그인 > 보안)")
    print("[3/4] 브리핑 웹페이지 비밀번호 (휴대폰에서 한 번 입력)")
    while True:
        pw = ask("비밀번호")
        if pw == ask("비밀번호 확인"):
            break
        print("    두 비밀번호가 다릅니다. 다시 입력하세요.")

    state_key = base64.b64encode(secrets.token_bytes(32)).decode()
    values = {
        "GEMINI_API_KEY": gemini_key,
        "KAKAO_REST_KEY": rest_key,
        "KAKAO_CLIENT_SECRET": client_secret,
        "BRIEFING_PASSWORD": pw,
        "STATE_KEY": state_key,
    }
    os.environ.update(values)

    print("\n[4/4] 카카오 로그인")
    sys.path.insert(0, str(ROOT))
    from briefing import kakao
    kakao.exchange_code(kakao_login(rest_key), REDIRECT)

    pages = subprocess.run(["gh", "repo", "view", "--json", "owner,name", "-q",
                            '"https://" + .owner.login + ".github.io/" + .name + "/"'],
                           capture_output=True, text=True, check=True).stdout.strip()
    values["PAGES_URL"] = pages
    kakao.send_text("✅ 아침 뉴스 브리핑이 카카오톡과 연결되었습니다.\n내일부터 매일 오전 7시에 브리핑을 보내드릴게요.", pages)
    print("  카톡으로 연결 확인 메시지를 보냈습니다.")

    print("\n  GitHub에 안전하게 저장하는 중…")
    for k, v in values.items():
        if k != "PAGES_URL":
            gh_secret(k, v)
    (ROOT / ".env").write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    print("\n=== 설정 완료! 이 창은 닫으셔도 됩니다. ===\n")


if __name__ == "__main__":
    main()
