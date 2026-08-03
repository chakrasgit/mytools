"""
YTubeCatchUp
A Streamlit tool to pull every video posted by a list of YouTube channels
within a chosen date range, with clickable links, into one page.
"""

import re
from datetime import datetime, time as dtime

import pandas as pd
import pytz
import requests
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
IST = pytz.timezone("Asia/Kolkata")

st.set_page_config(page_title="YTubeCatchUp", layout="wide")


def html_block(html):
    """Streamlit's markdown renderer treats 4+ leading spaces on a line as
    an indented code block, which prints raw HTML tags instead of rendering
    them. Strip leading whitespace from every line to avoid that."""
    return "\n".join(line.strip() for line in html.strip().splitlines())

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
    .channel-card {
        background-color: #11161d;
        border: 1px solid #1f2a37;
        border-radius: 10px;
        padding: 18px 22px;
        margin-bottom: 28px;
    }
    .channel-title {
        font-size: 22px;
        font-weight: 700;
        color: #58a6ff;
        display: inline-block;
        margin-right: 18px;
    }
    .channel-stats {
        font-size: 14px;
        color: #9fb3c8;
    }
    table.video-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 14px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }
    table.video-table th {
        background-color: #1f6feb;
        color: #ffffff;
        text-align: left;
        padding: 8px 10px;
        font-size: 13px;
    }
    table.video-table td {
        padding: 8px 10px;
        border-bottom: 1px solid #1f2a37;
        color: #e6edf3;
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
    .warning-row {
        color: #f0883e;
        font-weight: 600;
    }
    div.stButton > button {
        background-color: #1f6feb;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
    }
    div.stButton > button:hover {
        background-color: #388bfd;
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
            return None, f"API error: {e}"
        if resp.get("items"):
            return resp["items"][0]["id"], None
        return None, f"Could not resolve handle @{handle}"

    m = re.search(r"youtube\.com/(?:c|user)/([a-zA-Z0-9_-]+)", url)
    if m:
        name = m.group(1)
        try:
            resp = youtube.channels().list(part="id", forUsername=name).execute()
            if resp.get("items"):
                return resp["items"][0]["id"], None
            resp = youtube.channels().list(part="id", forHandle=name).execute()
            if resp.get("items"):
                return resp["items"][0]["id"], None
            resp = youtube.search().list(
                part="snippet", q=name, type="channel", maxResults=1
            ).execute()
            if resp.get("items"):
                return resp["items"][0]["snippet"]["channelId"], None
        except HttpError as e:
            return None, f"API error: {e}"
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
    return {
        "title": item["snippet"]["title"],
        "subscribers": None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "uploads_playlist": item["contentDetails"]["relatedPlaylists"]["uploads"],
    }


def get_videos_in_range(uploads_playlist_id, start_utc, end_utc, youtube):
    """Uploads playlist returns newest-first, so we can stop early."""
    video_items = []
    next_page = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page,
        ).execute()

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

    return video_items


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


def classify_type(video_id, duration_seconds):
    if duration_seconds > 180:
        return "Long"
    try:
        r = requests.get(
            f"https://www.youtube.com/shorts/{video_id}",
            allow_redirects=True,
            timeout=5,
        )
        return "Short" if "/shorts/" in r.url else "Long"
    except requests.RequestException:
        return "Short" if duration_seconds <= 60 else "Long"


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
    st.session_state.clear()
    st.rerun()


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
st.title("📺 YTubeCatchUp")
st.caption("Pull every video posted by your chosen channels, in one place.")

# Small buttons at the top. They're read further down, after the widgets
# below define their values, but they render here because that's where
# they're called.
top_col1, top_col2, _spacer = st.columns([1, 1, 6])
search_clicked = top_col1.button("🔍 Search")
top_col2.button("♻️ Reset", on_click=reset_everything)

channels_input = st.text_area(
    "Channel links (comma-separated)",
    placeholder="https://www.youtube.com/@channel1, https://www.youtube.com/channel/UCxxxxxx, ...",
    key="channels_input",
    height=100,
)

col1, col2 = st.columns(2)
with col1:
    from_date = st.date_input("From date", format="DD/MM/YYYY", key="from_date")
with col2:
    to_date = st.date_input("To date", format="DD/MM/YYYY", key="to_date")

if search_clicked:
    if not channels_input.strip():
        st.warning("Please paste at least one channel link.")
    elif from_date > to_date:
        st.warning("'From date' must not be after 'To date'.")
    else:
        youtube = get_youtube_client()
        start_utc, end_utc = date_bounds_ist(from_date, to_date)
        links = [c.strip() for c in channels_input.split(",") if c.strip()]

        results = []
        csv_rows = []

        progress = st.progress(0.0, text="Starting...")
        for idx, link in enumerate(links):
            progress.progress((idx) / len(links), text=f"Fetching {link}")

            cache_key = (link, str(from_date), str(to_date))
            if cache_key in st.session_state.cache:
                results.append(st.session_state.cache[cache_key])
                continue

            channel_id, err = resolve_channel_id(link, youtube)
            if err:
                entry = {"error": err, "link": link}
                results.append(entry)
                st.session_state.cache[cache_key] = entry
                continue

            try:
                meta = get_channel_meta(channel_id, youtube)
                if not meta:
                    entry = {"error": "Channel not found", "link": link}
                    results.append(entry)
                    st.session_state.cache[cache_key] = entry
                    continue

                items = get_videos_in_range(meta["uploads_playlist"], start_utc, end_utc, youtube)
                video_ids = [it["contentDetails"]["videoId"] for it in items]
                details = get_video_details(video_ids, youtube) if video_ids else {}

                videos = []
                for it in items:
                    vid = it["contentDetails"]["videoId"]
                    d = details.get(vid, {})
                    dur_str, dur_sec = parse_duration(d.get("contentDetails", {}).get("duration"))
                    vtype = classify_type(vid, dur_sec)
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

                entry = {"error": None, "meta": meta, "videos": videos, "link": link}
                results.append(entry)
                st.session_state.cache[cache_key] = entry

            except HttpError as e:
                entry = {"error": f"API error: {e}", "link": link}
                results.append(entry)
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
                    f'⚠️ {entry["link"]} — {entry["error"]}</span></div>'
                ),
                unsafe_allow_html=True,
            )
            continue

        meta = entry["meta"]
        videos = entry["videos"]

        subs_display = fmt_num(meta["subscribers"]) if meta["subscribers"] is not None else "Hidden"
        views_display = fmt_num(meta["total_views"])

        header_html = (
            '<div class="channel-card">'
            f'<span class="channel-title">{meta["title"]}</span>'
            f'<span class="channel-stats">👥 {subs_display} subscribers &nbsp;|&nbsp; '
            f'👁 {views_display} total views</span>'
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
            rows_html += (
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{v['title']}</td>"
                f'<td><a href="{v["url"]}" target="_blank">Click here</a></td>'
                f"<td>{v['duration']}</td>"
                f"<td>{v['type']}</td>"
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
        st.download_button(
            "⬇️ Download CSV",
            data=csv_bytes,
            file_name="ytubecatchup_results.csv",
            mime="text/csv",
        )
