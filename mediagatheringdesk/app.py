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

# Badge colors (background, text) per media type, lower-case keys.
BADGES = {
    "real image": ("#12304a", "#7cc8f0"),
    "screenshot": ("#17315c", "#8fb8f5"),
    "screen recording": ("#2b2354", "#b6a6f0"),
    "clip": ("#232a5e", "#a3b0f2"),
    "animation clip": ("#10393a", "#6fd0c4"),
    "animation code": ("#0f3744", "#6cc9df"),
    "ai-generated image": ("#431f38", "#eca0c8"),
    "ai-generated video": ("#473416", "#e6b867"),
}
DEFAULT_BADGE = ("#232b3b", "#a6b0c4")

# Column widths: ID, gathered mark, media, what to gather, source, script.
SPEC = [0.55, 0.45, 2.4, 3.2, 3.2, 3.4]
HEADS = ["ID", "\u2713", "Media", "What to gather", "Source or prompt", "Script"]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;500&display=swap');

[data-testid="stHeader"]{display:none}
[data-testid="stMainBlockContainer"]{padding:0.8rem 1.4rem 3rem;max-width:100%}

.st-key-topbar{position:sticky;top:0;z-index:100;background:#0e1526;padding:0.2rem 0 0.5rem;gap:0.5rem}
.st-key-pane{background:#121b30;border:1px solid #26344f;border-radius:10px;padding:0.6rem 0.7rem;gap:0.5rem}
.st-key-grp_status,.st-key-grp_type{background:#0e1526;border:1px solid #223051;border-radius:8px;padding:0.5rem 0.65rem;gap:0.35rem}

.title{font-size:1.2rem;font-weight:500;color:#eaf1ff}
.glabel{font-size:11px;color:#8d9bb8}
.fname{font-size:12px;color:#8d9bb8}

[data-testid="stFileUploaderDropzone"]{padding:0.35rem 0.6rem;background:#121b30;border:1px solid #26344f;border-radius:10px}
[data-testid="stFileUploaderDropzoneInstructions"]{display:none}

[class*="st-key-fs_"] button,[class*="st-key-ft_"] button,.st-key-reset_filters button{
  width:100%;min-height:30px;height:30px;padding:0 6px;border-radius:6px;font-size:12px;
  white-space:nowrap;overflow:hidden;transition:background .12s,border-color .12s,color .12s,transform .06s}
[class*="st-key-fs_"] button p,[class*="st-key-ft_"] button p,.st-key-reset_filters button p{
  font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"],
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"],
.st-key-reset_filters button{background:transparent;border:1px solid #2f4066;color:#a9b6d3}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"]:hover,
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"]:hover,
.st-key-reset_filters button:hover{background:rgba(79,140,240,.22);border-color:rgba(79,140,240,.6);color:#d6e4ff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-secondary"]:active,
[class*="st-key-ft_"] button[data-testid="stBaseButton-secondary"]:active,
.st-key-reset_filters button:active{background:rgba(79,140,240,.42);border-color:#6aa0f5;color:#fff;transform:scale(.97)}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"],
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]{background:rgba(79,140,240,.68);border:1px solid #7fb0f8;color:#fff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"]:hover,
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]:hover{background:rgba(79,140,240,.8);border-color:#9bc2fa;color:#fff}
[class*="st-key-fs_"] button[data-testid="stBaseButton-primary"]:active,
[class*="st-key-ft_"] button[data-testid="stBaseButton-primary"]:active{background:rgba(79,140,240,.9);transform:scale(.97)}
.st-key-reset_filters button{width:34px;min-width:34px;padding:0}

[class*="st-key-g_"] button{width:22px;min-width:22px;min-height:22px;height:22px;padding:0;border-radius:6px;
  transition:none;box-shadow:none}
[class*="st-key-g_"] button p{font-size:14px;line-height:1}
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"],
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"]:hover,
[class*="st-key-g_"] button[data-testid="stBaseButton-secondary"]:active{background:#2a3552;border:1px solid #4a5a80;color:transparent}
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"],
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"]:hover,
[class*="st-key-g_"] button[data-testid="stBaseButton-primary"]:active{background:#4f8cf0;border:1px solid #4f8cf0;color:#fff}

[class*="st-key-row_"]{border-bottom:1px solid #1c2740;padding:0.55rem 0}
.head{font-size:11px;color:#8d9bb8;border-bottom:1px solid #26344f;padding-bottom:4px}

.cell{font-size:13px;line-height:1.55;color:#dbe3f4;overflow-wrap:anywhere}
.cell a{color:#7fb0f8}
.sid{font-weight:500}
.mname{font-weight:500;margin-bottom:4px}
.dur{font-size:12px;color:#8d9bb8;margin-top:4px}
.bd{display:inline-block;font-size:11px;padding:1px 9px;border-radius:6px}
.rl{display:inline-block;font-size:11px;padding:1px 8px;border-radius:6px;background:#473416;color:#e6b867;margin-right:6px}
.also{font-size:12px;color:#8d9bb8;margin-top:6px}
.chunk{font-size:11px;color:#8d9bb8;margin-bottom:3px}
.te{font-family:"Noto Sans Telugu","Nirmala UI","Gautami",sans-serif;font-size:13px;line-height:1.8}
.en{font-size:13px;color:#98a6c4;margin-top:4px}
.anc{display:block;position:relative;top:-230px;visibility:hidden}
.empty{color:#8d9bb8;padding:2rem 0}
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
    if "scene_id" not in fields or "media_name" not in fields:
        raise ValueError("This does not look like a scene plan CSV (needs scene_id and media_name columns).")
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
    for k in ("rows", "done", "fid", "fname"):
        st.session_state.pop(k, None)
    reset_filters()


def load_upload(up):
    """Load a new upload into session state; clear state if the file was removed."""
    if up is None:
        if st.session_state.get("fid") is not None:
            clear_data()
        return
    fid = (up.name, up.size, getattr(up, "file_id", ""))
    if st.session_state.get("fid") == fid:
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
    st.session_state.fid = fid
    st.session_state.fname = up.name
    reset_filters()


# ---------- rendering ----------

def filter_buttons(prefix, options, current, state_name, slots):
    cols = st.columns(slots, gap="small")
    for i, (value, label) in enumerate(options):
        cols[i].button(
            label, key=f"{prefix}_{i}", width="stretch",
            type="primary" if value == current else "secondary",
            on_click=set_filter, args=(state_name, value),
        )


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
    slots = max(3, len(type_opts))

    with st.container(key="pane"):
        head, reset = st.columns([30, 1], vertical_alignment="center")
        head.markdown('<div class="glabel">Filters</div>', unsafe_allow_html=True)
        reset.button("\u21bb", key="reset_filters", help="Reset filters", on_click=reset_filters)
        with st.container(key="grp_status"):
            st.markdown('<div class="glabel">Status</div>', unsafe_allow_html=True)
            filter_buttons("fs", status_opts, f_status, "f_status", slots)
        with st.container(key="grp_type"):
            st.markdown('<div class="glabel">Media type</div>', unsafe_allow_html=True)
            filter_buttons("ft", type_opts, f_type, "f_type", slots)

    visible = [
        r for r in in_type
        if f_status == "All" or (f_status == "done") == bool(done.get(r["key"]))
    ]
    return visible


def render_header_row():
    cols = st.columns(SPEC, gap="small")
    for col, head in zip(cols, HEADS):
        col.markdown(f'<div class="head">{head}</div>', unsafe_allow_html=True)


def render_rows(visible, rows, done):
    by_key = {r["key"]: r for r in rows}
    if not visible:
        st.markdown('<div class="empty">No scenes match these filters.</div>', unsafe_allow_html=True)
        return
    dim = [
        f'.st-key-row_{r["key"]} [data-testid="stMarkdownContainer"]'
        for r in visible if done.get(r["key"])
    ]
    if dim:
        st.markdown(f"<style>{','.join(dim)}{{opacity:.5}}</style>", unsafe_allow_html=True)
    for r in visible:
        key = r["key"]
        is_done = bool(done.get(key))
        with st.container(key=f"row_{key}"):
            c = st.columns(SPEC, gap="small")
            c[0].markdown(cell_id(r), unsafe_allow_html=True)
            c[1].button(
                "\u2713" if is_done else "\u00a0", key=f"g_{key}",
                type="primary" if is_done else "secondary",
                help="Gathered. Click to undo." if is_done else "Mark as gathered",
                on_click=toggle_done, args=(key,),
            )
            c[2].markdown(cell_media(r), unsafe_allow_html=True)
            c[3].markdown(cell_gather(r), unsafe_allow_html=True)
            c[4].markdown(cell_source(r, by_key), unsafe_allow_html=True)
            c[5].markdown(cell_script(r), unsafe_allow_html=True)


def main():
    st.set_page_config(page_title=TITLE, page_icon="\U0001F3AC", layout="wide")
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    st.session_state.setdefault("f_type", "All")
    st.session_state.setdefault("f_status", "All")

    with st.container(key="topbar"):
        left, right = st.columns([3, 2], vertical_alignment="center")
        left.markdown(f'<div class="title">{TITLE}</div>', unsafe_allow_html=True)
        up = right.file_uploader("Scene plan CSV", type=["csv"], label_visibility="collapsed")
        load_upload(up)
        rows = st.session_state.get("rows")
        if rows:
            done = st.session_state.done
            visible = render_filters(rows, done)
            render_header_row()

    if not rows:
        st.markdown(
            '<div class="empty">Upload a scene plan CSV to begin.</div>', unsafe_allow_html=True
        )
        return
    render_rows(visible, rows, st.session_state.done)


if __name__ == "__main__":
    main()
