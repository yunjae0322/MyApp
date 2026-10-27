# 단계별 개발 프롬프트 (AI 여행 동선 플래너)

`prd.md`를 기준으로, Claude Code에 단계별로 입력할 프롬프트입니다.
각 단계는 이전 단계 결과물이 있다는 전제로 작성했습니다. 한 단계가 끝나고 실행해서 확인한 뒤 다음 단계로 넘어가세요.

> 참고: 이 앱은 게임이 아니므로, 2단계 "게임 규칙 기능"은 앱의 **핵심 규칙(장소 필터 기준, 동선 생성 규칙)**을 구현하는 단계로 바꿨습니다.

---

## 1단계: 기본 뼈대 작성

```text
prd.md를 읽고, 그 내용대로 Streamlit 앱의 기본 뼈대를 app.py로 만들어줘.

목표: 화면 흐름과 데이터 흐름이 처음부터 끝까지 이어지는 최소 동작 버전.

요구사항:
1. 환경 설정
   - python-dotenv로 .env에서 OPENAI_API_KEY, OPENAI_MODEL(기본값 gpt-4o-mini), GOOGLE_MAPS_API_KEY(선택)를 읽어.
   - OPENAI_API_KEY가 없으면 안내 메시지를 띄우고 st.stop() 해줘.
   - requirements.txt와 .env.example도 만들어줘. 기존 .env 파일은 절대 수정하지 마.
2. 입력 화면 (PRD F1)
   - 여행지(text_input), 일정(date_input 날짜 범위, 오늘 이후, 최대 10일)
   - 이동 수단(대중교통/자동차/도보), 여행 강도(여유롭게/보통/알차게), 숙소/출발지(선택)
3. 단계 진행 구조
   - st.session_state로 "스타일 추천 → 스타일 선택 → 동선 결과" 단계를 관리해.
   - 여행지나 날짜가 바뀌면 이전 스타일과 결과를 초기화해.
4. OpenAI 연동 함수
   - ask_json(system, user) 함수 하나로 Chat Completions API를 JSON 모드(response_format=json_object)로 호출해.
   - 여행 스타일 추천 함수: 여행지에 맞는 스타일 8개를 {name, emoji, description, keywords[3], is_food} 형식으로 받아.
5. 지금 단계에서는 장소 검색과 동선 생성은 간단한 임시 구현(OpenAI가 장소 목록과 일정을 그대로 생성)이면 충분해.
   결과는 텍스트로만 출력해도 돼.

완료 조건:
- pip install -r requirements.txt 후 python -m streamlit run app.py 로 실행되고,
  여행지 입력 → 스타일 8개 표시 → 스타일 선택 → 일정 텍스트 출력까지 오류 없이 동작해야 해.
- 실행해서 직접 확인하고 결과를 알려줘.
```

---

## 2단계: 핵심 규칙 기능 추가

```text
prd.md의 F3~F5를 기준으로 app.py에 핵심 규칙 기능을 추가해줘. UI 디자인은 아직 신경 쓰지 마.

1. 장소 검색 (F3)
   - GOOGLE_MAPS_API_KEY가 있으면 Google Places API (New) Text Search
     (POST https://places.googleapis.com/v1/places:searchText, X-Goog-Api-Key, X-Goog-FieldMask 헤더)를 사용해.
     필드: id, displayName, formattedAddress, location, rating, userRatingCount, types, primaryType, googleMapsUri
   - 선택한 스타일의 keywords로 각각 검색하고, 식사 장소 확보를 위해 "{여행지} 맛집"은 항상 추가로 검색해.
   - 장소 id로 중복을 제거하고, 검색 결과는 st.cache_data(ttl=3600)로 캐시해.
   - 키가 없으면 OpenAI가 실제 장소 후보(이름, 주소, lat, lng, 추정 별점, 추정 리뷰 수, category, is_food)를 만들게 하고,
     구글지도 검색 URL을 붙여줘. 이 경우 결과가 "AI 추정치"라는 표시를 남겨.
2. 장소 필터링 (F4) — 가장 중요한 규칙
   - 음식점(is_food 또는 types에 restaurant/food/cafe/bakery/bar 등 포함)은
     별점 3.8 이상 AND 리뷰 200개 이상만 남겨. 기준값은 상수(MIN_FOOD_RATING, MIN_FOOD_REVIEWS)로 분리해.
   - 음식점이 아닌 장소는 (Google 모드에서) 리뷰 30개 미만만 제외해.
   - 별점 × min(리뷰 수, 5000) 순으로 정렬하고 상위 70곳만 후보로 써.
3. 동선 생성 (F5)
   - 후보 장소를 위도/경도로 k-means 클러스터링해서 여행 일수만큼 권역(area)으로 나눠. 외부 라이브러리 없이 구현해.
   - OpenAI에 후보 목록(id, name, area, category, is_food, rating, reviews, lat, lng)을 주고 다음 규칙으로 일정을 JSON으로 받아:
     · 하루는 한 area 위주로 구성하고 다른 area로 왔다 갔다 하지 않기
     · 하루 안에서는 이동 거리가 최소가 되도록 순서 정하기
     · 매일 점심·저녁은 is_food 장소, 같은 장소 중복 금지
     · 여행 강도별 하루 장소 수: 여유롭게 4 / 보통 5 / 알차게 7
     · 형식: {summary, days:[{day, date, theme, stops:[{id, time, stay, note, move}]}], tips}
   - 응답의 id를 후보 목록과 대조해 없는 id는 버리고, 실제 장소 정보를 붙여.
4. 오류 처리
   - Google API 오류(HTTP 상태 코드와 메시지), 조건을 만족하는 장소가 0곳일 때, 동선 생성 실패 시 사용자에게 안내해.

완료 조건:
- 출력된 모든 음식점이 별점 3.8 이상·리뷰 200개 이상인지 코드로 확인하는 짧은 검증을 해보고 결과를 알려줘.
- 실제로 "부산, 2박 3일, 맛집 탐방 + 해변 휴양"으로 실행해서 하루 동선이 한 지역 안에 모이는지 확인해줘.
```

---

## 3단계: UI 디자인

```text
prd.md의 F6, F7과 5장(비기능 요구사항: 사용성)을 기준으로 app.py의 UI를 다듬어줘. 기능 로직은 바꾸지 마.

1. 전체 레이아웃
   - st.set_page_config(page_title="AI 여행 동선 플래너", page_icon="🧳", layout="wide")
   - 제목과 한 줄 설명, "1️⃣ 여행지와 일정", "2️⃣ 선호하는 여행 스타일" 처럼 단계 번호가 보이는 소제목.
   - 입력 칸은 st.columns로 정리하고, 다음 단계 버튼은 type="primary"로 강조해.
2. 여행 스타일 선택
   - 스타일을 4열 카드(st.container(border=True)) 안의 체크박스로 보여주고, 아래에 한 줄 설명을 작게 표시.
   - 하나도 선택하지 않으면 "동선 짜기" 버튼을 비활성화.
3. 진행 상황
   - st.status로 "장소 검색 중 → 후보 N곳 중 M곳 통과 → 동선 최적화 중 → 완성" 단계를 보여줘.
4. 결과 화면
   - 상단에 전체 요약(st.info).
   - folium + streamlit-folium 지도: 날짜별 다른 색 마커(음식점은 식기 아이콘, 관광지는 깃발 아이콘), 같은 날 장소는 경로선으로 연결,
     툴팁에 "Day1-2. 장소명", 모든 마커가 보이도록 fit_bounds.
   - Day별 탭: 날짜·테마, "📍 구글지도에서 이 날 동선 보기" 버튼
     (google.com/maps/dir/?api=1, origin/destination/waypoints 최대 9개, 이동 수단 반영),
     방문지 카드(시간, 아이콘, 번호, 구글지도 링크가 걸린 장소명, 주소, ⭐별점·리뷰 수, 💡팁과 체류 시간),
     카드 사이에 "⬇️ 이동 방법" 표시.
   - 여행 팁은 expander로, AI 모드일 때는 "AI 추정치" 안내 문구를 하단에 표시.
5. 사이드바
   - 사용 중인 모델, 장소 검색 모드(Google/AI)를 success/warning으로 구분 표시,
     음식점 기준(⭐3.8 이상·리뷰 200개 이상), "처음부터 다시" 버튼.

완료 조건:
- 실행해서 데스크톱 화면과 좁은 화면에서 레이아웃이 깨지지 않는지 확인하고, 스크린샷 기준으로 결과를 알려줘.
```

---

## 4단계: PRD 대비 검토 및 버그 점검 (Playwright 활용)

```text
지금 app.py가 prd.md대로 개발되었는지, 버그가 없는지 자세하게 검토해줘. 코드를 고치기 전에 먼저 검토 결과를 보고해줘.

1. 코드 리뷰 (정적 검토)
   - prd.md의 F1~F7, 비기능 요구사항, 환경 변수 항목을 하나씩 체크리스트로 만들고
     각각 [구현됨 / 부분 구현 / 미구현]과 근거가 되는 코드 위치(파일:줄)를 적어줘.
   - 버그 가능성 점검: session_state 초기화 누락, 날짜 하나만 선택했을 때, 10일 초과,
     LLM이 JSON 형식을 어기거나 없는 id를 줄 때, 좌표가 없는 장소, 장소가 1곳뿐일 때(지도·k-means),
     Google API 오류, 캐시가 잘못된 결과를 재사용하는 경우, API 키가 화면·로그에 노출되는지.
2. E2E 테스트 (Playwright MCP 사용)
   - python -m streamlit run app.py --server.headless true --server.port 8501 로 앱을 띄우고
     Playwright로 http://localhost:8501 에 접속해 다음 시나리오를 실행해:
     a. 정상 흐름: 여행지 "부산", 2박 3일 → 스타일 추천 → 스타일 2개 선택 → 동선 짜기 → 결과 확인
        · Day 탭 개수가 여행 일수와 같은지
        · 모든 음식점 카드의 별점이 3.8 이상, 리뷰가 200 이상인지 (화면 텍스트에서 추출해 검사)
        · 지도와 "구글지도에서 이 날 동선 보기" 링크가 있는지, 링크의 travelmode가 선택한 이동 수단과 맞는지
     b. 예외 흐름: 여행지 빈 값일 때 버튼 비활성화, 스타일 미선택 시 "동선 짜기" 비활성화,
        11일 이상 선택 시 경고, "처음부터 다시" 동작, 여행지 변경 시 이전 결과 초기화
     c. 해외 여행지(예: 도쿄) 1박 2일로 한 번 더 실행
   - Streamlit은 비동기로 다시 그려지므로 각 동작 후 요소가 나타날 때까지 기다리고,
     단계마다 스크린샷을 찍어줘. 브라우저 콘솔 오류와 서버 로그 오류도 확인해.
3. 보고 형식
   - PRD 체크리스트 표
   - 발견한 버그 목록: 심각도(높음/중간/낮음), 재현 방법, 원인 코드 위치, 수정 제안
   - E2E 시나리오별 통과/실패 결과와 스크린샷
   - 확인하지 못한 항목(예: Google 키가 없어 Google 모드 미검증)은 따로 명시
4. 보고 후, 심각도 높음·중간 버그를 수정하고 같은 Playwright 시나리오를 다시 돌려 통과하는지 확인해줘.
```
