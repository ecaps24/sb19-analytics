"""
Social Media Agent - Unified automation for posting to X (Twitter).

Consolidates all social media posting functionality:
- Monthly listener updates (from monthly_listeners.csv)
- Daily stream updates / top gainers (from selenium_results.csv)
- Milestone celebrations (e.g. 10M, 50M, 100M streams)
- Significant jump/spike detection
- Weekly summaries
- Album stream updates with screenshots (Simula at Wakas)
- Custom posts with optional image attachments

Uses browser automation (Selenium + Edge) to post, avoiding API costs.

Usage:
    python social_media_agent.py listeners             # Post monthly listener update
    python social_media_agent.py daily                 # Post daily stream top gainers
    python social_media_agent.py top10                 # Post top 10 SB19 tracks by daily streams
    python social_media_agent.py solo-top10            # Post top 10 solo member tracks by daily streams
    python social_media_agent.py milestones            # Check and post milestones
    python social_media_agent.py spikes                # Post significant jump alerts
    python social_media_agent.py weekly                # Post weekly summary
    python social_media_agent.py solo-top              # Post top tracks for each solo member
    python social_media_agent.py opm-top-tracks        # Post OPM top 20 tracks by daily streams
    python social_media_agent.py opm-top-streams       # Post OPM top artists by total streams
    python social_media_agent.py album                 # Post album update with screenshot
    python social_media_agent.py youtube-channel       # Post YouTube channel stats (subs + views)
    python social_media_agent.py custom "Your message" # Post a custom message
    python social_media_agent.py preview               # Preview all pending posts
    python social_media_agent.py status                # Show data status and readiness

Flags:
    --dry-run           Preview post without sending
    --test              Open browser and type but don't click Post
    --keep-open         Keep browser open after posting
    --skip-validation   Skip data freshness checks
    --image PATH        Attach an image to the post
    --force             Force post even on wrong day (e.g. weekly not on Sunday)
    --headless          Run browser in headless mode
    --no-profile        Don't use Edge user profile
"""

import argparse
import base64
import csv
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from PIL import Image

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from x_browser_poster import XBrowserPoster


# ---------------------------------------------------------------------------
# Constants - imported from centralized config
# ---------------------------------------------------------------------------

from config import (
    SCRIPT_DIR,
    SELENIUM_RESULTS_CSV as STREAMS_FILE,
    STREAMS_LEGACY_CSV as STREAMS_LEGACY_FILE,
    MONTHLY_LISTENERS_CSV as LISTENERS_FILE,
    POSTED_LOG,
    ALBUM_IMAGE_DIR, ALBUM_IMAGE_PATH, TOP10_IMAGE_PATH,
    SOLO_TOP10_IMAGE_PATH, LOCAL_INDEX,
    MEMBER_PHOTOS_DIR, LISTENERS_IMAGE_PATH,
    OPM_TOP_IMAGE_PATH, PPOP_TOP_IMAGE_PATH,
    OPM_TRACKS_RESULTS_CSV as OPM_TRACKS_FILE,
    OPM_TOP_TRACKS_IMAGE_PATH, OPM_TOP_STREAMS_IMAGE_PATH,
    MEMBER_PHOTO_FILES, MEMBER_BAR_COLORS,
    MILESTONES, MILESTONE_LABELS,
    SPIKE_THRESHOLD_PERCENT, SPIKE_THRESHOLD_ABSOLUTE,
    YOUTUBE_API_KEY, YOUTUBE_VIDEO_ID, YOUTUBE_VIDEO_URL,
    YOUTUBE_CHANNEL_HANDLE, YOUTUBE_CHANNEL_URL, YOUTUBE_MUSIC_URL,
    YT_CHANNEL_HISTORY_FILE, YT_CHANNEL_STATS_CSV, YT_CHANNEL_IMAGE_PATH,
    YOUTUBE_MV_IDS,
    YT_HISTORY_FILE, YT_STREAMS_CSV, YT_EMOJI_IMAGE_PATH,
    SPOTIFY_VISA_URL, SPOTIFY_VISA_IMAGE_PATH,
    MAIN_ARTISTS, SOLO_ARTISTS, X_HANDLES,
    SOLO_TOP_N, X_CHAR_LIMIT, SITE_TAG, ALBUM_TRACKS,
    WAS_ALBUM_NAME, WAS_ALBUM_IMAGE_PATH,
    LOCAL_SERVER_PORT,
)
from shared import format_number, format_with_commas
from screenshot_generator import (
    capture_top10_screenshot,
    capture_solo_top10_screenshot,
    capture_opm_top_screenshot,
    capture_opm_top_tracks_screenshot,
    capture_opm_top_streams_screenshot,
    capture_ppop_top_screenshot,
    capture_youtube_visa_screenshot,
    capture_youtube_channel_screenshot,
    capture_spotify_visa_screenshot,
    capture_album_screenshot,
    capture_was_album_screenshot,
    capture_listeners_screenshot,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def format_change(change, use_commas=True):
    """Format a change value with +/- sign."""
    if use_commas:
        if change > 0:
            return f"+{change:,}"
        elif change < 0:
            return f"{change:,}"
        return "0"
    else:
        if change > 0:
            return f"+{format_number(change)}"
        return format_number(change)


def format_change_delta(delta):
    """Format change-over-change with indicator."""
    if delta is None:
        return ""
    if delta > 0:
        return f" (+{delta:,})"
    elif delta < 0:
        return f" ({delta:,})"
    return ""


def enforce_char_limit(message):
    """Print a warning if message exceeds 280-character X limit. Returns message unchanged."""
    char_count = len(message)
    if char_count > X_CHAR_LIMIT:
        print(f"[WARN] Post is {char_count} chars — EXCEEDS {X_CHAR_LIMIT} limit by {char_count - X_CHAR_LIMIT}!")
    else:
        print(f"[INFO] Post length: {char_count}/{X_CHAR_LIMIT} chars — OK")
    return message


def short_date(date_str):
    """Convert YYYYMMDD or YYYY-MM-DD to short format like 'Feb 18'."""
    cleaned = date_str.replace("-", "")[:8]
    try:
        return datetime.strptime(cleaned, "%Y%m%d").strftime("%b %d")
    except ValueError:
        return date_str


def _resolve_solo_artist(name):
    """Return the canonical SOLO_ARTISTS name for a case-insensitive match, or None."""
    lower = name.strip().lower()
    for artist in SOLO_ARTISTS:
        if artist.lower() == lower:
            return artist
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_listeners_data():
    """Load monthly listener records from CSV."""
    data = []
    if not os.path.exists(LISTENERS_FILE):
        print(f"[WARN] Listeners file not found: {LISTENERS_FILE}")
        return data

    with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                listeners = row.get("monthly_listeners", "")
                if not listeners or listeners == "N/A":
                    continue
                listeners = int(listeners)
                timestamp = row.get("timestamp", "")
                data.append({
                    "artist": row["artist_name"],
                    "listeners": listeners,
                    "timestamp": timestamp,
                    "date": str(timestamp)[:8],
                })
            except (ValueError, KeyError):
                continue
    return data


def load_streams_data(file_path=None):
    """Load stream count records from CSV (semicolon-delimited)."""
    path = file_path or STREAMS_FILE
    data = []
    if not os.path.exists(path):
        print(f"[WARN] Streams file not found: {path}")
        return data

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                streams = int(row["streams"]) if row["streams"] else 0
                timestamp = row["timestamp"]
                # Handle both "20260204_060000" and "2026-02-04 06:00:00" formats
                date = timestamp[:10].replace("-", "") if "-" in timestamp else timestamp[:8]
                data.append({
                    "timestamp": timestamp,
                    "song_title": row["song_title"],
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                    "streams": streams,
                    "date": date,
                })
            except (ValueError, KeyError):
                continue
    return data


def dedup_same_stream_tracks(track_map):
    """Remove tracks with identical stream counts per artist (auto-play interludes).

    Some artists have short interlude/chapter tracks that share stream counts
    with the main track due to Spotify auto-play. This inflates daily gains
    when aggregated per artist. Keeps only one track per unique stream value
    per artist.
    """
    seen = {}  # (artist_lower, streams) -> first key encountered
    to_remove = []
    for key, s in track_map.items():
        sig = (s["artist"].lower(), s["streams"])
        if sig in seen:
            to_remove.append(key)
        else:
            seen[sig] = key
    for key in to_remove:
        del track_map[key]


def load_posted_log():
    """Load log of already-posted milestones."""
    if not os.path.exists(POSTED_LOG):
        return {"milestones": {}, "last_daily": None, "last_weekly": None}
    with open(POSTED_LOG, "r") as f:
        return json.load(f)


def save_posted_log(log):
    """Persist the posted-milestones log."""
    with open(POSTED_LOG, "w") as f:
        json.dump(log, f, indent=2)


# ---------------------------------------------------------------------------
# Social Media Agent
# ---------------------------------------------------------------------------

class SocialMediaAgent:
    """Unified agent for generating and posting social media content to X."""

    def __init__(self, headless=False, use_profile=True, keep_open=False):
        self.headless = headless
        self.use_profile = use_profile
        self.keep_open = keep_open
        self._poster = None

    # -- browser lifecycle --------------------------------------------------

    def _get_poster(self):
        """Lazily create and return the XBrowserPoster instance."""
        if self._poster is None:
            self._poster = XBrowserPoster(
                headless=self.headless,
                use_profile=self.use_profile,
                keep_open=self.keep_open,
            )
        return self._poster

    def _start_browser(self):
        """Start browser and verify login."""
        poster = self._get_poster()
        poster.start()
        if not poster.check_login_status():
            print("[ERR] Not logged into X!")
            print("[INFO] Steps to fix:")
            print("  1. Close this script")
            print("  2. Open Microsoft Edge")
            print("  3. Go to https://x.com and log in")
            print("  4. Close Edge completely")
            print("  5. Run this script again")
            return False
        return True

    def _stop_browser(self):
        if self._poster:
            if self.keep_open:
                print("[INFO] Browser kept open. Close it manually when done.")
            else:
                self._poster.stop()
                self._poster = None

    # -- post dispatch ------------------------------------------------------

    def post(self, message, dry_run=False, test_mode=False, image_path=None):
        """Send a post to X with the given message.

        Returns True on success.
        """
        poster = self._get_poster()

        if dry_run:
            return poster.create_post(message, dry_run=True)

        if not self._start_browser():
            return False

        return poster.create_post(
            message, dry_run=False, test_mode=test_mode, image_path=image_path,
        )

    # -- data validation ----------------------------------------------------

    def check_listeners_data(self):
        """Check if listener data exists for today."""
        data = load_listeners_data()
        if not data:
            return False, "No listener data found"

        today = datetime.now().strftime("%Y%m%d")
        today_data = [d for d in data if d["date"] == today]

        if not today_data:
            dates = sorted(set(d["date"] for d in data))
            latest = dates[-1] if dates else "unknown"
            return False, f"No data for today ({today}). Latest: {latest}"

        found = sum(
            1 for entry in today_data
            if any(m.upper() == entry["artist"].upper() for m in MAIN_ARTISTS)
        )
        if found < len(MAIN_ARTISTS):
            return False, f"Incomplete: {found}/{len(MAIN_ARTISTS)} main artists"

        return True, f"Found {len(today_data)} records for today"

    def check_streams_data(self):
        """Check if stream data exists for today."""
        if not os.path.exists(STREAMS_FILE):
            return False, "Streams file not found"

        today = datetime.now().strftime("%Y-%m-%d")
        with open(STREAMS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row.get("timestamp", "")[:10] == today:
                    return True, f"Found data for today ({today})"

        # Find latest date
        latest_date = None
        with open(STREAMS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                date = row.get("timestamp", "")[:10]
                if date and (latest_date is None or date > latest_date):
                    latest_date = date
        return False, f"No data for today ({today}). Latest: {latest_date or 'unknown'}"

    def check_opm_tracks_data(self):
        """Check if OPM track stream data exists for today."""
        if not os.path.exists(OPM_TRACKS_FILE):
            return False, "OPM tracks file not found"

        today = datetime.now().strftime("%Y-%m-%d")
        with open(OPM_TRACKS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row.get("timestamp", "")[:10] == today:
                    return True, f"Found OPM track data for today ({today})"

        # Find latest date
        latest_date = None
        with open(OPM_TRACKS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                date = row.get("timestamp", "")[:10]
                if date and (latest_date is None or date > latest_date):
                    latest_date = date
        return False, f"No OPM track data for today ({today}). Latest: {latest_date or 'unknown'}"

    def check_streams_quality(self):
        """Check that SB19 Emoji track has non-zero streams (canary for scraping)."""
        data = load_streams_data()
        if not data:
            return False, "No stream data found"
        latest_date = max(e["date"] for e in data)
        emoji_entries = [
            e for e in data
            if e["date"] == latest_date
            and e["song_title"].lower() == "emoji"
            and e["artist"].upper() == "SB19"
        ]
        if not emoji_entries:
            return False, f"Emoji track not found on {latest_date}"
        streams = max(e["streams"] for e in emoji_entries)
        if streams == 0:
            return False, f"Emoji track has 0 streams on {latest_date} — scraping may have failed"
        return True, f"Emoji streams OK ({streams:,} on {latest_date})"

    def check_leaderboard_streams_quality(self):
        """Check SB19 and BINI have non-zero streams (canary for leaderboard scraping)."""
        sb19_data = load_streams_data()
        opm_data = load_streams_data(file_path=OPM_TRACKS_FILE)
        if not sb19_data:
            return False, "No SB19 stream data found"
        if not opm_data:
            return False, "No OPM track data found"
        # Check SB19
        sb19_latest = max(e["date"] for e in sb19_data)
        sb19_total = sum(
            e["streams"] for e in sb19_data
            if e["date"] == sb19_latest and e["artist"].upper() == "SB19"
        )
        if sb19_total == 0:
            return False, f"SB19 streams are all zero on {sb19_latest} — scraping may have failed"
        # Check BINI
        bini_latest = max(e["date"] for e in opm_data)
        bini_total = sum(
            e["streams"] for e in opm_data
            if e["date"] == bini_latest and e["artist"].upper() == "BINI"
        )
        if bini_total == 0:
            return False, f"BINI streams are all zero on {bini_latest} — scraping may have failed"
        return True, f"SB19 ({sb19_total:,}) and BINI ({bini_total:,}) streams OK"

    # ======================================================================
    # Content generators — each returns a message string (or None)
    # ======================================================================

    def generate_listeners_post(self):
        """Monthly listener update for SB19 and members.

        Top panel: SB19 group historical listeners (last 14 days).
        Bottom panel: Solo member monthly listeners (current snapshot).

        Returns (message, image_path_or_None).
        """
        data = load_listeners_data()
        if not data:
            print("[WARN] No listener data available!")
            return None, None

        # --- SB19 group: 14-day history ---
        sb19_entries = [e for e in data if e["artist"].upper() == "SB19"]
        sb19_entries.sort(key=lambda x: x["timestamp"], reverse=True)

        # Deduplicate by date, keeping latest entry per day
        sb19_by_date = {}
        for entry in sb19_entries:
            if entry["date"] not in sb19_by_date:
                sb19_by_date[entry["date"]] = entry

        sb19_dates = sorted(sb19_by_date.keys(), reverse=True)[:14]
        sb19_dates.reverse()  # chronological order

        sb19_history = []
        for date in sb19_dates:
            e = sb19_by_date[date]
            sb19_history.append({
                "date": date,
                "listeners": e["listeners"],
            })

        if not sb19_history:
            print("[WARN] No SB19 history data found!")
            return None, None

        sb19_change = 0
        sb19_change_delta = None
        if len(sb19_history) >= 2:
            sb19_change = sb19_history[-1]["listeners"] - sb19_history[-2]["listeners"]
        if len(sb19_history) >= 3:
            sb19_prev_change = sb19_history[-2]["listeners"] - sb19_history[-3]["listeners"]
            sb19_change_delta = sb19_change - sb19_prev_change

        # --- Solo members: latest data ---
        solo_data = []
        for artist in SOLO_ARTISTS:
            artist_entries = [e for e in data if e["artist"].upper() == artist.upper()]
            if not artist_entries:
                continue
            artist_entries.sort(key=lambda x: x["timestamp"], reverse=True)

            # Deduplicate by date
            by_date = {}
            for entry in artist_entries:
                if entry["date"] not in by_date:
                    by_date[entry["date"]] = entry
            dates_desc = sorted(by_date.keys(), reverse=True)

            latest = by_date[dates_desc[0]]
            prev = by_date[dates_desc[1]] if len(dates_desc) >= 2 else None
            prev_prev = by_date[dates_desc[2]] if len(dates_desc) >= 3 else None

            change = (latest["listeners"] - prev["listeners"]) if prev else 0
            prev_change = (prev["listeners"] - prev_prev["listeners"]) if prev and prev_prev else None
            change_delta = change - prev_change if prev_change is not None else None

            solo_data.append({
                "artist": artist,
                "listeners": latest["listeners"],
                "change": change,
                "change_delta": change_delta,
            })

        solo_data.sort(key=lambda x: x["listeners"], reverse=True)

        # Determine "as of" date
        all_timestamps = [e["timestamp"] for e in data if e.get("timestamp")]
        latest_date_str = ""
        if all_timestamps:
            latest_ts = max(all_timestamps)
            try:
                date_obj = datetime.strptime(latest_ts[:8], "%Y%m%d")
                latest_date_str = date_obj.strftime("%b %d, %Y")
            except ValueError:
                pass

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(max(all_timestamps)[:8]) if all_timestamps else ""
        if date_short:
            message = (
                f"SB19 Monthly Listeners on Spotify | {date_short}\n\n"
                f"{SITE_TAG}\n"
                f"#SB19 #OPM"
            )
        else:
            message = (
                f"SB19 Monthly Listeners on Spotify\n\n"
                f"{SITE_TAG}\n"
                f"#SB19 #OPM"
            )
        enforce_char_limit(message)

        # Capture social card screenshot
        image_path = None
        screenshot_ok = capture_listeners_screenshot(
            sb19_history=sb19_history,
            sb19_change=sb19_change,
            sb19_change_delta=sb19_change_delta,
            solo_data=solo_data,
            date_str=latest_date_str,
        )
        if screenshot_ok and os.path.exists(LISTENERS_IMAGE_PATH):
            image_path = LISTENERS_IMAGE_PATH

        return message, image_path

    def generate_daily_post(self):
        """Daily stream update — top 5 gainers."""
        data = load_streams_data()
        if not data:
            return None

        dates = sorted(set(e["date"] for e in data))
        if len(dates) < 2:
            print("[WARN] Not enough data for daily comparison")
            return None

        today, yesterday = dates[-1], dates[-2]
        today_map = {(e["song_title"], e["artist"]): e for e in data if e["date"] == today}
        yest_map = {(e["song_title"], e["artist"]): e for e in data if e["date"] == yesterday}

        gains = []
        for key, entry in today_map.items():
            if key in yest_map:
                change = entry["streams"] - yest_map[key]["streams"]
                if change > 0:
                    gains.append({
                        "song": entry["song_title"],
                        "artist": entry["artist"],
                        "streams": entry["streams"],
                        "change": change,
                    })

        gains.sort(key=lambda x: x["change"], reverse=True)
        if not gains:
            print("[INFO] No stream gains detected")
            return None

        # Parse date for display
        try:
            date_formatted = datetime.strptime(today.replace("-", "")[:8], "%Y%m%d").strftime("%B %d, %Y")
        except ValueError:
            date_formatted = today

        # Compact format for 280-char limit
        date_short = short_date(today)
        top = gains[:5]
        lines = [f"SB19 Top Gainers | {date_short}", ""]
        for i, g in enumerate(top, 1):
            lines.append(f"{i}. {g['song']}: {format_change(g['change'], use_commas=False)}")
        lines.append("")
        lines.append(f"{SITE_TAG} #SB19")
        message = "\n".join(lines)
        # Safety: if over 280, reduce to 3 tracks
        if len(message) > X_CHAR_LIMIT:
            lines = [f"SB19 Top Gainers | {date_short}", ""]
            for i, g in enumerate(gains[:3], 1):
                lines.append(f"{i}. {g['song']}: {format_change(g['change'], use_commas=False)}")
            lines.append("")
            lines.append(f"{SITE_TAG} #SB19")
            message = "\n".join(lines)
        enforce_char_limit(message)
        return message

    def generate_top10_post(self):
        """Top 10 SB19 group tracks by daily added streams with screenshot.

        Returns (message, image_path_or_None).
        """
        data = load_streams_data()
        if not data:
            return None, None

        dates = sorted(set(e["date"] for e in data))
        if len(dates) < 2:
            print("[WARN] Not enough data for daily comparison")
            return None, None

        today, yesterday = dates[-1], dates[-2]

        # Filter to SB19 group tracks only
        today_map = {
            e["song_title"]: e for e in data
            if e["date"] == today and e["artist"].upper() == "SB19"
        }
        yest_map = {
            e["song_title"]: e for e in data
            if e["date"] == yesterday and e["artist"].upper() == "SB19"
        }

        gains = []
        for song, entry in today_map.items():
            if song in yest_map:
                change = entry["streams"] - yest_map[song]["streams"]
                gains.append({
                    "song": song,
                    "streams": entry["streams"],
                    "change": change,
                })

        gains.sort(key=lambda x: x["change"], reverse=True)

        # Build previous day's ranking (by daily change) for rank comparison
        prev_gains = []
        if len(dates) >= 3:
            day_before = dates[-3]
            day_before_map = {
                e["song_title"]: e for e in data
                if e["date"] == day_before and e["artist"].upper() == "SB19"
            }
            for song, entry in yest_map.items():
                if song in day_before_map:
                    prev_change = entry["streams"] - day_before_map[song]["streams"]
                    prev_gains.append({"song": song, "change": prev_change})
            prev_gains.sort(key=lambda x: x["change"], reverse=True)

        prev_rank_map = {g["song"]: i + 1 for i, g in enumerate(prev_gains)}

        # Compute rank streaks: how many consecutive days each track held its current rank
        # Build daily rankings for all available dates
        sb19_data = [e for e in data if e["artist"].upper() == "SB19"]
        all_dates = sorted(set(e["date"] for e in sb19_data))

        daily_rank_maps = {}
        for di in range(1, len(all_dates)):
            curr_d = all_dates[di]
            prev_d = all_dates[di - 1]
            curr_map_d = {e["song_title"]: e["streams"] for e in sb19_data if e["date"] == curr_d}
            prev_map_d = {e["song_title"]: e["streams"] for e in sb19_data if e["date"] == prev_d}
            day_gains = []
            for s in curr_map_d:
                if s in prev_map_d:
                    day_gains.append((s, curr_map_d[s] - prev_map_d[s]))
            day_gains.sort(key=lambda x: x[1], reverse=True)
            daily_rank_maps[curr_d] = {s: r + 1 for r, (s, _) in enumerate(day_gains)}

        # Annotate top 10 with rank change info
        top = gains[:20]
        for i, g in enumerate(top):
            current_rank = i + 1
            prev_rank = prev_rank_map.get(g["song"])
            if prev_rank is not None:
                rank_diff = prev_rank - current_rank  # positive = moved up
                g["rank_change"] = rank_diff
                g["prev_rank"] = prev_rank
            else:
                g["rank_change"] = None
                g["prev_rank"] = None

            # Compute streak (consecutive days at this rank, walking backwards)
            streak = 1
            for di in range(len(all_dates) - 2, 0, -1):
                d = all_dates[di]
                rm = daily_rank_maps.get(d, {})
                if rm.get(g["song"]) == current_rank:
                    streak += 1
                else:
                    break
            g["streak"] = streak

        if not top:
            print("[INFO] No SB19 group stream gains detected")
            return None, None

        # Parse date for display
        try:
            date_formatted = datetime.strptime(
                today.replace("-", "")[:8], "%Y%m%d"
            ).strftime("%B %d, %Y")
        except ValueError:
            date_formatted = today

        # Total daily added across ALL SB19 group tracks
        total_added = sum(g["change"] for g in gains)

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(today)
        total_str_text = format_change(total_added, use_commas=False)
        message = (
            f"SB19 Top Tracks by Daily Streams | {date_short}\n\n"
            f"Total added: {total_str_text}\n\n"
            f"{SITE_TAG}\n"
            f"#SB19 #OPM"
        )
        enforce_char_limit(message)

        # Split into top 3 podium + table
        top3_data = []
        for i, g in enumerate(top[:3]):
            top3_data.append({
                "rank": i + 1,
                "song": g["song"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
            })
        table_data = []
        for i, g in enumerate(top[3:], 4):
            table_data.append({
                "rank": i,
                "song": g["song"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
            })

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_top10_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_added=total_added,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(TOP10_IMAGE_PATH):
            image_path = TOP10_IMAGE_PATH

        return message, image_path

    def generate_solo_top10_post(self):
        """Top 10 solo member tracks (combined) by daily added streams with screenshot.

        Returns (message, image_path_or_None).
        """
        data = load_streams_data()
        if not data:
            return None, None

        dates = sorted(set(e["date"] for e in data))
        if len(dates) < 2:
            print("[WARN] Not enough data for daily comparison")
            return None, None

        today, yesterday = dates[-1], dates[-2]

        # Filter to solo artists (case-insensitive) and key by (song, canonical_artist)
        today_map = {}
        yest_map = {}
        for e in data:
            canonical = _resolve_solo_artist(e["artist"])
            if canonical is None:
                continue
            key = (e["song_title"], canonical)
            if e["date"] == today:
                today_map[key] = {**e, "artist": canonical}
            elif e["date"] == yesterday:
                yest_map[key] = {**e, "artist": canonical}

        gains = []
        for key, entry in today_map.items():
            if key in yest_map:
                change = entry["streams"] - yest_map[key]["streams"]
                gains.append({
                    "song": entry["song_title"],
                    "artist": entry["artist"],
                    "streams": entry["streams"],
                    "change": change,
                })

        gains.sort(key=lambda x: x["change"], reverse=True)

        # Build previous day's ranking for rank comparison
        prev_gains = []
        if len(dates) >= 3:
            day_before = dates[-3]
            day_before_map = {}
            for e in data:
                canonical = _resolve_solo_artist(e["artist"])
                if canonical is None:
                    continue
                if e["date"] == day_before:
                    day_before_map[(e["song_title"], canonical)] = {**e, "artist": canonical}
            for key, entry in yest_map.items():
                if key in day_before_map:
                    prev_change = entry["streams"] - day_before_map[key]["streams"]
                    prev_gains.append({"key": key, "change": prev_change})
            prev_gains.sort(key=lambda x: x["change"], reverse=True)

        prev_rank_map = {g["key"]: i + 1 for i, g in enumerate(prev_gains)}

        # Build daily rankings for streak computation
        solo_data = [
            {**e, "artist": _resolve_solo_artist(e["artist"])}
            for e in data if _resolve_solo_artist(e["artist"]) is not None
        ]
        all_dates = sorted(set(e["date"] for e in solo_data))

        daily_rank_maps = {}
        for di in range(1, len(all_dates)):
            curr_d = all_dates[di]
            prev_d = all_dates[di - 1]
            curr_map_d = {
                (e["song_title"], e["artist"]): e["streams"]
                for e in solo_data if e["date"] == curr_d
            }
            prev_map_d = {
                (e["song_title"], e["artist"]): e["streams"]
                for e in solo_data if e["date"] == prev_d
            }
            day_gains = []
            for s in curr_map_d:
                if s in prev_map_d:
                    day_gains.append((s, curr_map_d[s] - prev_map_d[s]))
            day_gains.sort(key=lambda x: x[1], reverse=True)
            daily_rank_maps[curr_d] = {s: r + 1 for r, (s, _) in enumerate(day_gains)}

        # Annotate top 20 with rank change and streak info
        top = gains[:20]
        for i, g in enumerate(top):
            current_rank = i + 1
            key = (g["song"], g["artist"])
            prev_rank = prev_rank_map.get(key)
            if prev_rank is not None:
                g["rank_change"] = prev_rank - current_rank
                g["prev_rank"] = prev_rank
            else:
                g["rank_change"] = None
                g["prev_rank"] = None

            streak = 1
            for di in range(len(all_dates) - 2, 0, -1):
                d = all_dates[di]
                rm = daily_rank_maps.get(d, {})
                if rm.get(key) == current_rank:
                    streak += 1
                else:
                    break
            g["streak"] = streak

        if not top:
            print("[INFO] No solo member stream gains detected")
            return None, None

        # Parse date for display
        try:
            date_formatted = datetime.strptime(
                today.replace("-", "")[:8], "%Y%m%d"
            ).strftime("%B %d, %Y")
        except ValueError:
            date_formatted = today

        # Total daily added across ALL solo tracks
        total_added = sum(g["change"] for g in gains)

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(today)
        total_str_text = format_change(total_added, use_commas=False)
        message = (
            f"SB19 Solo Top Tracks by Daily Streams | {date_short}\n\n"
            f"Total added: {total_str_text}\n\n"
            f"{SITE_TAG}\n"
            f"#SB19 #OPM"
        )
        enforce_char_limit(message)

        # Split into top 3 podium + table
        top3_data = []
        for i, g in enumerate(top[:3]):
            top3_data.append({
                "rank": i + 1,
                "song": g["song"],
                "artist": g["artist"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
            })
        table_data = []
        for i, g in enumerate(top[3:], 4):
            table_data.append({
                "rank": i,
                "song": g["song"],
                "artist": g["artist"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
            })

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_solo_top10_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_added=total_added,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(SOLO_TOP10_IMAGE_PATH):
            image_path = SOLO_TOP10_IMAGE_PATH

        return message, image_path

    def generate_milestone_posts(self):
        """Detect new milestones and return list of (message, milestone_key) tuples."""
        data = load_streams_data()
        if not data:
            return []

        posted_log = load_posted_log()

        # Build latest streams per track
        latest = {}
        for entry in data:
            key = (entry["song_title"], entry["artist"])
            if key not in latest or entry["streams"] > latest[key]["streams"]:
                latest[key] = entry

        posts = []
        for (song, artist), entry in latest.items():
            streams = entry["streams"]
            for milestone in MILESTONES:
                milestone_key = f"{song}_{artist}_{milestone}"
                if streams >= milestone and milestone_key not in posted_log.get("milestones", {}):
                    label = MILESTONE_LABELS.get(milestone, format_number(milestone))
                    msg = (
                        f"MILESTONE! \"{song}\" by {artist} surpassed {label} Spotify streams!\n\n"
                        f"Now at {format_number(streams)}\n\n"
                        f"{SITE_TAG} #SB19"
                    )
                    enforce_char_limit(msg)
                    posts.append((msg, milestone_key))
        return posts

    def generate_spikes_posts(self):
        """Detect significant stream jumps and return list of messages."""
        data = load_streams_data()
        if not data:
            return []

        dates = sorted(set(e["date"] for e in data))
        if len(dates) < 2:
            return []

        today, yesterday = dates[-1], dates[-2]
        today_map = {(e["song_title"], e["artist"]): e for e in data if e["date"] == today}
        yest_map = {(e["song_title"], e["artist"]): e for e in data if e["date"] == yesterday}

        spikes = []
        for key, entry in today_map.items():
            if key in yest_map:
                prev = yest_map[key]["streams"]
                if prev == 0:
                    continue
                change = entry["streams"] - prev
                pct = (change / prev) * 100
                if pct >= SPIKE_THRESHOLD_PERCENT or change >= SPIKE_THRESHOLD_ABSOLUTE:
                    spikes.append({
                        "song": entry["song_title"],
                        "artist": entry["artist"],
                        "streams": entry["streams"],
                        "change": change,
                        "pct": pct,
                    })

        spikes.sort(key=lambda x: x["change"], reverse=True)
        posts = []
        for spike in spikes[:3]:
            msg = (
                f"TRENDING! \"{spike['song']}\" by {spike['artist']} "
                f"+{format_number(spike['change'])} streams ({spike['pct']:.1f}%)\n\n"
                f"Total: {format_number(spike['streams'])}\n\n"
                f"{SITE_TAG} #SB19"
            )
            enforce_char_limit(msg)
            posts.append(msg)
        return posts

    def generate_opm_top_post(self):
        """OPM Leaderboard ranked by daily streams with listeners, followers, total streams.

        Returns (message, image_path_or_None).
        """
        data = load_listeners_data()
        if not data:
            return None, None

        latest_date = max(e["date"] for e in data)
        latest = [e for e in data if e["date"] == latest_date]

        if not latest:
            print("[WARN] No data for latest date")
            return None, None

        # Re-read CSV for genre field and followers
        genre_lookup = {}
        followers_lookup = {}
        if os.path.exists(LISTENERS_FILE):
            with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = row.get("timestamp", "")
                    if ts[:8] == latest_date:
                        name_key = row["artist_name"].lower()
                        genre_lookup[name_key] = row.get("genre", "")
                        fol = row.get("followers", "")
                        if fol and fol != "N/A":
                            try:
                                followers_lookup[name_key] = int(fol)
                            except ValueError:
                                pass

        # Exclude SB19 solo members from ranking
        sb19_solo = {a.lower() for a in SOLO_ARTISTS}
        all_artists = [e for e in latest if e["artist"].lower() not in sb19_solo]

        # Deduplicate by artist name (keep highest listeners if duplicated)
        artist_map = {}
        for e in all_artists:
            key = e["artist"].lower()
            if key not in artist_map or e["listeners"] > artist_map[key]["listeners"]:
                artist_map[key] = e

        if not artist_map:
            print("[INFO] No OPM artist data found")
            return None, None

        # --- Load streams data for Total Streams and Daily Streams ---
        sb19_streams = load_streams_data(STREAMS_FILE)
        opm_streams = load_streams_data(OPM_TRACKS_FILE)
        all_streams = sb19_streams + opm_streams

        stream_dates = sorted(set(s["date"] for s in all_streams))
        s_today = stream_dates[-1] if stream_dates else ""
        s_yesterday = stream_dates[-2] if len(stream_dates) >= 2 else ""
        s_day_before = stream_dates[-3] if len(stream_dates) >= 3 else ""

        # Build per-track maps (dedup by title+artist, keep highest streams)
        today_map, yesterday_map, daybefore_map = {}, {}, {}
        for s in all_streams:
            key = (s["song_title"].lower(), s["artist"].lower())
            if s["date"] == s_today:
                if key not in today_map or s["streams"] > today_map[key]["streams"]:
                    today_map[key] = s
            elif s["date"] == s_yesterday:
                if key not in yesterday_map or s["streams"] > yesterday_map[key]["streams"]:
                    yesterday_map[key] = s
            elif s_day_before and s["date"] == s_day_before:
                if key not in daybefore_map or s["streams"] > daybefore_map[key]["streams"]:
                    daybefore_map[key] = s

        # Remove auto-play interlude tracks (same artist, same stream count)
        dedup_same_stream_tracks(today_map)
        dedup_same_stream_tracks(yesterday_map)
        dedup_same_stream_tracks(daybefore_map)

        # Aggregate per artist: total streams, daily gain, previous daily gain
        artist_total = {}
        artist_daily = {}
        artist_prev_daily = {}

        for key, s in today_map.items():
            akey = s["artist"].lower()
            artist_total[akey] = artist_total.get(akey, 0) + s["streams"]

        if s_today and s_yesterday:
            for key, s in today_map.items():
                y = yesterday_map.get(key)
                if y:
                    akey = s["artist"].lower()
                    artist_daily[akey] = artist_daily.get(akey, 0) + (s["streams"] - y["streams"])

        if s_yesterday and s_day_before:
            for key, s in yesterday_map.items():
                db = daybefore_map.get(key)
                if db:
                    akey = s["artist"].lower()
                    artist_prev_daily[akey] = artist_prev_daily.get(akey, 0) + (s["streams"] - db["streams"])

        # Previous day data for monthly listener changes
        all_dates = sorted(set(e["date"] for e in data))
        prev_date = None
        for d in reversed(all_dates):
            if d < latest_date:
                prev_date = d
                break

        prev_map = {}
        if prev_date:
            prev_entries = [e for e in data if e["date"] == prev_date and e["artist"].lower() not in sb19_solo]
            prev_artist_map = {}
            for e in prev_entries:
                key = e["artist"].lower()
                if key not in prev_artist_map or e["listeners"] > prev_artist_map[key]["listeners"]:
                    prev_artist_map[key] = e
            for key, e in prev_artist_map.items():
                prev_map[key] = e["listeners"]

        # Format date
        try:
            date_formatted = datetime.strptime(latest_date[:8], "%Y%m%d").strftime("%B %d, %Y")
        except ValueError:
            date_formatted = latest_date

        # Build data for ALL artists, sorted by daily streams desc
        unsorted_data = []
        for key, e in artist_map.items():
            prev_val = prev_map.get(key)
            change = (e["listeners"] - prev_val) if prev_val is not None else 0
            daily = artist_daily.get(key, 0)
            prev_daily = artist_prev_daily.get(key, 0)
            daily_change = (daily - prev_daily) if daily and prev_daily else 0
            unsorted_data.append({
                "artist": e["artist"],
                "genre": genre_lookup.get(key, ""),
                "listeners": e["listeners"],
                "change": change,
                "followers": followers_lookup.get(key, 0),
                "total_streams": artist_total.get(key, 0),
                "daily_streams": daily,
                "daily_change": daily_change,
            })

        # Sort by daily streams descending (artists with no data at bottom)
        ranked = sorted(unsorted_data, key=lambda x: x["daily_streams"], reverse=True)
        for i, d in enumerate(ranked, 1):
            d["rank"] = i

        # Find SB19's rank
        sb19_rank = None
        for d in ranked:
            if d["artist"].upper() == "SB19":
                sb19_rank = d["rank"]
                break

        top20 = ranked[:20]
        sb19_in_top20 = any(d["artist"].upper() == "SB19" for d in top20)

        # SB19 extra section if rank > 20
        sb19_card = None
        if sb19_rank and not sb19_in_top20:
            for d in ranked:
                if d["artist"].upper() == "SB19":
                    sb19_card = dict(d)
                    break

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(latest_date)
        sb19_line = ""
        if sb19_rank:
            sb19_line = f"\n\nSB19 ranked #{sb19_rank} out of {len(ranked)} artists"
        message = (
            f"OPM Leaderboard | Spotify | {date_short}"
            f"{sb19_line}\n\n"
            f"{SITE_TAG}\n"
            f"#OPM #SB19"
        )
        enforce_char_limit(message)

        image_path = None
        screenshot_ok = capture_opm_top_screenshot(
            table_data=top20,
            sb19_data=sb19_card,
            total_artists=len(ranked),
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(OPM_TOP_IMAGE_PATH):
            image_path = OPM_TOP_IMAGE_PATH

        return message, image_path
    def generate_opm_top_tracks_post(self):
        """Top 20 OPM tracks by daily stream gains, including SB19's best track.

        Returns (message, image_path_or_None).
        """
        # Load OPM track data
        opm_data = load_streams_data(file_path=OPM_TRACKS_FILE)
        if not opm_data:
            print("[WARN] No OPM track data available!")
            return None, None

        opm_dates = sorted(set(e["date"] for e in opm_data))
        if len(opm_dates) < 2:
            print("[WARN] Need at least 2 days of OPM track data for daily comparison")
            return None, None

        opm_today, opm_yesterday = opm_dates[-1], opm_dates[-2]

        # Build OPM today/yesterday maps keyed by (song_title, artist)
        opm_today_map = {}
        for e in opm_data:
            if e["date"] == opm_today:
                key = (e["song_title"], e["artist"])
                if key not in opm_today_map or e["streams"] > opm_today_map[key]["streams"]:
                    opm_today_map[key] = e
        opm_yest_map = {}
        for e in opm_data:
            if e["date"] == opm_yesterday:
                key = (e["song_title"], e["artist"])
                if key not in opm_yest_map or e["streams"] > opm_yest_map[key]["streams"]:
                    opm_yest_map[key] = e

        # Remove auto-play interlude tracks (same artist, same stream count)
        dedup_same_stream_tracks(opm_today_map)
        dedup_same_stream_tracks(opm_yest_map)

        # Compute OPM track gains
        opm_gains = []
        for key, entry in opm_today_map.items():
            if key in opm_yest_map:
                change = entry["streams"] - opm_yest_map[key]["streams"]
                opm_gains.append({
                    "song": entry["song_title"],
                    "artist": entry["artist"],
                    "streams": entry["streams"],
                    "change": change,
                    "key": key,
                    "is_sb19": False,
                })

        # Load SB19 track data and find best daily gainer
        sb19_data = load_streams_data()
        sb19_best = None
        if sb19_data:
            sb19_dates = sorted(set(e["date"] for e in sb19_data))
            if len(sb19_dates) >= 2:
                sb19_today = sb19_dates[-1]
                sb19_yesterday = sb19_dates[-2]
                sb19_today_map = {
                    e["song_title"]: e for e in sb19_data
                    if e["date"] == sb19_today and e["artist"].upper() == "SB19"
                }
                sb19_yest_map = {
                    e["song_title"]: e for e in sb19_data
                    if e["date"] == sb19_yesterday and e["artist"].upper() == "SB19"
                }
                best_change = 0
                for song, entry in sb19_today_map.items():
                    if song in sb19_yest_map:
                        change = entry["streams"] - sb19_yest_map[song]["streams"]
                        if change > best_change:
                            best_change = change
                            sb19_best = {
                                "song": song,
                                "artist": "SB19",
                                "streams": entry["streams"],
                                "change": change,
                                "key": (song, "SB19"),
                                "is_sb19": True,
                            }

        # Combine OPM + SB19 best track
        combined = opm_gains[:]
        if sb19_best:
            combined.append(sb19_best)

        combined.sort(key=lambda x: x["change"], reverse=True)

        # Build previous day's ranking for rank comparison
        prev_gains = []
        if len(opm_dates) >= 3:
            opm_day_before = opm_dates[-3]
            opm_db_map = {}
            for e in opm_data:
                if e["date"] == opm_day_before:
                    key = (e["song_title"], e["artist"])
                    if key not in opm_db_map or e["streams"] > opm_db_map[key]["streams"]:
                        opm_db_map[key] = e
            for key, entry in opm_yest_map.items():
                if key in opm_db_map:
                    prev_gains.append({
                        "key": key,
                        "change": entry["streams"] - opm_db_map[key]["streams"],
                    })
            # Add SB19 best from previous day
            if sb19_data and len(sb19_dates) >= 3:
                sb19_db = sb19_dates[-3]
                sb19_db_map = {
                    e["song_title"]: e for e in sb19_data
                    if e["date"] == sb19_db and e["artist"].upper() == "SB19"
                }
                best_prev_change = 0
                best_prev_key = None
                for song, entry in sb19_yest_map.items():
                    if entry.get("artist", "").upper() == "SB19" and song in sb19_db_map:
                        pc = entry["streams"] - sb19_db_map[song]["streams"]
                        if pc > best_prev_change:
                            best_prev_change = pc
                            best_prev_key = (song, "SB19")
                if best_prev_key:
                    prev_gains.append({"key": best_prev_key, "change": best_prev_change})

            prev_gains.sort(key=lambda x: x["change"], reverse=True)

        prev_rank_map = {g["key"]: i + 1 for i, g in enumerate(prev_gains)}

        # Compute rank streaks using all available dates
        all_opm_dates = sorted(set(e["date"] for e in opm_data))
        daily_rank_maps = {}
        for di in range(1, len(all_opm_dates)):
            curr_d = all_opm_dates[di]
            prev_d = all_opm_dates[di - 1]
            curr_map = {}
            for e in opm_data:
                if e["date"] == curr_d:
                    k = (e["song_title"], e["artist"])
                    if k not in curr_map or e["streams"] > curr_map[k]:
                        curr_map[k] = e["streams"]
            prev_map_d = {}
            for e in opm_data:
                if e["date"] == prev_d:
                    k = (e["song_title"], e["artist"])
                    if k not in prev_map_d or e["streams"] > prev_map_d[k]:
                        prev_map_d[k] = e["streams"]
            day_gains = []
            for k in curr_map:
                if k in prev_map_d:
                    day_gains.append((k, curr_map[k] - prev_map_d[k]))
            day_gains.sort(key=lambda x: x[1], reverse=True)
            daily_rank_maps[curr_d] = {k: r + 1 for r, (k, _) in enumerate(day_gains)}

        # Take top 20 and annotate with rank changes and streaks
        top = combined[:20]
        for i, g in enumerate(top):
            current_rank = i + 1
            prev_rank = prev_rank_map.get(g["key"])
            if prev_rank is not None:
                g["rank_change"] = prev_rank - current_rank
                g["prev_rank"] = prev_rank
            else:
                g["rank_change"] = None
                g["prev_rank"] = None

            # Compute streak (consecutive days at this rank, walking backwards)
            streak = 1
            for di in range(len(all_opm_dates) - 2, 0, -1):
                d = all_opm_dates[di]
                rm = daily_rank_maps.get(d, {})
                if rm.get(g["key"]) == current_rank:
                    streak += 1
                else:
                    break
            g["streak"] = streak

        if not top:
            print("[INFO] No OPM track stream gains detected")
            return None, None

        # Parse date for display
        try:
            date_formatted = datetime.strptime(
                opm_today.replace("-", "")[:8], "%Y%m%d"
            ).strftime("%B %d, %Y")
        except ValueError:
            date_formatted = opm_today

        total_added = sum(g["change"] for g in combined)
        total_tracks = len(opm_today_map) + (1 if sb19_best else 0)

        # Compact caption (image carries the data)
        date_short = short_date(opm_today)
        message = (
            f"OPM Top Tracks by Daily Streams | Spotify | {date_short}\n\n"
            f"{SITE_TAG}\n"
            f"#OPM #SB19"
        )
        enforce_char_limit(message)

        # Split into top 3 podium + table
        top3_data = []
        for i, g in enumerate(top[:3]):
            top3_data.append({
                "rank": i + 1,
                "song": g["song"],
                "artist": g["artist"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
                "is_sb19": g.get("is_sb19", False),
            })
        table_data = []
        for i, g in enumerate(top[3:], 4):
            table_data.append({
                "rank": i,
                "song": g["song"],
                "artist": g["artist"],
                "change": g["change"],
                "streams": g["streams"],
                "rank_change": g.get("rank_change"),
                "streak": g.get("streak", 1),
                "is_sb19": g.get("is_sb19", False),
            })

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_opm_top_tracks_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_added=total_added,
            total_tracks=total_tracks,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(OPM_TOP_TRACKS_IMAGE_PATH):
            image_path = OPM_TOP_TRACKS_IMAGE_PATH

        return message, image_path
    def generate_opm_top_streams_post(self):
        """Top 20 OPM artists by total daily streams (sum of daily gains per artist).

        For each track, computes today - yesterday streams, then sums those daily
        gains per artist. Ranks artists by that total daily streams number.
        Adds SB19 as a single entry from selenium_results.csv.

        Returns (message, image_path_or_None).
        """
        # Load OPM track data
        opm_data = load_streams_data(file_path=OPM_TRACKS_FILE)
        if not opm_data:
            print("[WARN] No OPM track data available!")
            return None, None

        opm_dates = sorted(set(e["date"] for e in opm_data))
        if len(opm_dates) < 2:
            print("[WARN] Need at least 2 days of OPM track data for daily comparison")
            return None, None

        opm_today, opm_yesterday = opm_dates[-1], opm_dates[-2]

        # Build per-track maps, dedup by (song_title, artist) keeping highest streams
        opm_today_map = {}
        for e in opm_data:
            if e["date"] == opm_today:
                key = (e["song_title"], e["artist"])
                if key not in opm_today_map or e["streams"] > opm_today_map[key]["streams"]:
                    opm_today_map[key] = e
        opm_yest_map = {}
        for e in opm_data:
            if e["date"] == opm_yesterday:
                key = (e["song_title"], e["artist"])
                if key not in opm_yest_map or e["streams"] > opm_yest_map[key]["streams"]:
                    opm_yest_map[key] = e

        # Remove auto-play interlude tracks (same artist, same stream count)
        dedup_same_stream_tracks(opm_today_map)
        dedup_same_stream_tracks(opm_yest_map)

        # Compute per-track daily gains, then aggregate by artist
        sb19_solo = {a.lower() for a in SOLO_ARTISTS}
        artist_daily = {}  # artist_lower -> {daily_total, count, display_name}
        for key, entry in opm_today_map.items():
            if key not in opm_yest_map:
                continue
            akey = entry["artist"].lower()
            if akey in sb19_solo:
                continue
            track_gain = entry["streams"] - opm_yest_map[key]["streams"]
            if akey not in artist_daily:
                artist_daily[akey] = {"daily_total": 0, "count": 0, "display_name": entry["artist"]}
            artist_daily[akey]["daily_total"] += track_gain
            artist_daily[akey]["count"] += 1

        # Build previous day's per-artist daily totals (yesterday vs day-before)
        prev_artist_daily = {}
        if len(opm_dates) >= 3:
            opm_day_before = opm_dates[-3]
            opm_db_map = {}
            for e in opm_data:
                if e["date"] == opm_day_before:
                    key = (e["song_title"], e["artist"])
                    if key not in opm_db_map or e["streams"] > opm_db_map[key]["streams"]:
                        opm_db_map[key] = e
            for key, entry in opm_yest_map.items():
                if key not in opm_db_map:
                    continue
                akey = entry["artist"].lower()
                if akey in sb19_solo:
                    continue
                track_gain = entry["streams"] - opm_db_map[key]["streams"]
                prev_artist_daily[akey] = prev_artist_daily.get(akey, 0) + track_gain

        # Load SB19 track data and compute daily totals
        sb19_data_raw = load_streams_data()
        sb19_daily_total = 0
        sb19_prev_daily_total = 0
        sb19_track_count = 0
        if sb19_data_raw:
            sb19_dates = sorted(set(e["date"] for e in sb19_data_raw))
            if len(sb19_dates) >= 2:
                sb19_today_d = sb19_dates[-1]
                sb19_yesterday_d = sb19_dates[-2]
                sb19_today_tracks = {}
                for e in sb19_data_raw:
                    if e["date"] == sb19_today_d and e["artist"].upper() == "SB19":
                        sb19_today_tracks[e["song_title"]] = e["streams"]
                sb19_yest_tracks = {}
                for e in sb19_data_raw:
                    if e["date"] == sb19_yesterday_d and e["artist"].upper() == "SB19":
                        sb19_yest_tracks[e["song_title"]] = e["streams"]
                for song, streams in sb19_today_tracks.items():
                    if song in sb19_yest_tracks:
                        sb19_daily_total += streams - sb19_yest_tracks[song]
                        sb19_track_count += 1
                # Previous day daily total for rank comparison
                if len(sb19_dates) >= 3:
                    sb19_db_d = sb19_dates[-3]
                    sb19_db_tracks = {}
                    for e in sb19_data_raw:
                        if e["date"] == sb19_db_d and e["artist"].upper() == "SB19":
                            sb19_db_tracks[e["song_title"]] = e["streams"]
                    for song, streams in sb19_yest_tracks.items():
                        if song in sb19_db_tracks:
                            sb19_prev_daily_total += streams - sb19_db_tracks[song]

        # Build combined artist list
        combined = []
        for akey, info in artist_daily.items():
            prev_daily = prev_artist_daily.get(akey, 0)
            change = info["daily_total"] - prev_daily
            combined.append({
                "artist": info["display_name"],
                "total_streams": info["daily_total"],
                "change": change,
                "track_count": info["count"],
                "is_sb19": False,
                "key": akey,
            })

        # Add SB19 entry
        if sb19_track_count > 0:
            combined.append({
                "artist": "SB19",
                "total_streams": sb19_daily_total,
                "change": sb19_daily_total - sb19_prev_daily_total if sb19_prev_daily_total else 0,
                "track_count": sb19_track_count,
                "is_sb19": True,
                "key": "sb19",
            })

        combined.sort(key=lambda x: x["total_streams"], reverse=True)

        # Build previous day ranking for rank changes
        prev_ranked_keys = []
        if prev_artist_daily:
            prev_totals = dict(prev_artist_daily)
            if sb19_prev_daily_total > 0:
                prev_totals["sb19"] = sb19_prev_daily_total
            prev_ranked_keys = sorted(prev_totals.keys(),
                                      key=lambda k: prev_totals[k], reverse=True)

        prev_rank_map = {k: i + 1 for i, k in enumerate(prev_ranked_keys)}

        # Take top 20
        top = combined[:20]
        sb19_entry_in_top = any(g["is_sb19"] for g in top)

        for i, g in enumerate(top):
            current_rank = i + 1
            prev_rank = prev_rank_map.get(g["key"])
            if prev_rank is not None:
                g["rank_change"] = prev_rank - current_rank
            else:
                g["rank_change"] = None

        # Find SB19 if not in top 20
        sb19_extra = None
        if not sb19_entry_in_top:
            for i, g in enumerate(combined):
                if g["is_sb19"]:
                    prev_rank = prev_rank_map.get("sb19")
                    g["rank_change"] = (prev_rank - (i + 1)) if prev_rank is not None else None
                    sb19_extra = {**g, "rank": i + 1}
                    break

        if not top:
            print("[INFO] No OPM artist stream data found")
            return None, None

        # Parse date for display
        try:
            date_formatted = datetime.strptime(
                opm_today.replace("-", "")[:8], "%Y%m%d"
            ).strftime("%B %d, %Y")
        except ValueError:
            date_formatted = opm_today

        grand_total = sum(g["total_streams"] for g in combined)
        total_artists = len(combined)

        # Genre lookup from monthly_listeners.csv
        genre_lookup = {}
        if os.path.exists(LISTENERS_FILE):
            with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    genre_lookup.setdefault(row["artist_name"].lower(), row.get("genre", ""))
        genre_lookup.setdefault("sb19", "P-Pop")

        # Compact caption
        date_short = short_date(opm_today)
        message = (
            f"OPM Top Artists by Daily Streams | Spotify | {date_short}\n\n"
            f"{SITE_TAG}\n"
            f"#OPM #SB19 #Spotify"
        )
        enforce_char_limit(message)

        # Split into top 3 podium + table
        top3_data = []
        for i, g in enumerate(top[:3]):
            top3_data.append({
                "rank": i + 1,
                "artist": g["artist"],
                "total_streams": g["total_streams"],
                "change": g["change"],
                "track_count": g["track_count"],
                "rank_change": g.get("rank_change"),
                "genre": genre_lookup.get(g["key"], ""),
                "is_sb19": g.get("is_sb19", False),
            })
        table_data = []
        for i, g in enumerate(top[3:], 4):
            table_data.append({
                "rank": i,
                "artist": g["artist"],
                "total_streams": g["total_streams"],
                "change": g["change"],
                "track_count": g["track_count"],
                "rank_change": g.get("rank_change"),
                "genre": genre_lookup.get(g["key"], ""),
                "is_sb19": g.get("is_sb19", False),
            })

        # SB19 extra section (only if rank > 20)
        sb19_card = None
        if sb19_extra:
            sb19_card = {
                "rank": sb19_extra["rank"],
                "artist": "SB19",
                "total_streams": sb19_extra["total_streams"],
                "change": sb19_extra["change"],
                "track_count": sb19_extra["track_count"],
                "rank_change": sb19_extra.get("rank_change"),
                "genre": "P-Pop",
                "is_sb19": True,
            }

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_opm_top_streams_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            sb19_data=sb19_card,
            grand_total=grand_total,
            total_artists=total_artists,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(OPM_TOP_STREAMS_IMAGE_PATH):
            image_path = OPM_TOP_STREAMS_IMAGE_PATH

        return message, image_path
    def generate_ppop_top_post(self):
        """P-Pop Leaderboard with streams, daily streams, monthly listeners.

        Returns (message, image_path_or_None).
        """
        data = load_listeners_data()
        if not data:
            return None, None

        latest_date = max(e["date"] for e in data)
        latest = [e for e in data if e["date"] == latest_date]

        if not latest:
            print("[WARN] No data for latest date")
            return None, None

        # Re-read CSV for genre field and followers
        genre_lookup = {}
        followers_lookup = {}
        if os.path.exists(LISTENERS_FILE):
            with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = row.get("timestamp", "")
                    if ts[:8] == latest_date:
                        name_key = row["artist_name"].lower()
                        genre_lookup[name_key] = row.get("genre", "")
                        fol = row.get("followers", "")
                        if fol and fol != "N/A":
                            try:
                                followers_lookup[name_key] = int(fol)
                            except ValueError:
                                pass

        # Separate P-Pop groups and SB19 Solo
        ppop_artists = {}
        solo_artists = {}
        for e in latest:
            key = e["artist"].lower()
            genre = genre_lookup.get(key, "")
            if genre == "P-Pop":
                if key not in ppop_artists or e["listeners"] > ppop_artists[key]["listeners"]:
                    ppop_artists[key] = e
            elif genre == "SB19 Solo":
                if key not in solo_artists or e["listeners"] > solo_artists[key]["listeners"]:
                    solo_artists[key] = e

        ppop_ranked = sorted(ppop_artists.values(), key=lambda x: x["listeners"], reverse=True)
        solo_ranked = sorted(solo_artists.values(), key=lambda x: x["listeners"], reverse=True)

        if not ppop_ranked:
            print("[INFO] No P-Pop artist data found")
            return None, None

        # --- Load streams data for Total Streams and Daily Streams ---
        sb19_streams = load_streams_data(STREAMS_FILE)
        opm_streams = load_streams_data(OPM_TRACKS_FILE)
        all_streams = sb19_streams + opm_streams

        stream_dates = sorted(set(s["date"] for s in all_streams))
        s_today = stream_dates[-1] if stream_dates else ""
        s_yesterday = stream_dates[-2] if len(stream_dates) >= 2 else ""
        s_day_before = stream_dates[-3] if len(stream_dates) >= 3 else ""

        # Build per-track maps (dedup by title+artist, keep highest streams)
        today_map, yesterday_map, daybefore_map = {}, {}, {}
        for s in all_streams:
            key = (s["song_title"].lower(), s["artist"].lower())
            if s["date"] == s_today:
                if key not in today_map or s["streams"] > today_map[key]["streams"]:
                    today_map[key] = s
            elif s["date"] == s_yesterday:
                if key not in yesterday_map or s["streams"] > yesterday_map[key]["streams"]:
                    yesterday_map[key] = s
            elif s_day_before and s["date"] == s_day_before:
                if key not in daybefore_map or s["streams"] > daybefore_map[key]["streams"]:
                    daybefore_map[key] = s

        # Remove auto-play interlude tracks (same artist, same stream count)
        dedup_same_stream_tracks(today_map)
        dedup_same_stream_tracks(yesterday_map)
        dedup_same_stream_tracks(daybefore_map)

        # Aggregate per artist: total streams, daily gain, previous daily gain
        artist_total = {}
        artist_daily = {}
        artist_prev_daily = {}

        for key, s in today_map.items():
            akey = s["artist"].lower()
            artist_total[akey] = artist_total.get(akey, 0) + s["streams"]

        if s_today and s_yesterday:
            for key, s in today_map.items():
                y = yesterday_map.get(key)
                if y:
                    akey = s["artist"].lower()
                    artist_daily[akey] = artist_daily.get(akey, 0) + (s["streams"] - y["streams"])

        if s_yesterday and s_day_before:
            for key, s in yesterday_map.items():
                db = daybefore_map.get(key)
                if db:
                    akey = s["artist"].lower()
                    artist_prev_daily[akey] = artist_prev_daily.get(akey, 0) + (s["streams"] - db["streams"])

        # Previous day data for changes and rank comparison
        all_dates = sorted(set(e["date"] for e in data))
        prev_date = None
        for d in reversed(all_dates):
            if d < latest_date:
                prev_date = d
                break

        prev_ppop_map = {}
        prev_ppop_rank_map = {}
        if prev_date:
            prev_genre_lookup = {}
            if os.path.exists(LISTENERS_FILE):
                with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ts = row.get("timestamp", "")
                        if ts[:8] == prev_date:
                            prev_genre_lookup[row["artist_name"].lower()] = row.get("genre", "")

            prev_entries = [e for e in data if e["date"] == prev_date]
            prev_ppop = {}
            for e in prev_entries:
                key = e["artist"].lower()
                genre = prev_genre_lookup.get(key, "")
                if genre == "P-Pop":
                    if key not in prev_ppop or e["listeners"] > prev_ppop[key]["listeners"]:
                        prev_ppop[key] = e

            for key, e in prev_ppop.items():
                prev_ppop_map[key] = e["listeners"]
            prev_ppop_ranked = sorted(prev_ppop.values(), key=lambda x: x["listeners"], reverse=True)
            for i, e in enumerate(prev_ppop_ranked, 1):
                prev_ppop_rank_map[e["artist"].lower()] = i

        # Format date
        try:
            date_formatted = datetime.strptime(latest_date[:8], "%Y%m%d").strftime("%B %d, %Y")
        except ValueError:
            date_formatted = latest_date

        def _rank_ind(rank_map, artist_key, current_rank):
            prev_r = rank_map.get(artist_key)
            if prev_r is None:
                return "", None
            diff = prev_r - current_rank
            if diff > 0:
                return f" (+{diff})", diff
            elif diff < 0:
                return f" ({diff})", diff
            return "", 0

        # Count total unique artists (all genres) for "X of Y" display
        total_artists = len(set(e["artist"].lower() for e in latest))

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(latest_date)
        message = (
            f"P-Pop Leaderboard | Spotify | {date_short}\n\n"
            f"Showing {len(ppop_ranked)} of {total_artists} artists\n\n"
            f"{SITE_TAG}\n"
            f"#PPop #SB19"
        )
        enforce_char_limit(message)

        # Build data for ALL groups, sorted by daily streams desc
        unsorted_data = []
        for e in ppop_ranked:
            key = e["artist"].lower()
            prev_val = prev_ppop_map.get(key)
            change = (e["listeners"] - prev_val) if prev_val is not None else 0
            daily = artist_daily.get(key, 0)
            prev_daily = artist_prev_daily.get(key, 0)
            daily_change = (daily - prev_daily) if daily and prev_daily else 0
            unsorted_data.append({
                "artist": e["artist"],
                "genre": "P-Pop",
                "listeners": e["listeners"],
                "change": change,
                "followers": followers_lookup.get(key, 0),
                "total_streams": artist_total.get(key, 0),
                "daily_streams": daily,
                "daily_change": daily_change,
            })

        # Sort by daily streams descending (artists with no data at bottom)
        card_data = sorted(unsorted_data, key=lambda x: x["daily_streams"], reverse=True)
        for i, d in enumerate(card_data, 1):
            d["rank"] = i

        image_path = None
        screenshot_ok = capture_ppop_top_screenshot(
            table_data=card_data,
            ppop_count=len(ppop_ranked),
            total_artists=total_artists,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(PPOP_TOP_IMAGE_PATH):
            image_path = PPOP_TOP_IMAGE_PATH

        return message, image_path
    def generate_weekly_post(self):
        """Weekly summary of listener changes for SB19 members."""
        data = load_listeners_data()
        if not data:
            return None

        dates = sorted(set(e["date"] for e in data))
        if len(dates) < 2:
            print("[WARN] Not enough data for weekly comparison!")
            return None

        latest_date = dates[-1]
        week_ago_idx = max(0, len(dates) - 8)
        week_ago_date = dates[week_ago_idx]

        latest_by = {}
        week_ago_by = {}
        for entry in data:
            if any(m.upper() == entry["artist"].upper() for m in MAIN_ARTISTS):
                if entry["date"] == latest_date:
                    latest_by[entry["artist"]] = entry
                elif entry["date"] == week_ago_date:
                    week_ago_by[entry["artist"]] = entry

        changes = []
        for artist, latest in latest_by.items():
            if artist in week_ago_by:
                prev = week_ago_by[artist]
                change = latest["listeners"] - prev["listeners"]
                pct = (change / prev["listeners"] * 100) if prev["listeners"] > 0 else 0
                changes.append({
                    "artist": artist,
                    "listeners": latest["listeners"],
                    "change": change,
                    "pct": pct,
                })

        if not changes:
            print("[WARN] No weekly changes to report!")
            return None

        changes.sort(key=lambda x: x["listeners"], reverse=True)

        # Compact format for 280-char limit
        lines = ["SB19 Weekly Recap", ""]
        for c in changes:
            sign = "+" if c["change"] >= 0 else ""
            lines.append(f"{c['artist']}: {format_number(c['listeners'])} ({sign}{c['pct']:.1f}%)")
        lines.append("")
        lines.append(f"{SITE_TAG} #SB19")
        message = "\n".join(lines)
        enforce_char_limit(message)
        return message

    def generate_solo_top_posts(self, top_n=None):
        """Generate one post per solo artist showing their top tracks with rank tenure.

        Each post lists the artist's top N tracks by streams, with how many
        consecutive days each track has held that exact rank position.

        Returns a list of (artist_name, message) tuples.
        """
        top_n = top_n or SOLO_TOP_N
        data = load_streams_data()
        if not data:
            print("[WARN] No stream data available!")
            return []

        dates = sorted(set(e["date"] for e in data))
        if not dates:
            return []

        latest_date = dates[-1]

        # Build per-date, per-artist rankings across all dates
        # {date: {artist: [(song, streams), ...] sorted desc}}
        daily_rankings = defaultdict(lambda: defaultdict(list))
        for entry in data:
            if entry["artist"] in SOLO_ARTISTS:
                daily_rankings[entry["date"]][entry["artist"]].append(
                    (entry["song_title"], entry["streams"])
                )

        # Sort each day's tracks descending by streams to assign ranks
        for date in daily_rankings:
            for artist in daily_rankings[date]:
                daily_rankings[date][artist].sort(key=lambda x: x[1], reverse=True)

        # For the latest date, compute rank tenure for each solo artist
        posts = []
        # Get previous date for daily change calculation
        prev_date = dates[-2] if len(dates) >= 2 else None
        prev_maps = {}
        if prev_date:
            for entry in data:
                if entry["date"] == prev_date and entry["artist"] in SOLO_ARTISTS:
                    prev_maps[(entry["song_title"], entry["artist"])] = entry["streams"]

        # Parse latest date for display
        try:
            date_display = datetime.strptime(
                latest_date.replace("-", "")[:8], "%Y%m%d"
            ).strftime("%b %d, %Y")
        except ValueError:
            date_display = latest_date

        for artist in SOLO_ARTISTS:
            latest_tracks = daily_rankings[latest_date].get(artist, [])
            if not latest_tracks:
                continue

            # Compute rank tenure: how many consecutive days (going backwards)
            # each track has held its current rank position
            rank_tenure = {}  # song -> consecutive days at current rank
            for current_rank, (song, _) in enumerate(latest_tracks):
                streak = 1  # today counts as 1

                # Walk backwards through previous dates
                for prev_idx in range(len(dates) - 2, -1, -1):
                    d = dates[prev_idx]
                    prev_tracks = daily_rankings[d].get(artist, [])
                    if current_rank < len(prev_tracks) and prev_tracks[current_rank][0] == song:
                        streak += 1
                    else:
                        break

                rank_tenure[song] = streak

            # Build compact post for this artist (280-char limit)
            handle = X_HANDLES.get(artist, "")
            date_short = short_date(latest_date)
            lines = [
                f"{artist} {handle} Top Tracks | {date_short}",
                "",
            ]

            for rank, (song, streams) in enumerate(latest_tracks[:top_n]):
                streams_str = format_number(streams)
                # Daily change
                prev_streams = prev_maps.get((song, artist))
                if prev_streams is not None:
                    change = streams - prev_streams
                    change_str = f" ({format_change(change, use_commas=False)})"
                else:
                    change_str = ""
                lines.append(
                    f"{rank + 1}. {song}: {streams_str}{change_str}"
                )

            lines.append("")
            lines.append(f"{SITE_TAG} #SB19")
            message = "\n".join(lines)
            # Safety: if over 280, reduce to 2 tracks
            if len(message) > X_CHAR_LIMIT:
                lines = [f"{artist} {handle} Top Tracks | {date_short}", ""]
                for rank, (song, streams) in enumerate(latest_tracks[:2]):
                    streams_str = format_number(streams)
                    prev_streams = prev_maps.get((song, artist))
                    if prev_streams is not None:
                        change = streams - prev_streams
                        change_str = f" ({format_change(change, use_commas=False)})"
                    else:
                        change_str = ""
                    lines.append(f"{rank + 1}. {song}: {streams_str}{change_str}")
                lines.append("")
                lines.append(f"{SITE_TAG} #SB19")
                message = "\n".join(lines)
            enforce_char_limit(message)
            posts.append((artist, message))

        return posts

    def generate_album_post(self):
        """Album stream update for Simula at Wakas Tour Kickoff.

        Returns (message, image_path_or_None).
        """
        if not os.path.exists(STREAMS_FILE):
            print(f"[ERR] Streams file not found: {STREAMS_FILE}")
            return None, None

        # Load all data
        rows = []
        with open(STREAMS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    streams = int(row["streams"]) if row["streams"] else 0
                    ts = row["timestamp"]
                    date = ts[:10] if ts else ""
                    rows.append({
                        "timestamp": ts,
                        "song_title": row["song_title"],
                        "streams": streams,
                        "date": date,
                    })
                except (ValueError, KeyError):
                    continue

        if not rows:
            return None, None

        dates = sorted(set(r["date"] for r in rows))
        if len(dates) < 2:
            print("[WARN] Not enough data for album comparison")
            return None, None

        latest_date, prev_date = dates[-1], dates[-2]

        def is_album_track(title):
            return any(t.lower() in title.lower() for t in ALBUM_TRACKS)

        latest_map = {r["song_title"]: r for r in rows if r["date"] == latest_date and is_album_track(r["song_title"])}
        prev_map = {r["song_title"]: r for r in rows if r["date"] == prev_date and is_album_track(r["song_title"])}

        total_streams = sum(r["streams"] for r in latest_map.values())
        total_change = sum(
            latest_map[t]["streams"] - prev_map[t]["streams"]
            for t in latest_map if t in prev_map
        )

        try:
            date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.strptime(latest_date.replace("-", "")[:8], "%Y%m%d")
        date_str = date_obj.strftime("%b %d, %Y")

        total_str = format_with_commas(total_streams)
        change_str = format_change(total_change)

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(date_str)
        message = (
            f"SB19 Simula at Wakas Concert Album: {total_str} total streams ({change_str}) | {date_short}\n\n"
            f"{SITE_TAG}\n"
            f"#SB19 #SimulaAtWakas"
        )
        enforce_char_limit(message)

        # Build per-track data sorted by streams descending
        track_list = []
        for title, r in sorted(latest_map.items(), key=lambda x: x[1]["streams"], reverse=True):
            prev = prev_map.get(title)
            change = r["streams"] - prev["streams"] if prev else 0
            # Clean display name: remove "(Simula at Wakas Tour Kickoff)"
            display = r["song_title"].replace(" (Simula at Wakas Tour Kickoff)", "")
            track_list.append({"name": display, "streams": r["streams"], "change": change})

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_album_screenshot(
            track_list=track_list,
            total_streams=total_streams,
            total_change=total_change,
            date_str=date_str,
        )
        if screenshot_ok and os.path.exists(ALBUM_IMAGE_PATH):
            image_path = ALBUM_IMAGE_PATH

        return message, image_path

    def generate_was_album_post(self):
        """Wakas At Simula studio album leaderboard ranked by daily streams.

        Returns (message, image_path_or_None).
        """
        from config import TRACKS_CSV
        if not os.path.exists(STREAMS_FILE):
            print(f"[ERR] Streams file not found: {STREAMS_FILE}")
            return None, None
        if not os.path.exists(TRACKS_CSV):
            print(f"[ERR] Tracks file not found: {TRACKS_CSV}")
            return None, None

        # Build WAS album track set from tracks.csv (url -> {title, feat})
        was_urls = {}
        with open(TRACKS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                album = (row.get("Album/EP/Single") or "").strip()
                if album == WAS_ALBUM_NAME:
                    url = (row.get("Spotify Link") or "").strip()
                    title = (row.get("Song Title") or "").strip()
                    feat = (row.get("Collaborating Artist(s)") or "").strip()
                    if url:
                        was_urls[url] = {"title": title, "feat": feat}

        if not was_urls:
            print(f"[WARN] No WAS tracks found in tracks.csv")
            return None, None

        # Read selenium_results and filter to WAS URLs
        album_rows = []
        with open(STREAMS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    url = (row.get("url") or "").strip()
                    if url not in was_urls:
                        continue
                    streams = int(row["streams"]) if row.get("streams") else 0
                    ts = row.get("timestamp", "")
                    date = ts[:10] if ts else ""
                    meta = was_urls[url]
                    album_rows.append({
                        "song_title": meta["title"],
                        "feat": meta["feat"],
                        "streams": streams,
                        "date": date,
                        "url": url,
                    })
                except (ValueError, KeyError):
                    continue

        if not album_rows:
            print(f"[WARN] No stream data found for WAS album URLs")
            return None, None

        dates = sorted(set(r["date"] for r in album_rows))
        latest_date = dates[-1]
        prev_date = dates[-2] if len(dates) >= 2 else None
        prev_prev_date = dates[-3] if len(dates) >= 3 else None

        latest_map = {r["url"]: r for r in album_rows if r["date"] == latest_date}
        prev_map = {r["url"]: r for r in album_rows if r["date"] == prev_date} if prev_date else {}
        prev_prev_map = {r["url"]: r for r in album_rows if r["date"] == prev_prev_date} if prev_prev_date else {}

        total_streams = sum(r["streams"] for r in latest_map.values())

        try:
            date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
        except ValueError:
            date_obj = datetime.strptime(latest_date.replace("-", "")[:8], "%Y%m%d")
        date_str = date_obj.strftime("%b %d, %Y")
        date_short = short_date(date_str)

        # Build per-track data with daily change (new tracks use total as daily)
        track_list = []
        for url, r in latest_map.items():
            prev = prev_map.get(url)
            prev_prev = prev_prev_map.get(url)
            change = r["streams"] - prev["streams"] if prev else r["streams"]
            prev_change = prev["streams"] - prev_prev["streams"] if prev and prev_prev else None
            change_delta = change - prev_change if prev_change is not None else None
            display = r["song_title"].replace(" (Wakas At Simula)", "")
            feat = r.get("feat", "")
            track_list.append({
                "name": display,
                "feat": feat,
                "streams": r["streams"],
                "change": change,
                "prev_change": prev_change,
                "change_delta": change_delta,
            })

        # Sort by daily streams descending
        track_list.sort(key=lambda t: t["change"], reverse=True)

        total_daily = sum(t["change"] for t in track_list)
        total_prev_daily = sum(t["prev_change"] for t in track_list if t["prev_change"] is not None)
        has_prev = any(t["prev_change"] is not None for t in track_list)
        total_delta = total_daily - total_prev_daily if has_prev else None
        daily_str = format_change(total_daily)
        total_delta_str = format_change_delta(total_delta)

        # Build tweet — top 3 highlighted, rest listed below
        top3 = track_list[:3]
        rest = track_list[3:]

        medals = [">>", ">>", ">>"]
        lines = [
            f"WAS Album Leaderboard | Daily Streams | {date_short}",
            "",
        ]
        for i, t in enumerate(top3):
            c = format_change(t["change"])
            d = format_change_delta(t["change_delta"])
            feat_tag = f" ft. {t['feat']}" if t["feat"] else ""
            lines.append(f"{medals[i]} {t['name']}{feat_tag} \u2014 {c}{d}")

        lines.append("")
        for i, t in enumerate(rest, 4):
            c = format_change(t["change"])
            d = format_change_delta(t["change_delta"])
            feat_tag = f" ft. {t['feat']}" if t["feat"] else ""
            lines.append(f"{i:>2}. {t['name']}{feat_tag} \u2014 {c}{d}")

        lines.append("")
        lines.append(f"Total Daily: {daily_str}{total_delta_str}")
        lines.append("")
        lines.append(SITE_TAG)
        lines.append("#SB19 #WakasAtSimula")

        message = "\n".join(lines)
        enforce_char_limit(message)

        # Prepare top3/table data for screenshot
        top3_data = []
        for i, t in enumerate(top3):
            top3_data.append({
                "rank": i + 1,
                "song": t["name"],
                "feat": t.get("feat", ""),
                "change": t["change"],
                "change_delta": t["change_delta"],
                "streams": t["streams"],
            })
        table_data = []
        for i, t in enumerate(rest, 4):
            table_data.append({
                "rank": i,
                "song": t["name"],
                "feat": t.get("feat", ""),
                "change": t["change"],
                "change_delta": t["change_delta"],
                "streams": t["streams"],
            })

        # Capture screenshot
        image_path = None
        screenshot_ok = capture_was_album_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_daily=total_daily,
            total_delta=total_delta,
            date_str=date_str,
        )
        if screenshot_ok and os.path.exists(WAS_ALBUM_IMAGE_PATH):
            image_path = WAS_ALBUM_IMAGE_PATH

        return message, image_path

    def _read_yt_csv_last_row(self):
        """Read the last row from yt_visa_streams.csv. Returns dict or None."""
        if not os.path.exists(YT_STREAMS_CSV):
            return None
        last = None
        with open(YT_STREAMS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last = row
        if last:
            return {
                "views": int(last.get("views", 0)),
                "likes": int(last.get("likes", 0)),
                "comments": int(last.get("comments", 0)),
                "timestamp": last.get("timestamp", ""),
            }
        return None

    def _append_yt_csv(self, timestamp, views, likes, comments):
        """Append a row to yt_visa_streams.csv, creating it if needed."""
        write_header = not os.path.exists(YT_STREAMS_CSV)
        with open(YT_STREAMS_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["timestamp", "views", "likes", "comments"])
            writer.writerow([timestamp, views, likes, comments])

    def generate_youtube_visa_post(self):
        """Fetch VISA MV YouTube stats and generate a post with screenshot.

        Returns (message, image_path) or (None, None) on failure.
        """
        import urllib.request

        url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics&id={YOUTUBE_VIDEO_ID}&key={YOUTUBE_API_KEY}"
        )

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[ERR] YouTube API call failed: {e}")
            return None, None

        items = data.get("items", [])
        if not items:
            print("[ERR] No video data returned from YouTube API")
            return None, None

        stats = items[0]["statistics"]
        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        now = datetime.now()
        now_str = now.strftime("%b %d, %Y %I:%M %p")
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        # Read previous run from CSV
        prev = self._read_yt_csv_last_row()
        view_change = views - prev["views"] if prev else 0
        like_change = likes - prev["likes"] if prev else 0
        comment_change = comments - prev["comments"] if prev else 0

        # Append current stats to CSV
        self._append_yt_csv(timestamp, views, likes, comments)
        print(f"[INFO] Logged to {YT_STREAMS_CSV}: {views} views, {likes} likes, {comments} comments")

        # Also update daily JSON history for dashboard
        today = now.strftime("%Y-%m-%d")
        history = {}
        if os.path.exists(YT_HISTORY_FILE):
            try:
                with open(YT_HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except Exception:
                history = {}
        history[today] = {"views": views, "likes": likes, "comments": comments}
        try:
            with open(YT_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

        # Build post text
        def stat_line(label, value, change):
            line = f"{label}: {format_with_commas(value)}"
            if change > 0:
                line += f" (+{format_with_commas(change)})"
            elif change < 0:
                line += f" ({format_with_commas(change)})"
            return line

        import random
        openers = [
            f"SB19 EMOJI MV Update as of {now_str}",
            f"SB19 EMOJI MV Stats | {now_str}",
            f"EMOJI MV by SB19 — {now_str}",
            f"SB19 x Jolin EMOJI MV | {now_str}",
            f"YouTube Update: SB19 EMOJI MV ({now_str})",
            f"EMOJI MV Numbers as of {now_str}",
            f"Latest SB19 EMOJI MV stats — {now_str}",
            f"SB19 EMOJI MV tracker | {now_str}",
        ]

        lines = [
            random.choice(openers),
            "",
            SITE_TAG,
            YOUTUBE_VIDEO_URL,
            "",
            stat_line("Views", views, view_change),
            stat_line("Likes", likes, like_change),
            stat_line("Comments", comments, comment_change),
            "",
            "SB19xJOLIN EMOJI MV OUT NOW",
            "#SB19 #EMOJI #MV #OPM #SB19xJolinEmoji",
        ]

        message = "\n".join(lines)
        enforce_char_limit(message)

        # Capture social card screenshot
        image_path = None
        ok = capture_youtube_visa_screenshot(
            views=views, likes=likes, comments=comments,
            view_change=view_change, like_change=like_change,
            comment_change=comment_change, now_str=now_str,
        )
        if ok and os.path.exists(YT_EMOJI_IMAGE_PATH):
            image_path = YT_EMOJI_IMAGE_PATH

        return message, image_path

    # ------------------------------------------------------------------
    # YouTube Channel Stats (subscribers + views + audience + MVs)
    # ------------------------------------------------------------------

    def _read_yt_channel_csv_last_row(self):
        """Read the last row from yt_channel_stats.csv. Returns dict or None."""
        if not os.path.exists(YT_CHANNEL_STATS_CSV):
            return None
        last = None
        with open(YT_CHANNEL_STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last = row
        if last:
            return {
                "subscribers": int(last.get("subscribers", 0)),
                "views": int(last.get("views", 0)),
                "audience": int(last.get("audience", 0)),
                "timestamp": last.get("timestamp", ""),
            }
        return None

    def _append_yt_channel_csv(self, timestamp, subscribers, views, audience):
        """Append a row to yt_channel_stats.csv, creating it if needed."""
        write_header = not os.path.exists(YT_CHANNEL_STATS_CSV)
        with open(YT_CHANNEL_STATS_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["timestamp", "subscribers", "views", "audience"])
            writer.writerow([timestamp, subscribers, views, audience])

    def _fetch_yt_music_audience(self):
        """Scrape monthly audience from YouTube Music artist page via Selenium.

        Returns the audience text (e.g. '4.7M') and numeric value, or (None, 0).
        """
        import re
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService

        print("[INFO] Fetching YouTube Music monthly audience...")
        options = EdgeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        driver = None
        try:
            driver = webdriver.Edge(service=EdgeService(), options=options)
            driver.get(YOUTUBE_MUSIC_URL)
            import time
            time.sleep(6)
            src = driver.page_source

            match = re.search(
                r'monthlyListenerCount.*?text.*?x22([0-9][\d.]*[KMB]?\s+monthly\s+audience)',
                src, re.IGNORECASE,
            )
            if match:
                text = match.group(1).strip()
                num_match = re.match(r'([\d.]+)([KMB]?)', text)
                if num_match:
                    num = float(num_match.group(1))
                    suffix = num_match.group(2).upper()
                    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
                    audience = int(num * multiplier)
                    display = f"{num_match.group(1)}{num_match.group(2)}"
                    print(f"[INFO] YouTube Music monthly audience: {display} ({audience:,})")
                    return display, audience

            print("[WARN] Could not extract monthly audience from YouTube Music")
            return None, 0
        except Exception as e:
            print(f"[WARN] YouTube Music scrape failed: {e}")
            return None, 0
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _fetch_mv_views(self):
        """Fetch view counts for all configured MVs in a single API call.

        Returns list of (name, views) sorted by views descending.
        """
        import urllib.request

        ids_str = ",".join(YOUTUBE_MV_IDS.values())
        url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?part=statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
        )
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[WARN] MV views fetch failed: {e}")
            return []

        id_to_name = {v: k for k, v in YOUTUBE_MV_IDS.items()}
        results = []
        for item in data.get("items", []):
            vid = item["id"]
            name = id_to_name.get(vid, vid)
            views = int(item["statistics"].get("viewCount", 0))
            results.append((name, views))

        results.sort(key=lambda x: x[1], reverse=True)
        for name, views in results:
            print(f"[INFO] MV {name}: {views:,} views")
        return results

    def generate_youtube_channel_post(self):
        """Fetch SB19 YouTube channel stats, MV views, and YT Music audience.

        Returns (message, image_path) or (None, None) on failure.
        """
        import urllib.request

        # 1. Channel stats (subscribers + total views)
        url = (
            f"https://www.googleapis.com/youtube/v3/channels"
            f"?part=statistics&forHandle={YOUTUBE_CHANNEL_HANDLE}&key={YOUTUBE_API_KEY}"
        )
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[ERR] YouTube Channels API call failed: {e}")
            return None, None

        items = data.get("items", [])
        if not items:
            print("[ERR] No channel data returned from YouTube API")
            return None, None

        stats = items[0]["statistics"]
        subscribers = int(stats.get("subscriberCount", 0))
        views = int(stats.get("viewCount", 0))

        # 2. YouTube Music monthly audience
        audience_display, audience = self._fetch_yt_music_audience()

        # 3. MV view counts
        mv_views = self._fetch_mv_views()

        now = datetime.now()
        now_str = now.strftime("%b %d, %Y %I:%M %p")
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        # Read previous run from CSV (channel-level deltas)
        prev = self._read_yt_channel_csv_last_row()
        sub_change = subscribers - prev["subscribers"] if prev else 0
        view_change = views - prev["views"] if prev else 0
        aud_change = audience - prev["audience"] if prev and audience else 0

        # Append current stats to CSV
        self._append_yt_channel_csv(timestamp, subscribers, views, audience)
        print(f"[INFO] Logged to {YT_CHANNEL_STATS_CSV}: {subscribers:,} subs, {views:,} views, {audience:,} audience")

        # Load JSON history and read previous MV views before overwriting
        today = now.strftime("%Y-%m-%d")
        history = {}
        if os.path.exists(YT_CHANNEL_HISTORY_FILE):
            try:
                with open(YT_CHANNEL_HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except Exception:
                history = {}

        prev_mvs = {}
        prev_day_key = None
        if today in history and "mvs" in history[today]:
            prev_mvs = history[today]["mvs"]
            prev_day_key = today
        elif history:
            # Fall back to most recent day that has MV data
            for day_key in sorted(history.keys(), reverse=True):
                if "mvs" in history[day_key]:
                    prev_mvs = history[day_key]["mvs"]
                    prev_day_key = day_key
                    break

        # Compute MV changes: list of (name, views, change)
        mv_views_with_change = []
        for name, v in mv_views:
            change = v - prev_mvs.get(name, v)
            mv_views_with_change.append((name, v, change))

        # Update daily JSON history
        entry = {"subscribers": subscribers, "views": views, "audience": audience}
        if mv_views:
            entry["mvs"] = {name: v for name, v in mv_views}
        history[today] = entry
        try:
            with open(YT_CHANNEL_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

        # Compute deltas from history (proper daily comparisons)
        all_days = sorted(history.keys())

        view_change_delta = None
        mv_change_deltas = {}
        if len(all_days) >= 3:
            d0, d1, d2 = all_days[-1], all_days[-2], all_days[-3]
            today_view_chg = history[d0].get("views", 0) - history[d1].get("views", 0)
            prev_view_chg = history[d1].get("views", 0) - history[d2].get("views", 0)
            view_change_delta = today_view_chg - prev_view_chg

            today_mvs_h = history[d0].get("mvs", {})
            prev_mvs_h = history[d1].get("mvs", {})
            prev2_mvs_h = history[d2].get("mvs", {})
            for name in today_mvs_h:
                if name in prev_mvs_h and name in prev2_mvs_h:
                    t_chg = today_mvs_h[name] - prev_mvs_h[name]
                    p_chg = prev_mvs_h[name] - prev2_mvs_h[name]
                    mv_change_deltas[name] = t_chg - p_chg

        # Merge deltas into mv_views_with_change
        mv_views_with_change = [
            (name, v, chg, mv_change_deltas.get(name))
            for name, v, chg in mv_views_with_change
        ]

        # Extract 14-day views history for chart
        views_history = []
        for d in all_days[-14:]:
            views_history.append({
                "date": d.replace("-", ""),
                "views": history[d].get("views", 0),
            })

        # Build post text
        def stat_line(label, value, change):
            line = f"{label}: {format_with_commas(value)}"
            if change > 0:
                line += f" (+{format_with_commas(change)})"
            elif change < 0:
                line += f" ({format_with_commas(change)})"
            return line

        def mv_line(name, views, change):
            line = f"  {name} \u2014 {format_with_commas(views)}"
            if change > 0:
                line += f" (+{format_with_commas(change)})"
            elif change < 0:
                line += f" ({format_with_commas(change)})"
            return line

        import random
        openers = [
            f"SB19 YouTube Update | {now_str}",
            f"SB19 Official YouTube Stats \u2014 {now_str}",
            f"YouTube Update: SB19 ({now_str})",
            f"SB19 YouTube Stats | {now_str}",
            f"Latest SB19 YouTube stats \u2014 {now_str}",
            f"SB19 Official YouTube \u2014 {now_str}",
        ]

        lines = [
            random.choice(openers),
            "",
            SITE_TAG,
            YOUTUBE_CHANNEL_URL,
            "",
            stat_line("Subscribers", subscribers, sub_change),
            stat_line("Total Views", views, view_change),
        ]

        if audience:
            lines.append(f"YT Music Audience: {audience_display}")

        if mv_views_with_change:
            lines.append("")
            lines.append("Top MVs:")
            for item in mv_views_with_change:
                name, v, chg = item[0], item[1], item[2]
                chg_delta = item[3] if len(item) > 3 else None
                lines.append(mv_line(name, v, chg) + format_change_delta(chg_delta))

        lines.append("")
        lines.append("#SB19 #YouTube #OPM #PPop")

        message = "\n".join(lines)
        enforce_char_limit(message)

        # Capture social card screenshot
        image_path = None
        ok = capture_youtube_channel_screenshot(
            subscribers=subscribers, views=views,
            sub_change=sub_change, view_change=view_change,
            view_change_delta=view_change_delta,
            audience_display=audience_display, audience_change=aud_change,
            mv_views=mv_views_with_change,
            views_history=views_history, now_str=now_str,
        )
        if ok and os.path.exists(YT_CHANNEL_IMAGE_PATH):
            image_path = YT_CHANNEL_IMAGE_PATH

        return message, image_path

    def _load_visa_daily_data(self):
        """Load VISA entries from selenium_results.csv grouped by date.

        Returns list of dicts sorted by date:
            [{"date": "20260221", "streams": 187650, "timestamp": "..."}, ...]
        """
        data = load_streams_data()
        if not data:
            return []

        visa_entries = [e for e in data if e["song_title"].upper() == "VISA"
                        and e["artist"].upper() == "SB19"]
        if not visa_entries:
            return []

        # Group by date, keep the latest entry per date
        by_date = {}
        for e in visa_entries:
            d = e["date"]
            if d not in by_date or e["timestamp"] > by_date[d]["timestamp"]:
                by_date[d] = e

        return sorted(by_date.values(), key=lambda x: x["date"])

    def generate_spotify_visa_post(self):
        """Generate Spotify VISA daily chart post with screenshot.

        Returns (message, image_path) or (None, None) on failure.
        """
        entries = self._load_visa_daily_data()
        if len(entries) < 2:
            print("[WARN] Not enough VISA data for daily comparison (need at least 2 days)")
            return None, None

        latest = entries[-1]
        prev = entries[-2]
        total_streams = latest["streams"]
        prev_streams = prev["streams"]
        daily_gain = total_streams - prev_streams

        # Build daily deltas for chart
        daily_deltas = []
        daily_labels = []
        for i in range(1, len(entries)):
            delta = entries[i]["streams"] - entries[i - 1]["streams"]
            d = entries[i]["date"]
            try:
                label = datetime.strptime(d[:8], "%Y%m%d").strftime("%m/%d")
            except ValueError:
                label = d
            daily_deltas.append(max(0, delta))
            daily_labels.append(label)

        now = datetime.now()
        now_str = now.strftime("%b %d, %Y %I:%M %p")
        date_short = short_date(latest["date"])

        # Build post text
        total_change = total_streams - prev_streams
        change_str = f"+{format_with_commas(total_change)}" if total_change >= 0 else format_with_commas(total_change)

        lines = [
            f"SB19 VISA Spotify Daily Update as of {now_str}",
            "",
            SITE_TAG,
            SPOTIFY_VISA_URL,
            "",
            f"Total Streams: {format_with_commas(total_streams)} ({change_str})",
            f"Daily Gain: {format_with_commas(daily_gain)}",
            "",
            "#SB19 #VISA #Spotify #OPM",
        ]

        message = "\n".join(lines)
        enforce_char_limit(message)

        # Capture social card screenshot
        image_path = None
        ok = capture_spotify_visa_screenshot(
            total_streams=total_streams,
            daily_gain=daily_gain,
            stream_change=total_change,
            daily_labels=daily_labels,
            daily_deltas=daily_deltas,
            now_str=now_str,
        )
        if ok and os.path.exists(SPOTIFY_VISA_IMAGE_PATH):
            image_path = SPOTIFY_VISA_IMAGE_PATH

        return message, image_path
    # ======================================================================

    def get_status(self):
        """Print data readiness summary."""
        print("=" * 60)
        print("SOCIAL MEDIA AGENT - DATA STATUS")
        print("=" * 60)

        # Listeners
        has_l, msg_l = self.check_listeners_data()
        status_l = "READY" if has_l else "NOT READY"
        print(f"  Listeners data:  [{status_l}] {msg_l}")

        # Streams
        has_s, msg_s = self.check_streams_data()
        status_s = "READY" if has_s else "NOT READY"
        print(f"  Streams data:    [{status_s}] {msg_s}")

        # Stream quality (Emoji canary)
        has_sq, msg_sq = self.check_streams_quality()
        status_sq = "READY" if has_sq else "NOT READY"
        print(f"  Stream quality:  [{status_sq}] {msg_sq}")

        # Leaderboard quality (SB19 + BINI)
        has_lq, msg_lq = self.check_leaderboard_streams_quality()
        status_lq = "READY" if has_lq else "NOT READY"
        print(f"  Leaderboard:     [{status_lq}] {msg_lq}")

        # Posted log
        log = load_posted_log()
        milestone_count = len(log.get("milestones", {}))
        print(f"  Posted log:      {milestone_count} milestones tracked")

        # Day info
        today = datetime.now()
        print(f"  Today:           {today.strftime('%A, %B %d, %Y')}")
        print(f"  Weekly post:     {'Due today (Sunday)' if today.weekday() == 6 else 'Not Sunday'}")
        print("=" * 60)

    def preview_all(self):
        """Preview all available posts without sending."""
        print("=" * 60)
        print("SOCIAL MEDIA AGENT - POST PREVIEW")
        print("=" * 60)

        def _char_status(msg):
            n = len(msg)
            status = "OK" if n <= X_CHAR_LIMIT else "OVER"
            return f"[{n}/{X_CHAR_LIMIT} chars] {status}"

        # 1. Listeners
        print("\n--- MONTHLY LISTENERS ---")
        msg, img = self.generate_listeners_post()
        if msg:
            print(msg)
            print(_char_status(msg))
            if img:
                print(f"[IMAGE] {img}")
        else:
            print("[SKIP] No data")

        # 2. Daily
        print("\n--- DAILY STREAM UPDATE ---")
        msg = self.generate_daily_post()
        if msg:
            print(msg)
            print(_char_status(msg))
        else:
            print("[SKIP] No data")

        # 2b. Top 10
        print("\n--- TOP 10 BY DAILY STREAMS ---")
        msg, img = self.generate_top10_post()
        if msg:
            print(msg)
            print(_char_status(msg))
            if img:
                print(f"[IMAGE] {img}")
        else:
            print("[SKIP] No data")

        # 2c. Solo Top 10
        print("\n--- SOLO TOP 10 BY DAILY STREAMS ---")
        msg, img = self.generate_solo_top10_post()
        if msg:
            print(msg)
            print(_char_status(msg))
            if img:
                print(f"[IMAGE] {img}")
        else:
            print("[SKIP] No data")

        # 3. Milestones
        print("\n--- MILESTONES ---")
        milestone_posts = self.generate_milestone_posts()
        if milestone_posts:
            for m, key in milestone_posts:
                print(m)
                print(f"  {_char_status(m)} | key: {key}")
                print()
        else:
            print("[SKIP] No new milestones")

        # 4. Spikes
        print("\n--- SPIKES ---")
        spike_posts = self.generate_spikes_posts()
        if spike_posts:
            for s in spike_posts:
                print(s)
                print(_char_status(s))
                print()
        else:
            print("[SKIP] No significant spikes")

        # 5. Weekly
        print("\n--- WEEKLY SUMMARY ---")
        msg = self.generate_weekly_post()
        if msg:
            print(msg)
            print(_char_status(msg))
        else:
            print("[SKIP] No data")

        # 6. Solo Top Tracks
        print("\n--- SOLO TOP TRACKS ---")
        solo_posts = self.generate_solo_top_posts()
        if solo_posts:
            for artist, msg in solo_posts:
                print(msg)
                print(_char_status(msg))
                print()
        else:
            print("[SKIP] No data")

        # 7. Album
        print("\n--- ALBUM UPDATE ---")
        album_msg, _ = self.generate_album_post()
        if album_msg:
            print(album_msg)
            print(_char_status(album_msg))
        else:
            print("[SKIP] No data")

        # 8. OPM Top
        print("\n--- OPM TOP 10 MONTHLY LISTENERS ---")
        opm_msg, opm_img = self.generate_opm_top_post()
        if opm_msg:
            print(opm_msg)
            print(_char_status(opm_msg))
            if opm_img:
                print(f"[IMAGE] {opm_img}")
        else:
            print("[SKIP] No data")

        # 9. P-Pop Top
        print("\n--- P-POP TOP 10 MONTHLY LISTENERS ---")
        ppop_msg, ppop_img = self.generate_ppop_top_post()
        if ppop_msg:
            print(ppop_msg)
            print(_char_status(ppop_msg))
            if ppop_img:
                print(f"[IMAGE] {ppop_img}")
        else:
            print("[SKIP] No data")

        print("\n" + "=" * 60)

    # ======================================================================
    # Milestone log management
    # ======================================================================

    def init_milestones(self):
        """Mark all existing milestones as already posted (run once on setup)."""
        data = load_streams_data()
        if not data:
            print("[WARN] No stream data to initialize milestones from")
            return

        log = load_posted_log()
        if "milestones" not in log:
            log["milestones"] = {}

        count = 0
        latest = {}
        for entry in data:
            key = (entry["song_title"], entry["artist"])
            if key not in latest or entry["streams"] > latest[key]["streams"]:
                latest[key] = entry

        for (song, artist), entry in latest.items():
            streams = entry["streams"]
            for milestone in MILESTONES:
                mk = f"{song}_{artist}_{milestone}"
                if streams >= milestone and mk not in log["milestones"]:
                    log["milestones"][mk] = "initialized"
                    count += 1

        save_posted_log(log)
        print(f"[INFO] Marked {count} existing milestones as already achieved.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Social Media Agent - Unified X posting automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python social_media_agent.py listeners                 # Post monthly listener update
  python social_media_agent.py daily                     # Post daily stream top gainers
  python social_media_agent.py top10                     # Post top 10 SB19 tracks by daily streams
  python social_media_agent.py solo-top10                # Post top 10 solo member tracks by daily streams
  python social_media_agent.py milestones                # Check & post new milestones
  python social_media_agent.py spikes                    # Post significant jump alerts
  python social_media_agent.py weekly                    # Post weekly summary
  python social_media_agent.py album                     # Post concert album update with screenshot
  python social_media_agent.py was-album                 # Post Wakas At Simula studio album update
  python social_media_agent.py was-album --dry-run       # Preview WAS album post
  python social_media_agent.py custom "Hello world!"     # Post a custom message
  python social_media_agent.py preview                   # Preview all pending posts
  python social_media_agent.py status                    # Show data readiness
  python social_media_agent.py init-milestones           # Initialize milestone log
  python social_media_agent.py listeners --dry-run       # Preview without posting
  python social_media_agent.py solo-top                  # Post top tracks for each solo member
  python social_media_agent.py solo-top --artist PABLO   # Post only PABLO's top tracks
  python social_media_agent.py youtube-emoji              # Post EMOJI MV YouTube stats
  python social_media_agent.py youtube-emoji --dry-run    # Preview YouTube EMOJI post
  python social_media_agent.py youtube-channel            # Post YouTube channel stats (subs + views)
  python social_media_agent.py youtube-channel --dry-run  # Preview YouTube channel post
  python social_media_agent.py spotify-visa              # Post VISA Spotify daily stats
  python social_media_agent.py spotify-visa --dry-run    # Preview Spotify VISA post
  python social_media_agent.py opm-top-tracks            # Post OPM top 20 tracks by daily streams
  python social_media_agent.py opm-top-tracks --dry-run  # Preview OPM top tracks post
  python social_media_agent.py opm-top-streams           # Post OPM top artists by total streams
  python social_media_agent.py opm-top-streams --dry-run # Preview OPM top streams post
  python social_media_agent.py custom "msg" --image pic.png
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "listeners", "daily", "top10", "solo-top10", "milestones", "spikes", "weekly",
            "album", "was-album", "solo-top", "opm-top", "opm-top-tracks", "opm-top-streams", "ppop-top",
            "youtube-emoji", "youtube-channel", "spotify-visa",
            "custom", "preview", "status", "init-milestones",
        ],
        help="Post type or action to perform",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Custom message text (required for 'custom' command)",
    )

    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--test", action="store_true", help="Type in browser but don't click Post")
    parser.add_argument("--keep-open", action="store_true", help="Keep browser open after posting")
    parser.add_argument("--skip-validation", action="store_true", help="Skip data freshness checks")
    parser.add_argument("--image", type=str, metavar="PATH", help="Image file to attach")
    parser.add_argument("--force", action="store_true", help="Force post (e.g. weekly on non-Sunday)")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--no-profile", action="store_true", help="Don't use Edge user profile")
    parser.add_argument("--artist", type=str, metavar="NAME",
                        help="Solo artist to post for (solo-top command). E.g. PABLO, FELIP")
    parser.add_argument("--top", type=int, default=SOLO_TOP_N, metavar="N",
                        help=f"Number of top tracks per artist (default: {SOLO_TOP_N})")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    agent = SocialMediaAgent(
        headless=args.headless,
        use_profile=not args.no_profile,
        keep_open=args.keep_open,
    )

    # Non-posting commands
    if args.command == "status":
        agent.get_status()
        return

    if args.command == "preview":
        agent.preview_all()
        return

    if args.command == "init-milestones":
        agent.init_milestones()
        return

    # Posting commands
    try:
        if args.command == "custom":
            if not args.message:
                print("[ERR] Custom command requires a message argument.")
                print("  Usage: python social_media_agent.py custom \"Your message here\"")
                return
            success = agent.post(
                args.message,
                dry_run=args.dry_run,
                test_mode=args.test,
                image_path=args.image,
            )
            _report(success)

        elif args.command == "listeners":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_listeners_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_listeners_post()
            if not message:
                print("[ERR] Could not generate listeners post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "daily":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_streams_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return
                ok, msg = agent.check_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message = agent.generate_daily_post()
            if not message:
                print("[ERR] Could not generate daily post.")
                return

            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=args.image,
            )
            _report(success)

        elif args.command == "top10":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_streams_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return
                ok, msg = agent.check_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_top10_post()
            if not message:
                print("[ERR] Could not generate top 10 post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "solo-top10":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_streams_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return
                ok, msg = agent.check_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_solo_top10_post()
            if not message:
                print("[ERR] Could not generate solo top 10 post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "milestones":
            milestone_posts = agent.generate_milestone_posts()
            if not milestone_posts:
                print("[INFO] No new milestones to post.")
                return

            print(f"[INFO] Found {len(milestone_posts)} new milestone(s)")
            posted_log = load_posted_log()

            for message, milestone_key in milestone_posts:
                success = agent.post(
                    message, dry_run=args.dry_run, test_mode=args.test, image_path=args.image,
                )
                if success and not args.dry_run and not args.test:
                    if "milestones" not in posted_log:
                        posted_log["milestones"] = {}
                    posted_log["milestones"][milestone_key] = datetime.now().isoformat()
                    save_posted_log(posted_log)
                    print(f"[INFO] Logged milestone: {milestone_key}")
                _report(success)

        elif args.command == "spikes":
            spike_posts = agent.generate_spikes_posts()
            if not spike_posts:
                print("[INFO] No significant spikes to post.")
                return

            print(f"[INFO] Found {len(spike_posts)} spike(s)")
            for message in spike_posts:
                success = agent.post(
                    message, dry_run=args.dry_run, test_mode=args.test, image_path=args.image,
                )
                _report(success)

        elif args.command == "weekly":
            if not args.force and datetime.now().weekday() != 6 and not args.dry_run:
                print("[SKIP] Weekly posts are sent on Sundays. Use --force to override.")
                return

            message = agent.generate_weekly_post()
            if not message:
                print("[ERR] Could not generate weekly post.")
                return

            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=args.image,
            )
            _report(success)

        elif args.command == "solo-top":
            solo_posts = agent.generate_solo_top_posts(top_n=args.top)
            if not solo_posts:
                print("[ERR] Could not generate solo top track posts.")
                return

            # Filter to specific artist if --artist is given
            if args.artist:
                match = args.artist.strip()
                solo_posts = [
                    (a, m) for a, m in solo_posts
                    if a.upper() == match.upper()
                ]
                if not solo_posts:
                    print(f"[ERR] No data found for artist: {match}")
                    print(f"[INFO] Available: {', '.join(SOLO_ARTISTS)}")
                    return

            print(f"[INFO] Posting top tracks for {len(solo_posts)} artist(s)")
            for artist, message in solo_posts:
                print(f"\n[INFO] Posting for {artist}...")
                success = agent.post(
                    message, dry_run=args.dry_run, test_mode=args.test,
                    image_path=args.image,
                )
                _report(success)

        elif args.command == "opm-top":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_leaderboard_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_opm_top_post()
            if not message:
                print("[ERR] Could not generate OPM top post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "opm-top-tracks":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_opm_tracks_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return
                ok, msg = agent.check_leaderboard_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_opm_top_tracks_post()
            if not message:
                print("[ERR] Could not generate OPM top tracks post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "opm-top-streams":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_opm_tracks_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return
                ok, msg = agent.check_leaderboard_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_opm_top_streams_post()
            if not message:
                print("[ERR] Could not generate OPM top streams post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "ppop-top":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_leaderboard_streams_quality()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, auto_image = agent.generate_ppop_top_post()
            if not message:
                print("[ERR] Could not generate P-Pop top post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "album":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_streams_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, screenshot_path = agent.generate_album_post()
            if not message:
                print("[ERR] Could not generate album post.")
                return

            image = args.image or screenshot_path
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image,
            )
            _report(success)

        elif args.command == "was-album":
            if not args.skip_validation and not args.dry_run:
                ok, msg = agent.check_streams_data()
                print(f"[VALIDATION] {msg}")
                if not ok:
                    print("[SKIP] Use --skip-validation to post anyway.")
                    return

            message, screenshot_path = agent.generate_was_album_post()
            if not message:
                print("[ERR] Could not generate Wakas At Simula album post.")
                return

            image = args.image or screenshot_path
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image,
            )
            _report(success)

        elif args.command == "youtube-emoji":
            message, auto_image = agent.generate_youtube_visa_post()
            if not message:
                print("[ERR] Could not generate YouTube EMOJI post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "youtube-channel":
            message, auto_image = agent.generate_youtube_channel_post()
            if not message:
                print("[ERR] Could not generate YouTube channel post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

        elif args.command == "spotify-visa":
            message, auto_image = agent.generate_spotify_visa_post()
            if not message:
                print("[ERR] Could not generate Spotify VISA post.")
                return

            image_path = args.image or auto_image
            success = agent.post(
                message, dry_run=args.dry_run, test_mode=args.test, image_path=image_path,
            )
            _report(success)

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")
    except Exception as e:
        print(f"\n[ERR] Unexpected error: {e}")
        raise
    finally:
        agent._stop_browser()


def _report(success):
    if success:
        print("[SUCCESS] Post completed!")
    else:
        print("[ERR] Post failed.")


if __name__ == "__main__":
    main()
