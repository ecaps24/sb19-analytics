"""
Centralized configuration for SB19 Analytics RPA scripts.

All hardcoded values, thresholds, paths, and constants live here.
Import from this module instead of scattering magic numbers across scripts.

Sensitive values (API keys, credentials) are loaded from environment
variables or .env file - never hardcode them here.
"""

import os

# Load .env file if it exists (no dependency on python-dotenv)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Data files
TRACKS_CSV = os.path.join(SCRIPT_DIR, "tracks.csv")
SELENIUM_RESULTS_CSV = os.path.join(SCRIPT_DIR, "selenium_results.csv")
STREAMS_LEGACY_CSV = os.path.join(SCRIPT_DIR, "sb19_streams_results.csv")
MONTHLY_LISTENERS_CSV = os.path.join(SCRIPT_DIR, "monthly_listeners.csv")
OPM_ARTISTS_CSV = os.path.join(SCRIPT_DIR, "opm_artists_spotify.csv")
OPM_TRACKS_RESULTS_CSV = os.path.join(SCRIPT_DIR, "opm_tracks_results.csv")
OPM_ALL_TRACKS_CSV = os.path.join(SCRIPT_DIR, "opm_all_tracks.csv")
POSTED_LOG = os.path.join(SCRIPT_DIR, "x_posted_log.json")
RPA_AUDIT_LOG = os.path.join(SCRIPT_DIR, "rpa_audit_log.csv")

# Directories
SAVED_PAGES_DIR = os.path.join(SCRIPT_DIR, "saved_pages")
MONTHLY_LISTENERS_DIR = os.path.join(SCRIPT_DIR, "monthly listeners")
ALBUM_IMAGE_DIR = os.path.join(SCRIPT_DIR, "album_images")
MEMBER_PHOTOS_DIR = os.path.join(SCRIPT_DIR, "profiles")

# Image paths
ALBUM_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "simula_wakas.png")
TOP10_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "top10_streams.png")
SOLO_TOP10_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "solo_top10_streams.png")
LISTENERS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "monthly_listeners.png")
OPM_TOP_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_listeners.png")
PPOP_TOP_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "ppop_top_listeners.png")
OPM_TOP_TRACKS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_tracks.png")
OPM_TOP_STREAMS_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "opm_top_streams.png")
YT_EMOJI_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "yt_emoji_stats.png")
SPOTIFY_VISA_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "spotify_visa_stats.png")
LOCAL_INDEX = os.path.join(SCRIPT_DIR, "index.html")

# ---------------------------------------------------------------------------
# CSV delimiters (standardize on semicolon for track data, comma for listeners)
# ---------------------------------------------------------------------------

DELIMITER_TRACKS = ";"
DELIMITER_LISTENERS = ","

# ---------------------------------------------------------------------------
# Selenium / WebDriver settings
# ---------------------------------------------------------------------------

# User agent string for headless mode
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 "
    "Safari/537.36 Edg/145.0.0.0"
)

# Wait times (seconds)
WAIT_INITIAL_PAGE_LOAD = 5
WAIT_TITLE_CHANGE = 15
WAIT_TITLE_CHANGE_RETRY = 20
WAIT_BUTTON_DETECTION = 10
WAIT_ELEMENT_DETECTION = 15
WAIT_POST_BUTTON = 10
WAIT_POST_SCROLL = 2
WAIT_POST_SCROLL_LONG = 3
WAIT_DIALOG_OPEN = 2
WAIT_BETWEEN_TRACKS = 2
WAIT_BETWEEN_ARTISTS = 2
WAIT_BETWEEN_ALBUMS = 1
WAIT_BETWEEN_SCROLLS = 1.5
WAIT_BROWSER_RECOVERY = 3
WAIT_TRACK_VERIFICATION = 3
WAIT_ALBUM_PAGE_LOAD = 4
WAIT_EDGE_KILL = 5

# Scroll amounts (pixels)
SCROLL_STANDARD = 500
SCROLL_ARTIST_PAGE = 300
SCROLL_LARGE = 800

# Retry & error thresholds
MAX_CONSECUTIVE_ERRORS = 3
MAX_STREAM_EXTRACTION_RETRIES = 2

# Track discovery
DISCOVERY_SCROLL_ITERATIONS = 3

# X/Twitter browser poster
TYPING_DELAY = 0.02           # seconds between characters
WAIT_X_HOME_LOAD = 5
WAIT_X_COMPOSE_LOAD = 3
WAIT_X_TEXTAREA = 15
WAIT_X_PRE_TYPE = 0.5
WAIT_X_POST_TYPE = 1
WAIT_X_IMAGE_UPLOAD = 3
WAIT_X_CONFIRMATION = 2
WAIT_X_POST_COMPLETE = 3

# Local dashboard server
LOCAL_SERVER_PORT = 8765

# ---------------------------------------------------------------------------
# System paths (Windows-specific, used by OCR script)
# ---------------------------------------------------------------------------

EDGE_PATH_PRIMARY = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PATH_FALLBACK = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------------------------------------------------------------------------
# Artists & identity
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Milestones & thresholds
# ---------------------------------------------------------------------------

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

# Spike detection
SPIKE_THRESHOLD_PERCENT = 50
SPIKE_THRESHOLD_ABSOLUTE = 100_000

# Data validation (OCR sanity checks)
MAX_STREAMS_SANITY = 1_500_000_000    # 1.5B
MIN_STREAMS_SANITY = 100
MAX_DAILY_CHANGE_RATIO = 0.10         # 10%

# ---------------------------------------------------------------------------
# YouTube & Spotify
# ---------------------------------------------------------------------------

# Load API key from environment variable (fallback to empty string)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_VIDEO_ID = "w6_sChrkvw8"
YOUTUBE_VIDEO_URL = "https://youtu.be/w6_sChrkvw8"
YT_HISTORY_FILE = os.path.join(SCRIPT_DIR, "yt_emoji_history.json")
YT_STREAMS_CSV = os.path.join(SCRIPT_DIR, "yt_emoji_streams.csv")

# YouTube channel stats (subscribers + total views + MV views)
YOUTUBE_CHANNEL_HANDLE = "officialSB19"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@officialSB19"
YOUTUBE_MUSIC_URL = "https://music.youtube.com/channel/UCm4v7afBTnJKRm4SlfHJzyg"
YT_CHANNEL_HISTORY_FILE = os.path.join(SCRIPT_DIR, "yt_channel_history.json")
YT_CHANNEL_STATS_CSV = os.path.join(SCRIPT_DIR, "yt_channel_stats.csv")
YT_CHANNEL_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "yt_channel_stats.png")

# Top SB19 music videos (name -> YouTube video ID)
YOUTUBE_MV_IDS = {
    "GENTO": "VZZA_38RUBI",
    "DAM": "de6CnBa-qj0",
    "DUNGKA!": "SO-G0WMzSdo",
    "Time": "NMq0DVeTwkY",
    "VISA": "0t6GNcINKeU",
    "EMOJI": "w6_sChrkvw8",
    "MAPA (Lyric Video)": "DDyr3DbTPtk",
}

SPOTIFY_VISA_URL = "https://open.spotify.com/track/6RYMQDnY4zPaLSfvfRdXT7"

# Sample tracks for freshness check (high-traffic tracks that update frequently)
FRESHNESS_CHECK_TRACKS = [
    "https://open.spotify.com/track/1o6uF8VmXna99ysHTcQRI2",  # Gento
    "https://open.spotify.com/track/6Fz2TpxUD0YvAPsuG8nDMJ",  # MAPA
    "https://open.spotify.com/track/5QZw4F3N3PvuKNKHm9L20b",  # Bazinga
]

# ---------------------------------------------------------------------------
# Social media / posting
# ---------------------------------------------------------------------------

X_CHAR_LIMIT = 25000       # Premium X/Twitter limit
SITE_TAG = "opminsights.com"
SOLO_TOP_N = 3              # Top N tracks per solo artist

# Wakas At Simula studio album
WAS_ALBUM_NAME = "Wakas At Simula"
WAS_ALBUM_IMAGE_PATH = os.path.join(ALBUM_IMAGE_DIR, "was_album.png")

# Simula at Wakas Tour Kickoff concert album tracks
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
# Track variant filters (for track discovery - skip these)
# ---------------------------------------------------------------------------

VARIANT_FILTERS = [
    r"sped\s*up",
    r"slowed\s*(down|and|\+)\s*reverb",
    r"slowed\s+down",
    r"\bkaraoke\b",
    r"\b8d\s*audio\b",
    r"\bnightcore\b",
]

# Genres excluded from OPM compilation
EXCLUDE_GENRES = {"SB19 Solo"}
EXCLUDE_ARTISTS = {"SB19"}
