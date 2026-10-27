"""쇼핑 리스트 앱 (Streamlit)."""

import html
import re
import uuid
from datetime import datetime

import streamlit as st

MAX_NAME_LENGTH = 50

# 좁은 화면에서도 st.columns가 세로로 쌓이지 않고 한 줄을 유지하도록 한다.
# 색은 테마(라이트/다크)에 상관없이 보이도록 opacity로만 조절한다.
CUSTOM_CSS = """
<style>
[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important;
}
button p {
    white-space: nowrap;
}

/* 추가 폼: 버튼은 글자 크기만큼, 입력창이 나머지를 차지 */
[data-testid="stForm"] [data-testid="stColumn"]:last-child {
    flex: 0 0 auto !important;
    width: auto !important;
}
[data-testid="stForm"] [data-testid="stColumn"]:first-child {
    flex: 1 1 auto !important;
}

/* 아이템 행: 체크박스/버튼은 내용 크기만큼, 이름(또는 수정 입력창)이 나머지를 차지 */
.st-key-item_list [data-testid="stHorizontalBlock"] {
    align-items: center;
    gap: 0.25rem;
}
.st-key-item_list [data-testid="stColumn"] {
    flex: 0 0 auto !important;
    width: auto !important;
}
.st-key-item_list [data-testid="stColumn"]:has(.item-name),
.st-key-item_list [data-testid="stColumn"]:has([data-testid="stTextInput"]) {
    flex: 1 1 auto !important;
}

/* 장 보면서 누르기 쉽게 체크박스와 아이콘 버튼의 터치 영역을 키운다 */
.st-key-item_list [data-testid="stCheckbox"] label {
    padding: 0.5rem;
}
.st-key-item_list [data-testid="stCheckbox"] label > span:first-child {
    transform: scale(1.25);
}
.st-key-item_list button {
    min-width: 2.5rem;
    min-height: 2.5rem;
}

.item-name {
    display: block;
    font-size: 1.05rem;
    overflow-wrap: anywhere;
}
.item-name.checked {
    text-decoration: line-through;
    opacity: 0.45;
}

.empty-state {
    text-align: center;
    padding: 1.5rem 0;
}
.empty-state .icon {
    font-size: 2.5rem;
}
.empty-state .title {
    margin: 0.5rem 0 0.25rem;
    font-weight: 600;
}
.empty-state .hint {
    margin: 0;
    opacity: 0.6;
    font-size: 0.9rem;
}
</style>
"""


def init_state():
    """세션 상태를 초기화한다."""
    defaults = {
        "items": [],
        "editing_id": None,
        "confirm_clear": False,
        "add_warning": None,
        "edit_warning": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def new_item(name):
    """PRD 5장 데이터 모델에 맞는 아이템 dict를 만든다."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "checked": False,
        "created_at": datetime.now().isoformat(),
    }


def find_item(item_id):
    """id로 아이템을 찾는다. 없으면 None."""
    return next((i for i in st.session_state["items"] if i["id"] == item_id), None)


def escape_markdown(text):
    """위젯 라벨용: 마크다운 특수문자를 escape한다."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!~<>|$:])", r"\\\1", text)


def validate_name(raw):
    """입력값을 정리하고 (이름, 오류 메시지)를 돌려준다."""
    name = (raw or "").strip()
    if not name:
        return None, "아이템 이름을 입력해 주세요."
    if len(name) > MAX_NAME_LENGTH:
        return None, f"아이템 이름은 {MAX_NAME_LENGTH}자 이하로 입력해 주세요. (현재 {len(name)}자)"
    return name, None


def add_item():
    """입력창의 값으로 아이템을 추가한다."""
    name, error = validate_name(st.session_state.get("new_item_name"))
    if error:
        st.session_state["add_warning"] = error
        return

    if any(i["name"] == name for i in st.session_state["items"]):
        st.session_state["add_warning"] = "이미 리스트에 있는 아이템입니다."
    st.session_state["items"].append(new_item(name))
    st.toast("추가되었습니다", icon="✅")


def update_item(item_id, name):
    """id에 해당하는 아이템의 이름을 바꾼다. 성공하면 True."""
    name, error = validate_name(name)
    if error:
        st.session_state["edit_warning"] = error
        return False

    item = find_item(item_id)
    if item:
        item["name"] = name
    return True


def start_edit(item_id):
    """아이템을 수정 모드로 전환한다. (한 번에 하나만)"""
    item = find_item(item_id)
    if item:
        st.session_state["editing_id"] = item_id
        st.session_state[f"edit_{item_id}"] = item["name"]
        st.session_state["edit_warning"] = None


def save_edit(item_id):
    """수정 입력값을 저장하고 수정 모드를 끝낸다."""
    if update_item(item_id, st.session_state.get(f"edit_{item_id}")):
        cancel_edit()
        st.toast("수정되었습니다", icon="✏️")


def cancel_edit():
    """수정 모드를 끝낸다."""
    st.session_state["editing_id"] = None
    st.session_state["edit_warning"] = None


def delete_item(item_id):
    """id에 해당하는 아이템을 삭제한다."""
    st.session_state["items"] = [
        i for i in st.session_state["items"] if i["id"] != item_id
    ]
    if st.session_state["editing_id"] == item_id:
        cancel_edit()
    st.toast("삭제되었습니다", icon="🗑️")


def toggle_item(item_id):
    """id에 해당하는 아이템의 체크 상태를 뒤집는다."""
    item = find_item(item_id)
    if item:
        item["checked"] = not item["checked"]


def clear_checked():
    """체크된 아이템을 모두 삭제한다."""
    items = st.session_state["items"]
    if st.session_state["editing_id"] in {i["id"] for i in items if i["checked"]}:
        cancel_edit()
    st.session_state["items"] = [i for i in items if not i["checked"]]
    st.toast("체크된 항목을 지웠습니다", icon="🧹")


def clear_all():
    """모든 아이템을 삭제한다."""
    st.session_state["items"] = []
    st.session_state["confirm_clear"] = False
    cancel_edit()
    st.toast("리스트를 모두 지웠습니다", icon="🧹")


def ask_clear_all():
    st.session_state["confirm_clear"] = True


def cancel_clear_all():
    st.session_state["confirm_clear"] = False


def sorted_items():
    """미체크 → 체크 순, 각 그룹 안에서는 추가된 순서로 정렬한다."""
    return sorted(
        st.session_state["items"], key=lambda i: (i["checked"], i["created_at"])
    )


def render_progress():
    items = st.session_state["items"]
    total = len(items)
    remaining = sum(1 for i in items if not i["checked"])
    ratio = (total - remaining) / total if total else 0.0
    st.progress(ratio, text=f"전체 {total}개 · 남은 {remaining}개")


def render_add_form():
    with st.form("add_form", clear_on_submit=True, border=False):
        col_input, col_button = st.columns([4, 1], vertical_alignment="bottom")
        # max_chars는 쓰지 않는다: 제한을 넘는 붙여넣기를 통째로 버려 입력이 사라진다.
        # 길이 제한은 validate_name에서 경고와 함께 처리한다.
        col_input.text_input(
            "아이템 이름",
            key="new_item_name",
            placeholder="살 물건을 입력하세요 (예: 우유)",
            label_visibility="collapsed",
        )
        col_button.form_submit_button(
            "추가", type="primary", icon=":material/add:", on_click=add_item, width="stretch"
        )

    if st.session_state["add_warning"]:
        st.warning(st.session_state["add_warning"])
        st.session_state["add_warning"] = None


def render_item(item):
    item_id = item["id"]

    if st.session_state["editing_id"] == item_id:
        col_input, col_save, col_cancel = st.columns(
            [6, 1, 1], vertical_alignment="center"
        )
        col_input.text_input(
            "아이템 이름 수정",
            key=f"edit_{item_id}",
            label_visibility="collapsed",
        )
        col_save.button(
            "저장", key=f"save_{item_id}", type="primary", on_click=save_edit, args=(item_id,)
        )
        col_cancel.button("취소", key=f"cancel_{item_id}", on_click=cancel_edit)
        if st.session_state["edit_warning"]:
            st.warning(st.session_state["edit_warning"])
        return

    col_check, col_name, col_edit, col_delete = st.columns(
        [1, 8, 1, 1], vertical_alignment="center"
    )
    # 라벨은 숨기지만 스크린리더가 아이템을 구분할 수 있게 이름을 넣는다.
    # (라벨은 마크다운으로 해석되므로 특수문자를 escape)
    col_check.checkbox(
        f"{escape_markdown(item['name'])} 구매 완료",
        value=item["checked"],
        key=f"check_{item_id}",
        on_change=toggle_item,
        args=(item_id,),
        label_visibility="collapsed",
    )
    # 사용자 입력은 마크다운/HTML로 해석되지 않도록 escape 후 st.html로 표시
    css_class = "item-name checked" if item["checked"] else "item-name"
    with col_name:
        st.html(f'<span class="{css_class}">{html.escape(item["name"])}</span>')
    col_edit.button(
        "✏️", key=f"edit_btn_{item_id}", type="tertiary", help="수정",
        on_click=start_edit, args=(item_id,),
    )
    col_delete.button(
        "🗑️", key=f"del_{item_id}", type="tertiary", help="삭제",
        on_click=delete_item, args=(item_id,),
    )


def render_list():
    if not st.session_state["items"]:
        st.html(
            '<div class="empty-state">'
            '<div class="icon">🧺</div>'
            '<p class="title">리스트가 비어 있어요</p>'
            '<p class="hint">위 입력창에 살 물건을 추가해 보세요</p>'
            "</div>"
        )
        return

    with st.container(border=True, key="item_list"):
        for item in sorted_items():
            render_item(item)


def render_bulk_actions():
    items = st.session_state["items"]
    has_checked = any(i["checked"] for i in items)

    # 확인 대기 중에 아이템을 하나씩 지워 리스트가 비면 확인창도 닫는다
    if not items:
        st.session_state["confirm_clear"] = False

    if st.session_state["confirm_clear"]:
        st.warning("정말 삭제할까요? 모든 아이템이 지워집니다.", icon="⚠️")
        col_yes, col_no = st.columns(2)
        col_yes.button(
            "예", key="confirm_clear_yes", type="primary", on_click=clear_all, width="stretch"
        )
        col_no.button(
            "아니오", key="confirm_clear_no", on_click=cancel_clear_all, width="stretch"
        )
        return

    col_checked, col_all = st.columns(2)
    col_checked.button(
        "체크된 항목 지우기",
        icon=":material/done_all:",
        on_click=clear_checked,
        disabled=not has_checked,
        width="stretch",
    )
    col_all.button(
        "전체 삭제",
        icon=":material/delete_sweep:",
        on_click=ask_clear_all,
        disabled=not items,
        width="stretch",
    )


def main():
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.html(CUSTOM_CSS)
    init_state()

    st.title("🛒 쇼핑 리스트")
    render_progress()
    render_add_form()
    render_list()
    render_bulk_actions()


if __name__ == "__main__":
    main()
