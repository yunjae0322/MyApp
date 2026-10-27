# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Shopping list web app (add / edit / delete / check items) built with Streamlit, to be deployed on Streamlit Community Cloud. Stages 1–4 are done: `app.py` implements all P0/P1 features and the styled UI, and passes the E2E checks in `tests/qa_playwright.js`. Planning docs:

- `PRD.md` — the source of truth for requirements (Korean). Section 9 is the acceptance checklist.
- `PROMPTS.md` — the staged development plan: 1) skeleton, 2) features, 3) UI, 4) PRD/bug review with Playwright, 5) deployment prep. Work proceeds one stage at a time; stay within the current stage's scope (e.g. no CSS in stage 2, no logic changes in stage 3).

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py                              # dev server at http://localhost:8501
streamlit run app.py --server.headless true       # for Playwright testing
```

No pytest suite or linter. Verification is `tests/qa_playwright.js`: start the headless server on port 8501, then pass the file (absolute path) as `filename` to the Playwright MCP `browser_run_code_unsafe` tool. It returns `{ total, passed, failed, errors }` and saves screenshots to `.playwright-mcp/` (gitignored). The Playwright MCP can only read files under the project directory, so scratch scripts must live there too.

When writing Playwright steps, wait for each rerun via `[data-testid="stApp"][data-test-script-state="notRunning"]`, not fixed sleeps. Checking an item reorders rows, and a `click()` resolved against the old order can land on a different item's button.

## Architecture (per PRD §5 and §7)

- Single-file app: `app.py`, single page, `layout="centered"`.
- State lives in `st.session_state["items"]` as `list[dict]` with `id` (uuid4), `name` (1–50 chars, stripped), `checked`, `created_at` (ISO 8601). `st.session_state["editing_id"]` allows only one row in edit mode at a time.
- Mutation functions: `add_item()`, `update_item(item_id, name)`, `delete_item(item_id)`, `toggle_item(item_id)`, `clear_checked()`, `clear_all()`. All state changes go through `on_click` / `on_change` callbacks, not inline after-button logic. Callbacks run before the page renders, so they can't show `st.warning` in place; they store the message in `add_warning` / `edit_warning`, and the render functions display it (`st.toast` is fine to call directly from callbacks).
- Always address items by `id`, never list index, and key widgets by id (`check_{id}`, `edit_{id}`, `del_{id}`) — duplicate item names are allowed, so name- or index-based handling causes wrong-row bugs after reordering.
- Display order: unchecked first, then checked; each group by `created_at`.
- The 50-char limit is enforced only in `validate_name`, not with `max_chars`: Streamlit's `max_chars` silently discards a paste that exceeds the limit, so the input ends up empty.
- Item names are user input: they're rendered via `st.html` after `html.escape` (not `st.markdown`, which would still interpret `**`/`~~`). Guard progress calculation against zero items.
- Styling is the `CUSTOM_CSS` block injected with `st.html`. Streamlit stacks `st.columns` vertically below ~640px; the CSS forces `nowrap` so rows stay on one line at 375px. List-row rules are scoped to the `st.container(key="item_list")` wrapper via its `.st-key-item_list` class. The CSS relies on Streamlit `data-testid` selectors (`stHorizontalBlock`, `stColumn`, `stForm`), so re-check the 375px layout after upgrading Streamlit.

## Persistence caveat

MVP uses `st.session_state` only, so data is lost on refresh. Whether data must persist is an open decision (PRD §5.1). A local JSON file on Streamlit Cloud is reset on restart and shared by all users; real persistence needs an external DB.
