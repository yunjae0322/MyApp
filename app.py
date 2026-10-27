"""여행 일정을 짜주는 AI Agent (4단계 검토 반영 완료)

동작 흐름: 여행지 입력 -> 일정 입력 -> 선호하는 여행 스타일 선택 -> 동선 출력
장소 검색(Google Places 또는 OpenAI) -> 필터링(음식점 별점 3.8↑·리뷰 200↑) -> 권역 분할 -> 동선 생성
결과는 지도(날짜별 색상 마커·경로선)와 Day별 카드로 보여준다.
"""

import html
import json
import math
import os
from datetime import date, timedelta
from urllib.parse import quote

import folium
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from streamlit_folium import st_folium

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

MAX_DAYS = 10
PLACES_PER_DAY = {"여유롭게": 4, "보통": 5, "알차게": 7}

# 문제정의서 기준: 음식점은 별점 3.8 이상, 후기 200개 이상
MIN_FOOD_RATING = 3.8
MIN_FOOD_REVIEWS = 200
MIN_SPOT_REVIEWS = 30  # 음식점이 아닌 장소의 최소 리뷰 수 (Google 모드)
MAX_CANDIDATES = 70
SAME_SPOT_KM = 0.3  # 이 거리 안의 관광지는 같은 장소로 본다
MEAL_TIMES = ("12:30", "18:30")  # 점심, 저녁 기준 시각
MEAL_WINDOWS = {"점심": ("11:30", "13:30", "12:30"), "저녁": ("17:30", "19:30", "18:30")}  # 시작, 끝, 자동 추가 시각
MAX_FOOD_PER_DAY = 3  # 점심 + 저녁 + 카페/간식 1곳

MAX_WAYPOINTS = 9  # 구글지도 길찾기 URL의 경유지 최대 개수
DAY_COLORS = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue", "darkgreen", "pink", "gray"]

FOOD_TYPES = {"restaurant", "food", "cafe", "bakery", "bar", "meal_takeaway", "coffee_shop"}
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELDS = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.types",
    "places.primaryType",
    "places.googleMapsUri",
])


class PlanError(Exception):
    """사용자에게 그대로 보여줄 수 있는 동선 생성 실패."""


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
@st.cache_resource
def get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def ask_json(system: str, user: str, temperature: float = 0.7) -> dict:
    """OpenAI 챗 모델에 JSON 형식 응답을 요청한다."""
    resp = get_client().chat.completions.create(
        model=OPENAI_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return json.loads(resp.choices[0].message.content)


@st.cache_data(show_spinner=False)
def suggest_styles(destination: str, nights: int) -> list[dict]:
    """여행지에 어울리는 여행 스타일 카테고리 8개를 생성한다."""
    data = ask_json(
        "너는 여행 기획 전문가야. 반드시 JSON으로만 답해.",
        f"""여행지: {destination} ({nights}박 {nights + 1}일)
이 여행지에서 고를 수 있는 여행 스타일 카테고리 8개를 만들어줘.
각 카테고리는 구글지도에서 검색할 키워드 3개를 포함해야 해. 키워드에는 여행지 이름을 넣어줘.
음식/카페 관련 카테고리는 is_food를 true로 해줘.

형식:
{{"styles": [{{"name": "맛집 탐방", "emoji": "🍜", "description": "한 줄 설명",
  "keywords": ["{destination} 맛집", "...", "..."], "is_food": true}}]}}""",
    )
    return data.get("styles", [])


# ---------------------------------------------------------------------------
# 장소 검색 (F3): Google Places API, 키가 없으면 OpenAI로 대체
# ---------------------------------------------------------------------------
def is_food_place(types: list[str]) -> bool:
    return bool(FOOD_TYPES.intersection(types or []))


@st.cache_data(show_spinner=False, ttl=3600)
def google_text_search(query: str) -> list[dict]:
    resp = requests.post(
        PLACES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": PLACES_FIELDS,
        },
        json={"textQuery": query, "languageCode": "ko", "maxResultCount": 20},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


def search_google(styles: list[dict], destination: str) -> list[dict]:
    queries = [(kw, s["name"], s.get("is_food", False)) for s in styles for kw in s.get("keywords", [])]
    # 스타일과 상관없이 식사 장소는 항상 필요하다
    queries.append((f"{destination} 맛집", "식사", True))

    places: dict[str, dict] = {}
    for query, category, food_style in queries:
        for p in google_text_search(query):
            if p["id"] in places or "location" not in p:
                continue
            types = p.get("types", [])
            places[p["id"]] = {
                "id": p["id"],
                "name": p.get("displayName", {}).get("text", ""),
                "address": p.get("formattedAddress", ""),
                "lat": p["location"]["latitude"],
                "lng": p["location"]["longitude"],
                "rating": p.get("rating", 0.0),
                "reviews": p.get("userRatingCount", 0),
                "category": category,
                "is_food": food_style or is_food_place(types),
                "url": p.get("googleMapsUri", ""),
            }
    return list(places.values())


def search_ai(styles: list[dict], destination: str, count: int) -> list[dict]:
    data = ask_json(
        "너는 여행지 정보에 해박한 가이드야. 실제로 존재하는 장소만 추천하고 반드시 JSON으로만 답해.",
        f"""여행지: {destination}
여행 스타일: {json.dumps([{"name": s["name"], "is_food": s.get("is_food", False)} for s in styles], ensure_ascii=False)}
위 스타일에 맞는 실제 장소 {count}곳을 추천해줘. 약 40%는 음식점/카페, 나머지 60%는 관광지·명소로 해줘.
장소들이 여행지 여러 지역에 고르게 퍼지도록 골라줘.
음식점은 구글지도 별점 {MIN_FOOD_RATING} 이상, 리뷰 {MIN_FOOD_REVIEWS}개 이상인 곳만 골라줘.
name은 구글지도에서 검색되는 실제 상호명/장소명으로 적어줘 ("{destination} 국밥" 같은 일반 명칭 금지).
rating과 reviews는 구글지도 기준 추정치, lat/lng는 정확한 좌표로 적어줘.

형식:
{{"places": [{{"name": "", "address": "", "lat": 0.0, "lng": 0.0, "rating": 4.3,
  "reviews": 1200, "category": "스타일 이름", "is_food": false}}]}}""",
        temperature=0.5,
    )
    places = []
    for i, p in enumerate(data.get("places", [])):
        try:
            lat, lng = float(p["lat"]), float(p["lng"])
            rating, reviews = float(p.get("rating") or 0), int(p.get("reviews") or 0)
        except (KeyError, TypeError, ValueError):
            continue  # 좌표나 숫자가 없는 장소는 동선에 쓸 수 없다
        name = p.get("name", "")
        places.append({
            "id": f"ai_{i}",
            "name": name,
            "address": p.get("address", ""),
            "lat": lat,
            "lng": lng,
            "rating": rating,
            "reviews": reviews,
            "category": p.get("category", ""),
            "is_food": bool(p.get("is_food")),
            "url": f"https://www.google.com/maps/search/?api=1&query={quote(f'{name} {destination}')}",
        })
    return places


# ---------------------------------------------------------------------------
# 장소 필터링 (F4)
# ---------------------------------------------------------------------------
def passes_food_rule(p: dict) -> bool:
    return p["rating"] >= MIN_FOOD_RATING and p["reviews"] >= MIN_FOOD_REVIEWS


def distance_km(p: dict, q: dict) -> float:
    dy = (p["lat"] - q["lat"]) * 111
    dx = (p["lng"] - q["lng"]) * 111 * math.cos(math.radians(p["lat"]))
    return math.hypot(dx, dy)


def filter_places(places: list[dict], source: str) -> list[dict]:
    """음식점은 별점/리뷰 기준을 적용하고, 나머지는 (Google 모드에서) 리뷰 수가 너무 적은 곳만 제외한다."""
    kept = []
    for p in places:
        if p["is_food"]:
            if passes_food_rule(p):
                kept.append(p)
        elif source == "ai" or p["reviews"] >= MIN_SPOT_REVIEWS:
            kept.append(p)
    kept.sort(key=lambda p: (p["rating"] or 0) * min(p["reviews"], 5000), reverse=True)

    # 관광지가 거의 같은 위치면 같은 장소로 본다 (예: "광안리 해변"과 "광안리 해수욕장")
    unique = []
    for p in kept:
        if p["is_food"] or all(q["is_food"] or distance_km(p, q) > SAME_SPOT_KM for q in unique):
            unique.append(p)
    return unique[:MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# 동선 생성 (F5)
# ---------------------------------------------------------------------------
def group_by_area(places: list[dict], k: int, iterations: int = 20) -> list[int]:
    """위도/경도로 장소를 k개 권역으로 나눈다 (간단한 k-means). 하루에 한 권역씩 돌도록 하기 위함."""
    k = max(1, min(k, len(places)))
    # 서로 멀리 떨어진 장소부터 중심으로 잡는다
    centers = [(places[0]["lat"], places[0]["lng"])]
    while len(centers) < k:
        far = max(places, key=lambda p: min((p["lat"] - c[0]) ** 2 + (p["lng"] - c[1]) ** 2 for c in centers))
        centers.append((far["lat"], far["lng"]))
    labels = [0] * len(places)
    for _ in range(iterations):
        labels = [
            min(range(k), key=lambda i: (p["lat"] - centers[i][0]) ** 2 + (p["lng"] - centers[i][1]) ** 2)
            for p in places
        ]
        for i in range(k):
            members = [p for p, label in zip(places, labels) if label == i]
            if members:
                centers[i] = (sum(p["lat"] for p in members) / len(members),
                              sum(p["lng"] for p in members) / len(members))
    return labels


def plan_route(destination, start_date, days, styles, places, pace, transport, base) -> dict:
    """후보 장소 목록을 바탕으로 일자별 동선을 짠다."""
    areas = group_by_area(places, days)
    candidates = [
        {
            "id": p["id"],
            "name": p["name"],
            "area": area + 1,
            "category": p["category"],
            "is_food": p["is_food"],
            "rating": p["rating"],
            "reviews": p["reviews"],
            "lat": round(p["lat"], 5),
            "lng": round(p["lng"], 5),
        }
        for p, area in zip(places, areas)
    ]
    dates = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]
    return ask_json(
        "너는 동선 최적화에 능숙한 여행 플래너야. 반드시 JSON으로만 답하고, 후보 목록에 있는 id만 사용해.",
        f"""여행지: {destination}
날짜: {", ".join(dates)}
선호 여행 스타일: {", ".join(s["name"] for s in styles)}
이동 수단: {transport}
숙소/출발지: {base or "미정"}
하루 방문 장소 수: 약 {PLACES_PER_DAY[pace]}곳 (점심·저녁 식사 장소 포함)

규칙:
- 후보는 위치에 따라 area(권역)로 나뉘어 있어. 하루는 되도록 한 area 안의 장소로만 구성하고, 다른 area로 왔다 갔다 하지 마.
- 하루 안에서는 위도/경도를 보고 이동 거리가 최소가 되도록 순서를 정해 (지나온 곳으로 되돌아가지 않기).
- 매일 점심(11:30~13:30 사이 1곳)과 저녁(17:30~19:30 사이 1곳)은 is_food=true 장소로 넣어.
  그 외 시간의 is_food 장소는 카페/간식으로 하루 최대 1곳까지만 넣어.
- 하루 일정은 보통 10:00 전후에 시작해서 저녁 식사 이후에 끝내.
- 같은 장소를 두 번 방문하지 마.
- 시간(time)은 "HH:MM" 형식, stay는 체류 시간(분).
- move는 다음 장소까지의 이동 방법과 예상 소요 시간 (마지막 장소는 빈 문자열).

후보 장소:
{json.dumps(candidates, ensure_ascii=False)}

형식:
{{"summary": "전체 일정 요약 2~3문장",
  "days": [{{"day": 1, "date": "YYYY-MM-DD", "theme": "그날의 테마",
    "stops": [{{"id": "후보 id", "time": "10:00", "stay": 90, "note": "추천 이유/팁", "move": "도보 10분"}}]}}],
  "tips": ["여행 팁"]}}""",
        temperature=0.4,
    )


def to_minutes(hhmm: str) -> int:
    try:
        h, m = str(hhmm).split(":")[:2]
        return int(h) * 60 + int(m)
    except ValueError:
        return 0


def limit_meals(stops: list[dict]) -> list[dict]:
    """하루 음식점을 점심·저녁 시각에 가장 가까운 곳과 간식 1곳까지만 남긴다."""
    foods = [s for s in stops if s["place"]["is_food"]]
    if len(foods) <= MAX_FOOD_PER_DAY:
        return stops
    keep = []
    for meal in MEAL_TIMES:
        rest = [s for s in foods if s not in keep]
        keep.append(min(rest, key=lambda s: abs(to_minutes(s.get("time")) - to_minutes(meal))))
    keep += [s for s in foods if s not in keep][:MAX_FOOD_PER_DAY - len(keep)]
    return [s for s in stops if not s["place"]["is_food"] or s in keep]


def fill_meals(stops: list[dict], foods: list[dict], used: set) -> list[dict]:
    """점심·저녁 시간대에 음식점이 없으면, 쓰지 않은 음식점 중 그날 동선에서 가장 가까운 곳을 끼워 넣는다."""
    for meal, (start, end, at) in MEAL_WINDOWS.items():
        lo, hi = to_minutes(start), to_minutes(end)
        if any(s["place"]["is_food"] and lo <= to_minutes(s.get("time")) <= hi for s in stops):
            continue
        pool = [p for p in foods if p["id"] not in used]
        if not pool or not stops:
            continue
        # 식사 시각 직전에 있던 장소(없으면 첫 장소) 근처의 음식점을 고른다
        before = [s for s in stops if to_minutes(s.get("time")) <= to_minutes(at)] or stops[:1]
        anchor = before[-1]["place"]
        p = min(pool, key=lambda q: distance_km(anchor, q))
        used.add(p["id"])
        stops.append({"id": p["id"], "time": at, "stay": 60, "note": f"{meal} 식사 (근처 기준 충족 음식점 자동 추가)",
                      "move": "", "place": p})
    return sorted(stops, key=lambda s: to_minutes(s.get("time")))


def attach_places(plan: dict, places: list[dict], start_date: date, num_days: int) -> list[dict]:
    """LLM이 돌려준 id를 실제 장소 정보와 연결한다.
    없는 id·중복 방문은 버리고, 빠진 식사는 채우고, 초과 식사는 줄이며, 일차·날짜는 실제 값으로 다시 매긴다."""
    by_id = {p["id"]: p for p in places}
    foods = [p for p in places if p["is_food"]]
    used = set()
    days = []
    for i, d in enumerate(plan.get("days", [])[:num_days]):
        stops = []
        for s in d.get("stops", []):
            sid = s.get("id")
            if isinstance(sid, str) and sid in by_id and sid not in used:
                used.add(sid)
                stops.append(dict(s, place=by_id[sid]))
        stops = limit_meals(fill_meals(stops, foods, used))
        if stops:
            days.append(dict(d, day=i + 1, date=(start_date + timedelta(days=i)).isoformat(), stops=stops))
    return days


def build_trip(destination, start_date, days, styles, pace, transport, base, progress=lambda msg: None) -> dict:
    """검색 -> 필터 -> 동선 생성 전체 파이프라인. progress로 진행 상황을 알린다."""
    if GOOGLE_MAPS_API_KEY:
        progress("🔎 구글지도에서 장소 검색 중...")
        raw, source = search_google(styles, destination), "google"
    else:
        progress("🔎 AI가 장소 후보를 찾는 중...")
        raw, source = search_ai(styles, destination, count=min(days * 10, 50)), "ai"
    places = filter_places(raw, source)
    progress(f"✅ 후보 {len(raw)}곳 중 기준을 통과한 {len(places)}곳 확보")
    if not places:
        raise PlanError("조건에 맞는 장소를 찾지 못했어요. 다른 스타일을 선택해보세요.")

    progress("🧭 일자별 동선을 최적화하는 중...")
    plan = plan_route(destination, start_date, days, styles, places, pace, transport, base)
    day_plans = attach_places(plan, places, start_date, days)
    if not day_plans:
        raise PlanError("동선 생성에 실패했어요. 다시 시도해주세요.")
    return {
        "plan": plan,
        "days": day_plans,
        "missing_days": days - len(day_plans),
        "source": source,
        "found": len(raw),
        "kept": len(places),
    }


# ---------------------------------------------------------------------------
# 출력 (F6): 지도 + Day별 카드
# ---------------------------------------------------------------------------
def directions_url(stops: list[dict], transport: str) -> str:
    """구글지도 길찾기 링크 (출발 -> 경유지 -> 도착)."""
    mode = {"대중교통": "transit", "자동차": "driving", "도보": "walking"}[transport]
    loc = lambda p: quote(f"{p['lat']},{p['lng']}")
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={loc(stops[0])}&destination={loc(stops[-1])}&travelmode={mode}"
    )
    middle = stops[1:-1][:MAX_WAYPOINTS]
    if middle:
        url += "&waypoints=" + quote("|".join(f"{p['lat']},{p['lng']}" for p in middle))
    return url


def draw_map(days: list[dict]) -> folium.Map:
    all_points = [[s["place"]["lat"], s["place"]["lng"]] for d in days for s in d["stops"]]
    center = [sum(p[0] for p in all_points) / len(all_points), sum(p[1] for p in all_points) / len(all_points)]
    # 휠 스크롤은 페이지 스크롤에 쓰고, 지도 확대/축소는 +/- 버튼으로 한다
    m = folium.Map(location=center, zoom_start=12, scrollWheelZoom=False)
    for d in days:
        color = DAY_COLORS[(d["day"] - 1) % len(DAY_COLORS)]
        coords = []
        for i, s in enumerate(d["stops"], 1):
            p = s["place"]
            coords.append([p["lat"], p["lng"]])
            name = html.escape(p["name"])
            folium.Marker(
                [p["lat"], p["lng"]],
                tooltip=f"Day{d['day']}-{i}. {name}",
                popup=folium.Popup(f"<b>Day{d['day']}-{i}. {name}</b><br>{html.escape(str(s.get('time', '')))}", max_width=250),
                icon=folium.Icon(color=color, icon="cutlery" if p["is_food"] else "flag"),
            ).add_to(m)
        if len(coords) > 1:
            folium.PolyLine(coords, color=color, weight=4, opacity=0.7).add_to(m)
    if len(all_points) > 1:
        m.fit_bounds(all_points)
    return m


def render_stop(i: int, s: dict):
    p = s["place"]
    icon = "🍽️" if p["is_food"] else "📌"
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        # 외부 데이터(장소명·주소)는 HTML로 해석되지 않도록 이스케이프한다
        name = html.escape(p["name"]).replace("[", "(").replace("]", ")")
        c1.markdown(
            f"**{html.escape(str(s.get('time', '')))} {icon} {i}. [{name}]({p['url']})**  \n"
            f"<small>{html.escape(p['address'])}</small>",
            unsafe_allow_html=True,
        )
        if p["rating"]:
            c2.markdown(f"⭐ **{p['rating']:.1f}**  \n<small>리뷰 {p['reviews']:,}</small>", unsafe_allow_html=True)
        if s.get("note"):
            stay = f" (체류 약 {s['stay']}분)" if s.get("stay") else ""
            st.caption(f"💡 {s['note']}{stay}")


def render_result(result: dict):
    plan, days = result["plan"], result["days"]

    st.subheader(f"🗺️ {result['destination']} 여행 동선")
    if plan.get("summary"):
        st.info(plan["summary"])
    if result.get("missing_days"):
        st.warning(f"AI가 {result['missing_days']}일치 일정을 만들지 못했어요. '동선 짜기'를 다시 눌러보세요.")

    st_folium(draw_map(days), height=480, use_container_width=True, returned_objects=[])

    tabs = st.tabs([f"Day {d['day']}" for d in days])
    for tab, d in zip(tabs, days):
        with tab:
            st.markdown(f"#### {d.get('date', '')} · {d.get('theme', '')}")
            st.link_button("📍 구글지도에서 이 날 동선 보기", directions_url([s["place"] for s in d["stops"]], result["transport"]))
            for i, s in enumerate(d["stops"], 1):
                render_stop(i, s)
                if s.get("move") and i < len(d["stops"]):
                    st.markdown(f"<div style='text-align:center;color:gray'>⬇️ {html.escape(str(s['move']))}</div>",
                                unsafe_allow_html=True)

    if plan.get("tips"):
        with st.expander("✈️ 여행 팁"):
            for t in plan["tips"]:
                st.markdown(f"- {t}")

    if result["source"] == "ai":
        st.caption("※ Google Maps API 키가 없어 별점·리뷰 수·좌표는 AI 추정치입니다. 장소 이름을 눌러 구글지도에서 확인하세요.")


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI 여행 동선 플래너", page_icon="🧳", layout="wide")
st.title("🧳 AI 여행 동선 플래너")
st.caption("여행지와 일정을 입력하고 여행 스타일을 고르면, 구글지도를 기반으로 동선을 짜드려요.")

if not OPENAI_API_KEY:
    st.error(".env 파일에 OPENAI_API_KEY를 설정해주세요.")
    st.stop()

# 사이드바 (F7)
with st.sidebar:
    st.header("⚙️ 설정")
    st.write(f"모델: `{OPENAI_MODEL}`")
    if GOOGLE_MAPS_API_KEY:
        st.success("Google Places API 사용 중")
    else:
        st.warning("GOOGLE_MAPS_API_KEY가 없어 AI가 장소를 추천합니다. (구글지도 링크는 제공)")
    st.markdown(f"**음식점 기준**  \n⭐ {MIN_FOOD_RATING} 이상 · 리뷰 {MIN_FOOD_REVIEWS}개 이상")
    if st.button("처음부터 다시"):
        for k in ("styles", "result", "trip"):
            st.session_state.pop(k, None)
        for k in [k for k in st.session_state if k.startswith("style_")]:
            del st.session_state[k]
        st.rerun()

# 1단계: 여행지 · 일정 입력
st.markdown("### 1️⃣ 여행지와 일정")
c1, c2 = st.columns(2)
destination = c1.text_input("여행지", placeholder="예: 부산, 도쿄, 제주도").strip()
travel_dates = c2.date_input(
    "일정",
    value=(date.today() + timedelta(days=7), date.today() + timedelta(days=9)),
    min_value=date.today(),
)
c3, c4, c5 = st.columns(3)
transport = c3.selectbox("이동 수단", ["대중교통", "자동차", "도보"])
pace = c4.select_slider("여행 강도", list(PLACES_PER_DAY), value="보통")
base = c5.text_input("숙소/출발지 (선택)", placeholder="예: 해운대역")

# 날짜를 하나만 고른 경우 당일치기로 처리
if isinstance(travel_dates, (tuple, list)):
    start_date = travel_dates[0]
    end_date = travel_dates[1] if len(travel_dates) > 1 else travel_dates[0]
else:
    start_date = end_date = travel_dates
days = (end_date - start_date).days + 1
if days < 1:
    st.warning("종료일이 시작일보다 빠를 수 없어요. 일정을 다시 선택해주세요.")
    st.stop()
if days > MAX_DAYS:
    st.warning(f"최대 {MAX_DAYS}일까지 계획할 수 있어요.")
    st.stop()

# 여행지나 날짜가 바뀌면 이전 단계 결과를 초기화
trip = (destination, start_date, end_date)
if st.session_state.get("trip") != trip:
    st.session_state.trip = trip
    st.session_state.pop("styles", None)
    st.session_state.pop("result", None)

# 2단계: 여행 스타일 추천
if st.button("여행 스타일 추천받기 ➡️", type="primary", disabled=not destination):
    try:
        with st.spinner(f"{destination}에 어울리는 여행 스타일을 찾는 중..."):
            st.session_state.styles = suggest_styles(destination, days - 1)
        st.session_state.pop("result", None)
    except Exception as e:
        st.error(f"스타일 추천 중 오류가 발생했어요: {e}")

# 3단계: 여행 스타일 선택
if styles := st.session_state.get("styles"):
    st.markdown("### 2️⃣ 선호하는 여행 스타일 (여러 개 선택 가능)")
    cols = st.columns(4)
    chosen = []
    for i, s in enumerate(styles):
        with cols[i % 4], st.container(border=True):
            if st.checkbox(f"{s.get('emoji', '')} {s.get('name', '')}", key=f"style_{i}"):
                chosen.append(s)
            st.caption(s.get("description", ""))

    # 4단계: 동선 생성
    if st.button("🗺️ 동선 짜기", type="primary", disabled=not chosen):
        try:
            with st.status("동선을 만드는 중...", expanded=True) as status:
                result = build_trip(destination, start_date, days, chosen, pace, transport, base, progress=st.write)
                st.session_state.result = dict(result, destination=destination, transport=transport)
                status.update(label="동선 완성!", state="complete", expanded=False)
        except PlanError as e:
            st.error(str(e))
        except requests.HTTPError as e:
            st.error(f"Google Places API 오류: {e.response.status_code} {e.response.text[:300]}")
        except Exception as e:
            st.error(f"동선 생성 중 오류가 발생했어요: {e}")

if result := st.session_state.get("result"):
    st.divider()
    render_result(result)
