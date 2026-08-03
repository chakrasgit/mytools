"""
YTubeCatchUp
A Streamlit tool to pull every video posted by a list of YouTube channels
within a chosen date range, with clickable links, into one page.
"""

import html
import re
from datetime import datetime, time as dtime

import pandas as pd
import pytz
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
IST = pytz.timezone("Asia/Kolkata")
MAX_PLAYLIST_PAGES = 40   # 40 * 50 = 2000 videos max per channel per search
SHORT_MAX_SECONDS = 180   # YouTube's own Shorts cutoff

st.set_page_config(page_title="YTubeCatchUp", layout="wide")


def html_block(html_str):
    """Streamlit's markdown renderer treats 4+ leading spaces on a line as
    an indented code block, which prints raw HTML tags instead of rendering
    them. Strip leading whitespace from every line to avoid that."""
    return "\n".join(line.strip() for line in html_str.strip().splitlines())

CUSTOM_CSS = """
<style>
    .stApp {
        background-color: #0b0f14;
        color: #e6edf3;
    }
    h1, h2, h3 {
        color: #58a6ff;
        font-family: 'Segoe UI', sans-serif;
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
    .channel-card {
        background-color: #11161d;
        border: 1px solid #1f2a37;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 26px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    .channel-card-header {
        display: flex;
        align-items: center;
        gap: 14px;
        flex-wrap: wrap;
    }
    .channel-avatar {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        object-fit: cover;
        flex-shrink: 0;
    }
    .channel-title {
        font-size: 19px;
        font-weight: 700;
        color: #e6edf3;
        margin-right: 4px;
    }
    .channel-stats {
        font-size: 13px;
        color: #9fb3c8;
    }
    .truncated-note {
        margin-top: 10px;
        font-size: 12.5px;
        color: #f0883e;
    }
    table.video-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 16px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 13.5px;
    }
    table.video-table th {
        background-color: #1f6feb;
        color: #ffffff;
        text-align: left;
        padding: 9px 10px;
        font-size: 12.5px;
        letter-spacing: 0.02em;
    }
    table.video-table td {
        padding: 9px 10px;
        border-bottom: 1px solid #1f2a37;
        color: #e6edf3;
        vertical-align: middle;
    }
    table.video-table tr:nth-child(even) {
        background-color: #0f141b;
    }
    table.video-table a {
        color: #58a6ff;
        text-decoration: none;
        font-weight: 600;
    }
    table.video-table a:hover {
        text-decoration: underline;
    }
    .badge {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 11.5px;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-short { background-color: #1f3a2a; color: #3fb950; }
    .badge-long  { background-color: #17293f; color: #58a6ff; }
    .badge-live  { background-color: #3f1f1f; color: #f85149; }
    .warning-row {
        color: #f0883e;
        font-weight: 600;
    }
    div.stButton > button,
    div[data-testid="stDownloadButton"] > button {
        background-color: #1f6feb;
        color: #ffffff;
        border: 1.5px solid #1f6feb;
        border-radius: 6px;
        font-weight: 600;
        padding: 6px 16px;
        transition: background-color 0.15s ease, border-color 0.15s ease, transform 0.05s ease;
    }
    div.stButton > button:hover,
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #388bfd;
        border-color: #388bfd;
    }
    div.stButton > button:active,
    div[data-testid="stDownloadButton"] > button:active {
        background-color: #1158c7;
        border-color: #1158c7;
        transform: scale(0.98);
    }
    /* Reset button: red outline by default, filled red on hover/press */
    .st-key-reset_btn button {
        background-color: transparent !important;
        color: #f85149 !important;
        border: 1.5px solid #f85149 !important;
    }
    .st-key-reset_btn button:hover {
        background-color: #f85149 !important;
        color: #ffffff !important;
        border-color: #f85149 !important;
    }
    .st-key-reset_btn button:active {
        background-color: #da3633 !important;
        border-color: #da3633 !important;
        transform: scale(0.98);
    }
    /* Drop the boxed border Streamlit puts around the paste area, and hide
       the built-in "Press Ctrl+Enter to apply" hint under it */
    div[data-testid="stTextArea"] textarea {
        border: 1px solid #1f2a37 !important;
        background-color: #11161d !important;
    }
    [data-testid="InputInstructions"] {
        display: none !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def get_youtube_client():
    api_key = st.secrets.get("YOUTUBE_API_KEY", "")
    if not api_key:
        st.error("No YouTube API key found. Add YOUTUBE_API_KEY to Streamlit secrets.")
        st.stop()
    return build("youtube", "v3", developerKey=api_key)


def friendly_api_error(e):
    """Turn an HttpError into something a non-developer can read."""
    status = None
    try:
        status = e.resp.status
    except Exception:
        pass
    msg = str(e)
    if status == 403 and "quota" in msg.lower():
        return "YouTube API daily quota exceeded. Try again after it resets (midnight Pacific time)."
    if status == 404:
        return "Channel or resource not found."
    if status == 400:
        return "The request was rejected by YouTube (bad request)."
    return f"API error{f' ({status})' if status else ''}: {msg}"


def resolve_channel_id(url, youtube):
    """Returns (channel_id, error_message)."""
    url = url.strip()
    if not url:
        return None, "Empty link"

    m = re.search(r"youtube\.com/channel/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1), None

    m = re.search(r"youtube\.com/@([a-zA-Z0-9_.-]+)", url)
    if m:
        handle = m.group(1)
        try:
            resp = youtube.channels().list(part="id", forHandle=handle).execute()
        except HttpError as e:
            return None, friendly_api_error(e)
        if resp.get("items"):
            return resp["items"][0]["id"], None
        return None, f"Could not resolve handle @{handle}"

    m = re.search(r"youtube\.com/(?:c|user)/([a-zA-Z0-9_.-]+)", url)
    if m:
        name = m.group(1)
        try:
            # Modern /c/ custom-URL links are almost never legacy usernames,
            # so try the reliable handle/search route first and fall back to
            # the legacy forUsername lookup only if that comes up empty.
            resp = youtube.channels().list(part="id", forHandle=name).execute()
            if resp.get("items"):
                return resp["items"][0]["id"], None

            resp = youtube.search().list(
                part="snippet", q=name, type="channel", maxResults=1
            ).execute()
            if resp.get("items"):
                return resp["items"][0]["snippet"]["channelId"], None

            resp = youtube.channels().list(part="id", forUsername=name).execute()
            if resp.get("items"):
                return resp["items"][0]["id"], None
        except HttpError as e:
            return None, friendly_api_error(e)
        return None, f"Could not resolve channel '{name}'"

    return None, "Unrecognized channel link format"


def get_channel_meta(channel_id, youtube):
    resp = youtube.channels().list(
        part="snippet,statistics,contentDetails", id=channel_id
    ).execute()
    if not resp.get("items"):
        return None
    item = resp["items"][0]
    stats = item["statistics"]
    thumbnails = item["snippet"].get("thumbnails", {})
    thumb_url = (
        thumbnails.get("default", {}).get("url")
        or thumbnails.get("medium", {}).get("url")
        or ""
    )
    return {
        "title": item["snippet"]["title"],
        "thumbnail": thumb_url,
        "subscribers": None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "uploads_playlist": item["contentDetails"]["relatedPlaylists"]["uploads"],
    }


def get_videos_in_range(uploads_playlist_id, start_utc, end_utc, youtube):
    """Uploads playlist returns newest-first, so we can stop early.
    Capped at MAX_PLAYLIST_PAGES pages to protect API quota; returns
    (video_items, truncated)."""
    video_items = []
    next_page = None
    pages_fetched = 0
    truncated = False

    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page,
        ).execute()
        pages_fetched += 1

        stop = False
        for it in resp.get("items", []):
            published = it["snippet"]["publishedAt"]
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if pub_dt < start_utc:
                stop = True
                break
            if start_utc <= pub_dt <= end_utc:
                video_items.append(it)

        next_page = resp.get("nextPageToken")
        if stop or not next_page:
            break
        if pages_fetched >= MAX_PLAYLIST_PAGES:
            truncated = True
            break

    return video_items, truncated


def get_video_details(video_ids, youtube):
    """Batches video IDs 50 at a time. Returns dict keyed by video_id."""
    details = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="contentDetails,statistics", id=",".join(chunk)
        ).execute()
        for item in resp.get("items", []):
            details[item["id"]] = item
    return details


def parse_duration(iso_duration):
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "PT0S")
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    total_seconds = h * 3600 + m * 60 + s
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}", total_seconds
    return f"{m}:{s:02d}", total_seconds


def classify_type(duration_seconds):
    """Classify by duration only (YouTube's own Shorts cutoff is 3 minutes).
    No live network probe here, that was slow and flaky under load."""
    if duration_seconds == 0:
        return "Live/Upcoming"
    return "Short" if duration_seconds <= SHORT_MAX_SECONDS else "Long"


def badge_html(vtype):
    cls = {"Short": "badge-short", "Long": "badge-long", "Live/Upcoming": "badge-live"}.get(vtype, "badge-long")
    return f'<span class="badge {cls}">{html.escape(vtype)}</span>'


def fmt_num(n):
    if n is None:
        return "Hidden"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "N/A"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.2f}K"
    return str(n)


def to_ist_str(utc_iso):
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    dt_ist = dt.astimezone(IST)
    return dt_ist.strftime("%d/%m/%Y %I:%M %p")


def date_bounds_ist(from_date, to_date):
    start_ist = IST.localize(datetime.combine(from_date, dtime.min))
    end_ist = IST.localize(datetime.combine(to_date, dtime.max))
    return start_ist.astimezone(pytz.utc), end_ist.astimezone(pytz.utc)


def dedupe_links(raw_text):
    """Split on commas, strip, and drop case/trailing-slash duplicates
    while preserving first-seen order."""
    seen = set()
    out = []
    for chunk in raw_text.split(","):
        link = chunk.strip()
        if not link:
            continue
        norm = link.lower().rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        out.append(link)
    return out


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "cache" not in st.session_state:
    st.session_state.cache = {}
if "results" not in st.session_state:
    st.session_state.results = None
if "csv_rows" not in st.session_state:
    st.session_state.csv_rows = None


def reset_everything():
    # st.button's on_click callback already triggers a rerun once it
    # returns, so no explicit st.rerun() is needed (and calling it here
    # would be redundant on top of Streamlit's own callback rerun).
    st.session_state.clear()


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
st.markdown(
    html_block(
        '<div class="app-header"><span class="icon">📺</span>'
        '<span class="title">YTubeCatchUp</span></div>'
        '<div class="app-caption">Pull every video posted by your chosen '
        'channels, in one place, no more clicking through each channel.</div>'
    ),
    unsafe_allow_html=True,
)

# One line: From date | To date | Search | Reset | Download CSV.
# vertical_alignment="bottom" lines up the button baselines with the date
# input boxes (date inputs have a label above them, buttons don't).
d1, d2, s1, r1, c1, _spacer = st.columns(
    [1.2, 1.2, 1.1, 1.1, 1.4, 2.2], gap="small", vertical_alignment="bottom"
)
with d1:
    from_date = st.date_input("From date", format="DD/MM/YYYY", key="from_date")
with d2:
    to_date = st.date_input("To date", format="DD/MM/YYYY", key="to_date")
with s1:
    search_clicked = st.button("Search", key="search_btn", use_container_width=True)
with r1:
    st.button("Reset", key="reset_btn", on_click=reset_everything, use_container_width=True)
with c1:
    csv_placeholder = st.empty()
    csv_placeholder.button("Download CSV", key="csv_btn_placeholder", disabled=True, use_container_width=True)

# No enclosing box here on purpose, just the field itself with a subtle
# border so it does not look like a boxed-in outline.
channels_input = st.text_area(
    "Channel links (comma-separated)",
    placeholder=(
        "Paste one or more channel links here, separated by commas. "
        "For example: https://www.youtube.com/@channel1, "
        "https://www.youtube.com/channel/UCxxxxxx. "
        "You can paste with Ctrl+V (Cmd+V on Mac)."
    ),
    key="channels_input",
    height=100,
    label_visibility="collapsed",
)

if search_clicked:
    if not channels_input.strip():
        st.warning("Please paste at least one channel link.")
    elif from_date > to_date:
        st.warning("'From date' must not be after 'To date'.")
    else:
        youtube = get_youtube_client()
        start_utc, end_utc = date_bounds_ist(from_date, to_date)
        links = dedupe_links(channels_input)

        # Cache entries are only trustworthy for ranges that are fully in
        # the past. If "to date" includes today, new uploads could land
        # after the first search, so we skip the cache for that case.
        today_ist = datetime.now(IST).date()
        cache_is_fresh_range = to_date < today_ist

        results = []
        csv_rows = []

        progress = st.progress(0.0, text="Starting...")
        for idx, link in enumerate(links):
            progress.progress(idx / len(links), text=f"Fetching {link}")

            cache_key = (link, str(from_date), str(to_date))
            if cache_is_fresh_range and cache_key in st.session_state.cache:
                results.append(st.session_state.cache[cache_key])
                continue

            channel_id, err = resolve_channel_id(link, youtube)
            if err:
                entry = {"error": err, "link": link}
                results.append(entry)
                if cache_is_fresh_range:
                    st.session_state.cache[cache_key] = entry
                continue

            try:
                meta = get_channel_meta(channel_id, youtube)
                if not meta:
                    entry = {"error": "Channel not found", "link": link}
                    results.append(entry)
                    if cache_is_fresh_range:
                        st.session_state.cache[cache_key] = entry
                    continue

                items, truncated = get_videos_in_range(
                    meta["uploads_playlist"], start_utc, end_utc, youtube
                )
                video_ids = [it["contentDetails"]["videoId"] for it in items]
                details = get_video_details(video_ids, youtube) if video_ids else {}

                videos = []
                for it in items:
                    vid = it["contentDetails"]["videoId"]
                    d = details.get(vid, {})
                    dur_str, dur_sec = parse_duration(d.get("contentDetails", {}).get("duration"))
                    vtype = classify_type(dur_sec)
                    stats = d.get("statistics", {})
                    videos.append({
                        "title": it["snippet"]["title"],
                        "video_id": vid,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "duration": dur_str,
                        "type": vtype,
                        "posted_ist": to_ist_str(it["snippet"]["publishedAt"]),
                        "views": stats.get("viewCount"),
                        "likes": stats.get("likeCount"),
                        "comments": stats.get("commentCount"),
                    })
                # newest first already, keep as-is

                entry = {
                    "error": None,
                    "meta": meta,
                    "videos": videos,
                    "link": link,
                    "truncated": truncated,
                }
                results.append(entry)
                if cache_is_fresh_range:
                    st.session_state.cache[cache_key] = entry

            except HttpError as e:
                entry = {"error": friendly_api_error(e), "link": link}
                results.append(entry)
                if cache_is_fresh_range:
                    st.session_state.cache[cache_key] = entry

        progress.progress(1.0, text="Done")
        progress.empty()

        st.session_state.results = results

        for entry in results:
            if entry.get("error"):
                continue
            for v in entry["videos"]:
                csv_rows.append({
                    "Channel": entry["meta"]["title"],
                    "Video Title": v["title"],
                    "Link": v["url"],
                    "Duration": v["duration"],
                    "Type": v["type"],
                    "Posted (IST)": v["posted_ist"],
                    "Views": v["views"],
                    "Likes": v["likes"],
                    "Comments": v["comments"],
                })
        st.session_state.csv_rows = csv_rows


# --------------------------------------------------------------------------
# Display results
# --------------------------------------------------------------------------
if st.session_state.results:
    for entry in st.session_state.results:
        if entry.get("error"):
            st.markdown(
                html_block(
                    f'<div class="channel-card"><span class="warning-row">'
                    f'⚠️ {html.escape(entry["link"])}: {html.escape(entry["error"])}</span></div>'
                ),
                unsafe_allow_html=True,
            )
            continue

        meta = entry["meta"]
        videos = entry["videos"]
        safe_title = html.escape(meta["title"])
        avatar_html = f'<img class="channel-avatar" src="{html.escape(meta["thumbnail"])}" />' if meta.get("thumbnail") else ""

        subs_display = fmt_num(meta["subscribers"]) if meta["subscribers"] is not None else "Hidden"
        views_display = fmt_num(meta["total_views"])

        header_html = (
            '<div class="channel-card">'
            '<div class="channel-card-header">'
            f'{avatar_html}'
            f'<span class="channel-title">{safe_title}</span>'
            f'<span class="channel-stats">👥 {subs_display} subscribers &nbsp;|&nbsp; '
            f'👁 {views_display} total views</span>'
            '</div>'
        )

        if entry.get("truncated"):
            header_html += (
                '<div class="truncated-note">⚠️ This channel had more '
                f'than {MAX_PLAYLIST_PAGES * 50} uploads to scan, results '
                'for the oldest part of the range may be incomplete.</div>'
            )

        if not videos:
            header_html += (
                "<p style='margin-top:12px;color:#9fb3c8;'>"
                "No videos posted in this date range.</p></div>"
            )
            st.markdown(html_block(header_html), unsafe_allow_html=True)
            continue

        rows_html = ""
        for i, v in enumerate(videos, start=1):
            likes = fmt_num(v["likes"]) if v["likes"] is not None else "Hidden"
            comments = fmt_num(v["comments"]) if v["comments"] is not None else "Disabled"
            safe_vtitle = html.escape(v["title"])
            rows_html += (
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{safe_vtitle}</td>"
                f'<td><a href="{v["url"]}" target="_blank">Click here</a></td>'
                f"<td>{v['duration']}</td>"
                f"<td>{badge_html(v['type'])}</td>"
                f"<td>{v['posted_ist']}</td>"
                f"<td>{fmt_num(v['views'])}</td>"
                f"<td>{likes}</td>"
                f"<td>{comments}</td>"
                "</tr>"
            )

        table_html = (
            '<table class="video-table">'
            "<tr>"
            "<th>S.No</th><th>Video Title</th><th>Link</th><th>Duration</th>"
            "<th>Type</th><th>Posted</th><th>Views</th><th>Likes</th><th>Comments</th>"
            "</tr>"
            f"{rows_html}"
            "</table></div>"
        )
        st.markdown(html_block(header_html + table_html), unsafe_allow_html=True)

    if st.session_state.csv_rows:
        df = pd.DataFrame(st.session_state.csv_rows)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        csv_placeholder.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="ytubecatchup_results.csv",
            mime="text/csv",
            use_container_width=True,
        )
