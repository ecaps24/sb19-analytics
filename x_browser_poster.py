"""
SB19 X (Twitter) Browser Automation Poster

Posts updates to X (Twitter) using browser automation (Selenium) instead of paid API.
Uses Microsoft Edge with user profile to maintain logged-in session.

Usage:
    python x_browser_poster.py --dry-run         # Preview post without sending
    python x_browser_poster.py --listeners       # Post monthly listener update
    python x_browser_poster.py --custom "msg"    # Post custom message
    python x_browser_poster.py --weekly          # Post weekly summary

Prerequisites:
    - Must be logged into X in Microsoft Edge browser
    - Close Edge completely before first run (to use profile)
"""

import argparse
import csv
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class XBrowserPoster:
    """Browser automation class for posting to X (Twitter)."""

    def __init__(self, headless=False, use_profile=True, keep_open=False):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.listeners_file = os.path.join(self.base_dir, "monthly_listeners.csv")
        self.headless = headless
        self.use_profile = use_profile
        self.keep_open = keep_open
        self.driver = None

        # Main artists to track with their X handles
        self.main_artists = ["SB19", "PABLO", "JOSH CULLEN", "Stell", "FELIP", "justin"]
        self.x_handles = {
            "SB19": "@SB19Official",
            "PABLO": "@imszmc",
            "JOSH CULLEN": "@JoshCullen_s",
            "Stell": "@stellajero_",
            "FELIP": "@felipsuperior",
            "justin": "@justintdedios"
        }

    def _close_all_edge_instances(self):
        """Close all running Edge browser instances."""
        print("[INIT] Closing all Edge browser instances...")
        try:
            # Kill all msedge.exe processes
            result = subprocess.run(
                ["taskkill", "/F", "/IM", "msedge.exe"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("[INIT] Edge processes terminated.")
            elif "not found" in result.stderr.lower() or result.returncode == 128:
                print("[INIT] No Edge processes were running.")
            else:
                # Some processes killed, some may have failed
                print("[INIT] Edge termination completed.")

            # Wait for processes to fully close
            time.sleep(2)

        except Exception as e:
            print(f"[WARN] Could not close Edge processes: {e}")

    def _setup_driver(self):
        """Setup Edge WebDriver with anti-detection measures."""
        # Close any existing Edge instances first
        if self.use_profile:
            self._close_all_edge_instances()

        print("[INIT] Setting up Edge WebDriver...")
        options = EdgeOptions()

        if self.headless:
            options.add_argument("--headless=new")
            print("[INIT] Running in headless mode (may trigger bot detection)")

        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")

        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Keep browser open after script ends
        if self.keep_open:
            options.add_experimental_option("detach", True)

        # Use Edge user profile to maintain login session
        if self.use_profile:
            username = os.environ.get("USERNAME", os.environ.get("USER", ""))
            user_data_dir = f"C:/Users/{username}/AppData/Local/Microsoft/Edge/User Data"
            if os.path.exists(user_data_dir):
                options.add_argument(f"user-data-dir={user_data_dir}")
                options.add_argument("profile-directory=Default")
                print(f"[INIT] Using Edge profile: {user_data_dir}")
            else:
                print(f"[WARN] Edge profile not found at {user_data_dir}")
                print("[WARN] You may need to log in manually")

        service = EdgeService()
        try:
            driver = webdriver.Edge(service=service, options=options)
            # Additional anti-detection
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            })
            return driver
        except Exception as e:
            print(f"[ERR] Failed to initialize Edge Driver: {e}")
            raise

    def start(self):
        """Start the browser driver."""
        if not self.driver:
            self.driver = self._setup_driver()

    def stop(self):
        """Stop and clean up the browser driver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("[INFO] Browser closed.")

    def _wait_for_element(self, selectors, timeout=10):
        """
        Wait for element using multiple selector strategies.
        Returns the first matching element found.
        """
        wait = WebDriverWait(self.driver, timeout)

        for selector_type, selector_value in selectors:
            try:
                element = wait.until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                return element
            except TimeoutException:
                continue

        return None

    def _find_element_multiple(self, selectors):
        """Try multiple selectors to find an element."""
        for selector_type, selector_value in selectors:
            try:
                element = self.driver.find_element(selector_type, selector_value)
                if element:
                    return element
            except NoSuchElementException:
                continue
        return None

    def check_login_status(self):
        """Check if user is logged into X."""
        print("[INFO] Checking login status...")
        self.driver.get("https://x.com/home")
        time.sleep(5)  # Wait for page load

        # Check if we're on the home timeline (logged in) or login page
        current_url = self.driver.current_url

        if "login" in current_url or "i/flow/login" in current_url:
            print("[WARN] Not logged in to X!")
            print("[WARN] Please log into X in your Edge browser first, then close Edge and retry.")
            return False

        # Look for compose tweet button as indicator of logged-in state
        compose_selectors = [
            (By.CSS_SELECTOR, '[data-testid="SideNav_NewTweet_Button"]'),
            (By.CSS_SELECTOR, '[aria-label="Post"]'),
            (By.CSS_SELECTOR, 'a[href="/compose/tweet"]'),
        ]

        element = self._find_element_multiple(compose_selectors)
        if element:
            print("[SUCCESS] Logged into X successfully!")
            return True

        # Check for timeline content
        try:
            self.driver.find_element(By.CSS_SELECTOR, '[data-testid="primaryColumn"]')
            print("[SUCCESS] Logged into X (timeline found)!")
            return True
        except NoSuchElementException:
            pass

        print("[WARN] Unable to verify login status. Proceeding anyway...")
        return True

    def create_post(self, message, dry_run=False, test_mode=False, image_path=None):
        """
        Create and post a message to X.

        Args:
            message: The text to post
            dry_run: If True, don't actually post (no browser)
            test_mode: If True, open browser and type but don't click Post

        Returns:
            bool: True if successful, False otherwise
        """
        print("\n" + "=" * 60)
        print("[POST] Creating post...")
        print("-" * 60)
        print(message)
        print("-" * 60)
        # Standard X limit: 280 characters
        char_count = len(message)
        if char_count > 280:
            print(f"[WARN] Post is {char_count} chars - EXCEEDS 280 limit by {char_count - 280}!")
        else:
            print(f"[INFO] Character count: {char_count}/280")

        if dry_run:
            print("[DRY RUN] Post preview complete. Not sending.")
            return True

        try:
            # Navigate to compose URL directly
            print("[INFO] Navigating to compose page...")
            self.driver.get("https://x.com/compose/post")
            time.sleep(3)

            # Wait for the compose textarea
            print("[INFO] Waiting for compose textarea...")
            textarea_selectors = [
                (By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'),
                (By.CSS_SELECTOR, '[data-testid="tweetTextarea_0RichTextInputContainer"]'),
                (By.CSS_SELECTOR, 'div[role="textbox"][data-testid="tweetTextarea_0"]'),
                (By.CSS_SELECTOR, 'div[role="textbox"]'),
                (By.CSS_SELECTOR, '.public-DraftEditor-content'),
            ]

            textarea = self._wait_for_element(textarea_selectors, timeout=15)

            if not textarea:
                print("[ERR] Could not find compose textarea!")
                self._save_debug_screenshot("compose_failed")
                return False

            print("[INFO] Found compose textarea, entering text...")

            # Click to focus (use JS click to bypass any overlay/mask)
            self.driver.execute_script("arguments[0].click();", textarea)
            time.sleep(0.5)

            # Type the message with human-like delay
            for char in message:
                textarea.send_keys(char)
                time.sleep(0.02)  # Small delay between characters

            time.sleep(1)

            # Upload image if provided
            if image_path and os.path.exists(image_path):
                print(f"[INFO] Uploading image: {image_path}")
                try:
                    # Find the file input element (hidden input for media upload)
                    file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"][accept*="image"]')
                    # Send the file path to upload
                    file_input.send_keys(os.path.abspath(image_path))
                    print("[INFO] Image uploaded, waiting for processing...")
                    time.sleep(3)  # Wait for image to upload and process
                except Exception as e:
                    print(f"[WARN] Could not upload image: {e}")

            # Test mode: stop here without posting
            if test_mode:
                print("\n[TEST MODE] Message typed successfully!")
                print("[TEST MODE] The Post button will NOT be clicked.")
                return True

            # Find and click the Post button
            print("[INFO] Looking for Post button...")
            post_button_selectors = [
                (By.CSS_SELECTOR, '[data-testid="tweetButton"]'),
                (By.CSS_SELECTOR, '[data-testid="tweetButtonInline"]'),
                (By.XPATH, '//button[@data-testid="tweetButton"]'),
                (By.XPATH, '//span[text()="Post"]/ancestor::button'),
            ]

            post_button = self._wait_for_element(post_button_selectors, timeout=10)

            if not post_button:
                print("[ERR] Could not find Post button!")
                self._save_debug_screenshot("post_button_failed")
                return False

            # Wait a moment before clicking
            time.sleep(2)

            # Scroll the button into view and click using JavaScript (avoids overlay issues)
            print("[INFO] Clicking Post button...")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", post_button)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", post_button)

            # Wait for post to be sent
            time.sleep(3)

            # Verify post was sent (check for success indicators)
            print("[SUCCESS] Post sent successfully!")
            return True

        except Exception as e:
            print(f"[ERR] Failed to create post: {e}")
            self._save_debug_screenshot("post_error")
            return False

    def _save_debug_screenshot(self, name):
        """Save a screenshot for debugging."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"debug_{name}_{timestamp}.png"
            filepath = os.path.join(self.base_dir, filename)
            self.driver.save_screenshot(filepath)
            print(f"[DEBUG] Screenshot saved: {filepath}")
        except Exception as e:
            print(f"[WARN] Could not save screenshot: {e}")

    def load_listeners_data(self):
        """Load monthly listeners data from CSV."""
        data = []
        if not os.path.exists(self.listeners_file):
            print(f"[WARN] Listeners file not found: {self.listeners_file}")
            return data

        with open(self.listeners_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    listeners = row.get("monthly_listeners", "")
                    if listeners and listeners != "N/A":
                        listeners = int(listeners)
                    else:
                        continue

                    timestamp = row.get("timestamp", "")
                    data.append({
                        "artist": row["artist_name"],
                        "listeners": listeners,
                        "timestamp": timestamp,
                        "date": str(timestamp)[:8]
                    })
                except (ValueError, KeyError):
                    continue

        return data

    def has_data_for_today(self):
        """Check if there's listener data for today."""
        data = self.load_listeners_data()
        if not data:
            return False, "No data found"

        today = datetime.now().strftime("%Y%m%d")
        today_data = [d for d in data if d["date"] == today]

        if not today_data:
            # Get the latest date in data
            dates = sorted(set(d["date"] for d in data))
            latest = dates[-1] if dates else "unknown"
            return False, f"No data for today ({today}). Latest data: {latest}"

        # Check if we have data for main artists
        main_artists_found = 0
        for entry in today_data:
            if any(main.upper() == entry["artist"].upper() for main in self.main_artists):
                main_artists_found += 1

        if main_artists_found < len(self.main_artists):
            return False, f"Incomplete data: only {main_artists_found}/{len(self.main_artists)} main artists"

        return True, f"Found {len(today_data)} records for today"

    def format_number(self, n):
        """Format large numbers for readability."""
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.2f}B"
        elif n >= 1_000_000:
            return f"{n / 1_000_000:.2f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    def format_number_with_commas(self, n):
        """Format number with comma separators."""
        return f"{n:,}"

    def format_change(self, change):
        """Format change with + or - sign and commas."""
        if change > 0:
            return f"+{change:,}"
        elif change < 0:
            return f"{change:,}"
        return "0"

    def generate_listeners_post(self):
        """Generate post content for monthly listeners update."""
        print("[INFO] Generating monthly listeners post...")
        data = self.load_listeners_data()

        if not data:
            print("[WARN] No listener data available!")
            return None

        # Group by artist
        by_artist = defaultdict(list)
        for entry in data:
            artist_upper = entry["artist"].upper()
            if any(main.upper() == artist_upper for main in self.main_artists):
                by_artist[entry["artist"]].append(entry)

        if not by_artist:
            print("[WARN] No main artist data found!")
            return None

        # Get unique dates and find latest two
        all_dates = sorted(set(entry["date"] for entry in data))

        # Get latest and previous date data for each artist
        latest_data = []
        for artist, entries in by_artist.items():
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            if entries:
                latest = entries[0]
                latest_date = latest["date"]

                # Find previous entry (different date)
                previous = None
                for entry in entries[1:]:
                    if entry["date"] != latest_date:
                        previous = entry
                        break

                change = 0
                if previous:
                    change = latest["listeners"] - previous["listeners"]

                latest_data.append({
                    "artist": artist,
                    "listeners": latest["listeners"],
                    "change": change
                })

        # Sort by listener count
        latest_data.sort(key=lambda x: x["listeners"], reverse=True)

        # Get latest date from data for "as of" line
        latest_date_str = ""
        if latest_data:
            # Find the most recent timestamp
            all_timestamps = [entry.get("timestamp", "") for entry in data if entry.get("timestamp")]
            if all_timestamps:
                latest_ts = max(all_timestamps)
                # Parse YYYYMMDD format
                try:
                    date_obj = datetime.strptime(latest_ts[:8], "%Y%m%d")
                    latest_date_str = date_obj.strftime("%b %d, %Y")
                except:
                    latest_date_str = ""

        # Build post with catchy intro
        if latest_date_str:
            lines = [
                f"A'TIN! Here's SB19's Monthly Listeners on Spotify as of {latest_date_str}. See full details at opminsights.com",
                ""
            ]
        else:
            lines = [
                "A'TIN! Here's SB19's Monthly Listeners on Spotify! See full details at opminsights.com",
                ""
            ]

        for entry in latest_data:
            # Get X handle (case-insensitive lookup)
            handle = ""
            for name, h in self.x_handles.items():
                if name.upper() == entry["artist"].upper():
                    handle = h
                    break
            listener_str = self.format_number_with_commas(entry["listeners"])
            change_str = f"({self.format_change(entry['change'])})"
            # Format: Artist Name @Handle: Monthly listeners
            lines.append(f"{entry['artist']} {handle}: {listener_str} {change_str}")

        lines.append("")
        lines.append("#SB19 #SB19Spotify #PPop #ATIN #OPM")

        post = "\n".join(lines)
        return post

    def generate_weekly_post(self):
        """Generate weekly summary post."""
        print("[INFO] Generating weekly summary post...")
        data = self.load_listeners_data()

        if not data:
            print("[WARN] No listener data available!")
            return None

        # Get unique dates
        dates = sorted(set(entry["date"] for entry in data))
        if len(dates) < 2:
            print("[WARN] Not enough data for weekly comparison!")
            return None

        # Get latest and week-ago data
        latest_date = dates[-1]
        week_ago_idx = max(0, len(dates) - 8)
        week_ago_date = dates[week_ago_idx]

        # Group by artist for both dates
        latest_by_artist = {}
        week_ago_by_artist = {}

        for entry in data:
            artist_upper = entry["artist"].upper()
            if any(main.upper() == artist_upper for main in self.main_artists):
                if entry["date"] == latest_date:
                    latest_by_artist[entry["artist"]] = entry
                elif entry["date"] == week_ago_date:
                    week_ago_by_artist[entry["artist"]] = entry

        # Calculate changes
        changes = []
        for artist, latest in latest_by_artist.items():
            if artist in week_ago_by_artist:
                prev = week_ago_by_artist[artist]
                change = latest["listeners"] - prev["listeners"]
                pct = (change / prev["listeners"] * 100) if prev["listeners"] > 0 else 0
                changes.append({
                    "artist": artist,
                    "listeners": latest["listeners"],
                    "change": change,
                    "pct": pct
                })

        if not changes:
            print("[WARN] No weekly changes to report!")
            return None

        changes.sort(key=lambda x: x["listeners"], reverse=True)

        # Build post
        lines = ["SB19 Weekly Listener Recap", ""]

        for c in changes:
            sign = "+" if c["change"] >= 0 else ""
            lines.append(f"{c['artist']}: {self.format_number(c['listeners'])} ({sign}{c['pct']:.1f}%)")

        lines.append("")
        lines.append("#SB19 #SB19Spotify")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SB19 X Browser Poster")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview post without sending")
    parser.add_argument("--listeners", action="store_true",
                        help="Post monthly listener update")
    parser.add_argument("--weekly", action="store_true",
                        help="Post weekly summary")
    parser.add_argument("--custom", type=str, metavar="MESSAGE",
                        help="Post a custom message")
    parser.add_argument("--image", type=str, metavar="PATH",
                        help="Path to image file to attach to post")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: opens browser, types message, but does NOT post")
    parser.add_argument("--keep-open", action="store_true",
                        help="Keep browser open after completion")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip data validation check (post even if no new data)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (may trigger bot detection)")
    parser.add_argument("--no-profile", action="store_true",
                        help="Don't use Edge user profile (will need to log in)")

    args = parser.parse_args()

    # Determine what to post
    message = None
    post_type = None

    poster = XBrowserPoster(
        headless=args.headless,
        use_profile=not args.no_profile,
        keep_open=args.keep_open
    )

    try:
        # Generate message based on flags (no browser needed for generation)
        if args.custom:
            message = args.custom
            post_type = "custom"
        elif args.weekly:
            message = poster.generate_weekly_post()
            post_type = "weekly"
        elif args.listeners:
            # Validate data before posting
            if not args.skip_validation and not args.dry_run:
                has_data, status_msg = poster.has_data_for_today()
                print(f"[VALIDATION] {status_msg}")
                if not has_data:
                    print("[SKIP] No new data for today. Skipping post.")
                    print("[INFO] Use --skip-validation to post anyway.")
                    return
            message = poster.generate_listeners_post()
            post_type = "listeners"
        else:
            # Default to listeners update with validation
            if not args.skip_validation and not args.dry_run:
                has_data, status_msg = poster.has_data_for_today()
                print(f"[VALIDATION] {status_msg}")
                if not has_data:
                    print("[SKIP] No new data for today. Skipping post.")
                    print("[INFO] Use --skip-validation to post anyway.")
                    return
            message = poster.generate_listeners_post()
            post_type = "listeners"

        if not message:
            print("[ERR] No message to post!")
            return

        print(f"\n[INFO] Post type: {post_type}")

        if args.dry_run:
            # Just preview (no browser)
            poster.create_post(message, dry_run=True)
        elif args.test:
            # Test mode: open browser, type message, but don't post
            print("\n[TEST MODE] Will open browser and type message, but NOT post.")
            poster.start()

            # Check login status
            if not poster.check_login_status():
                print("\n[ERR] Please log into X in Edge browser first!")
                print("[INFO] Steps to fix:")
                print("  1. Close this script")
                print("  2. Open Microsoft Edge")
                print("  3. Go to https://x.com and log in")
                print("  4. Close Edge completely")
                print("  5. Run this script again")
                return

            # Test the message (type but don't post)
            success = poster.create_post(message, test_mode=True, image_path=args.image)

            if success:
                print("\n[TEST MODE] Test completed successfully!")
            else:
                print("\n[ERR] Test failed.")
        else:
            # Actually post
            poster.start()

            # Check login status
            if not poster.check_login_status():
                print("\n[ERR] Please log into X in Edge browser first!")
                print("[INFO] Steps to fix:")
                print("  1. Close this script")
                print("  2. Open Microsoft Edge")
                print("  3. Go to https://x.com and log in")
                print("  4. Close Edge completely")
                print("  5. Run this script again")
                return

            # Post the message
            success = poster.create_post(message, image_path=args.image)

            if success:
                print("\n[SUCCESS] Post completed!")
            else:
                print("\n[ERR] Failed to post.")

    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user.")
        poster.stop()
    except Exception as e:
        print(f"\n[ERR] Unexpected error: {e}")
        poster.stop()
        raise
    else:
        # Only close browser if --keep-open is not set
        if args.keep_open:
            print("\n[INFO] Browser kept open. Close it manually when done.")
        else:
            poster.stop()


if __name__ == "__main__":
    main()
