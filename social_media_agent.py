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
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Data files
STREAMS_FILE = os.path.join(SCRIPT_DIR, "selenium_results.csv")
STREAMS_LEGACY_FILE = os.path.join(SCRIPT_DIR, "sb19_streams_results.csv")
LISTENERS_FILE = os.path.join(SCRIPT_DIR, "monthly_listeners.csv")
POSTED_LOG = os.path.join(SCRIPT_DIR, "x_posted_log.json")

# Album screenshot
ALBUM_IMAGE_DIR = os.path.join(SCRIPT_DIR, "album_images")
ALBUM_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "simula_wakas.png")
TOP10_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "top10_streams.png")
SOLO_TOP10_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "solo_top10_streams.png")
LOCAL_INDEX = os.path.join(SCRIPT_DIR, "index.html")

# Listeners screenshot
MEMBER_PHOTOS_DIR = os.path.join(SCRIPT_DIR, "profiles")
LISTENERS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "monthly_listeners.png")
OPM_TOP_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_listeners.png")
PPOP_TOP_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "ppop_top_listeners.png")
OPM_TRACKS_FILE = os.path.join(SCRIPT_DIR, "opm_tracks_results.csv")
OPM_TOP_TRACKS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_tracks.png")
OPM_TOP_STREAMS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_streams.png")
MEMBER_PHOTO_FILES = {
    "SB19": "sb19.jpg",
    "PABLO": "pablo.jpg",
    "JOSH CULLEN": "josh cullen.jpg",
    "Stell": "stell.jpg",
    "FELIP": "felip.jpg",
    "justin": "justin.jpg",
}
MEMBER_BAR_COLORS = {
    "SB19": "#3b82f6",
    "PABLO": "#ef4444",
    "JOSH CULLEN": "#f59e0b",
    "Stell": "#a855f7",
    "FELIP": "#10b981",
    "justin": "#ec4899",
}

# Milestone thresholds
MILESTONES = [
    1_000_000, 5_000_000, 10_000_000, 25_000_000, 50_000_000,
    75_000_000, 100_000_000, 150_000_000, 200_000_000, 250_000_000,
]

MILESTONE_LABELS = {
    1_000_000: "1M", 5_000_000: "5M", 10_000_000: "10M",
    25_000_000: "25M", 50_000_000: "50M", 75_000_000: "75M",
    100_000_000: "100M", 150_000_000: "150M", 200_000_000: "200M",
    250_000_000: "250M",
}

# Spike detection thresholds
SPIKE_THRESHOLD_PERCENT = 50
SPIKE_THRESHOLD_ABSOLUTE = 100_000

# YouTube VISA MV
YOUTUBE_API_KEY = "AIzaSyCG-ZWidx7LVzf8NSts4lvUwwEMMao34q8"
YOUTUBE_VIDEO_ID = "0t6GNcINKeU"
YOUTUBE_VIDEO_URL = "https://youtu.be/0t6GNcINKeU"
YT_HISTORY_FILE = os.path.join(SCRIPT_DIR, "yt_visa_history.json")
YT_STREAMS_CSV = os.path.join(SCRIPT_DIR, "yt_visa_streams.csv")
YT_VISA_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "yt_visa_stats.png")

# Spotify VISA daily
SPOTIFY_VISA_URL = "https://open.spotify.com/track/6RYMQDnY4zPaLSfvfRdXT7"
SPOTIFY_VISA_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "spotify_visa_stats.png")

# Main artists with X handles
MAIN_ARTISTS = ["SB19", "PABLO", "JOSH CULLEN", "Stell", "FELIP", "justin"]
SOLO_ARTISTS = ["PABLO", "JOSH CULLEN", "Stell", "FELIP", "justin"]
X_HANDLES = {
    "SB19": "@SB19Official",
    "PABLO": "@imszmc",
    "JOSH CULLEN": "@JoshCullen_s",
    "Stell": "@stellajero_",
    "FELIP": "@felipsuperior",
    "justin": "@justintdedios",
}

# Number of top tracks to show per solo artist
SOLO_TOP_N = 3

# X (Twitter) character limit (Premium)
X_CHAR_LIMIT = 25000
SITE_TAG = "opminsights.com"

# Simula at Wakas album tracks
ALBUM_TRACKS = [
    "Prologue (Simula at Wakas Tour Kickoff)",
    "Moonlight (Simula at Wakas Tour Kickoff)",
    "I WANT YOU (Simula at Wakas Tour Kickoff)",
    "What? (Simula at Wakas Tour Kickoff)",
    "Mana (Simula at Wakas Tour Kickoff)",
    "GENTO (Simula at Wakas Tour Kickoff)",
    "WYAT (Where You At) (Simula at Wakas Tour Kickoff)",
    "ILAW (Simula at Wakas Tour Kickoff)",
    "8TonBall (Simula at Wakas Tour Kickoff)",
    "Quit (Simula at Wakas Tour Kickoff)",
    "Nyebe (Simula at Wakas Tour Kickoff)",
    "DUNGKA! (Simula at Wakas Tour Kickoff)",
    "Bazinga (Simula at Wakas Tour Kickoff)",
    "CRIMZONE (Simula at Wakas Tour Kickoff)",
    "Time (Simula at Wakas Tour Kickoff)",
    "Shooting for the Stars (Simula at Wakas Tour Kickoff)",
    "MAPA (Simula at Wakas Tour Kickoff)",
    "SLMT (Simula at Wakas Tour Kickoff)",
    "DAM (Simula at Wakas Tour Kickoff)",
    "FREEDOM (Simula at Wakas Tour Kickoff)",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def format_number(n):
    """Format large numbers for compact display (e.g. 1.25M)."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_with_commas(n):
    """Format number with comma separators."""
    return f"{n:,}"


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

    # ======================================================================
    # Content generators — each returns a message string (or None)
    # ======================================================================

    def generate_listeners_post(self):
        """Monthly listener update for SB19 and members.

        Returns (message, image_path_or_None).
        """
        data = load_listeners_data()
        if not data:
            print("[WARN] No listener data available!")
            return None, None

        by_artist = defaultdict(list)
        for entry in data:
            if any(m.upper() == entry["artist"].upper() for m in MAIN_ARTISTS):
                by_artist[entry["artist"]].append(entry)

        if not by_artist:
            print("[WARN] No main artist data found!")
            return None, None

        latest_data = []
        for artist, entries in by_artist.items():
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            latest = entries[0]
            latest_date = latest["date"]

            previous = None
            for entry in entries[1:]:
                if entry["date"] != latest_date:
                    previous = entry
                    break

            change = (latest["listeners"] - previous["listeners"]) if previous else 0
            latest_data.append({
                "artist": artist,
                "listeners": latest["listeners"],
                "change": change,
            })

        latest_data.sort(key=lambda x: x["listeners"], reverse=True)

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
        screenshot_ok = self._capture_listeners_screenshot(latest_data, latest_date_str)
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
        screenshot_ok = self._capture_top10_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_added=total_added,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(TOP10_IMAGE_PATH):
            image_path = TOP10_IMAGE_PATH

        return message, image_path

    def _capture_top10_screenshot(self, top3_data=None, table_data=None,
                                    total_added=0, date_str=""):
        """Capture a social-media-friendly SB19 top tracks card.

        Section A: Top 3 as equal-width podium bars.
        Section B: Remaining tracks as compact table.
        """
        print("[INFO] Capturing top tracks screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not top3_data:
            print("[ERR] No track data for top tracks card")
            return False

        podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]  # gold, silver, bronze

        def _rank_change_html(rc, streak=1):
            if rc is not None and rc > 0:
                return f'<span class="rank-up">▲{rc}</span>'
            elif rc is not None and rc < 0:
                return f'<span class="rank-down">▼{abs(rc)}</span>'
            elif rc == 0 and streak > 1:
                return f'<span class="rank-same">{streak}d</span>'
            else:
                return '<span class="rank-same">―</span>'

        def _change_html(change):
            if change > 0:
                return f'<span class="change-up">+{change:,}</span>'
            elif change < 0:
                return f'<span class="change-down">{change:,}</span>'
            return '<span class="change-same">―</span>'

        # --- Section A: Top 3 podium bars (equal width) ---
        top3_rows = ""
        for i, t in enumerate(top3_data):
            color = podium_colors[i]
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))

            top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['song']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

        # --- Section B: Table for remaining tracks ---
        table_rows = ""
        if table_data:
            for t in table_data:
                streams_str = f"{t['streams']:,}"
                ch_html = _change_html(t["change"])
                rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))

                table_rows += f"""
                <tr>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

        total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
/* --- Top 3 Podium --- */
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 380px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
/* --- Shared --- */
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Top Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_top10_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(TOP10_IMAGE_PATH)

                img = Image.open(TOP10_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(TOP10_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Top tracks screenshot saved: {TOP10_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Top tracks screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Top tracks screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    def _capture_solo_top10_screenshot(self, top3_data=None, table_data=None,
                                       total_added=0, date_str=""):
        """Capture a social-media-friendly solo top tracks card.

        Section A: Top 3 as equal-width podium bars with artist badge.
        Section B: Remaining tracks as compact table with artist column.
        """
        print("[INFO] Capturing solo top tracks screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not top3_data:
            print("[ERR] No track data for solo top tracks card")
            return False

        podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]  # gold, silver, bronze

        def _rank_change_html(rc, streak=1):
            if rc is not None and rc > 0:
                return f'<span class="rank-up">▲{rc}</span>'
            elif rc is not None and rc < 0:
                return f'<span class="rank-down">▼{abs(rc)}</span>'
            elif rc == 0 and streak > 1:
                return f'<span class="rank-same">{streak}d</span>'
            else:
                return '<span class="rank-same">―</span>'

        def _change_html(change):
            if change > 0:
                return f'<span class="change-up">+{change:,}</span>'
            elif change < 0:
                return f'<span class="change-down">{change:,}</span>'
            return '<span class="change-same">―</span>'

        # --- Section A: Top 3 podium bars with artist badge ---
        top3_rows = ""
        for i, t in enumerate(top3_data):
            color = podium_colors[i]
            artist_color = MEMBER_BAR_COLORS.get(t["artist"], "#3b82f6")
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))
            badge_html = (
                f'<span class="artist-badge" style="background: {artist_color};">'
                f'{t["artist"]}</span>'
            )

            top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['song']}</span>
                        {badge_html}
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {artist_color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

        # --- Section B: Table for remaining tracks ---
        table_rows = ""
        if table_data:
            for t in table_data:
                artist_color = MEMBER_BAR_COLORS.get(t["artist"], "#3b82f6")
                streams_str = f"{t['streams']:,}"
                ch_html = _change_html(t["change"])
                rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))

                table_rows += f"""
                <tr>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-artist" style="color: {artist_color};">{t['artist']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

        total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
/* --- Top 3 Podium --- */
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.artist-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    flex-shrink: 0;
    opacity: 0.9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
}}
td.col-artist {{
    font-weight: 600;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
/* --- Shared --- */
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Solo Top Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th>Artist</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_solo_top10_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(SOLO_TOP10_IMAGE_PATH)

                img = Image.open(SOLO_TOP10_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(SOLO_TOP10_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Solo top tracks screenshot saved: {SOLO_TOP10_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Solo top tracks screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Solo top tracks screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

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
        screenshot_ok = self._capture_solo_top10_screenshot(
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
        """Top 10 OPM artists by monthly listeners with SB19 rank.

        Returns (message, image_path_or_None).
        """
        data = load_listeners_data()
        if not data:
            return None, None

        # Get the latest date
        latest_date = max(e["date"] for e in data)
        latest = [e for e in data if e["date"] == latest_date]

        if not latest:
            print("[WARN] No data for latest date")
            return None, None

        # Exclude SB19 solo members from ranking
        sb19_solo = {a.lower() for a in SOLO_ARTISTS}
        all_artists = [e for e in latest if e["artist"].lower() not in sb19_solo]

        # Deduplicate by artist name (keep highest listeners if duplicated)
        artist_map = {}
        for e in all_artists:
            key = e["artist"].lower()
            if key not in artist_map or e["listeners"] > artist_map[key]["listeners"]:
                artist_map[key] = e
        ranked = sorted(artist_map.values(), key=lambda x: x["listeners"], reverse=True)

        # Find SB19's entry and rank
        sb19_entry = None
        sb19_rank = None
        for i, e in enumerate(ranked, 1):
            if e["artist"].upper() == "SB19":
                sb19_entry = e
                sb19_rank = i
                break

        top20 = ranked[:20]

        if not top20:
            print("[INFO] No OPM artist data found")
            return None, None

        # Get previous date data for change comparison
        all_dates = sorted(set(e["date"] for e in data))
        prev_date = None
        for d in reversed(all_dates):
            if d < latest_date:
                prev_date = d
                break

        prev_map = {}
        prev_rank_map = {}
        if prev_date:
            prev_entries = [e for e in data if e["date"] == prev_date and e["artist"].lower() not in sb19_solo]
            prev_artist_map = {}
            for e in prev_entries:
                key = e["artist"].lower()
                if key not in prev_artist_map or e["listeners"] > prev_artist_map[key]["listeners"]:
                    prev_artist_map[key] = e
            for key, e in prev_artist_map.items():
                prev_map[key] = e["listeners"]
            # Build previous ranking to compute rank changes
            prev_ranked = sorted(prev_artist_map.values(), key=lambda x: x["listeners"], reverse=True)
            for i, e in enumerate(prev_ranked, 1):
                prev_rank_map[e["artist"].lower()] = i

        # Format date
        try:
            date_formatted = datetime.strptime(latest_date[:8], "%Y%m%d").strftime("%B %d, %Y")
        except ValueError:
            date_formatted = latest_date

        # Compute rank changes
        def _rank_indicator(artist_key, current_rank):
            prev_r = prev_rank_map.get(artist_key)
            if prev_r is None:
                return "", None
            diff = prev_r - current_rank  # positive = moved up
            if diff > 0:
                return f" (+{diff})", diff
            elif diff < 0:
                return f" ({diff})", diff
            return "", 0

        # Compact caption for 280-char limit (image carries the data)
        date_short = short_date(latest_date)
        sb19_line = ""
        if sb19_rank:
            sb19_line = f"\n\nSB19 ranked #{sb19_rank} out of {len(ranked)} artists"
        message = (
            f"OPM Top Artists by Monthly Listeners | Spotify | {date_short}"
            f"{sb19_line}\n\n"
            f"{SITE_TAG}\n"
            f"#OPM #SB19"
        )
        enforce_char_limit(message)

        # Re-read CSV for genre field
        genre_lookup = {}
        if os.path.exists(LISTENERS_FILE):
            with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = row.get("timestamp", "")
                    if ts[:8] == latest_date:
                        genre_lookup[row["artist_name"].lower()] = row.get("genre", "")

        # Build data for all top 20
        card_data = []
        for i, e in enumerate(top20, 1):
            prev_val = prev_map.get(e["artist"].lower())
            change = (e["listeners"] - prev_val) if prev_val is not None else 0
            _, rank_change = _rank_indicator(e["artist"].lower(), i)
            genre = genre_lookup.get(e["artist"].lower(), "")
            card_data.append({
                "rank": i,
                "artist": e["artist"],
                "listeners": e["listeners"],
                "change": change,
                "rank_change": rank_change,
                "genre": genre,
            })

        # Split into top 3 podium + table
        top3_data = card_data[:3]
        table_data = card_data[3:]

        # SB19 separate section only if rank > 20
        sb19_card = None
        if sb19_entry and sb19_rank and sb19_rank > 20:
            prev_val = prev_map.get("sb19")
            sb19_change = (sb19_entry["listeners"] - prev_val) if prev_val is not None else 0
            _, sb19_rc = _rank_indicator("sb19", sb19_rank)
            sb19_card = {
                "rank": sb19_rank,
                "artist": "SB19",
                "listeners": sb19_entry["listeners"],
                "change": sb19_change,
                "rank_change": sb19_rc,
                "genre": "P-Pop",
            }

        image_path = None
        screenshot_ok = self._capture_opm_top_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            sb19_data=sb19_card,
            total_artists=len(ranked),
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(OPM_TOP_IMAGE_PATH):
            image_path = OPM_TOP_IMAGE_PATH

        return message, image_path

    def _capture_opm_top_screenshot(self, top3_data=None, table_data=None,
                                     sb19_data=None, total_artists=0, date_str=""):
        """Capture a social-media-friendly OPM top artists card.

        Section A: Top 3 as equal-width podium bars with genre label.
        Section B: Remaining artists as compact table.
        Section C: SB19 separate row (only if rank > 20).
        """
        print("[INFO] Capturing OPM top listeners screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not top3_data:
            print("[ERR] No data for OPM top card")
            return False

        podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]  # gold, silver, bronze

        def _rank_change_html(rc):
            if rc is not None and rc > 0:
                return f'<span class="rank-up">▲{rc}</span>'
            elif rc is not None and rc < 0:
                return f'<span class="rank-down">▼{abs(rc)}</span>'
            else:
                return '<span class="rank-same">―</span>'

        def _change_html(change):
            if change > 0:
                return f'<span class="change-up">+{change:,}</span>'
            elif change < 0:
                return f'<span class="change-down">{change:,}</span>'
            return '<span class="change-same">―</span>'

        # --- Section A: Top 3 podium bars ---
        top3_rows = ""
        for i, t in enumerate(top3_data):
            color = podium_colors[i]
            listeners_str = f"{t['listeners']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html(t.get("rank_change"))
            genre_label = t.get("genre", "")

            top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['artist']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-genre">{genre_label}</div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-listeners">{listeners_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

        # --- Section B: Table for remaining artists ---
        table_rows = ""
        if table_data:
            for t in table_data:
                listeners_str = f"{t['listeners']:,}"
                ch_html = _change_html(t["change"])
                rc_html = _rank_change_html(t.get("rank_change"))
                genre_label = t.get("genre", "")
                is_sb19 = t["artist"].upper() == "SB19"
                row_class = ' class="sb19-row"' if is_sb19 else ""

                table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{genre_label}</td>
                    <td class="col-listeners">{listeners_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

        # --- Section C: SB19 separate row (only if rank > 20) ---
        sb19_section = ""
        if sb19_data:
            sb19_listeners_str = f"{sb19_data['listeners']:,}"
            sb19_ch_html = _change_html(sb19_data["change"])
            sb19_rc_html = _rank_change_html(sb19_data.get("rank_change"))
            sb19_section = f"""
    <div class="sb19-extra-section">
        <div class="sb19-divider"></div>
        <div class="sb19-extra-label">SB19</div>
        <table class="sb19-extra-table">
            <tr class="sb19-row">
                <td class="col-rank">{sb19_data['rank']}</td>
                <td class="col-artist">SB19</td>
                <td class="col-genre">P-Pop</td>
                <td class="col-listeners">{sb19_listeners_str}</td>
                <td class="col-change">{sb19_ch_html}</td>
                <td class="col-rc">{sb19_rc_html}</td>
            </tr>
        </table>
    </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
/* --- Top 3 Podium --- */
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-listeners {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-listeners, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
}}
td.col-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
td.col-listeners {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-listeners {{
    color: #22d3ee;
}}
/* --- SB19 Extra Section (rank > 20) --- */
.sb19-extra-section {{
    margin-top: 8px;
}}
.sb19-divider {{
    border-top: 2px dashed rgba(6, 182, 212, 0.3);
    margin: 16px 0 12px;
}}
.sb19-extra-label {{
    font-size: 16px;
    font-weight: 600;
    color: #22d3ee;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
}}
.sb19-extra-table {{
    width: 100%;
    border-collapse: collapse;
}}
.sb19-extra-table td {{
    font-size: 14px;
    padding: 7px 10px;
    border-bottom: none;
}}
/* --- Shared --- */
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Top Artists by Monthly Listeners</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_artists}</div>
                <div class="stat-label">Artists Tracked</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Artists</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-listeners">Listeners</th>
                    <th class="col-change">Change</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    {sb19_section}
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_opm_top_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(OPM_TOP_IMAGE_PATH)

                img = Image.open(OPM_TOP_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(OPM_TOP_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] OPM top screenshot saved: {OPM_TOP_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] OPM top screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] OPM top screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

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
        screenshot_ok = self._capture_opm_top_tracks_screenshot(
            top3_data=top3_data,
            table_data=table_data,
            total_added=total_added,
            total_tracks=total_tracks,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(OPM_TOP_TRACKS_IMAGE_PATH):
            image_path = OPM_TOP_TRACKS_IMAGE_PATH

        return message, image_path

    def _capture_opm_top_tracks_screenshot(self, top3_data=None, table_data=None,
                                            total_added=0, total_tracks=0, date_str=""):
        """Capture a social-media-friendly OPM top tracks by daily streams card.

        Section A: Top 3 as equal-width podium bars. SB19 tracks get cyan styling.
        Section B: Remaining tracks as compact table. SB19 rows highlighted.
        """
        print("[INFO] Capturing OPM top tracks screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not top3_data:
            print("[ERR] No track data for OPM top tracks card")
            return False

        podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]  # gold, silver, bronze
        sb19_color = "#06b6d4"  # cyan for SB19 tracks

        def _rank_change_html(rc, streak=1):
            if rc is not None and rc > 0:
                return f'<span class="rank-up">▲{rc}</span>'
            elif rc is not None and rc < 0:
                return f'<span class="rank-down">▼{abs(rc)}</span>'
            elif rc == 0 and streak > 1:
                return f'<span class="rank-same">{streak}d</span>'
            else:
                return '<span class="rank-same">―</span>'

        def _change_html(change):
            if change > 0:
                return f'<span class="change-up">+{change:,}</span>'
            elif change < 0:
                return f'<span class="change-down">{change:,}</span>'
            return '<span class="change-same">―</span>'

        # --- Section A: Top 3 podium bars ---
        top3_rows = ""
        for i, t in enumerate(top3_data):
            is_sb19 = t.get("is_sb19", False)
            color = sb19_color if is_sb19 else podium_colors[i]
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))

            podium_class = f"podium-row podium-{i+1}"
            if is_sb19:
                podium_class += " podium-sb19"
            name_style = ' style="color: #22d3ee;"' if is_sb19 else ""
            artist_style = ' style="color: #67e8f9;"' if is_sb19 else ""

            top3_rows += f"""
            <div class="{podium_class}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name"{name_style}>{t['song']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-artist"{artist_style}>{t['artist']}</div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

        # --- Section B: Table for remaining tracks ---
        table_rows = ""
        if table_data:
            for t in table_data:
                is_sb19 = t.get("is_sb19", False)
                streams_str = f"{t['streams']:,}"
                ch_html = _change_html(t["change"])
                rc_html = _rank_change_html(t.get("rank_change"), t.get("streak", 1))
                row_class = ' class="sb19-row"' if is_sb19 else ""

                table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

        total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-value-blue {{
    font-size: 36px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
/* --- Top 3 Podium --- */
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-sb19 {{
    background: rgba(6, 182, 212, 0.10) !important;
    border: 1px solid rgba(6, 182, 212, 0.25) !important;
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-sb19 .podium-rank {{ color: #06b6d4 !important; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-artist {{
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 260px;
}}
td.col-artist {{
    font-size: 13px;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 160px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-track {{
    color: #22d3ee;
}}
tr.sb19-row td.col-artist {{
    color: #67e8f9;
}}
tr.sb19-row td.col-streams {{
    color: #22d3ee;
}}
/* --- Shared --- */
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Top Tracks by Daily Streams</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-value-blue">{total_tracks:,}</div>
                <div class="stat-label">Tracks Tracked</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th>Artist</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_opm_top_tracks_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(OPM_TOP_TRACKS_IMAGE_PATH)

                img = Image.open(OPM_TOP_TRACKS_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(OPM_TOP_TRACKS_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] OPM top tracks screenshot saved: {OPM_TOP_TRACKS_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] OPM top tracks screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] OPM top tracks screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

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
        screenshot_ok = self._capture_opm_top_streams_screenshot(
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

    def _capture_opm_top_streams_screenshot(self, top3_data=None, table_data=None,
                                             sb19_data=None, grand_total=0,
                                             total_artists=0, date_str=""):
        """Capture OPM top artists by daily streams card.

        Section A: Top 3 podium bars with genre label, daily streams, vs-prev-day change, track count.
        Section B: Remaining artists as compact table.
        Section C: SB19 separate row (only if rank > 20).
        """
        print("[INFO] Capturing OPM top streams screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not top3_data:
            print("[ERR] No data for OPM top streams card")
            return False

        podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]  # gold, silver, bronze
        sb19_color = "#06b6d4"  # cyan for SB19

        def _rank_change_html(rc):
            if rc is not None and rc > 0:
                return f'<span class="rank-up">&#9650;{rc}</span>'
            elif rc is not None and rc < 0:
                return f'<span class="rank-down">&#9660;{abs(rc)}</span>'
            else:
                return '<span class="rank-same">―</span>'

        def _change_html(change):
            if change > 0:
                return f'<span class="change-up">+{change:,}</span>'
            elif change < 0:
                return f'<span class="change-down">{change:,}</span>'
            return '<span class="change-same">―</span>'

        # --- Section A: Top 3 podium bars ---
        top3_rows = ""
        for i, t in enumerate(top3_data):
            is_sb19 = t.get("is_sb19", False)
            color = sb19_color if is_sb19 else podium_colors[i]
            streams_str = f"{t['total_streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html(t.get("rank_change"))
            genre_label = t.get("genre", "")
            track_badge = f'<span class="track-badge">{t["track_count"]} tracks</span>'

            podium_class = f"podium-row podium-{i+1}"
            if is_sb19:
                podium_class += " podium-sb19"
            name_style = ' style="color: #22d3ee;"' if is_sb19 else ""

            top3_rows += f"""
            <div class="{podium_class}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name"{name_style}>{t['artist']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-meta">
                        <span class="podium-genre">{genre_label}</span>
                        {track_badge}
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

        # --- Section B: Table for remaining artists ---
        table_rows = ""
        if table_data:
            for t in table_data:
                is_sb19 = t.get("is_sb19", False)
                streams_str = f"{t['total_streams']:,}"
                ch_html = _change_html(t["change"])
                rc_html = _rank_change_html(t.get("rank_change"))
                genre_label = t.get("genre", "")
                row_class = ' class="sb19-row"' if is_sb19 else ""

                table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{genre_label}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-tracks">{t['track_count']}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

        # --- Section C: SB19 separate row (only if rank > 20) ---
        sb19_section = ""
        if sb19_data:
            sb19_streams_str = f"{sb19_data['total_streams']:,}"
            sb19_ch_html = _change_html(sb19_data["change"])
            sb19_rc_html = _rank_change_html(sb19_data.get("rank_change"))
            sb19_section = f"""
    <div class="sb19-extra-section">
        <div class="sb19-divider"></div>
        <div class="sb19-extra-label">SB19</div>
        <table class="sb19-extra-table">
            <tr class="sb19-row">
                <td class="col-rank">{sb19_data['rank']}</td>
                <td class="col-artist">SB19</td>
                <td class="col-genre">P-Pop</td>
                <td class="col-streams">{sb19_streams_str}</td>
                <td class="col-change">{sb19_ch_html}</td>
                <td class="col-tracks">{sb19_data['track_count']}</td>
                <td class="col-rc">{sb19_rc_html}</td>
            </tr>
        </table>
    </div>"""

        grand_total_str = f"{grand_total:,}"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(16, 185, 129, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-value-blue {{
    font-size: 36px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
/* --- Top 3 Podium --- */
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-sb19 {{
    background: rgba(6, 182, 212, 0.10) !important;
    border: 1px solid rgba(6, 182, 212, 0.25) !important;
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-sb19 .podium-rank {{ color: #06b6d4 !important; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.track-badge {{
    font-size: 11px;
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.12);
    padding: 2px 8px;
    border-radius: 10px;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-tracks, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 260px;
}}
td.col-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-tracks {{
    text-align: right;
    font-size: 13px;
    color: #94a3b8;
    width: 60px;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-streams {{
    color: #22d3ee;
}}
/* --- SB19 Extra Section (rank > 20) --- */
.sb19-extra-section {{
    margin-top: 8px;
}}
.sb19-divider {{
    border-top: 2px dashed rgba(6, 182, 212, 0.3);
    margin: 16px 0 12px;
}}
.sb19-extra-label {{
    font-size: 16px;
    font-weight: 600;
    color: #22d3ee;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
}}
.sb19-extra-table {{
    width: 100%;
    border-collapse: collapse;
}}
.sb19-extra-table td {{
    font-size: 14px;
    padding: 7px 10px;
    border-bottom: none;
}}
/* --- Shared --- */
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #10b981;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Top Artists by Daily Streams</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{grand_total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-value-blue">{total_artists}</div>
                <div class="stat-label">Artists Tracked</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Artists</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-streams">Daily Streams</th>
                    <th class="col-change">vs Prev Day</th>
                    <th class="col-tracks">Tracks</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    {sb19_section}
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_opm_top_streams_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(OPM_TOP_STREAMS_IMAGE_PATH)

                img = Image.open(OPM_TOP_STREAMS_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(OPM_TOP_STREAMS_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] OPM top streams screenshot saved: {OPM_TOP_STREAMS_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] OPM top streams screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] OPM top streams screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

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
        screenshot_ok = self._capture_ppop_top_screenshot(
            table_data=card_data,
            ppop_count=len(ppop_ranked),
            total_artists=total_artists,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(PPOP_TOP_IMAGE_PATH):
            image_path = PPOP_TOP_IMAGE_PATH

        return message, image_path

    def _capture_ppop_top_screenshot(self, table_data=None,
                                      ppop_count=0, total_artists=0, date_str=""):
        """Capture P-Pop leaderboard as a flat table sorted by daily streams."""
        print("[INFO] Capturing P-Pop leaderboard screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not table_data:
            print("[ERR] No data for P-Pop leaderboard")
            return False

        def _fmt_num(n):
            absn = abs(n)
            if absn >= 1e9:
                return f"{absn/1e9:.1f}B"
            if absn >= 1e6:
                return f"{absn/1e6:.1f}M"
            if absn >= 1e3:
                return f"{absn/1e3:.1f}K"
            return f"{absn:,}"

        def _change_html(change):
            if change > 0:
                absn = abs(change)
                s = _fmt_num(change) if absn >= 10000 else f"{change:,}"
                return f'<span class="change-up">+{s}</span>'
            elif change < 0:
                absn = abs(change)
                s = _fmt_num(change) if absn >= 10000 else f"{absn:,}"
                return f'<span class="change-down">-{s}</span>'
            return '<span class="change-same">―</span>'

        def _daily_html(daily, daily_change):
            if not daily:
                return '<span class="change-same">―</span>'
            prefix = "+" if daily > 0 else ""
            cls = "change-up" if daily > 0 else "change-down" if daily < 0 else "change-same"
            html = f'<span class="{cls}">{prefix}{daily:,}</span>'
            if daily_change:
                dc_prefix = "+" if daily_change > 0 else ""
                dc_cls = "change-up" if daily_change > 0 else "change-down"
                html += f' <span class="{dc_cls}" style="font-size:11px">({dc_prefix}{_fmt_num(daily_change)})</span>'
            return html

        # --- Top 3 medallion section ---
        medal_colors = [
            ("#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.35)"),  # gold
            ("#94a3b8", "rgba(148, 163, 184, 0.10)", "rgba(148, 163, 184, 0.30)"),  # silver
            ("#cd7f32", "rgba(205, 127, 50, 0.10)", "rgba(205, 127, 50, 0.30)"),  # bronze
        ]
        top3_html = ""
        top3_data = table_data[:3]
        remaining_data = table_data[3:]

        for i, t in enumerate(top3_data):
            color, bg, border = medal_colors[i]
            listeners_str = f"{t['listeners']:,}"
            ch_html = _change_html(t["change"])
            total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "―"
            daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
            followers_str = f"{t['followers']:,}" if t.get("followers") else "―"

            top3_html += f"""
            <div class="medal-card" style="background: {bg}; border-color: {border};">
                <div class="medal-circle" style="background: {color}; box-shadow: 0 0 20px {color}40;">
                    <span class="medal-rank">{t['rank']}</span>
                </div>
                <div class="medal-name">{t['artist']}</div>
                <div class="medal-row">
                    <span class="medal-label">Daily Streams</span>
                    <span class="medal-daily">{daily_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Monthly Listeners</span>
                    <span class="medal-value">{listeners_str}</span>
                    <span class="medal-change">{ch_html}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Total Streams</span>
                    <span class="medal-value">{total_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Followers</span>
                    <span class="medal-value-sm">{followers_str}</span>
                </div>
            </div>"""

        # Build table rows (rank 4+)
        table_rows = ""
        for t in remaining_data:
            listeners_str = f"{t['listeners']:,}"
            ch_html = _change_html(t["change"])
            followers_str = f"{t['followers']:,}" if t.get("followers") else "―"
            total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "―"
            daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
            is_sb19 = t["artist"].lower() == "sb19"
            row_class = ' class="sb19-row"' if is_sb19 else ""

            table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{t.get('genre', 'P-Pop')}</td>
                    <td class="col-listeners">{listeners_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-followers">{followers_str}</td>
                    <td class="col-total-streams">{total_str}</td>
                    <td class="col-daily">{daily_str}</td>
                </tr>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1200px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(6, 182, 212, 0.2);
    border-radius: 20px;
    padding: 40px 44px 36px;
    box-shadow: 0 0 60px rgba(6, 182, 212, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 28px;
    padding-bottom: 22px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 28px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 6px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 16px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 14px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 32px;
    font-weight: 800;
    color: #06b6d4;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 13px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.stat-detail {{
    font-size: 12px;
    color: #475569;
    margin-top: 1px;
}}
/* --- Top 3 Medallions --- */
.medal-section {{
    display: flex;
    gap: 20px;
    margin-bottom: 28px;
}}
.medal-card {{
    flex: 1;
    border: 1px solid;
    border-radius: 16px;
    padding: 20px 18px 16px;
    text-align: center;
    position: relative;
}}
.medal-circle {{
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
}}
.medal-rank {{
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
}}
.medal-name {{
    font-size: 20px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.medal-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    gap: 6px;
}}
.medal-label {{
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
}}
.medal-value {{
    font-size: 15px;
    font-weight: 700;
    color: #e2e8f0;
}}
.medal-value-sm {{
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
}}
.medal-change {{
    font-size: 12px;
    font-weight: 500;
}}
.medal-daily {{
    font-size: 13px;
    font-weight: 600;
}}
/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 0 0 20px;
}}
.section-label {{
    font-size: 14px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
}}
/* --- Table Section --- */
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 8px 8px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank {{ text-align: right; width: 36px; }}
th.col-listeners, th.col-change, th.col-followers, th.col-total-streams, th.col-daily {{
    text-align: right;
}}
td {{
    font-size: 13px;
    padding: 6px 8px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 36px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
}}
td.col-genre {{
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
}}
td.col-listeners {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
td.col-followers {{
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-total-streams {{
    font-weight: 600;
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-daily {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-listeners {{
    color: #22d3ee;
}}
/* --- Shared --- */
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 22px;
    padding-top: 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 13px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #06b6d4;
    font-weight: 600;
}}
.footer-note {{
    font-size: 12px;
    color: #64748b;
    font-style: italic;
    margin-bottom: 6px;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">P-Pop Leaderboard</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{ppop_count}</div>
                <div class="stat-label">P-Pop Groups</div>
                <div class="stat-detail">of {total_artists} artists tracked</div>
            </div>
        </div>
    </div>
    <div class="medal-section">{top3_html}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Groups</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-listeners">Monthly Listeners</th>
                    <th class="col-change">Change</th>
                    <th class="col-followers">Followers</th>
                    <th class="col-total-streams">Total Streams</th>
                    <th class="col-daily">Daily Streams</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-note">*Ranked by daily streams</div>
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_ppop_top_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 3000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(PPOP_TOP_IMAGE_PATH)

                img = Image.open(PPOP_TOP_IMAGE_PATH)
                if img.width > 3200:
                    ratio = 3200 / img.width
                    img = img.resize((3200, int(img.height * ratio)), Image.LANCZOS)
                    img.save(PPOP_TOP_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] P-Pop top screenshot saved: {PPOP_TOP_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] P-Pop top screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] P-Pop top screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

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
        screenshot_ok = self._capture_album_screenshot(
            track_list=track_list,
            total_streams=total_streams,
            total_change=total_change,
            date_str=date_str,
        )
        if screenshot_ok and os.path.exists(ALBUM_IMAGE_PATH):
            image_path = ALBUM_IMAGE_PATH

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

        lines = [
            f"SB19 VISA MV Update as of {now_str}",
            "",
            SITE_TAG,
            YOUTUBE_VIDEO_URL,
            "",
            stat_line("Views", views, view_change),
            stat_line("Likes", likes, like_change),
            stat_line("Comments", comments, comment_change),
            "",
            "#SB19 #VISA #MV #OPM",
        ]

        message = "\n".join(lines)
        enforce_char_limit(message)

        # Capture social card screenshot
        image_path = None
        ok = self._capture_youtube_visa_screenshot(
            views=views, likes=likes, comments=comments,
            view_change=view_change, like_change=like_change,
            comment_change=comment_change, now_str=now_str,
        )
        if ok and os.path.exists(YT_VISA_IMAGE_PATH):
            image_path = YT_VISA_IMAGE_PATH

        return message, image_path

    def _compute_hourly_deltas(self):
        """Read yt_visa_streams.csv and compute hourly view deltas for the chart."""
        if not os.path.exists(YT_STREAMS_CSV):
            return [], []
        rows = []
        with open(YT_STREAMS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        if len(rows) < 2:
            return [], []

        # Bucket by 4-hour slot, take max views per slot
        hourly = {}
        for row in rows:
            ts = row.get("timestamp", "").strip()
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                slot = (dt.hour // 4) * 4
                hour_key = f"{dt.strftime('%Y-%m-%d')} {slot:02d}"
            except ValueError:
                continue
            v = int(row.get("views", 0))
            if hour_key not in hourly or v > hourly[hour_key]:
                hourly[hour_key] = v

        sorted_hours = sorted(hourly.keys())
        labels = []
        deltas = []
        def _fmt_h(h):
            h12 = h % 12 or 12
            ap = 'p' if h >= 12 else 'a'
            return f"{h12}{ap}"
        for i in range(1, len(sorted_hours)):
            delta = hourly[sorted_hours[i]] - hourly[sorted_hours[i - 1]]
            if delta < 0:
                delta = 0
            prev_hour = int(sorted_hours[i - 1][-2:])
            curr_hour = int(sorted_hours[i][-2:])
            labels.append(f"{_fmt_h(prev_hour)}-{_fmt_h(curr_hour)}")
            deltas.append(delta)

        # Keep only the last 6 bars
        if len(labels) > 6:
            labels = labels[-6:]
            deltas = deltas[-6:]

        return labels, deltas

    def _capture_youtube_visa_screenshot(self, views, likes, comments,
                                          view_change, like_change,
                                          comment_change, now_str):
        """Capture a social-media-friendly YouTube VISA stats card."""
        print("[INFO] Capturing YouTube VISA screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        # Encode VISA artwork as base64 for the card background
        visa_img_path = os.path.join(SCRIPT_DIR, "photos", "visa.png")
        bg_data_uri = ""
        if os.path.exists(visa_img_path):
            with open(visa_img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                bg_data_uri = f"data:image/png;base64,{b64}"

        def stat_with_change(value, change):
            val_str = f"{value:,}"
            if change > 0:
                return val_str, f"+{change:,}"
            elif change < 0:
                return val_str, f"{change:,}"
            return val_str, ""

        def format_k(v):
            if v >= 1_000_000:
                return f"{v / 1_000_000:.1f}M"
            if v >= 1_000:
                return f"{v / 1_000:.1f}K"
            return str(v)

        v_str, v_chg = stat_with_change(views, view_change)
        l_str, l_chg = stat_with_change(likes, like_change)
        c_str, c_chg = stat_with_change(comments, comment_change)

        # Change color
        chg_color_v = "#34d399" if view_change >= 0 else "#f87171"
        chg_color_l = "#34d399" if like_change >= 0 else "#f87171"
        chg_color_c = "#34d399" if comment_change >= 0 else "#f87171"

        v_chg_html = f'<div class="stat-change" style="color:{chg_color_v}">{v_chg}</div>' if v_chg else ""
        l_chg_html = f'<div class="stat-change" style="color:{chg_color_l}">{l_chg}</div>' if l_chg else ""
        c_chg_html = f'<div class="stat-change" style="color:{chg_color_c}">{c_chg}</div>' if c_chg else ""

        # Build hourly chart bars (pure CSS)
        chart_labels, chart_deltas = self._compute_hourly_deltas()
        # Projection: average of last 3 hours (or fewer if not enough data)
        projection = 0
        if chart_deltas:
            recent = chart_deltas[-3:] if len(chart_deltas) >= 3 else chart_deltas
            projection = int(sum(recent) / len(recent))

        all_values = chart_deltas + ([projection] if projection > 0 else [])
        max_delta = max(all_values) if all_values else 1
        chart_bars_html = ""
        if chart_deltas:
            bars = []
            for i, (label, delta) in enumerate(zip(chart_labels, chart_deltas)):
                pct = max(int((delta / max_delta) * 100), 4) if max_delta > 0 else 4
                val_label = format_k(delta) if delta > 0 else ""
                bars.append(
                    f'<div class="bar-col">'
                    f'<div class="bar-val">{val_label}</div>'
                    f'<div class="bar" style="height:{pct}%"></div>'
                    f'<div class="bar-label">{label}</div>'
                    f'</div>'
                )
            # Add projection bar (next 4h window)
            if projection > 0:
                # Parse end hour from last label like "4p-8p"
                last_lbl = chart_labels[-1] if chart_labels else ""
                _parts = last_lbl.split("-")
                if len(_parts) == 2:
                    _end_part = _parts[1]  # e.g. "8p"
                    _eh = int(_end_part[:-1])
                    _eap = _end_part[-1]
                    _end24 = (_eh + 12) if _eap == 'p' and _eh != 12 else (0 if _eap == 'a' and _eh == 12 else _eh)
                    _next_end = (_end24 + 4) % 24
                    _fh = lambda h: f"{h % 12 or 12}{'p' if h >= 12 else 'a'}"
                    next_label = f"~{_fh(_end24)}-{_fh(_next_end)}"
                else:
                    next_label = "~next"
                proj_pct = max(int((projection / max_delta) * 100), 4)
                proj_val = f"~{format_k(projection)}"
                bars.append(
                    f'<div class="bar-col">'
                    f'<div class="bar-val bar-val-proj">{proj_val}</div>'
                    f'<div class="bar bar-proj" style="height:{proj_pct}%"></div>'
                    f'<div class="bar-label">{next_label}</div>'
                    f'</div>'
                )
            # Compute SVG trendline over the real bars (exclude projection)
            trend_svg = ""
            n_real = len(chart_deltas)
            if n_real >= 2 and max_delta > 0:
                n_total = n_real + (1 if projection > 0 else 0)
                sum_x = sum(range(n_real))
                sum_y = sum(chart_deltas)
                sum_xy = sum(i * v for i, v in enumerate(chart_deltas))
                sum_x2 = sum(i * i for i in range(n_real))
                slope = (n_real * sum_xy - sum_x * sum_y) / (n_real * sum_x2 - sum_x * sum_x)
                intercept = (sum_y - slope * sum_x) / n_real
                # Linear regression: just need start and end points
                y_start = max(0, intercept)
                y_end = max(0, slope * (n_real - 1) + intercept)
                # X: center of first and last real bar columns
                x1_pct = 0.5 / n_total * 100
                x2_pct = (n_real - 0.5) / n_total * 100
                # Y: percentage of max_delta, inverted for SVG (top=0)
                y1_pct = max(4, min(100, y_start / max_delta * 100))
                y2_pct = max(4, min(100, y_end / max_delta * 100))
                y1_px = 200 - (y1_pct / 100 * 200)
                y2_px = 200 - (y2_pct / 100 * 200)
                trend_svg = (
                    f'<svg class="trend-svg" xmlns="http://www.w3.org/2000/svg">'
                    f'<line x1="{x1_pct:.1f}%" y1="{y1_px:.0f}" x2="{x2_pct:.1f}%" y2="{y2_px:.0f}" /></svg>'
                )

            chart_bars_html = f"""
        <div class="chart-section">
            <div class="chart-title">Views per 4 Hours</div>
            <div class="chart-row-wrap">
                <div class="chart-row">{"".join(bars)}</div>
                {trend_svg}
            </div>
        </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    height: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border-radius: 0;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}
.bg-image {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: brightness(0.3) blur(2px);
    transform: scale(1.1);
}}
.bg-overlay {{
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg,
        rgba(15,23,42,0.6) 0%,
        rgba(15,23,42,0.4) 25%,
        rgba(15,23,42,0.7) 55%,
        rgba(15,23,42,0.95) 100%);
}}
.content {{
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 60px 24px;
    text-align: center;
}}
.header-row {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 32px;
}}
.yt-icon {{
    width: 48px;
    height: 34px;
    background: #ff0000;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.yt-icon::after {{
    content: '';
    display: block;
    width: 0; height: 0;
    border-left: 15px solid white;
    border-top: 9px solid transparent;
    border-bottom: 9px solid transparent;
    margin-left: 3px;
}}
.title {{
    font-size: 64px;
    font-weight: 900;
    color: #fff;
    letter-spacing: 6px;
    line-height: 1;
    text-shadow: 0 4px 20px rgba(0,0,0,0.5);
}}
.artist {{
    font-size: 22px;
    color: rgba(255,255,255,0.5);
    font-weight: 600;
    letter-spacing: 4px;
    text-transform: uppercase;
}}
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    width: 100%;
    max-width: 780px;
    margin-bottom: 0;
}}
.stat-box {{
    text-align: center;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 24px 16px;
}}
.stat-value {{
    font-size: 40px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -1px;
    line-height: 1.1;
}}
.stat-label {{
    font-size: 12px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 6px;
}}
.stat-change {{
    font-size: 16px;
    font-weight: 600;
    margin-top: 4px;
}}
/* ── Hourly chart ── */
.chart-section {{
    width: 100%;
    max-width: 780px;
    margin-top: 28px;
}}
.chart-title {{
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 600;
    margin-bottom: 12px;
    text-align: left;
}}
.chart-row-wrap {{
    position: relative;
    height: 200px;
    width: 100%;
}}
.chart-row {{
    display: flex;
    align-items: flex-end;
    gap: 10px;
    height: 200px;
    width: 100%;
}}
.trend-svg {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 200px;
    pointer-events: none;
}}
.trend-svg line {{
    stroke: rgba(251,191,36,0.5);
    stroke-width: 2px;
    stroke-dasharray: 6 3;
}}
.bar-col {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    height: 100%;
    min-width: 0;
}}
.bar {{
    width: 60%;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(56,189,248,0.9) 0%, rgba(59,130,246,0.5) 100%);
    min-height: 4px;
}}
.bar-val {{
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.7);
    margin-bottom: 4px;
    white-space: nowrap;
}}
.bar-label {{
    font-size: 9px;
    color: rgba(255,255,255,0.35);
    margin-top: 5px;
    font-weight: 500;
}}
.bar-proj {{
    background: none;
    border: 2px dashed rgba(56,189,248,0.5);
    opacity: 0.7;
}}
.bar-val-proj {{
    color: rgba(56,189,248,0.6);
    font-style: italic;
}}
.footer {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 20px 60px 28px;
    border-top: 1px solid rgba(255,255,255,0.06);
}}
.footer-text {{
    font-size: 14px;
    color: #64748b;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    {"<img src='" + bg_data_uri + "' class='bg-image' />" if bg_data_uri else ""}
    <div class="bg-overlay"></div>
    <div class="content">
        <div class="header-row">
            <div class="yt-icon"></div>
            <div class="title">VISA</div>
            <div class="artist">&nbsp;&middot;&nbsp;SB19</div>
        </div>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{v_str}</div>
                <div class="stat-label">Views</div>
                {v_chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{l_str}</div>
                <div class="stat-label">Likes</div>
                {l_chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{c_str}</div>
                <div class="stat-label">Comments</div>
                {c_chg_html}
            </div>
        </div>{chart_bars_html}
    </div>
    <div class="footer">
        <div class="footer-text">As of {now_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_yt_visa_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 1200)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(YT_VISA_IMAGE_PATH)

                img = Image.open(YT_VISA_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(YT_VISA_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Screenshot saved: {YT_VISA_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Card screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    # -- Spotify VISA daily ---------------------------------------------------

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
        ok = self._capture_spotify_visa_screenshot(
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

    def _capture_spotify_visa_screenshot(self, total_streams, daily_gain,
                                         stream_change, daily_labels,
                                         daily_deltas, now_str):
        """Capture a Spotify VISA daily stats card (similar to YouTube VISA card)."""
        print("[INFO] Capturing Spotify VISA screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        # Encode VISA artwork as base64 for the card background
        visa_img_path = os.path.join(SCRIPT_DIR, "photos", "visa.png")
        bg_data_uri = ""
        if os.path.exists(visa_img_path):
            with open(visa_img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                bg_data_uri = f"data:image/png;base64,{b64}"

        def format_k(v):
            if v >= 1_000_000:
                return f"{v / 1_000_000:.1f}M"
            if v >= 1_000:
                return f"{v / 1_000:.1f}K"
            return str(v)

        total_str = f"{total_streams:,}"
        daily_str = f"{daily_gain:,}"

        if stream_change > 0:
            chg_str = f"+{stream_change:,}"
            chg_color = "#1db954"
        elif stream_change < 0:
            chg_str = f"{stream_change:,}"
            chg_color = "#f87171"
        else:
            chg_str = ""
            chg_color = "#1db954"

        chg_html = f'<div class="stat-change" style="color:{chg_color}">{chg_str}</div>' if chg_str else ""

        # Build daily chart bars
        max_delta = max(daily_deltas) if daily_deltas else 1
        chart_bars_html = ""
        if daily_deltas:
            bars = []
            for label, delta in zip(daily_labels, daily_deltas):
                pct = max(int((delta / max_delta) * 100), 4) if max_delta > 0 else 4
                val_label = format_k(delta) if delta > 0 else ""
                bars.append(
                    f'<div class="bar-col">'
                    f'<div class="bar-val">{val_label}</div>'
                    f'<div class="bar" style="height:{pct}%"></div>'
                    f'<div class="bar-label">{label}</div>'
                    f'</div>'
                )

            # Trendline SVG
            trend_svg = ""
            n_real = len(daily_deltas)
            if n_real >= 2 and max_delta > 0:
                sum_x = sum(range(n_real))
                sum_y = sum(daily_deltas)
                sum_xy = sum(i * v for i, v in enumerate(daily_deltas))
                sum_x2 = sum(i * i for i in range(n_real))
                denom = n_real * sum_x2 - sum_x * sum_x
                if denom != 0:
                    slope = (n_real * sum_xy - sum_x * sum_y) / denom
                    intercept = (sum_y - slope * sum_x) / n_real
                    y_start = max(0, intercept)
                    y_end = max(0, slope * (n_real - 1) + intercept)
                    x1_pct = 0.5 / n_real * 100
                    x2_pct = (n_real - 0.5) / n_real * 100
                    y1_pct = max(4, min(100, y_start / max_delta * 100))
                    y2_pct = max(4, min(100, y_end / max_delta * 100))
                    y1_px = 200 - (y1_pct / 100 * 200)
                    y2_px = 200 - (y2_pct / 100 * 200)
                    trend_svg = (
                        f'<svg class="trend-svg" xmlns="http://www.w3.org/2000/svg">'
                        f'<line x1="{x1_pct:.1f}%" y1="{y1_px:.0f}" x2="{x2_pct:.1f}%" y2="{y2_px:.0f}" /></svg>'
                    )

            chart_bars_html = f"""
        <div class="chart-section">
            <div class="chart-title">Daily Streams</div>
            <div class="chart-row-wrap">
                <div class="chart-row">{"".join(bars)}</div>
                {trend_svg}
            </div>
        </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    height: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border-radius: 0;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}
.bg-image {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: brightness(0.3) blur(2px);
    transform: scale(1.1);
}}
.bg-overlay {{
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg,
        rgba(15,23,42,0.6) 0%,
        rgba(15,23,42,0.4) 25%,
        rgba(15,23,42,0.7) 55%,
        rgba(15,23,42,0.95) 100%);
}}
.content {{
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 60px 24px;
    text-align: center;
}}
.header-row {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 32px;
}}
.sp-icon {{
    width: 48px;
    height: 48px;
    background: #1db954;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.sp-icon svg {{
    width: 28px;
    height: 28px;
    fill: white;
}}
.title {{
    font-size: 64px;
    font-weight: 900;
    color: #fff;
    letter-spacing: 6px;
    line-height: 1;
    text-shadow: 0 4px 20px rgba(0,0,0,0.5);
}}
.artist {{
    font-size: 22px;
    color: rgba(255,255,255,0.5);
    font-weight: 600;
    letter-spacing: 4px;
    text-transform: uppercase;
}}
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 24px;
    width: 100%;
    max-width: 580px;
    margin-bottom: 0;
}}
.stat-box {{
    text-align: center;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 24px 16px;
}}
.stat-value {{
    font-size: 40px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -1px;
    line-height: 1.1;
}}
.stat-label {{
    font-size: 12px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 6px;
}}
.stat-change {{
    font-size: 16px;
    font-weight: 600;
    margin-top: 4px;
}}
/* ── Daily chart ── */
.chart-section {{
    width: 100%;
    max-width: 780px;
    margin-top: 28px;
}}
.chart-title {{
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 600;
    margin-bottom: 12px;
    text-align: left;
}}
.chart-row-wrap {{
    position: relative;
    height: 200px;
    width: 100%;
}}
.chart-row {{
    display: flex;
    align-items: flex-end;
    gap: 10px;
    height: 200px;
    width: 100%;
}}
.trend-svg {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 200px;
    pointer-events: none;
}}
.trend-svg line {{
    stroke: rgba(251,191,36,0.5);
    stroke-width: 2px;
    stroke-dasharray: 6 3;
}}
.bar-col {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    height: 100%;
    min-width: 0;
}}
.bar {{
    width: 60%;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(29,185,84,0.9) 0%, rgba(29,185,84,0.4) 100%);
    min-height: 4px;
}}
.bar-val {{
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.7);
    margin-bottom: 4px;
    white-space: nowrap;
}}
.bar-label {{
    font-size: 9px;
    color: rgba(255,255,255,0.35);
    margin-top: 5px;
    font-weight: 500;
}}
.footer {{
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 20px 60px 28px;
    border-top: 1px solid rgba(255,255,255,0.06);
}}
.footer-text {{
    font-size: 14px;
    color: #64748b;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #1db954;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    {"<img src='" + bg_data_uri + "' class='bg-image' />" if bg_data_uri else ""}
    <div class="bg-overlay"></div>
    <div class="content">
        <div class="header-row">
            <div class="sp-icon"><svg viewBox="0 0 24 24"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg></div>
            <div class="title">VISA</div>
            <div class="artist">&nbsp;&middot;&nbsp;SB19</div>
        </div>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Streams</div>
                {chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{daily_str}</div>
                <div class="stat-label">Daily Gain</div>
            </div>
        </div>{chart_bars_html}
    </div>
    <div class="footer">
        <div class="footer-text">As of {now_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_sp_visa_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 1200)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(SPOTIFY_VISA_IMAGE_PATH)

                img = Image.open(SPOTIFY_VISA_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(SPOTIFY_VISA_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Screenshot saved: {SPOTIFY_VISA_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Card screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    def _capture_album_screenshot(self, track_list=None, total_streams=0,
                                    total_change=0, date_str=""):
        """Capture a social-media-friendly album card screenshot."""
        print("[INFO] Capturing album screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not track_list:
            print("[ERR] No track data for album card")
            return False

        # Build custom HTML social card
        max_streams = max(t["streams"] for t in track_list) if track_list else 1
        # Bar colors cycling through a vibrant palette
        bar_colors = [
            "#ec4899", "#6366f1", "#10b981", "#f59e0b", "#a855f7",
            "#eab308", "#ef4444", "#14b8a6", "#3b82f6", "#f97316",
            "#8b5cf6", "#06b6d4", "#84cc16", "#e11d4f", "#0ea5e9",
            "#d946ef", "#22c55e", "#fb923c", "#64748b",
        ]

        track_rows = ""
        for i, t in enumerate(track_list):
            pct = (t["streams"] / max_streams) * 100
            color = bar_colors[i % len(bar_colors)]
            change_str = f"+{t['change']:,}" if t["change"] > 0 else f"{t['change']:,}"
            track_rows += f"""
            <div class="track-row">
                <div class="track-rank">{i + 1}</div>
                <div class="track-info">
                    <div class="track-name">{t['name']}</div>
                    <div class="track-bar-container">
                        <div class="track-bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                </div>
                <div class="track-stats">
                    <div class="track-streams">{t['streams']:,}</div>
                    <div class="track-change">{change_str}</div>
                </div>
            </div>"""

        total_str = f"{total_streams:,}"
        change_display = f"+{total_change:,}" if total_change > 0 else f"{total_change:,}"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.album-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 18px;
    letter-spacing: -0.3px;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
}}
.stat-box {{
    text-align: center;
}}
.stat-value {{
    font-size: 38px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.stat-change {{
    font-size: 38px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.tracks {{
    display: flex;
    flex-direction: column;
    gap: 8px;
}}
.track-row {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 9px 0;
}}
.track-rank {{
    font-size: 18px;
    font-weight: 700;
    color: #475569;
    width: 30px;
    text-align: right;
    flex-shrink: 0;
}}
.track-info {{
    flex: 1;
    min-width: 0;
}}
.track-name {{
    font-size: 19px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.track-bar-container {{
    height: 8px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 3px;
    overflow: hidden;
}}
.track-bar {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
}}
.track-stats {{
    text-align: right;
    flex-shrink: 0;
    min-width: 120px;
}}
.track-streams {{
    font-size: 19px;
    font-weight: 700;
    color: #f1f5f9;
}}
.track-change {{
    font-size: 14px;
    color: #10b981;
    font-weight: 500;
}}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
.track-row:nth-child(even) {{
    filter: blur(3px);
    opacity: 0.7;
}}
.cta-footer {{
    text-align: center;
    margin-top: 20px;
    font-size: 16px;
    color: #94a3b8;
    font-weight: 500;
    letter-spacing: 0.3px;
}}
.cta-footer span {{
    color: #3b82f6;
    font-weight: 700;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="album-title">Simula at Wakas Tour Kickoff Concert Album</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-change">{change_display}</div>
                <div class="stat-label">Daily Change</div>
            </div>
        </div>
    </div>
    <div class="tracks">{track_rows}
    </div>
    <div class="cta-footer">Full details at <span>opminsights.com</span></div>
    <div class="footer">
        <div class="footer-text">As of {date_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        # Write temp HTML file
        temp_html = os.path.join(SCRIPT_DIR, "_album_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 1800)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(ALBUM_IMAGE_PATH)

                img = Image.open(ALBUM_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(ALBUM_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Screenshot saved: {ALBUM_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Card screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    def _capture_listeners_screenshot(self, artist_data, date_str):
        """Capture a social-media-friendly monthly listeners card screenshot.

        Args:
            artist_data: List of dicts with 'artist', 'listeners', 'change' keys.
            date_str: Formatted date string for the card subtitle.

        Returns:
            True on success, False on failure.
        """
        print("[INFO] Capturing monthly listeners screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not artist_data:
            print("[ERR] No artist data for listeners card")
            return False

        # Embed member photos as base64 data URIs
        photo_data_uris = {}
        for artist_name, photo_file in MEMBER_PHOTO_FILES.items():
            photo_path = os.path.join(MEMBER_PHOTOS_DIR, photo_file)
            if os.path.exists(photo_path):
                with open(photo_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = photo_file.rsplit(".", 1)[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                photo_data_uris[artist_name] = f"data:{mime};base64,{b64}"

        max_listeners = max(d["listeners"] for d in artist_data) if artist_data else 1

        # Build artist rows HTML
        artist_rows = ""
        for d in artist_data:
            # Match artist name case-insensitively for photo/color lookup
            matched_key = None
            for key in MEMBER_PHOTO_FILES:
                if key.upper() == d["artist"].upper():
                    matched_key = key
                    break
            photo_uri = photo_data_uris.get(matched_key, "")
            color = MEMBER_BAR_COLORS.get(matched_key, "#3b82f6")
            pct = (d["listeners"] / max_listeners) * 100
            listeners_str = f"{d['listeners']:,}"
            change = d["change"]
            if change > 0:
                change_str = f"+{change:,}"
                change_color = "#10b981"
            elif change < 0:
                change_str = f"{change:,}"
                change_color = "#ef4444"
            else:
                change_str = "0"
                change_color = "#64748b"

            photo_html = ""
            if photo_uri:
                photo_html = f'<img class="artist-photo" src="{photo_uri}" alt="{d["artist"]}" />'
            else:
                photo_html = f'<div class="artist-photo" style="background:{color};"></div>'

            is_solo = d["artist"].upper() != "SB19"
            row_class = "artist-row solo" if is_solo else "artist-row"
            artist_rows += f"""
            <div class="{row_class}">
                <div class="artist-left">
                    {photo_html}
                    <div class="artist-name">{d['artist']}</div>
                </div>
                <div class="artist-middle">
                    <div class="bar-container">
                        <div class="bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                </div>
                <div class="artist-right">
                    <div class="artist-listeners">{listeners_str}</div>
                    <div class="artist-change" style="color: {change_color};">{change_str}</div>
                </div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 40px;
    padding-bottom: 32px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 32px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-title .spotify {{
    color: #1db954;
}}
.card-date {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.artists {{
    display: flex;
    flex-direction: column;
    gap: 24px;
}}
.artist-row {{
    display: flex;
    align-items: center;
    gap: 20px;
}}
.artist-left {{
    display: flex;
    align-items: center;
    gap: 16px;
    width: 240px;
    flex-shrink: 0;
}}
.artist-photo {{
    width: 64px;
    height: 64px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    border: 2px solid rgba(148, 163, 184, 0.2);
}}
.artist-name {{
    font-size: 22px;
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
}}
.artist-middle {{
    flex: 1;
    min-width: 0;
}}
.bar-container {{
    height: 28px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 6px;
    overflow: hidden;
}}
.bar {{
    height: 100%;
    border-radius: 6px;
}}
.artist-right {{
    text-align: right;
    flex-shrink: 0;
    min-width: 160px;
}}
.artist-listeners {{
    font-size: 24px;
    font-weight: 700;
    color: #f1f5f9;
}}
.artist-change {{
    font-size: 16px;
    font-weight: 500;
    margin-top: 2px;
}}
.footer {{
    text-align: center;
    margin-top: 36px;
    padding-top: 24px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
/* SB19 row: double-sized photo, labels, and bar */
.artist-row:not(.solo) .artist-photo {{
    width: 128px;
    height: 128px;
    border: 3px solid rgba(59, 130, 246, 0.8);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.4), 0 0 40px rgba(59, 130, 246, 0.15);
}}
.artist-row:not(.solo) .artist-name {{
    font-size: 44px;
}}
.artist-row:not(.solo) .bar-container {{
    height: 56px;
    border-radius: 10px;
}}
.artist-row:not(.solo) .bar {{
    border-radius: 10px;
}}
.artist-row:not(.solo) .artist-listeners {{
    font-size: 48px;
}}
.artist-row:not(.solo) .artist-change {{
    font-size: 32px;
}}
.artist-row:not(.solo) .artist-left {{
    width: 360px;
}}
.artist-row.solo .artist-photo {{
    margin-left: 32px;
}}
.artist-row.solo .artist-middle,
.artist-row.solo .artist-right {{
    filter: blur(6px);
    opacity: 0.25;
}}
.cta-footer {{
    text-align: center;
    margin-top: 20px;
    font-size: 16px;
    color: #94a3b8;
    font-weight: 500;
    letter-spacing: 0.3px;
}}
.cta-footer span {{
    color: #3b82f6;
    font-weight: 700;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Monthly Listeners on <span class="spotify">Spotify</span></div>
        <div class="card-date">As of {date_str}</div>
    </div>
    <div class="artists">{artist_rows}
    </div>
    <div class="cta-footer">Full details at <span>opminsights.com</span></div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

        temp_html = os.path.join(SCRIPT_DIR, "_listeners_card.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)

        try:
            options = EdgeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--force-device-scale-factor=2")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = EdgeService()
            driver = None
            try:
                driver = webdriver.Edge(service=service, options=options)
                driver.set_window_size(1200, 1000)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(LISTENERS_IMAGE_PATH)

                img = Image.open(LISTENERS_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(LISTENERS_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Listeners screenshot saved: {LISTENERS_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Listeners card screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Listeners screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    # ======================================================================
    # Status & preview
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
  python social_media_agent.py album                     # Post album update with screenshot
  python social_media_agent.py custom "Hello world!"     # Post a custom message
  python social_media_agent.py preview                   # Preview all pending posts
  python social_media_agent.py status                    # Show data readiness
  python social_media_agent.py init-milestones           # Initialize milestone log
  python social_media_agent.py listeners --dry-run       # Preview without posting
  python social_media_agent.py solo-top                  # Post top tracks for each solo member
  python social_media_agent.py solo-top --artist PABLO   # Post only PABLO's top tracks
  python social_media_agent.py youtube-visa              # Post VISA MV YouTube stats
  python social_media_agent.py youtube-visa --dry-run    # Preview YouTube VISA post
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
            "album", "solo-top", "opm-top", "opm-top-tracks", "opm-top-streams", "ppop-top",
            "youtube-visa", "spotify-visa",
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

        elif args.command == "youtube-visa":
            message, auto_image = agent.generate_youtube_visa_post()
            if not message:
                print("[ERR] Could not generate YouTube VISA post.")
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
