"""
SB19 Automated X (Twitter) Poster

Automatically posts updates about SB19 and member Spotify statistics to X.
Supports:
- Daily stream updates (top gainers)
- Milestone celebrations (10M, 25M, 50M, 75M, 100M+)
- Weekly summaries
- Monthly listener updates
- Significant jump/spike detection

Usage:
    python x_poster.py --daily          # Post daily update
    python x_poster.py --milestones     # Check and post milestones
    python x_poster.py --weekly         # Post weekly summary (run on Sundays)
    python x_poster.py --listeners      # Post monthly listener updates
    python x_poster.py --all            # Run all checks and post
    python x_poster.py --init           # Initialize milestone log (run once on first setup)

Setup:
    1. Create x_config.json with your API credentials
    2. Run --init first to mark existing milestones as already achieved
    3. Run with desired flags
"""

import csv
import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# Optional: tweepy for X API
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("Warning: tweepy not installed. Running in dry-run mode.")
    print("Install with: pip install tweepy")

# File paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STREAMS_FILE = os.path.join(SCRIPT_DIR, "sb19_streams_results.csv")
LISTENERS_FILE = os.path.join(SCRIPT_DIR, "monthly_listeners.csv")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "x_config.json")
POSTED_LOG = os.path.join(SCRIPT_DIR, "x_posted_log.json")

# Milestone thresholds
MILESTONES = [1_000_000, 5_000_000, 10_000_000, 25_000_000, 50_000_000,
              75_000_000, 100_000_000, 150_000_000, 200_000_000, 250_000_000]

# Significant jump threshold (percentage increase in a day)
SPIKE_THRESHOLD_PERCENT = 50  # 50% increase
SPIKE_THRESHOLD_ABSOLUTE = 100_000  # or 100k+ streams in a day

# Main artists to track
MAIN_ARTISTS = ["SB19", "PABLO", "JOSH CULLEN", "Stell", "FELIP", "justin"]


def load_config():
    """Load X API credentials from config file."""
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def get_x_client():
    """Initialize and return tweepy client."""
    config = load_config()
    if not config or not TWEEPY_AVAILABLE:
        return None

    try:
        client = tweepy.Client(
            consumer_key=config["api_key"],
            consumer_secret=config["api_key_secret"],
            access_token=config["access_token"],
            access_token_secret=config["access_token_secret"]
        )
        return client
    except Exception as e:
        print(f"Error initializing X client: {e}")
        return None


def load_posted_log():
    """Load log of already posted milestones to avoid duplicates."""
    if not os.path.exists(POSTED_LOG):
        return {"milestones": {}, "last_daily": None, "last_weekly": None}
    with open(POSTED_LOG, "r") as f:
        return json.load(f)


def save_posted_log(log):
    """Save posted log."""
    with open(POSTED_LOG, "w") as f:
        json.dump(log, f, indent=2)


def load_streams_data():
    """Load and parse streams CSV data."""
    data = []
    if not os.path.exists(STREAMS_FILE):
        print(f"Warning: Streams file not found: {STREAMS_FILE}")
        return data
    with open(STREAMS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                streams = int(row["streams"]) if row["streams"] else 0
                data.append({
                    "timestamp": row["timestamp"],
                    "song_title": row["song_title"],
                    "artist": row["artist"],
                    "album": row["album"],
                    "streams": streams,
                    "date": row["timestamp"][:8]  # YYYYMMDD
                })
            except (ValueError, KeyError):
                continue
    return data


def load_listeners_data():
    """Load and parse monthly listeners CSV data."""
    data = []
    if not os.path.exists(LISTENERS_FILE):
        print(f"Warning: Listeners file not found: {LISTENERS_FILE}")
        return data
    with open(LISTENERS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)  # Auto-detect delimiter (default comma)
        for row in reader:
            try:
                listeners = int(row["monthly_listeners"]) if row["monthly_listeners"] else 0
                timestamp = row.get("timestamp", row.get("data_date", ""))
                data.append({
                    "artist": row["artist_name"],
                    "listeners": listeners,
                    "timestamp": timestamp,
                    "date": str(timestamp)[:8]
                })
            except (ValueError, KeyError) as e:
                continue
    return data


def get_latest_by_track(data):
    """Get the latest entry for each track."""
    latest = {}
    for entry in data:
        key = (entry["song_title"], entry["artist"])
        if key not in latest or entry["streams"] > latest[key]["streams"]:
            latest[key] = entry
    return latest


def get_data_by_date(data, target_date):
    """Get all entries for a specific date."""
    return {(e["song_title"], e["artist"]): e for e in data if e["date"] == target_date}


def get_unique_dates(data):
    """Get sorted list of unique dates in the data."""
    dates = sorted(set(e["date"] for e in data))
    return dates


def format_number(n):
    """Format large numbers for readability."""
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def format_change(change):
    """Format stream change with + sign for positive."""
    if change > 0:
        return f"+{format_number(change)}"
    return format_number(change)


def post_to_x(client, message, dry_run=False):
    """Post a message to X."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Posting to X:")
    print("-" * 50)
    print(message)
    print("-" * 50)
    print(f"Character count: {len(message)}/280")

    if dry_run or not client:
        return True

    try:
        response = client.create_tweet(text=message)
        print(f"Posted successfully! Tweet ID: {response.data['id']}")
        return True
    except Exception as e:
        print(f"Error posting: {e}")
        return False


# =============================================================================
# POST TYPE HANDLERS
# =============================================================================

def check_daily_updates(data, dry_run=False):
    """Generate and post daily stream updates for top gainers."""
    dates = get_unique_dates(data)
    if len(dates) < 2:
        print("Not enough data for daily comparison")
        return []

    today = dates[-1]
    yesterday = dates[-2]

    today_data = get_data_by_date(data, today)
    yesterday_data = get_data_by_date(data, yesterday)

    # Calculate daily gains
    gains = []
    for key, entry in today_data.items():
        if key in yesterday_data:
            change = entry["streams"] - yesterday_data[key]["streams"]
            if change > 0:
                gains.append({
                    "song": entry["song_title"],
                    "artist": entry["artist"],
                    "streams": entry["streams"],
                    "change": change,
                    "pct_change": (change / yesterday_data[key]["streams"] * 100) if yesterday_data[key]["streams"] > 0 else 0
                })

    # Sort by daily gain
    gains.sort(key=lambda x: x["change"], reverse=True)

    posts = []
    if gains:
        # Top 5 gainers post
        top_5 = gains[:5]
        date_formatted = datetime.strptime(today, "%Y%m%d").strftime("%B %d, %Y")

        lines = [f"SB19 Daily Stream Update - {date_formatted}", ""]
        lines.append("Top Gainers:")
        for i, g in enumerate(top_5, 1):
            lines.append(f"{i}. {g['song']} ({g['artist']}): {format_change(g['change'])}")

        lines.append("")
        lines.append("#SB19 #SB19Spotify")

        post = "\n".join(lines)
        posts.append(("daily", post))

    return posts


def check_milestones(data, posted_log, dry_run=False):
    """Check for and post milestone celebrations."""
    latest = get_latest_by_track(data)
    posts = []

    for (song, artist), entry in latest.items():
        streams = entry["streams"]

        for milestone in MILESTONES:
            milestone_key = f"{song}_{artist}_{milestone}"

            # Check if we crossed this milestone and haven't posted about it
            if streams >= milestone and milestone_key not in posted_log.get("milestones", {}):
                emoji_map = {
                    1_000_000: "1M",
                    5_000_000: "5M",
                    10_000_000: "10M",
                    25_000_000: "25M",
                    50_000_000: "50M",
                    75_000_000: "75M",
                    100_000_000: "100M",
                    150_000_000: "150M",
                    200_000_000: "200M",
                    250_000_000: "250M",
                }

                milestone_str = emoji_map.get(milestone, format_number(milestone))

                post = f"MILESTONE ACHIEVED!\n\n\"{song}\" by {artist} has surpassed {milestone_str} streams on Spotify!\n\nCurrent streams: {format_number(streams)}\n\n#SB19 #SB19Spotify #{artist.replace(' ', '')}"

                posts.append(("milestone", post, milestone_key))

    return posts


def check_significant_jumps(data, dry_run=False):
    """Detect and post about significant stream jumps/spikes."""
    dates = get_unique_dates(data)
    if len(dates) < 2:
        return []

    today = dates[-1]
    yesterday = dates[-2]

    today_data = get_data_by_date(data, today)
    yesterday_data = get_data_by_date(data, yesterday)

    spikes = []
    for key, entry in today_data.items():
        if key in yesterday_data:
            prev_streams = yesterday_data[key]["streams"]
            if prev_streams == 0:
                continue

            change = entry["streams"] - prev_streams
            pct_change = (change / prev_streams) * 100

            # Check for significant spike
            if pct_change >= SPIKE_THRESHOLD_PERCENT or change >= SPIKE_THRESHOLD_ABSOLUTE:
                spikes.append({
                    "song": entry["song_title"],
                    "artist": entry["artist"],
                    "streams": entry["streams"],
                    "change": change,
                    "pct_change": pct_change
                })

    posts = []
    for spike in spikes[:3]:  # Limit to top 3 spikes
        post = f"TRENDING!\n\n\"{spike['song']}\" by {spike['artist']} is on fire!\n\n+{format_number(spike['change'])} streams ({spike['pct_change']:.1f}% increase)\n\nTotal: {format_number(spike['streams'])}\n\n#SB19 #SB19Spotify"
        posts.append(("spike", post))

    return posts


def check_weekly_summary(data, dry_run=False):
    """Generate weekly summary post."""
    dates = get_unique_dates(data)
    if len(dates) < 7:
        print("Not enough data for weekly summary")
        return []

    # Get data from 7 days ago and today
    today = dates[-1]
    week_ago_idx = max(0, len(dates) - 8)
    week_ago = dates[week_ago_idx]

    today_data = get_data_by_date(data, today)
    week_ago_data = get_data_by_date(data, week_ago)

    # Calculate weekly gains
    weekly_gains = []
    total_weekly_streams = 0

    for key, entry in today_data.items():
        if key in week_ago_data:
            change = entry["streams"] - week_ago_data[key]["streams"]
            if change > 0:
                weekly_gains.append({
                    "song": entry["song_title"],
                    "artist": entry["artist"],
                    "change": change
                })
                total_weekly_streams += change

    weekly_gains.sort(key=lambda x: x["change"], reverse=True)

    posts = []
    if weekly_gains:
        # Calculate date range
        start_date = datetime.strptime(week_ago, "%Y%m%d").strftime("%b %d")
        end_date = datetime.strptime(today, "%Y%m%d").strftime("%b %d, %Y")

        lines = [f"SB19 Weekly Recap ({start_date} - {end_date})", ""]
        lines.append(f"Total streams gained: {format_number(total_weekly_streams)}")
        lines.append("")
        lines.append("Top 5 of the Week:")

        for i, g in enumerate(weekly_gains[:5], 1):
            lines.append(f"{i}. {g['song']}: {format_change(g['change'])}")

        lines.append("")
        lines.append("#SB19 #SB19Spotify #SB19Weekly")

        post = "\n".join(lines)
        posts.append(("weekly", post))

    return posts


def check_listener_updates(listener_data, dry_run=False):
    """Check and post significant monthly listener changes."""
    # Group by artist and date
    by_artist = defaultdict(list)
    for entry in listener_data:
        if entry["artist"].upper() in [a.upper() for a in MAIN_ARTISTS]:
            by_artist[entry["artist"]].append(entry)

    posts = []
    changes = []

    for artist, entries in by_artist.items():
        # Sort by date
        entries.sort(key=lambda x: x["date"])
        if len(entries) < 2:
            continue

        latest = entries[-1]
        previous = entries[-2]

        change = latest["listeners"] - previous["listeners"]
        pct_change = (change / previous["listeners"] * 100) if previous["listeners"] > 0 else 0

        # Only report significant changes (>5%)
        if abs(pct_change) >= 5:
            changes.append({
                "artist": artist,
                "listeners": latest["listeners"],
                "change": change,
                "pct_change": pct_change
            })

    if changes:
        lines = ["SB19 Monthly Listener Update", ""]

        for c in sorted(changes, key=lambda x: x["listeners"], reverse=True):
            direction = "+" if c["change"] > 0 else ""
            lines.append(f"{c['artist']}: {format_number(c['listeners'])} ({direction}{c['pct_change']:.1f}%)")

        lines.append("")
        lines.append("#SB19 #SB19Spotify")

        post = "\n".join(lines)
        posts.append(("listeners", post))

    return posts


def initialize_milestone_log(data):
    """Initialize the milestone log with all existing milestones (run once on setup)."""
    print("Initializing milestone log with existing milestones...")
    latest = get_latest_by_track(data)
    posted_log = load_posted_log()

    if "milestones" not in posted_log:
        posted_log["milestones"] = {}

    count = 0
    for (song, artist), entry in latest.items():
        streams = entry["streams"]
        for milestone in MILESTONES:
            if streams >= milestone:
                milestone_key = f"{song}_{artist}_{milestone}"
                if milestone_key not in posted_log["milestones"]:
                    posted_log["milestones"][milestone_key] = "initialized"
                    count += 1

    save_posted_log(posted_log)
    print(f"Marked {count} existing milestones as already achieved.")
    print("Future runs will only post about NEW milestones.")
    return posted_log


def main():
    parser = argparse.ArgumentParser(description="SB19 Automated X Poster")
    parser.add_argument("--daily", action="store_true", help="Post daily stream updates")
    parser.add_argument("--milestones", action="store_true", help="Check and post milestones")
    parser.add_argument("--weekly", action="store_true", help="Post weekly summary")
    parser.add_argument("--listeners", action="store_true", help="Post monthly listener updates")
    parser.add_argument("--spikes", action="store_true", help="Post significant jump alerts")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--init", action="store_true", help="Initialize milestone log (run once on first setup)")
    parser.add_argument("--dry-run", action="store_true", help="Preview posts without actually posting")

    args = parser.parse_args()

    # Load stream data (always needed)
    print("Loading stream data...")
    stream_data = load_streams_data()
    print(f"Loaded {len(stream_data)} stream entries")

    # Handle initialization mode
    if args.init:
        initialize_milestone_log(stream_data)
        print("\nInitialization complete! You can now run the poster normally.")
        return

    # Default to all if no specific flag
    if not any([args.daily, args.milestones, args.weekly, args.listeners, args.spikes, args.all]):
        args.all = True

    if args.all:
        args.daily = args.milestones = args.weekly = args.listeners = args.spikes = True

    listener_data = []
    if args.listeners or args.all:
        print("Loading listener data...")
        listener_data = load_listeners_data()
        print(f"Loaded {len(listener_data)} listener entries")

    # Initialize X client
    client = get_x_client()
    dry_run = args.dry_run or client is None

    if dry_run:
        print("\nRunning in DRY RUN mode - posts will be previewed but not sent")

    # Load posted log
    posted_log = load_posted_log()

    all_posts = []

    # Check each type
    if args.daily:
        print("\n=== Checking Daily Updates ===")
        all_posts.extend(check_daily_updates(stream_data, dry_run))

    if args.milestones:
        print("\n=== Checking Milestones ===")
        all_posts.extend(check_milestones(stream_data, posted_log, dry_run))

    if args.spikes:
        print("\n=== Checking Significant Jumps ===")
        all_posts.extend(check_significant_jumps(stream_data, dry_run))

    if args.weekly:
        # Only post weekly on Sundays or if forced
        if datetime.now().weekday() == 6 or args.dry_run:
            print("\n=== Generating Weekly Summary ===")
            all_posts.extend(check_weekly_summary(stream_data, dry_run))
        else:
            print("\n=== Weekly Summary (skipped - not Sunday) ===")

    if args.listeners:
        print("\n=== Checking Listener Updates ===")
        all_posts.extend(check_listener_updates(listener_data, dry_run))

    # Post all
    print(f"\n{'='*50}")
    print(f"Total posts to send: {len(all_posts)}")
    print(f"{'='*50}")

    for post_info in all_posts:
        post_type = post_info[0]
        post_text = post_info[1]

        success = post_to_x(client, post_text, dry_run)

        # Update posted log for milestones
        if success and not dry_run and post_type == "milestone":
            milestone_key = post_info[2]
            if "milestones" not in posted_log:
                posted_log["milestones"] = {}
            posted_log["milestones"][milestone_key] = datetime.now().isoformat()
            save_posted_log(posted_log)

    if not all_posts:
        print("\nNo posts to send at this time.")

    print("\nDone!")


if __name__ == "__main__":
    main()
