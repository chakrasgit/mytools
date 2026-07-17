import streamlit as st
import re
import io
import os
import tempfile

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YTranscricom",
    page_icon="🎬",
    layout="centered",
)

# ── Session state init ────────────────────────────────────────────────────────
for key in ["transcript_text", "comments", "total_comments", "video_id"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "input_key_version" not in st.session_state:
    st.session_state.input_key_version = 0

# ── Load API key (secrets only) ───────────────────────────────────────────────
def load_api_key():
    try:
        return st.secrets["YOUTUBE_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None

YOUTUBE_API_KEY = load_api_key()

# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_video_id(url):
    m = re.search(r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None


def clean_vtt(vtt_text):
    lines = vtt_text.splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"^\d{2}:\d{2}", line) or re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            text_lines.append(line)
    deduped = []
    for line in text_lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def get_transcript(video_id):
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "skip_download": True,
                "writeautomaticsub": True,
                "writesubtitles": True,
                "subtitleslangs": ["en", "en-US", "en-GB"],
                "subtitlesformat": "vtt",
                "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            vtt_file = None
            for fname in os.listdir(tmpdir):
                if fname.endswith(".vtt"):
                    vtt_file = os.path.join(tmpdir, fname)
                    break
            if not vtt_file:
                return None, "No captions/subtitles found for this video."
            with open(vtt_file, "r", encoding="utf-8") as f:
                vtt_text = f.read()
            transcript = clean_vtt(vtt_text)
            if not transcript.strip():
                return None, "Captions file was empty after processing."
            return transcript, None
    except Exception as e:
        return None, str(e)


def get_total_comment_count(video_id, api_key):
    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=api_key)
        resp = youtube.videos().list(part="statistics", id=video_id).execute()
        items = resp.get("items", [])
        if not items:
            return None
        count = items[0]["statistics"].get("commentCount")
        return int(count) if count else None
    except Exception:
        return None


def get_comments(video_id, api_key, max_comments=500, progress_bar=None):
    try:
        from googleapiclient.discovery import build
        youtube = build("youtube", "v3", developerKey=api_key)
        all_comments = []
        next_page_token = None

        while len(all_comments) < max_comments:
            resp = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=min(100, max_comments - len(all_comments)),
                pageToken=next_page_token,
                textFormat="plainText",
            ).execute()

            for item in resp.get("items", []):
                if len(all_comments) >= max_comments:
                    break
                top = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"].strip()
                all_comments.append(top)

                reply_count = item["snippet"].get("totalReplyCount", 0)
                if reply_count == 0 or len(all_comments) >= max_comments:
                    continue

                embedded_replies = item.get("replies", {}).get("comments", [])
                if len(embedded_replies) >= reply_count:
                    for reply in embedded_replies:
                        if len(all_comments) >= max_comments:
                            break
                        all_comments.append(f"  ↳ {reply['snippet']['textDisplay'].strip()}")
                else:
                    thread_id = item["id"]
                    reply_page_token = None
                    while len(all_comments) < max_comments:
                        reply_resp = youtube.comments().list(
                            part="snippet",
                            parentId=thread_id,
                            maxResults=min(100, max_comments - len(all_comments)),
                            pageToken=reply_page_token,
                            textFormat="plainText",
                        ).execute()
                        for r in reply_resp.get("items", []):
                            if len(all_comments) >= max_comments:
                                break
                            all_comments.append(f"  ↳ {r['snippet']['textDisplay'].strip()}")
                        reply_page_token = reply_resp.get("nextPageToken")
                        if not reply_page_token:
                            break

                if progress_bar:
                    progress_bar.progress(min(len(all_comments) / max_comments, 1.0))

            next_page_token = resp.get("nextPageToken")
            if not next_page_token:
                break

        return all_comments, None
    except Exception as e:
        return None, str(e)


# ── UI ────────────────────────────────────────────────────────────────────────
header_col, reset_col = st.columns([5, 1])
with header_col:
    st.title("🎬 YTranscricom")
    st.caption("Extract transcripts & comments — no usernames, no timestamps.")
with reset_col:
    st.write("")
    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.transcript_text = None
        st.session_state.comments = None
        st.session_state.total_comments = None
        st.session_state.video_id = None
        st.session_state.input_key_version += 1
        st.rerun()

st.divider()

if not YOUTUBE_API_KEY:
    st.error(
        "No YouTube API key configured. Add `YOUTUBE_API_KEY` under this app's "
        "Settings → Secrets in Streamlit Cloud (or in a local `.streamlit/secrets.toml` "
        "file when running locally), then reload the app. Comment extraction won't "
        "work without it — transcripts will still work."
    )

video_url = st.text_input(
    "YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=...",
    key=f"video_url_{st.session_state.input_key_version}",
)

# Show total comment count as soon as URL is entered
if video_url.strip():
    video_id_preview = extract_video_id(video_url.strip())
    if video_id_preview and YOUTUBE_API_KEY:
        total = get_total_comment_count(video_id_preview, YOUTUBE_API_KEY)
        if total is not None:
            st.info(f"💬 This video has **{total:,} total comments** (including replies) on YouTube.")

with st.expander("⚙️ Options"):
    fetch_transcript = st.checkbox("Extract Transcript", value=True)
    fetch_comments = st.checkbox("Extract Comments", value=True)
    max_comments = st.slider("Max comments to fetch", 50, 1000, 200, step=50)

st.divider()
custom_name = st.text_input(
    "📁 File name prefix (optional)",
    placeholder="e.g. fireship_rust_video",
    help="Files will be saved as {name}_transcript.txt and {name}_comments.txt. Leave blank to use the video ID.",
    key=f"custom_name_{st.session_state.input_key_version}",
)

run = st.button("🚀 Extract", use_container_width=True, type="primary")

# ── Extraction — only runs when Extract is clicked ────────────────────────────
if run:
    if not video_url.strip():
        st.error("Please enter a YouTube URL.")
        st.stop()

    video_id = extract_video_id(video_url.strip())
    if not video_id:
        st.error("Could not parse a video ID from that URL.")
        st.stop()

    st.session_state.transcript_text = None
    st.session_state.comments = None
    st.session_state.total_comments = None
    st.session_state.video_id = video_id

    st.info(f"Video ID: `{video_id}`")

    if fetch_transcript:
        with st.spinner("Fetching transcript... (this may take 20–30 seconds)"):
            transcript_text, err = get_transcript(video_id)
        if transcript_text:
            st.session_state.transcript_text = transcript_text
        else:
            st.warning(f"Could not fetch transcript: {err or 'Unknown error'}")

    if fetch_comments:
        if not YOUTUBE_API_KEY:
            st.warning("An API key is required to fetch comments.")
        else:
            total = get_total_comment_count(video_id, YOUTUBE_API_KEY)
            st.session_state.total_comments = total
            if total:
                st.caption(f"ℹ️ Fetching {max_comments:,} of {total:,} total comments (including replies).")
            progress_bar = st.progress(0, text="Fetching comments and replies...")
            comments, err = get_comments(video_id, YOUTUBE_API_KEY, max_comments, progress_bar)
            progress_bar.empty()
            if comments is not None:
                st.session_state.comments = comments
            else:
                st.error(f"Failed to fetch comments: {err}")

# ── Results — always shown if session_state has data ─────────────────────────
file_prefix = custom_name.strip() if custom_name.strip() else st.session_state.video_id

if st.session_state.transcript_text:
    st.divider()
    transcript_text = st.session_state.transcript_text
    word_count = len(transcript_text.split())
    char_count = len(transcript_text)
    col1, col2 = st.columns(2)
    col1.metric("📝 Word Count", f"{word_count:,}")
    col2.metric("🔤 Characters", f"{char_count:,}")
    st.success("✅ Transcript ready")
    with st.expander("📄 Preview Transcript"):
        st.write(transcript_text[:3000] + ("…" if len(transcript_text) > 3000 else ""))
    st.download_button(
        "⬇️ Download Transcript (.txt)",
        data=io.BytesIO(transcript_text.encode()),
        file_name=f"{file_prefix}_transcript.txt",
        mime="text/plain",
        use_container_width=True,
    )

if st.session_state.comments:
    st.divider()
    comments = st.session_state.comments
    total = st.session_state.total_comments
    top_level = sum(1 for c in comments if not c.startswith("  ↳"))
    replies = sum(1 for c in comments if c.startswith("  ↳"))

    col1, col2, col3 = st.columns(3)
    col1.metric("💬 Total Fetched", f"{len(comments):,}")
    col2.metric("🗨️ Top-level", f"{top_level:,}")
    col3.metric("↳ Replies", f"{replies:,}")
    if total:
        st.caption(f"📊 Video has {total:,} total comments on YouTube.")

    st.success("✅ Comments ready")
    with st.expander("💬 Preview (first 20)"):
        for i, c in enumerate(comments[:20], 1):
            st.markdown(f"**{i}.** {c}")
        if len(comments) > 20:
            st.caption(f"…and {len(comments) - 20} more in the file.")

    comments_text = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(comments, 1))
    st.download_button(
        "⬇️ Download Comments (.txt)",
        data=io.BytesIO(comments_text.encode()),
        file_name=f"{file_prefix}_comments.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.divider()
st.caption("Built with yt-dlp & YouTube Data API v3. No data stored.")
