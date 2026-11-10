"""
TechFeedDeck
Quick-launch page for AI news sources. One box per company (independent
sources first), fixed-size tiles inside each box, each tile opens in a new
tab. All data lives in sources.yaml, no API keys needed.
"""

import html
from pathlib import Path

import streamlit as st
import yaml

APP_NAME = "TechFeedDeck"
# Resolved relative to this file so it also works on Streamlit Cloud when the
# app lives in a subfolder of the repo.
DATA_FILE = Path(__file__).parent / "sources.yaml"

st.set_page_config(page_title=APP_NAME, page_icon="🗂️", layout="wide")

# (yaml key, label shown in the box, kind of tile)
GROUPS = [
    ("accounts", "Company accounts", "x"),
    ("people", "People", "x"),
    ("links", "News and blogs", "web"),
    ("youtube", "YouTube", "youtube"),
]
INDEPENDENT_LABELS = {"accounts": "Accounts"}
ICONS = {
    "x": "fa-brands fa-x-twitter",
    "web": "fa-solid fa-newspaper",
    "youtube": "fa-brands fa-youtube",
}
INDEPENDENT_ACCENT = "#9fb3c8"
ACCENTS = [
    "#7aa2ff", "#ff8a5c", "#4fd1b5", "#f2c14e", "#c792ea", "#6ee7a8",
    "#ff6b8b", "#5cc8ff", "#e6a15c", "#a3e635", "#f08fc0", "#8be0ff",
    "#d4b483", "#9d8cff",
]

CUSTOM_CSS = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700&display=swap">
<style>
    :root {
        --bg: #0e1116;
        --surface: #151a21;
        --tile: #1b212a;
        --tile-hover: #222a35;
        --line: #272f3b;
        --text: #e8ecf1;
        --muted: #8b96a5;
    }
    .stApp {
        background-color: var(--bg);
        color: var(--text);
        font-family: 'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif;
    }
    .app-header {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .app-header .icon { font-size: 26px; line-height: 1; }
    .app-header .title {
        font-size: 28px;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.01em;
    }
    .app-caption {
        color: var(--muted);
        font-size: 14px;
        margin: 2px 0 14px 0;
    }

    /* search box */
    div[data-testid="stTextInput"] input {
        border: 1.5px solid var(--line) !important;
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
        font-size: 14px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #7aa2ff !important;
        box-shadow: 0 0 0 1px #7aa2ff !important;
    }

    /* company filter chips (st.pills) */
    button[data-testid="stBaseButton-pills"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--line) !important;
        color: var(--muted) !important;
    }
    button[data-testid="stBaseButton-pills"]:hover {
        color: var(--text) !important;
        border-color: #3a4556 !important;
    }
    button[data-testid="stBaseButton-pillsActive"] {
        background-color: #e8ecf1 !important;
        border: 1px solid #e8ecf1 !important;
        color: #0e1116 !important;
    }

    /* company boxes */
    .box-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(min(100%, 560px), 1fr));
        gap: 16px;
        align-items: start;
        margin-top: 18px;
    }
    .co {
        background: var(--surface);
        border: 1px solid var(--line);
        border-top: 3px solid var(--accent);
        border-radius: 12px;
        padding: 14px 16px 16px 16px;
    }
    .co-head {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin-bottom: 4px;
    }
    .co-name {
        font-size: 18px;
        font-weight: 700;
        color: var(--text);
    }
    .co-count {
        font-size: 13px;
        color: var(--muted);
    }
    .grp { margin-top: 12px; }
    .grp-label {
        font-size: 13px;
        font-weight: 600;
        color: var(--muted);
        margin-bottom: 6px;
    }

    /* fixed-size tiles: every tile is exactly the same size */
    .tiles {
        display: grid;
        grid-template-columns: repeat(auto-fill, 160px);
        gap: 8px;
    }
    a.tile {
        box-sizing: border-box;
        width: 160px;
        height: 52px;
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 0 12px;
        background: var(--tile);
        border: 1px solid var(--line);
        border-radius: 9px;
        color: var(--text) !important;
        text-decoration: none !important;
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.2;
        transition: background-color 0.12s ease, border-color 0.12s ease;
    }
    a.tile:hover {
        background: var(--tile-hover);
        border-color: var(--accent);
    }
    a.tile:active { background: var(--bg); }
    a.tile:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
    }
    a.tile .ico {
        flex: 0 0 16px;
        text-align: center;
        font-size: 15px;
        color: var(--accent);
    }
    a.tile .lbl {
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow-wrap: anywhere;
    }
    .empty-note {
        color: var(--muted);
        font-size: 14px;
        margin-top: 18px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def html_block(html_str):
    """Streamlit's markdown renderer treats 4+ leading spaces (and blank
    lines) in HTML as code or paragraph breaks. Strip every line and drop
    empty ones so the HTML renders as-is."""
    return "\n".join(
        line.strip() for line in html_str.strip().splitlines() if line.strip()
    )


def normalize(entry, kind):
    """Turn one YAML entry into {'name', 'url', 'kind'}, or None if unusable.
    X entries can be a bare handle ('OpenAI') or a name/url dict. Link and
    YouTube entries must be name/url dicts."""
    if isinstance(entry, (str, int)) and kind == "x":
        handle = str(entry).strip().lstrip("@")
        if not handle:
            return None
        return {"name": f"@{handle}", "url": f"https://x.com/{handle}", "kind": kind}
    if isinstance(entry, dict):
        url = str(entry.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            return None
        name = str(entry.get("name", "")).strip() or url
        return {"name": name, "url": url, "kind": kind}
    return None


def build_groups(raw, labels=None):
    labels = labels or {}
    groups = []
    for key, label, kind in GROUPS:
        items = [normalize(e, kind) for e in (raw.get(key) or [])]
        items = [i for i in items if i]
        if items:
            groups.append({"label": labels.get(key, label), "items": items})
    return groups


@st.cache_data
def load_sources(_mtime):
    """_mtime is only here so editing sources.yaml refreshes the cache."""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    sections = []
    independent = build_groups(data.get("independent") or {}, INDEPENDENT_LABELS)
    if independent:
        sections.append(
            {"name": "Independent", "accent": INDEPENDENT_ACCENT, "groups": independent}
        )
    for idx, company in enumerate(data.get("companies") or []):
        name = str(company.get("name", "")).strip()
        groups = build_groups(company)
        if name and groups:
            sections.append(
                {"name": name, "accent": ACCENTS[idx % len(ACCENTS)], "groups": groups}
            )
    return sections


def count_items(section):
    return sum(len(g["items"]) for g in section["groups"])


def filter_section(section, query):
    """Search matches tile names. If the query matches the company name, the
    whole box is kept."""
    if not query or query in section["name"].lower():
        return section
    groups = []
    for g in section["groups"]:
        items = [i for i in g["items"] if query in i["name"].lower()]
        if items:
            groups.append({**g, "items": items})
    return {**section, "groups": groups} if groups else None


def render_tile(item):
    name = html.escape(item["name"], quote=True)
    url = html.escape(item["url"], quote=True)
    icon = ICONS.get(item["kind"], ICONS["web"])
    return (
        f'<a class="tile" href="{url}" target="_blank" rel="noopener noreferrer" '
        f'title="{name}"><i class="ico {icon}"></i><span class="lbl">{name}</span></a>'
    )


def render_section(section):
    groups_html = ""
    for g in section["groups"]:
        tiles = "".join(render_tile(i) for i in g["items"])
        groups_html += (
            f'<div class="grp"><div class="grp-label">{html.escape(g["label"])}</div>'
            f'<div class="tiles">{tiles}</div></div>'
        )
    return (
        f'<section class="co" style="--accent:{section["accent"]}">'
        f'<div class="co-head"><span class="co-name">{html.escape(section["name"])}</span>'
        f'<span class="co-count">{count_items(section)}</span></div>'
        f"{groups_html}</section>"
    )


# ---------- page ----------

sections_all = load_sources(DATA_FILE.stat().st_mtime)
company_names = [s["name"] for s in sections_all]

st.markdown(
    html_block(
        f'<div class="app-header"><span class="icon">🗂️</span>'
        f'<span class="title">{html.escape(APP_NAME)}</span></div>'
    ),
    unsafe_allow_html=True,
)

search_col, _spacer = st.columns([1, 3])
with search_col:
    try:
        # autocomplete="off" stops the browser suggesting unrelated entries
        query = st.text_input(
            "Search",
            placeholder="Search by name...",
            label_visibility="collapsed",
            key="search_box",
            autocomplete="off",
        )
    except TypeError:  # older Streamlit without the autocomplete argument
        query = st.text_input(
            "Search",
            placeholder="Search by name...",
            label_visibility="collapsed",
            key="search_box",
        )

options = ["All"] + company_names
if hasattr(st, "pills"):
    choice = st.pills(
        "Company",
        options,
        selection_mode="single",
        default="All",
        label_visibility="collapsed",
        key="company_filter",
    )
else:  # older Streamlit versions
    choice = st.radio(
        "Company",
        options,
        horizontal=True,
        label_visibility="collapsed",
        key="company_filter",
    )
choice = choice or "All"  # clicking the active chip again clears it

q = query.strip().lower()
visible = []
for section in sections_all:
    if choice != "All" and section["name"] != choice:
        continue
    filtered = filter_section(section, q)
    if filtered:
        visible.append(filtered)

if not visible:
    st.markdown(
        '<p class="empty-note">No sources match your search. '
        "Clear the search box or pick All.</p>",
        unsafe_allow_html=True,
    )
else:
    total = sum(count_items(s) for s in visible)
    st.markdown(
        f'<div class="app-caption">{total} sources in {len(visible)} '
        f'{"box" if len(visible) == 1 else "boxes"}</div>',
        unsafe_allow_html=True,
    )
    boxes = "".join(render_section(s) for s in visible)
    st.markdown(
        html_block(f'<div class="box-grid">{boxes}</div>'),
        unsafe_allow_html=True,
    )
