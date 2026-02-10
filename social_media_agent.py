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
SOLO_TOP_N = 5

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

        if latest_date_str:
            lines = [
                f"A'TIN! Here's SB19's Monthly Listeners on Spotify as of {latest_date_str}. See full details at opminsights.com",
                "",
            ]
        else:
            lines = [
                "A'TIN! Here's SB19's Monthly Listeners on Spotify! See full details at opminsights.com",
                "",
            ]

        for entry in latest_data:
            handle = ""
            for name, h in X_HANDLES.items():
                if name.upper() == entry["artist"].upper():
                    handle = h
                    break
            listener_str = format_with_commas(entry["listeners"])
            change_str = f"({format_change(entry['change'])})"
            lines.append(f"{entry['artist']} {handle}: {listener_str} {change_str}")

        lines.append("")
        lines.append("#SB19 #SB19Spotify #PPop #ATIN #OPM")
        message = "\n".join(lines)

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

        top = gains[:5]
        lines = [f"SB19 Daily Stream Update - {date_formatted}", ""]
        lines.append("Top Gainers:")
        for i, g in enumerate(top, 1):
            lines.append(f"{i}. {g['song']} ({g['artist']}): {format_change(g['change'], use_commas=False)}")
        lines.append("")
        lines.append("#SB19 #SB19Spotify")
        return "\n".join(lines)

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
        top = gains[:10]
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

        # Text post
        lines = [
            f"SB19 Top 10 Tracks by Daily Streams - {date_formatted}",
            "opminsights.com",
            "",
        ]
        for i, g in enumerate(top, 1):
            # Rank indicator
            rc = g["rank_change"]
            if rc is not None and rc > 0:
                rank_ind = f" (+{rc})"
            elif rc is not None and rc < 0:
                rank_ind = f" (-{abs(rc)})"
            elif rc == 0 and g["streak"] > 1:
                rank_ind = f" ({g['streak']}d)"
            else:
                rank_ind = ""
            lines.append(
                f"{i:>2}. {g['song']}: {format_change(g['change'], use_commas=False)} "
                f"({format_number(g['streams'])} total){rank_ind}"
            )
        lines.append("")
        lines.append(f"Total added: {format_change(total_added, use_commas=False)}")
        lines.append("")
        lines.append("#SB19 #SB19Spotify #PPop #ATIN #OPM")
        message = "\n".join(lines)

        # Capture screenshot
        image_path = None
        screenshot_ok = self._capture_top10_screenshot(
            track_list=top,
            total_added=total_added,
            date_str=date_formatted,
        )
        if screenshot_ok and os.path.exists(TOP10_IMAGE_PATH):
            image_path = TOP10_IMAGE_PATH

        return message, image_path

    def _capture_top10_screenshot(self, track_list=None, total_added=0, date_str=""):
        """Capture a social-media-friendly top 10 daily streams card."""
        print("[INFO] Capturing top 10 streams screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not track_list:
            print("[ERR] No track data for top 10 card")
            return False

        max_change = max(t["change"] for t in track_list) if track_list else 1
        if max_change <= 0:
            max_change = 1

        bar_colors = [
            "#3b82f6", "#6366f1", "#ec4899", "#10b981", "#f59e0b",
            "#a855f7", "#ef4444", "#14b8a6", "#f97316", "#8b5cf6",
        ]

        track_rows = ""
        for i, t in enumerate(track_list):
            pct = (t["change"] / max_change) * 100 if t["change"] > 0 else 0
            color = bar_colors[i % len(bar_colors)]
            change_str = f"+{t['change']:,}" if t["change"] > 0 else f"{t['change']:,}"
            streams_str = f"{t['streams']:,}"

            # Rank change indicator
            rc = t.get("rank_change")
            streak = t.get("streak", 1)
            if rc is not None and rc > 0:
                rank_ind_html = f'<span class="rank-up">▲{rc}</span>'
            elif rc is not None and rc < 0:
                rank_ind_html = f'<span class="rank-down">▼{abs(rc)}</span>'
            elif rc == 0 and streak > 1:
                rank_ind_html = f'<span class="rank-same">{streak}d</span>'
            else:
                rank_ind_html = '<span class="rank-same">―</span>'

            track_rows += f"""
            <div class="track-row">
                <div class="track-rank">{i + 1}</div>
                <div class="rank-indicator">{rank_ind_html}</div>
                <div class="track-info">
                    <div class="track-name">{t['song']}</div>
                    <div class="track-bar-container">
                        <div class="track-bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                </div>
                <div class="track-stats">
                    <div class="track-change">{change_str}</div>
                    <div class="track-streams">{streams_str}</div>
                </div>
            </div>"""

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
.stat-box {{
    text-align: center;
}}
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
.tracks {{
    display: flex;
    flex-direction: column;
    gap: 6px;
}}
.track-row {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 0;
}}
.track-rank {{
    font-size: 20px;
    font-weight: 700;
    color: #475569;
    width: 32px;
    text-align: right;
    flex-shrink: 0;
}}
.track-row:nth-child(1) .track-rank {{ color: #fbbf24; }}
.track-row:nth-child(2) .track-rank {{ color: #94a3b8; }}
.track-row:nth-child(3) .track-rank {{ color: #cd7f32; }}
.rank-indicator {{
    width: 42px;
    text-align: center;
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 600;
}}
.rank-up {{
    color: #34d399;
}}
.rank-down {{
    color: #f87171;
}}
.rank-same {{
    color: #9ca3af;
}}
.track-info {{
    flex: 1;
    min-width: 0;
}}
.track-name {{
    font-size: 18px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.track-bar-container {{
    height: 30px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 6px;
    overflow: hidden;
}}
.track-bar {{
    height: 100%;
    border-radius: 6px;
}}
.track-stats {{
    text-align: right;
    flex-shrink: 0;
    min-width: 140px;
}}
.track-change {{
    font-size: 20px;
    font-weight: 700;
    color: #10b981;
}}
.track-streams {{
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
    margin-top: 2px;
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
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Top 10 Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="tracks">{track_rows}
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
                driver.set_window_size(1200, 1600)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(TOP10_IMAGE_PATH)

                img = Image.open(TOP10_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(TOP10_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Top 10 screenshot saved: {TOP10_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Top 10 screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Top 10 screenshot setup failed: {e}")
            return False
        finally:
            try:
                os.remove(temp_html)
            except OSError:
                pass

    def _capture_solo_top10_screenshot(self, track_list=None, total_added=0, date_str=""):
        """Capture a social-media-friendly solo top 10 daily streams card."""
        print("[INFO] Capturing solo top 10 streams screenshot...")
        os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

        if not track_list:
            print("[ERR] No track data for solo top 10 card")
            return False

        max_change = max(t["change"] for t in track_list) if track_list else 1
        if max_change <= 0:
            max_change = 1

        track_rows = ""
        for i, t in enumerate(track_list):
            pct = (t["change"] / max_change) * 100 if t["change"] > 0 else 0
            color = MEMBER_BAR_COLORS.get(t["artist"], "#3b82f6")
            change_str = f"+{t['change']:,}" if t["change"] > 0 else f"{t['change']:,}"
            streams_str = f"{t['streams']:,}"

            # Rank change indicator
            rc = t.get("rank_change")
            streak = t.get("streak", 1)
            if rc is not None and rc > 0:
                rank_ind_html = f'<span class="rank-up">&#9650;{rc}</span>'
            elif rc is not None and rc < 0:
                rank_ind_html = f'<span class="rank-down">&#9660;{abs(rc)}</span>'
            elif rc == 0 and streak > 1:
                rank_ind_html = f'<span class="rank-same">{streak}d</span>'
            else:
                rank_ind_html = '<span class="rank-same">&#8213;</span>'

            # Artist badge (colored pill)
            badge_html = (
                f'<span class="artist-badge" style="background: {color};">'
                f'{t["artist"]}</span>'
            )

            track_rows += f"""
            <div class="track-row">
                <div class="track-rank">{i + 1}</div>
                <div class="rank-indicator">{rank_ind_html}</div>
                <div class="track-info">
                    <div class="track-name-row">
                        <span class="track-name">{t['song']}</span>
                        {badge_html}
                    </div>
                    <div class="track-bar-container">
                        <div class="track-bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                </div>
                <div class="track-stats">
                    <div class="track-change">{change_str}</div>
                    <div class="track-streams">{streams_str}</div>
                </div>
            </div>"""

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
.stat-box {{
    text-align: center;
}}
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
.tracks {{
    display: flex;
    flex-direction: column;
    gap: 6px;
}}
.track-row {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 0;
}}
.track-rank {{
    font-size: 20px;
    font-weight: 700;
    color: #475569;
    width: 32px;
    text-align: right;
    flex-shrink: 0;
}}
.track-row:nth-child(1) .track-rank {{ color: #fbbf24; }}
.track-row:nth-child(2) .track-rank {{ color: #94a3b8; }}
.track-row:nth-child(3) .track-rank {{ color: #cd7f32; }}
.rank-indicator {{
    width: 42px;
    text-align: center;
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 600;
}}
.rank-up {{
    color: #34d399;
}}
.rank-down {{
    color: #f87171;
}}
.rank-same {{
    color: #9ca3af;
}}
.track-info {{
    flex: 1;
    min-width: 0;
}}
.track-name-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 5px;
}}
.track-name {{
    font-size: 18px;
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
.track-bar-container {{
    height: 30px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 6px;
    overflow: hidden;
}}
.track-bar {{
    height: 100%;
    border-radius: 6px;
}}
.track-stats {{
    text-align: right;
    flex-shrink: 0;
    min-width: 140px;
}}
.track-change {{
    font-size: 20px;
    font-weight: 700;
    color: #10b981;
}}
.track-streams {{
    font-size: 14px;
    color: #64748b;
    font-weight: 500;
    margin-top: 2px;
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
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Solo Top 10 Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="tracks">{track_rows}
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
                driver.set_window_size(1200, 1600)

                driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                time.sleep(3)

                card = driver.find_element(By.ID, "card")
                card.screenshot(SOLO_TOP10_IMAGE_PATH)

                img = Image.open(SOLO_TOP10_IMAGE_PATH)
                if img.width > 2400:
                    ratio = 2400 / img.width
                    img = img.resize((2400, int(img.height * ratio)), Image.LANCZOS)
                    img.save(SOLO_TOP10_IMAGE_PATH)
                print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                print(f"[SUCCESS] Solo top 10 screenshot saved: {SOLO_TOP10_IMAGE_PATH}")
                return True
            except Exception as e:
                print(f"[ERR] Solo top 10 screenshot failed: {e}")
                return False
            finally:
                if driver:
                    driver.quit()
        except Exception as e:
            print(f"[ERR] Solo top 10 screenshot setup failed: {e}")
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

        # Annotate top 10 with rank change and streak info
        top = gains[:10]
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

        # Text post
        lines = [
            f"SB19 Solo Top 10 Tracks by Daily Streams - {date_formatted}",
            "opminsights.com",
            "",
        ]
        for i, g in enumerate(top, 1):
            rc = g["rank_change"]
            if rc is not None and rc > 0:
                rank_ind = f" (+{rc})"
            elif rc is not None and rc < 0:
                rank_ind = f" (-{abs(rc)})"
            elif rc == 0 and g["streak"] > 1:
                rank_ind = f" ({g['streak']}d)"
            else:
                rank_ind = ""
            lines.append(
                f"{i:>2}. {g['song']} ({g['artist']}): {format_change(g['change'], use_commas=False)} "
                f"({format_number(g['streams'])} total){rank_ind}"
            )
        lines.append("")
        lines.append(f"Total added: {format_change(total_added, use_commas=False)}")
        lines.append("")
        lines.append("#SB19 #SB19Spotify #PPop #ATIN #OPM")
        message = "\n".join(lines)

        # Capture screenshot
        image_path = None
        screenshot_ok = self._capture_solo_top10_screenshot(
            track_list=top,
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
                        f"MILESTONE ACHIEVED!\n\n"
                        f"\"{song}\" by {artist} has surpassed {label} streams on Spotify!\n\n"
                        f"Current streams: {format_number(streams)}\n\n"
                        f"#SB19 #SB19Spotify #{artist.replace(' ', '')}"
                    )
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
                f"TRENDING!\n\n"
                f"\"{spike['song']}\" by {spike['artist']} is on fire!\n\n"
                f"+{format_number(spike['change'])} streams ({spike['pct']:.1f}% increase)\n\n"
                f"Total: {format_number(spike['streams'])}\n\n"
                f"#SB19 #SB19Spotify"
            )
            posts.append(msg)
        return posts

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

        lines = ["SB19 Weekly Listener Recap", ""]
        for c in changes:
            sign = "+" if c["change"] >= 0 else ""
            lines.append(f"{c['artist']}: {format_number(c['listeners'])} ({sign}{c['pct']:.1f}%)")
        lines.append("")
        lines.append("#SB19 #SB19Spotify")
        return "\n".join(lines)

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

            # Build post for this artist
            handle = X_HANDLES.get(artist, "")
            lines = [
                f"{artist} {handle} Top Tracks on Spotify as of {date_display}",
                "",
            ]

            for rank, (song, streams) in enumerate(latest_tracks[:top_n]):
                streams_str = format_number(streams)
                tenure = rank_tenure.get(song, 1)

                # Daily change
                prev_streams = prev_maps.get((song, artist))
                if prev_streams is not None:
                    change = streams - prev_streams
                    change_str = f" ({format_change(change, use_commas=False)})"
                else:
                    change_str = ""

                if tenure <= 1:
                    tenure_str = "NEW"
                else:
                    tenure_str = f"{tenure}d at #{rank + 1}"

                lines.append(
                    f"{rank + 1}. {song}: {streams_str}{change_str} [{tenure_str}]"
                )

            lines.append("")
            lines.append(f"#SB19 #{artist.replace(' ', '')} #SB19Spotify #OPM")

            posts.append((artist, "\n".join(lines)))

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

        message = (
            f"SB19's Simula at Wakas Tour Kickoff Concert Album has now reached "
            f"{total_str} total streams ({change_str}) as of {date_str}. "
            f"See full details at opminsights.com\n\n"
            f"#SB19 #SB19Spotify #SimulaAtWakas #PPop #ATIN #OPM"
        )

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

            artist_rows += f"""
            <div class="artist-row">
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
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Monthly Listeners on <span class="spotify">Spotify</span></div>
        <div class="card-date">As of {date_str}</div>
    </div>
    <div class="artists">{artist_rows}
    </div>
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

        # 1. Listeners
        print("\n--- MONTHLY LISTENERS ---")
        msg, img = self.generate_listeners_post()
        if msg:
            print(msg)
            print(f"[{len(msg)} chars]")
            if img:
                print(f"[IMAGE] {img}")
        else:
            print("[SKIP] No data")

        # 2. Daily
        print("\n--- DAILY STREAM UPDATE ---")
        msg = self.generate_daily_post()
        if msg:
            print(msg)
            print(f"[{len(msg)} chars]")
        else:
            print("[SKIP] No data")

        # 2b. Top 10
        print("\n--- TOP 10 BY DAILY STREAMS ---")
        msg, img = self.generate_top10_post()
        if msg:
            print(msg)
            print(f"[{len(msg)} chars]")
            if img:
                print(f"[IMAGE] {img}")
        else:
            print("[SKIP] No data")

        # 2c. Solo Top 10
        print("\n--- SOLO TOP 10 BY DAILY STREAMS ---")
        msg, img = self.generate_solo_top10_post()
        if msg:
            print(msg)
            print(f"[{len(msg)} chars]")
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
                print(f"  key: {key}")
                print()
        else:
            print("[SKIP] No new milestones")

        # 4. Spikes
        print("\n--- SPIKES ---")
        spike_posts = self.generate_spikes_posts()
        if spike_posts:
            for s in spike_posts:
                print(s)
                print()
        else:
            print("[SKIP] No significant spikes")

        # 5. Weekly
        print("\n--- WEEKLY SUMMARY ---")
        msg = self.generate_weekly_post()
        if msg:
            print(msg)
            print(f"[{len(msg)} chars]")
        else:
            print("[SKIP] No data")

        # 6. Solo Top Tracks
        print("\n--- SOLO TOP TRACKS ---")
        solo_posts = self.generate_solo_top_posts()
        if solo_posts:
            for artist, msg in solo_posts:
                print(msg)
                print(f"[{len(msg)} chars]")
                print()
        else:
            print("[SKIP] No data")

        # 7. Album
        print("\n--- ALBUM UPDATE ---")
        album_msg, _ = self.generate_album_post()
        if album_msg:
            print(album_msg)
            print(f"[{len(album_msg)} chars]")
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
  python social_media_agent.py custom "msg" --image pic.png
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "listeners", "daily", "top10", "solo-top10", "milestones", "spikes", "weekly",
            "album", "solo-top", "custom", "preview", "status", "init-milestones",
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
    parser.add_argument("--top", type=int, default=5, metavar="N",
                        help="Number of top tracks per artist (default: 5)")

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
