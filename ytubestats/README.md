# 📺 YTubeStats

A Streamlit app that takes a YouTube channel (ID, `@handle`, or URL) and gives
you a small analytics dashboard plus a full CSV export of every uploaded
video.

**Interface:** one input field + a **Go** button up top, a **Reset** button
in the top-right corner that clears everything for the next channel.

**CSV export** (newest first), one row per video:

- Serial number, Title, **Video URL** (a working link straight to the video —
  included in the CSV only, not shown in the on-screen table, to keep the
  dashboard view compact)
- Duration (mm:ss, or h:mm:ss for longer videos)
- Type — `Short` or `Long` (heuristic: ≤3 min = Short)
- Published date, Views, Likes, Comment count
- Auto-named file, e.g. `MrBeast_YTubeStats_2026-07-16.csv`, via a download
  button — nothing is stored server-side or persisted; it exists only for
  the current session, exactly as requested

**Dashboard, built with Plotly:**

- KPI cards: Total videos, Avg uploads/day, Current subscribers, Total
  channel views
- Upload timeline bar chart with a Month / Quarter / Year toggle
- Video duration bucket chart (<1 min, 1–3, 3–5, 5–10, 10–20, 20–40, 40–60,
  >60 min)

Built on the official **YouTube Data API v3** — no scraping, no fragile
HTML parsing.

**Not included (by design, for now):** historical subscriber growth. YouTube's
public API only returns the *current* subscriber count — there's no
retroactive time series for an arbitrary channel. Real historical growth is
only obtainable for a channel you own, via OAuth + the YouTube Analytics API,
which is a separate, bigger feature. Happy to add it later if you want it for
your own channel specifically.

## 1. Get a free API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or pick an existing one).
3. Go to **APIs & Services → Library**, search for **YouTube Data API v3**,
   and click **Enable**.
4. Go to **APIs & Services → Credentials → Create Credentials → API key**.
5. Copy the key. (Optional but recommended: click "Restrict key" and limit
   it to the YouTube Data API v3.)

The free tier gives you 10,000 quota units/day — enough to pull a channel
with several thousand videos in one run.

## 2. Run locally

```bash
git clone <your-repo-url>
cd ytubestats
pip install -r requirements.txt
streamlit run app.py
```

Paste your API key into the sidebar field when the app opens (it's only
kept in memory for that session — never written to disk or the repo).

## 3. Deploy on Streamlit Community Cloud

1. Push this repo to GitHub (public is fine — **your API key is never in
   the code**).
2. Go to [share.streamlit.io](https://share.streamlit.io) and deploy the
   repo, pointing at `app.py`.
3. In the app's **Settings → Secrets**, add:
   ```toml
   YOUTUBE_API_KEY = "your-api-key-here"
   ```
   The app will pick it up automatically and pre-fill the sidebar field
   (users can still override it with their own key if you leave the field
   editable).

⚠️ Never commit a real `secrets.toml` — it's already in `.gitignore`. Use
`.streamlit/secrets.toml.example` as a template.

## Notes & limitations

- **Shorts detection**: the YouTube API doesn't expose an explicit "this is
  a Short" flag. This app uses a duration-based approximation (≤ 3 minutes,
  YouTube's current Shorts cap as of Oct 2024). It won't be 100% accurate
  for edge cases (e.g. a 90-second 16:9 video is counted as "Short" here
  even though it may not appear in the Shorts feed).
- **Quota**: fetching N videos costs roughly `1 + ceil(N/50) + ceil(N/50)`
  units. A 5,000-video channel costs ~200 units — trivial against the daily
  10,000 limit. Very large channels (50k+ videos) could approach the limit
  in a single run.
- **Private/unlisted videos**: only public videos on the uploads playlist
  are returned, since this uses a public API key (no OAuth).

## Possible future addition

- Historical subscriber growth for your own channel (needs OAuth + YouTube
  Analytics API) — intentionally left out for now, see above.
