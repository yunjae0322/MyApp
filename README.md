# 🛒 쇼핑 리스트

아이템 추가 · 수정 · 삭제 · 체크 기능이 있는 가벼운 쇼핑 리스트 앱입니다. (Streamlit)

요구사항은 [PRD.md](PRD.md)를 참고하세요.

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
