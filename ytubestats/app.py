"""
YouTube Channel Video Exporter & Dashboard
-------------------------------------------
Paste a YouTube channel (ID, @handle, or URL) and get:
  - Every uploaded video's title, duration, type, publish date, views,
    likes, and comment count, exportable as CSV (newest first).
  - KPI cards: total videos, avg uploads/day, current subscribers, total views.
  - An interactive upload-timeline chart (Month / Quarter / Year toggle).
  - A video-duration bucket chart.

Uses the official YouTube Data API v3. Requires a free Google Cloud API key
with "YouTube Data API v3" enabled (see README.md).
"""

import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = "https://www.googleapis.com/youtube/v3"
SHORT_THRESHOLD_SECONDS = 180  # YouTube raised the Shorts cap to 3 min in Oct 2024

DURATION_BUCKET_EDGES = [0, 60, 180, 300, 600, 1200, 2400, 3600, float("inf")]
DURATION_BUCKET_LABELS = [
    "<1 min", "1-3 min", "3-5 min", "5-10 min",
    "10-20 min", "20-40 min", "40-60 min", ">60 min",
]


# --------------------------------------------------------------------------- #
# YouTube API helpers
# --------------------------------------------------------------------------- #
def parse_iso8601_duration(duration_str: str) -> int:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def format_duration(total_seconds: int) -> str:
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def api_get(endpoint: str, params: dict, api_key: str) -> dict:
    resp = requests.get(f"{API_BASE}/{endpoint}", params={**params, "key": api_key}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"YouTube API error ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def resolve_channel_id(raw_input: str, api_key: str) -> str:
    raw_input = raw_input.strip()
    if re.fullmatch(r"UC[\w-]{22}", raw_input):
        return raw_input

    handle = None
    if "youtube.com" in raw_input:
        m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", raw_input)
        if m:
            return m.group(1)
        m = re.search(r"youtube\.com/@([\w.-]+)", raw_input)
        if m:
            handle = m.group(1)
        m = re.search(r"youtube\.com/(?:c|user)/([\w.-]+)", raw_input)
        if m:
            handle = m.group(1)
    elif raw_input.startswith("@"):
        handle = raw_input[1:]
    else:
        handle = raw_input

    if handle:
        data = api_get("channels", {"part": "id", "forHandle": handle}, api_key)
        items = data.get("items", [])
        if items:
            return items[0]["id"]

        data = api_get("channels", {"part": "id", "forUsername": handle}, api_key)
        items = data.get("items", [])
        if items:
            return items[0]["id"]

        data = api_get(
            "search", {"part": "snippet", "q": handle, "type": "channel", "maxResults": 1}, api_key
        )
        items = data.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]

    raise ValueError("Could not resolve a channel ID from that input.")


def get_channel_info(channel_id: str, api_key: str) -> dict:
    data = api_get(
        "channels", {"part": "snippet,statistics,contentDetails", "id": channel_id}, api_key
    )
    items = data.get("items", [])
    if not items:
        raise ValueError("Channel not found.")
    item = items[0]
    stats = item.get("statistics", {})
    return {
        "title": item["snippet"]["title"],
        "uploads_playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
        "subscriber_count": None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
        "total_views": int(stats.get("viewCount", 0)) if "viewCount" in stats else None,
    }


def get_all_video_ids(uploads_playlist_id: str, api_key: str, progress_cb=None) -> list:
    video_ids = []
    page_token = None
    while True:
        params = {"part": "contentDetails", "playlistId": uploads_playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = api_get("playlistItems", params, api_key)
        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        if progress_cb:
            progress_cb(len(video_ids))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def get_video_details(video_ids: list, api_key: str, progress_cb=None) -> list:
    rows = []
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i : i + chunk_size]
        data = api_get(
            "videos", {"part": "snippet,contentDetails,statistics", "id": ",".join(chunk)}, api_key
        )
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})

            total_seconds = parse_iso8601_duration(content.get("duration", "PT0S"))
            published_raw = snippet.get("publishedAt", "")
            try:
                published_dt = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            except ValueError:
                published_dt = None

            rows.append(
                {
                    "Title": snippet.get("title", ""),
                    "Video ID": item.get("id", ""),
                    "URL": f"https://www.youtube.com/watch?v={item.get('id', '')}",
                    "Published Date": published_dt.strftime("%Y-%m-%d %H:%M:%S") if published_dt else published_raw,
                    "_published_dt": published_dt,
                    "Duration (mm:ss)": format_duration(total_seconds),
                    "Duration (seconds)": total_seconds,
                    "Type": "Short" if total_seconds <= SHORT_THRESHOLD_SECONDS else "Long",
                    "Views": int(stats.get("viewCount", 0)) if "viewCount" in stats else None,
                    "Likes": int(stats.get("likeCount", 0)) if "likeCount" in stats else None,
                    "Comments": int(stats.get("commentCount", 0)) if "commentCount" in stats else None,
                }
            )
        if progress_cb:
            progress_cb(min(i + chunk_size, len(video_ids)), len(video_ids))
    return rows


def fetch_channel_data(channel_input: str, api_key: str, status) -> dict:
    channel_id = resolve_channel_id(channel_input, api_key)
    status.write(f"Channel ID: `{channel_id}`")

    info = get_channel_info(channel_id, api_key)
    status.write(f"Channel: **{info['title']}**")

    status.write("Fetching video list...")
    id_progress = st.empty()

    def id_progress_cb(count):
        id_progress.write(f"Found {count} videos so far...")

    video_ids = get_all_video_ids(info["uploads_playlist_id"], api_key, id_progress_cb)
    status.write(f"Total videos found: **{len(video_ids)}**")

    status.write("Fetching video details (title, duration, stats)...")
    detail_progress_bar = st.progress(0.0)

    def detail_progress_cb(done, total):
        detail_progress_bar.progress(done / total if total else 1.0)

    rows = get_video_details(video_ids, api_key, detail_progress_cb)

    columns = [
        "Title", "Video ID", "URL", "Published Date", "_published_dt",
        "Duration (mm:ss)", "Duration (seconds)", "Type", "Views", "Likes", "Comments",
    ]
    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values("_published_dt", ascending=False, na_position="last").reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=columns)
    df.insert(0, "S.No", range(1, len(df) + 1))

    return {
        "channel_id": channel_id,
        "channel_title": info["title"],
        "subscriber_count": info["subscriber_count"],
        "total_views": info["total_views"],
        "df": df,
    }


# --------------------------------------------------------------------------- #
# Chart builders
# --------------------------------------------------------------------------- #
def build_timeline_chart(df: pd.DataFrame, granularity: str):
    data = df.dropna(subset=["_published_dt"]).copy()
    if data.empty:
        return None

    if granularity == "Month":
        data["period"] = data["_published_dt"].dt.to_period("M").astype(str)
        sort_key = data["_published_dt"].dt.to_period("M")
    elif granularity == "Quarter":
        data["period"] = (
            data["_published_dt"].dt.year.astype(str) + " Q" + data["_published_dt"].dt.quarter.astype(str)
        )
        sort_key = data["_published_dt"].dt.to_period("Q")
    else:  # Year
        data["period"] = data["_published_dt"].dt.year.astype(str)
        sort_key = data["_published_dt"].dt.year

    data["_sort_key"] = sort_key
    counts = (
        data.groupby(["period", "_sort_key"]).size().reset_index(name="Videos").sort_values("_sort_key")
    )

    fig = px.bar(counts, x="period", y="Videos", labels={"period": granularity})
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
    return fig


def build_duration_bucket_chart(df: pd.DataFrame):
    data = df.copy()
    data["Bucket"] = pd.cut(
        data["Duration (seconds)"], bins=DURATION_BUCKET_EDGES, labels=DURATION_BUCKET_LABELS, right=False
    )
    counts = data["Bucket"].value_counts().reindex(DURATION_BUCKET_LABELS).reset_index()
    counts.columns = ["Bucket", "Videos"]

    fig = px.bar(counts, x="Bucket", y="Videos")
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
    return fig


# --------------------------------------------------------------------------- #
# Streamlit UI
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="YTubeStats", page_icon="📺", layout="wide")

if "result" not in st.session_state:
    st.session_state.result = None
if "input_key_version" not in st.session_state:
    st.session_state.input_key_version = 0

header_col, reset_col = st.columns([5, 1])
with header_col:
    st.title("📺 YTubeStats")
with reset_col:
    st.write("")
    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.result = None
        st.session_state.input_key_version += 1
        st.rerun()

api_key = st.secrets.get("YOUTUBE_API_KEY", "") if hasattr(st, "secrets") else ""

if not api_key:
    st.error(
        "No YouTube API key configured. Add `YOUTUBE_API_KEY` under this app's "
        "Settings → Secrets in Streamlit Cloud (or in a local `.streamlit/secrets.toml` "
        "file when running locally), then reload the app."
    )
    st.stop()

top_col1, top_col2 = st.columns([5, 1])
with top_col1:
    channel_input = st.text_input(
        "Channel ID / @handle / channel URL",
        placeholder="e.g. @MrBeast or https://www.youtube.com/@MrBeast or UCX6OQ3DkcsbYNE6H8uQQuVA",
        label_visibility="collapsed",
        key=f"channel_input_{st.session_state.input_key_version}",
    )
with top_col2:
    go_clicked = st.button("Go →", type="primary", use_container_width=True, disabled=not channel_input)

if go_clicked:
    try:
        with st.status("Fetching channel data...", expanded=True) as status:
            st.session_state.result = fetch_channel_data(channel_input, api_key, status)
            status.update(label="Done!", state="complete", expanded=False)
    except Exception as exc:
        st.error(f"Something went wrong: {exc}")
        st.session_state.result = None

result = st.session_state.result

if result:
    df = result["df"]
    n_videos = len(df)

    st.subheader(result["channel_title"])

    if n_videos == 0:
        st.info("No public videos found for this channel.")
    else:
        dated = df.dropna(subset=["_published_dt"])
        if not dated.empty:
            span_days = max((dated["_published_dt"].max() - dated["_published_dt"].min()).days, 1)
            avg_per_day = n_videos / span_days
        else:
            avg_per_day = 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Videos", f"{n_videos:,}")
        k2.metric("Avg Uploads / Day", f"{avg_per_day:.2f}")
        k3.metric(
            "Subscribers", f"{result['subscriber_count']:,}" if result["subscriber_count"] is not None else "Hidden"
        )
        k4.metric("Total Channel Views", f"{result['total_views']:,}" if result["total_views"] is not None else "N/A")

        st.divider()

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("**Upload timeline**")
            granularity = st.radio(
                "Granularity", ["Month", "Quarter", "Year"], horizontal=True, label_visibility="collapsed"
            )
            timeline_fig = build_timeline_chart(df, granularity)
            if timeline_fig:
                st.plotly_chart(timeline_fig, use_container_width=True)
            else:
                st.info("No publish-date data available to chart.")

        with chart_col2:
            st.markdown("**Video duration distribution**")
            st.plotly_chart(build_duration_bucket_chart(df), use_container_width=True)

        st.divider()

        st.markdown("**Video data**")
        display_df = df.drop(columns=["_published_dt", "URL"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        csv_df = df.drop(columns=["_published_dt"])
        csv_bytes = csv_df.to_csv(index=False).encode("utf-8")
        safe_name = re.sub(r"[^\w\-]+", "_", result["channel_title"]).strip("_")
        file_name = f"{safe_name}_YTubeStats_{datetime.now().strftime('%Y-%m-%d')}.csv"
        st.download_button("⬇️ Download CSV", data=csv_bytes, file_name=file_name, mime="text/csv")

        st.caption(
            "Note: 'Short' vs 'Long' is inferred from duration (≤3 min = Short) since YouTube's "
            "public API doesn't expose an explicit Shorts flag — this is an approximation."
        )
else:
    st.info("Paste a channel link, ID, or @handle above and click **Go →** to get started.")
