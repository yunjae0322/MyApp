# 🛒 쇼핑 리스트

아이템 추가 · 수정 · 삭제 · 체크 기능이 있는 가벼운 쇼핑 리스트 앱입니다. (Streamlit)

**배포 URL:** https://<앱이름>.streamlit.app <!-- 배포 후 실제 주소로 바꿔 주세요 -->

요구사항은 [PRD.md](PRD.md)를 참고하세요.

> 리스트는 브라우저 세션에만 저장됩니다. 새로고침하거나 창을 닫으면 사라집니다. (PRD 5.1 MVP)

## 로컬 실행

Python 3.10 이상이 필요합니다.

```bash
# (선택) 가상환경
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.

## 배포 (Streamlit Community Cloud)

1. 이 폴더를 GitHub 저장소에 push 합니다. (`app.py`, `requirements.txt`, `.streamlit/config.toml`이 저장소 루트에 있어야 합니다)
2. [share.streamlit.io](https://share.streamlit.io)에 GitHub 계정으로 로그인합니다.
3. **Create app** → **Deploy a public app from GitHub** 를 선택합니다.
4. 저장소 / 브랜치(`main`) / 메인 파일 경로(`app.py`)를 지정합니다.
5. 원하면 **App URL**에 주소를 정합니다. (예: `my-shopping-list` → `https://my-shopping-list.streamlit.app`)
6. **Advanced settings**에서 Python 버전을 **3.12**로 선택합니다.
7. **Deploy** 를 누르면 몇 분 뒤 앱이 열립니다.

코드를 수정해 `main`에 push 하면 배포된 앱에 자동으로 반영됩니다.

## 테스트

`tests/qa_playwright.js`는 PRD 기준 E2E 점검 스크립트입니다. 앱을 `streamlit run app.py --server.headless true`로 띄운 뒤 Playwright MCP의 `browser_run_code_unsafe`에 파일 경로를 넘겨 실행합니다. 자세한 내용은 [CLAUDE.md](CLAUDE.md)를 참고하세요.
