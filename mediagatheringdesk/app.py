"""Media Gathering Desk: a board for gathering the media listed in a scene plan CSV.

Data lives in memory only (st.session_state). Nothing is stored or logged.
"""
import csv
import html
import io
import re

import streamlit as st

TITLE = "Media Gathering Desk"

FIELDS = [
    "chunk", "scene_id", "media_name", "media_type", "role", "start", "end",
    "duration_s", "script_part_te", "script_part_en", "what_to_gather",
    "source_or_prompt", "reuse_of", "suggested_format", "notes",
]

# Columns the app shows. The CSV must contain all of them; any other columns are ignored.
REQUIRED = [
    "chunk", "scene_id", "media_name", "media_type", "duration_s", "script_part_te",
    "script_part_en", "what_to_gather", "source_or_prompt", "reuse_of",
]

# Badge colors (background, text) per media type, lower-case keys.
BADGES = {
    "real image": ("#17415f", "#9ad9f7"),
    "screenshot": ("#1d3f78", "#a9c8fb"),
    "screen recording": ("#392f73", "#cbbdf8"),
    "clip": ("#2e3680", "#bcc6f8"),
    "animation clip": ("#14504f", "#8fe0d4"),
    "animation code": ("#12495c", "#8ddaee"),
    "ai-generated image": ("#5a2748", "#f4b6d6"),
    "ai-generated video": ("#5c4519", "#f2cb80"),
}
DEFAULT_BADGE = ("#313a50", "#c3cce0")

# Column widths: mark + ID, media, what to gather, source, script.
SPEC = [1.15, 2.4, 3.2, 3.2, 3.4]
HEADS = ["ID", "Media", "What to gather", "Source or prompt", "Script"]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;500&display=swap');

[data-testid="stHeader"]{display:none}
[data-testid="stMainBlockContainer"]{padding:1.1rem 2.6rem 3rem;max-width:100%}
.title,.cell,.glabel,.head,.fchip,[class*="st-key-"] button{font-family:"Segoe UI",system-ui,-apple-system,sans-serif}

/* sticky top area: title, filters, table header */
[data-testid="stLayoutWrapper"]:has(> .st-key-topbar){position:sticky;top:0;z-index:100;background:#0e1526}
.st-key-topbar{background:#0e1526;padding:0;gap:0.9rem}
.title{font-size:1.3rem;font-weight:600;color:#f1f5ff;padding-bottom:1rem}

/* upload: compact button before upload, plain chip after */
[data-testid="stFileUploader"]{width:fit-content;margin-left:auto}
[data-testid="stFileUploader"] section{padding:0}
[data-testid="stFileUploaderDropzone"]{padding:0;min-height:0;background:transparent;border:none}
[data-testid="stFileUploaderDropzoneInstructions"]{display:none}
[data-testid="stFileUploaderDropzone"] button{background:#3b78e7;color:#fff;border:none;border-radius:7px;padding:0.4rem 1.1rem;font-size:13px;font-weight:500}
[data-testid="stFileUploaderDropzone"] button:hover{background:#4d87f0;color:#fff}
[data-testid="stFileUploader"] [data-testid="stBaseButton-borderlessIcon"]{display:none}
[data-testid="stFileUploader"] [data-testid="stBaseButton-minimal"]{background:transparent;color:#aab6d1;padding:0.2rem}
.fchip{display:inline-block;background:#1b2845;border-radius:8px;padding:7px 14px;font-size:13px;color:#e8eefc}
.fchip span{color:#aab6d1;margin-left:8px}
.chipwrap{text-align:right;padding-bottom:1rem}

/* filter panel */
.st-key-pane{position:relative;background:#16213a;border-radius:10px;padding:0.55rem 1rem;gap:0}
.st-key-frow_status,.st-key-frow_type{padding:0.55rem 0}
.st-key-frow_type{border-top:1px solid #2a3b61}
.glabel{font-size:13px;font-weight:500;color:#b9c5de;white-space:nowrap;padding-bottom:1rem}

[class*="st-key-fs_"] button,[class*="st-key-ft_"] button{
  width:100%;height:32px;min-height:32px;padding:0 8px;border:none;border-radius:7px;box-shadow:none;
  white-space:nowrap;overflow:hidden;transition:background .12s,color .12s,transform .06s}
[class*="st-key-fs_"] button p,[class*="st-key-ft_"] button p{
  font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"],
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"]{background:#1f2d4d;color:#d3ddf2}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"]:hover,
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"]:hover{background:#2b4378;color:#ffffff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"]:active,
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"]:active{background:#35569e;color:#ffffff;transform:scale(.97)}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"],
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]{background:#3b78e7;color:#ffffff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"]:hover,
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]:hover{background:#4d87f0;color:#ffffff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"]:active,
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]:active{background:#2f66cc;color:#ffffff;transform:scale(.97)}

/* reset: top-right corner of the panel, icon drawn by CSS so it is exactly centered */
.st-key-reset_filters{position:absolute;top:0.55rem;right:1rem;width:auto;z-index:5}
.st-key-reset_filters button{position:relative;width:32px;min-width:32px;height:32px;min-height:32px;padding:0;border:none;
  border-radius:7px;background:#1f2d4d;color:#d3ddf2;box-shadow:none;overflow:hidden}
.st-key-reset_filters button > *{display:none}
.st-key-reset_filters button::before{content:"";position:absolute;inset:0;margin:auto;width:16px;height:16px;background:currentColor;
  -webkit-mask:url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4'/%3E%3Cpath d='M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4'/%3E%3Cpath d='M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4'/%3E%3C/svg%3E") center/contain no-repeat}
.st-key-reset_filters button:hover{background:#2b4378;color:#fff}
.st-key-reset_filters button:active{background:#35569e;color:#fff;transform:scale(.95)}

/* table: header bar and body read as one object */
.st-key-thead{background:#25376a;border-radius:10px 10px 0 0;padding:0.7rem 1rem;margin-top:0.35rem}
.head{font-size:13px;font-weight:600;color:#f4f7ff;letter-spacing:.2px;padding-bottom:1rem}
[data-testid="stLayoutWrapper"]:has(> .st-key-tbody){margin-top:-1rem}
.st-key-tbody{background:#121b30;border-radius:0 0 10px 10px;padding:0 1rem 0.3rem;gap:0}
[class*="st-key-row_"]{border-bottom:1px solid #26365a;padding:0.85rem 0}

/* gathered mark: two states, plain fill */
[class*="st-key-g_"] button{width:24px;min-width:24px;height:24px;min-height:24px;padding:0;border:none;border-radius:7px;
  box-shadow:none;transition:none;margin-top:1px}
[class*="st-key-g_"] button > *{display:none}
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"],
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"]:hover,
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"]:active{background:#3a4a72}
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"],
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"]:hover,
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"]:active{background:#3b78e7}

.cell{font-size:13.5px;line-height:1.6;color:#e8eefc;overflow-wrap:anywhere;padding-bottom:1rem}
.cell a{color:#8fbcff}
.sid{font-weight:600;color:#f1f5ff}
.mname{font-weight:500;color:#f1f5ff;margin-bottom:5px}
.dur{font-size:12.5px;color:#aab6d1;margin-top:5px}
.bd{display:inline-block;font-size:12px;font-weight:500;padding:2px 10px;border-radius:6px}
.rl{display:inline-block;font-size:12px;font-weight:500;padding:2px 9px;border-radius:6px;background:#5c4519;color:#f2cb80;margin-right:7px}
.also{font-size:12.5px;color:#aab6d1;margin-top:6px}
.chunk{font-size:12px;color:#9fb0cf;margin-bottom:4px}
.te{font-family:"Noto Sans Telugu","Nirmala UI","Gautami",sans-serif;font-size:13.5px;line-height:1.85;color:#f1f5ff}
.en{font-size:13.5px;color:#b9c5de;margin-top:5px}
.anc{display:block;position:relative;top:-260px;visibility:hidden}
.empty{color:#aab6d1;padding:2rem 0}
"""

URL_RE = re.compile(
    r"(https?://[^\s<>\"]+"
    r"|(?<![\w@/.\-])(?:[a-z0-9\-]+\.)+(?:com|org|net|io|ai|dev|app|co|gov|edu|info|news|tech|xyz)\b(?:/[^\s<>\"]*)?)",
    re.I,
)
TRAIL = ".,;:!?'\"]"


def esc(text):
    """Escape CSV text for safe HTML. Keeps line breaks, blocks LaTeX parsing of $."""
    return html.escape(text, quote=True).replace("$", "&#36;").replace("\n", "<br>")


def linkify(text):
    """Escape text and turn full URLs and bare domains into links opening in a new tab."""
    out, pos = [], 0
    for m in URL_RE.finditer(text):
        url = m.group(0)
        end = m.end()
        while url and (url[-1] in TRAIL or (url[-1] == ")" and "(" not in url)):
            url = url[:-1]
            end -= 1
        if not url:
            continue
        out.append(esc(text[pos:m.start()]))
        href = url if url.lower().startswith("http") else "https://" + url
        out.append(
            f'<a href="{html.escape(href, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{esc(url)}</a>'
        )
        pos = end
    out.append(esc(text[pos:]))
    return "".join(out)


def sort_key(item):
    index, row = item
    sid = row["scene_id"] or row["media_name"]
    nums = [int(n) for n in re.findall(r"\d+", sid)] or [10**9]
    return (nums, sid, index)


def build_rows(text):
    """Parse the CSV (all values stay strings) and return rows sorted by scene ID."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames or []
    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        raise ValueError("This CSV can't be used. Missing columns: " + ", ".join(missing))
    raw = []
    for rec in reader:
        row = {f: (rec.get(f) or "").strip() for f in FIELDS}
        if row["scene_id"] or row["media_name"]:
            raw.append(row)
    rows = [r for _, r in sorted(enumerate(raw), key=sort_key)]
    for i, r in enumerate(rows):
        r["key"] = str(i)
        r["media_type"] = r["media_type"] or "Other"
        r["used_in"] = []
        r["reuse_key"] = ""
    by_name = {r["media_name"]: r["key"] for r in rows if r["media_name"]}
    by_sid = {r["scene_id"]: r["key"] for r in rows if r["scene_id"]}
    by_key = {r["key"]: r for r in rows}
    for r in rows:
        if r["reuse_of"]:
            target = by_name.get(r["reuse_of"]) or by_sid.get(r["reuse_of"])
            if target and target != r["key"]:
                r["reuse_key"] = target
                by_key[target]["used_in"].append(r["key"])
    return rows


# ---------- cell renderers (all return one HTML string starting with a tag) ----------

def cell_id(r):
    return f'<div class="cell sid">{esc(r["scene_id"])}</div>'


def cell_media(r):
    bg, fg = BADGES.get(r["media_type"].lower(), DEFAULT_BADGE)
    dur = f'<div class="dur">{esc(r["duration_s"])}s</div>' if r["duration_s"] else ""
    return (
        f'<div class="cell"><span id="row-{r["key"]}" class="anc"></span>'
        f'<div class="mname">{esc(r["media_name"])}</div>'
        f'<span class="bd" style="background:{bg};color:{fg}">{esc(r["media_type"])}</span>'
        f"{dur}</div>"
    )


def cell_gather(r):
    return f'<div class="cell">{linkify(r["what_to_gather"])}</div>'


def cell_source(r, by_key):
    parts = []
    if r["reuse_of"]:
        if r["reuse_key"]:
            name = f'<a href="#row-{r["reuse_key"]}">{esc(r["reuse_of"])}</a>'
        else:
            name = esc(r["reuse_of"])
        parts.append(f'<div><span class="rl">Reused</span>{name}</div>')
        src = r["source_or_prompt"]
        if src and not re.match(r"\s*see\s+reuse_of", src, re.I):
            parts.append(f"<div>{linkify(src)}</div>")
    elif r["source_or_prompt"]:
        parts.append(f'<div>{linkify(r["source_or_prompt"])}</div>')
    if r["used_in"]:
        links = ", ".join(
            f'<a href="#row-{k}">{esc(by_key[k]["scene_id"])}</a>' for k in r["used_in"]
        )
        parts.append(f'<div class="also">Also used in: {links}</div>')
    return f'<div class="cell">{"".join(parts)}</div>'


def cell_script(r):
    chunk = f'<div class="chunk">Chunk {esc(r["chunk"])}</div>' if r["chunk"] else ""
    te = f'<div class="te">{esc(r["script_part_te"])}</div>' if r["script_part_te"] else ""
    en = f'<div class="en">{esc(r["script_part_en"])}</div>' if r["script_part_en"] else ""
    return f'<div class="cell">{chunk}{te}{en}</div>'


# ---------- state and callbacks ----------

def set_filter(name, value):
    st.session_state[name] = value


def reset_filters():
    st.session_state.f_type = "All"
    st.session_state.f_status = "All"


def toggle_done(key):
    st.session_state.done[key] = not st.session_state.done.get(key, False)


def clear_data():
    for k in ("rows", "done", "fname"):
        st.session_state.pop(k, None)
    reset_filters()


def load_upload(up):
    """Load a new upload into session state, then rerun so the uploader is replaced by a chip."""
    if up is None:
        return
    try:
        rows = build_rows(up.getvalue().decode("utf-8-sig"))
    except UnicodeDecodeError:
        st.error("Couldn't read this file. Save it as a UTF-8 CSV and upload it again.")
        return
    except (ValueError, csv.Error) as exc:
        st.error(str(exc))
        return
    st.session_state.rows = rows
    st.session_state.done = {r["key"]: False for r in rows}
    st.session_state.fname = up.name
    reset_filters()
    st.rerun()


# ---------- rendering ----------

FILTER_SPEC_LABEL = 1.15


def filter_row(prefix, label, options, current, state_name, slots):
    """One filter line: a label column, then equal-width buttons. Returns the columns."""
    cols = st.columns([FILTER_SPEC_LABEL] + [2] * slots, gap="small", vertical_alignment="center")
    cols[0].markdown(f'<div class="glabel">{label}</div>', unsafe_allow_html=True)
    for i, (value, text) in enumerate(options):
        cols[i + 1].button(
            text, key=f"{prefix}_{i}", width="stretch",
            type="primary" if value == current else "secondary",
            on_click=set_filter, args=(state_name, value),
        )
    return cols


def render_filters(rows, done):
    f_type, f_status = st.session_state.f_type, st.session_state.f_status

    type_counts = {}
    for r in rows:
        type_counts[r["media_type"]] = type_counts.get(r["media_type"], 0) + 1
    ordered = sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    type_opts = [("All", f"All [{len(rows)}]")] + [(t, f"{t} [{n}]") for t, n in ordered]
    if f_type not in {v for v, _ in type_opts}:
        f_type = st.session_state.f_type = "All"

    in_type = [r for r in rows if f_type == "All" or r["media_type"] == f_type]
    n_done = sum(1 for r in in_type if done.get(r["key"]))
    status_opts = [
        ("All", f"All [{len(in_type)}]"),
        ("todo", f"To gather [{len(in_type) - n_done}]"),
        ("done", f"Gathered [{n_done}]"),
    ]
    slots = max(4, len(type_opts))

    with st.container(key="pane"):
        with st.container(key="frow_status"):
            cols = filter_row("fs", "Status", status_opts, f_status, "f_status", slots)
            cols[-1].button(
                "\u200b", key="reset_filters",
                help="Reset filters", on_click=reset_filters,
            )
        with st.container(key="frow_type"):
            filter_row("ft", "Media type", type_opts, f_type, "f_type", slots)

    return [
        r for r in in_type
        if f_status == "All" or (f_status == "done") == bool(done.get(r["key"]))
    ]


def render_header_row():
    with st.container(key="thead"):
        cols = st.columns(SPEC, gap="small")
        for col, head in zip(cols, HEADS):
            col.markdown(f'<div class="head">{head}</div>', unsafe_allow_html=True)


def render_rows(visible, rows, done):
    by_key = {r["key"]: r for r in rows}
    with st.container(key="tbody"):
        if not visible:
            st.markdown('<div class="empty">No scenes match these filters.</div>', unsafe_allow_html=True)
            return
        dim = [
            f'.st-key-row_{r["key"]} [data-testid="stMarkdownContainer"]'
            for r in visible if done.get(r["key"])
        ]
        if dim:
            st.markdown(f"<style>{','.join(dim)}{{opacity:.38}}</style>", unsafe_allow_html=True)
        for r in visible:
            key = r["key"]
            is_done = bool(done.get(key))
            with st.container(key=f"row_{key}"):
                c = st.columns(SPEC, gap="small")
                mark, sid = c[0].columns([1, 2.2], gap="xsmall")
                mark.button(
                    "\u200b", key=f"g_{key}",
                    type="primary" if is_done else "secondary",
                    on_click=toggle_done, args=(key,),
                )
                sid.markdown(cell_id(r), unsafe_allow_html=True)
                c[1].markdown(cell_media(r), unsafe_allow_html=True)
                c[2].markdown(cell_gather(r), unsafe_allow_html=True)
                c[3].markdown(cell_source(r, by_key), unsafe_allow_html=True)
                c[4].markdown(cell_script(r), unsafe_allow_html=True)


def main():
    st.set_page_config(page_title=TITLE, page_icon="\U0001F3AC", layout="wide")
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    st.session_state.setdefault("f_type", "All")
    st.session_state.setdefault("f_status", "All")

    with st.container(key="topbar"):
        left, right = st.columns([3, 2], vertical_alignment="center")
        left.markdown(f'<div class="title">{TITLE}</div>', unsafe_allow_html=True)
        rows = st.session_state.get("rows")
        if rows:
            right.markdown(
                f'<div class="chipwrap"><div class="fchip">{esc(st.session_state.get("fname", ""))}'
                f'<span>{len(rows)} scenes</span></div></div>',
                unsafe_allow_html=True,
            )
            done = st.session_state.done
            visible = render_filters(rows, done)
            render_header_row()
        else:
            up = right.file_uploader("Scene plan CSV", type=["csv"], label_visibility="collapsed")
            load_upload(up)

    if not rows:
        st.markdown(
            '<div class="empty">Upload a scene plan CSV to begin.</div>', unsafe_allow_html=True
        )
        return
    render_rows(visible, rows, st.session_state.done)


if __name__ == "__main__":
    main()
