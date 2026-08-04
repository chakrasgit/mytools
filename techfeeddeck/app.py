"""
TechFeedDeck
A Streamlit page that lists your Twitter/X accounts, subreddits, and
websites in one table, each entry a clickable button that opens in a
new tab. All data lives in sources.yaml, no API keys needed.
"""

import html
from itertools import zip_longest
from pathlib import Path

import streamlit as st
import yaml

APP_NAME = "TechFeedDeck"
# Resolved relative to this file, not the working directory Streamlit is
# launched from, since Streamlit Cloud runs from the repo root, not the
# app's own folder, when the app lives in a subfolder.
DATA_FILE = Path(__file__).parent / "sources.yaml"

st.set_page_config(page_title=APP_NAME, layout="wide")


def html_block(html_str):
    """Streamlit's markdown renderer treats 4+ leading spaces on a line as
    an indented code block, which prints raw HTML tags instead of rendering
    them. Strip leading whitespace from every line to avoid that."""
    return "\n".join(line.strip() for line in html_str.strip().splitlines())


CUSTOM_CSS = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
    .stApp {
        background-color: #0b0f14;
        color: #e6edf3;
    }
    .app-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 2px;
    }
    .app-header .icon {
        font-size: 26px;
        line-height: 1;
    }
    .app-header .title {
        font-size: 26px;
        font-weight: 700;
        color: #58a6ff;
    }
    .app-caption {
        color: #9fb3c8;
        font-size: 14px;
        margin-bottom: 18px;
    }
    div[data-testid="stTextInput"] input {
        border: 1px solid #1f2a37 !important;
        background-color: #11161d !important;
        color: #e6edf3 !important;
    }
    table.source-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 16px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        table-layout: fixed;
    }
    table.source-table th {
        text-align: left;
        padding: 10px 12px;
        font-size: 14px;
        border-bottom: 2px solid #1f2a37;
    }
    table.source-table th.col-twitter { color: #e6edf3; }
    table.source-table th.col-reddit { color: #ff6a3d; }
    table.source-table th.col-websites { color: #3fd9c7; }
    table.source-table td {
        padding: 6px 12px;
        vertical-align: top;
    }
    table.source-table tr:nth-child(even) {
        background-color: #0f141b;
    }
    .src-btn {
        display: inline-block;
        width: 100%;
        box-sizing: border-box;
        padding: 7px 12px;
        margin: 3px 0;
        border-radius: 6px;
        background-color: #11161d;
        border: 1.5px solid #1f2a37;
        color: #e6edf3 !important;
        text-decoration: none !important;
        font-weight: 600;
        font-size: 13.5px;
        transition: background-color 0.15s ease, border-color 0.15s ease, transform 0.05s ease;
    }
    .src-btn:hover {
        border-color: #58a6ff;
        background-color: #16202b;
    }
    .src-btn:active {
        transform: scale(0.98);
        background-color: #1a2733;
    }
    .col-twitter .src-btn:hover { border-color: #e6edf3; }
    .col-reddit .src-btn:hover { border-color: #ff6a3d; }
    .col-websites .src-btn:hover { border-color: #3fd9c7; }
    .empty-note {
        color: #6b7f93;
        font-size: 13px;
        margin-top: 14px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data
def load_sources():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return (
        data.get("twitter", []) or [],
        data.get("reddit", []) or [],
        data.get("websites", []) or [],
    )


def filter_entries(entries, query):
    if not query:
        return entries
    q = query.lower()
    return [e for e in entries if q in e.get("name", "").lower()]


def render_button(entry):
    """Returns the inner <a> button for one cell, or an empty string when
    a column has run out of entries for this row."""
    if entry is None:
        return ""
    name = html.escape(entry.get("name", ""))
    url = html.escape(entry.get("url", "#"))
    return (
        f'<a class="src-btn" href="{url}" target="_blank" '
        f'rel="noopener noreferrer">{name}</a>'
    )


st.markdown(
    html_block(
        f'<div class="app-header"><span class="icon">🗂️</span>'
        f'<span class="title">{html.escape(APP_NAME)}</span></div>'
        '<div class="app-caption">All your Twitter/X accounts, subreddits, '
        'and websites in one place. Click a name to open it in a new tab.</div>'
    ),
    unsafe_allow_html=True,
)

query = st.text_input(
    "Search",
    placeholder="Search by name...",
    label_visibility="collapsed",
)

twitter_all, reddit_all, websites_all = load_sources()

twitter = filter_entries(twitter_all, query)
reddit = filter_entries(reddit_all, query)
websites = filter_entries(websites_all, query)

if not (twitter or reddit or websites):
    st.markdown(
        '<p class="empty-note">No sources match your search.</p>',
        unsafe_allow_html=True,
    )
else:
    rows_html = ""
    for i, (t, r, w) in enumerate(zip_longest(twitter, reddit, websites), start=1):
        rows_html += (
            "<tr>"
            f"<td>{i}</td>"
            f'<td class="col-twitter">{render_button(t)}</td>'
            f'<td class="col-reddit">{render_button(r)}</td>'
            f'<td class="col-websites">{render_button(w)}</td>'
            "</tr>"
        )

    table_html = (
        '<table class="source-table">'
        "<tr>"
        "<th style='width:6%'>#</th>"
        "<th class='col-twitter'><i class='fa-brands fa-x-twitter'></i>&nbsp; Twitter / X</th>"
        "<th class='col-reddit'><i class='fa-brands fa-reddit-alien'></i>&nbsp; Reddit</th>"
        "<th class='col-websites'><i class='fa-solid fa-globe'></i>&nbsp; Websites</th>"
        "</tr>"
        f"{rows_html}"
        "</table>"
    )
    st.markdown(html_block(table_html), unsafe_allow_html=True)

st.caption(f"Edit {DATA_FILE} to add, remove, or reorder sources.")
