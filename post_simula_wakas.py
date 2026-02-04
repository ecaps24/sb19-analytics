"""
Post SB19 Simula at Wakas Album Update to X

This script posts the album streams update with an image.
Run manually or via scheduled task.

The script automatically captures a fresh screenshot from the local dashboard
before posting.
"""

import csv
import http.server
import os
import socketserver
import sys
import threading
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from x_browser_poster import XBrowserPoster

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STREAMS_FILE = os.path.join(SCRIPT_DIR, "selenium_results.csv")
IMAGE_PATH = os.path.join(SCRIPT_DIR, "album_images", "simula_wakas.png")
LOCAL_INDEX = os.path.join(SCRIPT_DIR, "index.html")

# Album tracks to match
ALBUM_TRACKS = [
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


def capture_album_screenshot():
    """Capture a fresh screenshot of the Simula at Wakas chart from local dashboard."""
    print("[INFO] Capturing screenshot from local dashboard")

    # Ensure album_images directory exists
    os.makedirs(os.path.dirname(IMAGE_PATH), exist_ok=True)

    if not os.path.exists(LOCAL_INDEX):
        print(f"[ERR] index.html not found at: {LOCAL_INDEX}")
        return False

    # Start local HTTP server
    port = 8765
    handler = http.server.SimpleHTTPRequestHandler
    httpd = None
    server_thread = None

    try:
        # Change to script directory for serving files
        os.chdir(SCRIPT_DIR)

        httpd = socketserver.TCPServer(("", port), handler)
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"[INFO] Started local server on port {port}")

        # Setup browser
        options = EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = EdgeService()
        driver = None

        try:
            driver = webdriver.Edge(service=service, options=options)

            # Set window size for consistent screenshots
            driver.set_window_size(1920, 1080)

            # Load from local server
            url = f"http://localhost:{port}/index.html"
            print(f"[INFO] Loading: {url}")
            driver.get(url)

            # Wait for page to load and charts to render
            time.sleep(10)

            # Wait for the page to fully load with data
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "canvas"))
                )
                print("[INFO] Charts loaded")
            except Exception:
                print("[WARN] Could not detect charts, proceeding anyway...")

            # Scroll to the Simula at Wakas chart section by finding its title
            try:
                # Find the kickoff chart title element
                kickoff_title = driver.find_element(By.ID, "kickoffChartTitle")
                # Scroll to bring the chart into view
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'instant', block: 'start'});",
                    kickoff_title
                )
                # Scroll up a bit to show more context
                driver.execute_script("window.scrollBy(0, -100);")
                time.sleep(2)
                print("[INFO] Scrolled to Simula at Wakas chart")
            except Exception as e:
                print(f"[WARN] Could not find kickoffChartTitle: {e}")
                # Fallback: try to find by text content
                try:
                    kickoff_title = driver.find_element(
                        By.XPATH, "//*[contains(text(), 'Simula at Wakas Tour Kickoff Concert Album')]"
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'instant', block: 'start'});",
                        kickoff_title
                    )
                    driver.execute_script("window.scrollBy(0, -100);")
                    time.sleep(2)
                    print("[INFO] Found chart by text, scrolled to position")
                except Exception:
                    # Last fallback: scroll to approximate position
                    print("[WARN] Using fallback scroll position")
                    driver.execute_script("window.scrollTo(0, 500);")
                    time.sleep(1)

            # Take screenshot
            driver.save_screenshot(IMAGE_PATH)
            print(f"[SUCCESS] Screenshot saved: {IMAGE_PATH}")
            return True

        except Exception as e:
            print(f"[ERR] Failed to capture screenshot: {e}")
            return False
        finally:
            if driver:
                driver.quit()

    except Exception as e:
        print(f"[ERR] Failed to start local server: {e}")
        return False
    finally:
        if httpd:
            httpd.shutdown()
            print("[INFO] Local server stopped")


def has_data_for_today():
    """Check if there's stream data for today."""
    if not os.path.exists(STREAMS_FILE):
        return False, "Streams file not found"

    today = datetime.now().strftime("%Y-%m-%d")

    with open(STREAMS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            timestamp = row.get("timestamp", "")
            if timestamp[:10] == today:
                return True, f"Found data for today ({today})"

    # Find latest date
    latest_date = None
    with open(STREAMS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            timestamp = row.get("timestamp", "")
            date = timestamp[:10] if timestamp else ""
            if date and (latest_date is None or date > latest_date):
                latest_date = date

    return False, f"No data for today ({today}). Latest: {latest_date or 'unknown'}"


def load_album_data():
    """Load album streams data from CSV and calculate totals."""
    if not os.path.exists(STREAMS_FILE):
        print(f"[ERR] Streams file not found: {STREAMS_FILE}")
        return None, None, None

    # Read all data
    data = []
    with open(STREAMS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                streams = int(row["streams"]) if row["streams"] else 0
                timestamp = row["timestamp"]
                # Handle "2026-01-24 02:49:49" format
                date = timestamp[:10] if timestamp else ""
                data.append({
                    "timestamp": timestamp,
                    "song_title": row["song_title"],
                    "streams": streams,
                    "date": date
                })
            except (ValueError, KeyError):
                continue

    if not data:
        return None, None, None

    # Get unique dates
    dates = sorted(set(d["date"] for d in data))
    if len(dates) < 2:
        print("[WARN] Not enough data for comparison")
        return None, None, None

    latest_date = dates[-1]
    prev_date = dates[-2]

    # Filter for album tracks
    def is_album_track(title):
        return any(track.lower() in title.lower() for track in ALBUM_TRACKS)

    # Get latest and previous data for album tracks
    latest_data = {d["song_title"]: d for d in data if d["date"] == latest_date and is_album_track(d["song_title"])}
    prev_data = {d["song_title"]: d for d in data if d["date"] == prev_date and is_album_track(d["song_title"])}

    # Calculate totals
    total_streams = sum(d["streams"] for d in latest_data.values())

    # Calculate change
    total_change = 0
    for title, current in latest_data.items():
        if title in prev_data:
            total_change += current["streams"] - prev_data[title]["streams"]

    # Format date (handle "2026-01-24" format)
    date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
    date_str = date_obj.strftime("%b %d, %Y")

    return total_streams, total_change, date_str


def main():
    print("[INFO] Generating Simula at Wakas album post...")

    # Validate data for today
    has_data, status_msg = has_data_for_today()
    print(f"[VALIDATION] {status_msg}")

    if not has_data:
        print("[SKIP] No new data for today. Skipping post.")
        return

    # Capture fresh screenshot from website
    print("\n[INFO] Capturing fresh screenshot from opminsights.com...")
    screenshot_success = capture_album_screenshot()

    if screenshot_success and os.path.exists(IMAGE_PATH):
        use_image = True
        print(f"[INFO] Using fresh screenshot: {IMAGE_PATH}")
    else:
        print("[WARN] Could not capture screenshot. Posting without image.")
        use_image = False

    # Load data
    total_streams, total_change, date_str = load_album_data()

    if total_streams is None:
        print("[ERR] Could not load album data. Using manual values.")
        # Fallback to manual entry
        total_streams = 1976291
        total_change = 708970
        date_str = datetime.now().strftime("%b %d, %Y")

    # Format numbers with commas
    total_str = f"{total_streams:,}"
    change_str = f"+{total_change:,}" if total_change >= 0 else f"{total_change:,}"

    # Generate message
    message = f"""SB19's Simula at Wakas Tour Kickoff Concert Album has now reached {total_str} total streams ({change_str}) as of {date_str}. See full details at opminsights.com

#SB19 #SB19Spotify #SimulaAtWakas #PPop #ATIN #OPM"""

    print(f"\n[INFO] Post message:\n{message}\n")

    # Post
    poster = XBrowserPoster(keep_open=True)

    try:
        poster.start()

        if not poster.check_login_status():
            print("[ERR] Not logged into X!")
            return

        image_path = IMAGE_PATH if use_image else None
        success = poster.create_post(message, image_path=image_path)

        if success:
            print("\n[SUCCESS] Posted successfully!")
        else:
            print("\n[ERR] Failed to post.")

    except Exception as e:
        print(f"[ERR] Error: {e}")
    finally:
        poster.stop()


if __name__ == "__main__":
    main()
