import argparse
import csv
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from shared import setup_driver, slugify, git_push
from config import (
    TRACKS_CSV, SELENIUM_RESULTS_CSV, SAVED_PAGES_DIR,
    FRESHNESS_CHECK_TRACKS, DELIMITER_TRACKS,
    WAIT_INITIAL_PAGE_LOAD, WAIT_TITLE_CHANGE, WAIT_TITLE_CHANGE_RETRY,
    WAIT_POST_SCROLL, WAIT_POST_SCROLL_LONG, WAIT_BETWEEN_TRACKS,
    WAIT_BROWSER_RECOVERY, MAX_CONSECUTIVE_ERRORS,
    MAX_STREAM_EXTRACTION_RETRIES, SCROLL_STANDARD,
)


class SB19SeleniumRPA:
    def __init__(self, tracks_csv=None, results_csv=None, skip_freshness_check=False, override_date=None, headless=False):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.saved_pages_dir = SAVED_PAGES_DIR
        os.makedirs(self.saved_pages_dir, exist_ok=True)

        self.tracks_csv_path = tracks_csv or TRACKS_CSV
        self.results_csv_path = results_csv or SELENIUM_RESULTS_CSV
        self.skip_freshness_check = skip_freshness_check
        self.override_date = override_date
        self.headless = headless

        self.sample_tracks_for_check = FRESHNESS_CHECK_TRACKS

        # Setup Driver
        self.driver = setup_driver(headless=self.headless)

    def _setup_driver(self):
        """Re-create driver (used after error recovery)."""
        return setup_driver(headless=self.headless)

    def _slugify(self, text):
        return slugify(text)

    def save_page_source(self, html_content, slug):
        """Save HTML content to a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{timestamp}.html"
        filepath = os.path.join(self.saved_pages_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            # print(f"[SAVE] Page source saved: {filename}")
            return filepath
        except Exception as e:
            print(f"[ERR] Failed to save page source: {e}")
            return None

    def extract_streams_from_html(self, html_content):
        """
        Extract stream count from HTML source using text analysis (BS4 + Regex).
        Replicates the logic from the OCR script but on the raw text content.
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            
            # Clean up text
            text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
            
            # Pattern 1: Look for duration pattern followed by stream count
            pattern = r'(\d{1,2}:\d{2})\s*(?:[•\-·|]|\s)\s*([\d,]+)'
            matches = re.findall(pattern, text)
            
            candidates = []
            for duration, count_str in matches:
                try:
                    clean_count = count_str.replace(',', '')
                    val = int(clean_count)
                    if val > 1000: 
                        candidates.append(val)
                except:
                    continue
            
            if candidates:
                return f"{max(candidates)}"

            # Fallback: Look for "plays" keyword
            plays_pattern = r'([\d,]+)\s+(?:plays|streams)'
            plays_matches = re.findall(plays_pattern, text, re.IGNORECASE)
            if plays_matches:
               vals = [int(p.replace(',', '')) for p in plays_matches if p.replace(',', '').isdigit()]
               if vals:
                   return f"{max(vals)}"
                   
            # Deep Fallback: Just Max Number in the whole text
            all_nums = re.findall(r'\b\d{1,3}(?:,\d{3})+\b', text)
            vals = []
            for n in all_nums:
                 try:
                     vals.append(int(n.replace(',', '')))
                 except: pass
            
            if vals:
                return f"{max(vals)}"

        except Exception as e:
            print(f"[ERR] Extraction failed: {e}")
            
        return None

    def load_tracks(self):
        tracks = []
        if not os.path.exists(self.tracks_csv_path):
            print(f"[ERR] Tracks file not found: {self.tracks_csv_path}")
            return []

        with open(self.tracks_csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row.get("Spotify Link", "").startswith("http"):
                    tracks.append(row)
        return tracks

    def load_previous_results(self):
        """Load previous results from the results CSV file."""
        results = []
        if not os.path.exists(self.results_csv_path):
            return results

        try:
            with open(self.results_csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    results.append(row)
        except Exception as e:
            print(f"[WARN] Could not load previous results: {e}")
        return results

    def get_previous_day_streams(self, url):
        """
        Get the most recent stream count for a track from previous results.
        Returns (streams, date) tuple or (None, None) if not found.
        """
        results = self.load_previous_results()
        if not results:
            return None, None

        # Filter results for this URL and sort by timestamp descending
        track_results = [r for r in results if r.get('url') == url]
        if not track_results:
            return None, None

        # Sort by timestamp descending (most recent first)
        track_results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        # Get the most recent result
        latest = track_results[0]
        streams = latest.get('streams', '')
        timestamp = latest.get('timestamp', '')

        # Parse streams as int
        try:
            streams_int = int(str(streams).replace(',', ''))
            return streams_int, timestamp
        except (ValueError, TypeError):
            return None, None

    def check_data_exists_for_date(self):
        """
        Check if data already exists for the target date.
        Returns: (exists, count, date_str)
        """
        target_date = self.override_date or datetime.now().strftime("%Y-%m-%d")
        results = self.load_previous_results()

        # Count records matching target date
        matching = [r for r in results if r.get('timestamp', '').startswith(target_date)]

        return len(matching) > 0, len(matching), target_date

    def check_data_freshness(self):
        """
        Check if Spotify is returning fresh data by scraping a few sample tracks
        and comparing against previous results.

        Returns: (is_fresh, details_message)
        """
        print("\n" + "=" * 60)
        print("[FRESHNESS CHECK] Checking if Spotify data has updated...")
        print("=" * 60)

        # Load tracks to find sample tracks
        all_tracks = self.load_tracks()
        sample_tracks = []

        for url in self.sample_tracks_for_check:
            track = next((t for t in all_tracks if t.get('Spotify Link') == url), None)
            if track:
                sample_tracks.append(track)

        if not sample_tracks:
            print("[WARN] Could not find sample tracks for freshness check, skipping...")
            return True, "No sample tracks found"

        # Check each sample track
        results = []
        for track in sample_tracks:
            title = track.get("Song Title", "Unknown")
            artist = track.get("Artist", "Unknown")
            url = track.get("Spotify Link")

            print(f"\n[CHECK] {title} - {artist}")

            # Get previous streams
            prev_streams, prev_timestamp = self.get_previous_day_streams(url)
            if prev_streams is None:
                print(f"       No previous data found, skipping comparison")
                results.append({'track': title, 'status': 'no_previous', 'changed': True})
                continue

            print(f"       Previous: {prev_streams:,} (from {prev_timestamp})")

            # Scrape current streams
            try:
                self.driver.get(url)
                time.sleep(5)
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(2)

                page_source = self.driver.page_source
                current_streams_str = self.extract_streams_from_html(page_source)

                if current_streams_str and current_streams_str != "N/A":
                    current_streams = int(current_streams_str.replace(',', ''))
                    print(f"       Current:  {current_streams:,}")

                    diff = current_streams - prev_streams
                    changed = diff != 0

                    if changed:
                        print(f"       Change:   {diff:+,} ✓ (Data is fresh!)")
                    else:
                        print(f"       Change:   0 ✗ (No change detected)")

                    results.append({
                        'track': title,
                        'prev': prev_streams,
                        'current': current_streams,
                        'diff': diff,
                        'changed': changed
                    })
                else:
                    print(f"       [WARN] Could not extract streams")
                    results.append({'track': title, 'status': 'extraction_failed', 'changed': True})

            except Exception as e:
                print(f"       [ERR] Error checking track: {e}")
                results.append({'track': title, 'status': 'error', 'changed': True})

        # Analyze results
        print("\n" + "-" * 60)
        tracks_with_data = [r for r in results if 'diff' in r]
        changed_count = sum(1 for r in tracks_with_data if r['changed'])
        total_checked = len(tracks_with_data)

        if total_checked == 0:
            print("[RESULT] Could not compare any tracks, proceeding with scrape...")
            return True, "No comparison data available"

        freshness_ratio = changed_count / total_checked
        is_fresh = freshness_ratio > 0  # At least one track has changed

        if is_fresh:
            print(f"[RESULT] ✓ Data appears FRESH ({changed_count}/{total_checked} tracks have changes)")
            return True, f"{changed_count}/{total_checked} tracks changed"
        else:
            print(f"[RESULT] ✗ Data appears STALE (0/{total_checked} tracks have changes)")
            print("[RESULT] Spotify may be serving cached data.")
            return False, f"0/{total_checked} tracks changed - Spotify serving cached data"

    def run(self, force=False):
        print(f"[START] Processing tracks from {self.tracks_csv_path}")
        tracks = self.load_tracks()
        print(f"[INFO] Found {len(tracks)} tracks.")

        # Check if data already exists for target date
        if not force:
            exists, count, date_str = self.check_data_exists_for_date()
            if exists:
                print(f"\n[SKIP] Data already exists for {date_str} ({count} records found)")
                print("[SKIP] Use --force to scrape anyway.")
                self.driver.quit()
                return

        # Perform freshness check unless skipped or forced
        if not self.skip_freshness_check and not force:
            is_fresh, message = self.check_data_freshness()
            if not is_fresh:
                print("\n" + "=" * 60)
                print("[ABORT] Scraping aborted - Spotify data has not updated.")
                print(f"[ABORT] Reason: {message}")
                print("[ABORT] Try again later or use --force to scrape anyway.")
                print("=" * 60)
                self.driver.quit()
                return
            print("\n" + "=" * 60)
            print("[CONTINUE] Freshness check passed, proceeding with full scrape...")
            print("=" * 60 + "\n")
        elif force:
            print("[INFO] Force mode enabled, skipping freshness check.")
        elif self.skip_freshness_check:
            print("[INFO] Freshness check disabled via --skip-check flag.")

        results = []
        consecutive_errors = 0
        max_consecutive_errors = 3  # Restart browser after this many consecutive failures

        try:
            for i, track in enumerate(tracks):
                title = track.get("Song Title", "Unknown")
                artist = track.get("Artist", "Unknown")
                url = track.get("Spotify Link")
                slug = self._slugify(f"{artist}_{title}")

                print(f"\n[{i+1}/{len(tracks)}] Processing: {title} - {artist}")
                print(f"       URL: {url}")

                result = None
                try:
                    self.driver.get(url)

                    # Wait for SPA to render track content (title changes from generic shell)
                    try:
                        WebDriverWait(self.driver, 15).until(
                            lambda d: d.title and d.title != "Spotify – Web Player" and d.title != "Spotify"
                        )
                    except Exception:
                        print(f"       [WAIT] Page title didn't update, continuing anyway...")

                    # Scroll to trigger lazy-loaded elements
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(2)

                    page_source = self.driver.page_source
                    saved_path = self.save_page_source(page_source, slug)
                    streams = self.extract_streams_from_html(page_source)

                    # Retry up to 2 times if extraction failed
                    for retry in range(2):
                        if streams:
                            break
                        print(f"       [RETRY {retry+1}/2] Stream count not found, reloading...")
                        self.driver.get(url)
                        try:
                            WebDriverWait(self.driver, 20).until(
                                lambda d: d.title and d.title != "Spotify – Web Player" and d.title != "Spotify"
                            )
                        except Exception:
                            pass
                        self.driver.execute_script("window.scrollBy(0, 500);")
                        time.sleep(3)
                        page_source = self.driver.page_source
                        saved_path = self.save_page_source(page_source, slug)
                        streams = self.extract_streams_from_html(page_source)

                    if streams:
                        print(f"       [SUCCESS] Streams: {streams}")
                    else:
                        print(f"       [WARN] Could not extract streams after retries.")
                        streams = "N/A"

                    # Use override date if provided, otherwise use current datetime
                    if self.override_date:
                        timestamp = f"{self.override_date} {datetime.now().strftime('%H:%M:%S')}"
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    result = {
                        "timestamp": timestamp,
                        "song_title": title,
                        "artist": artist,
                        "streams": streams,
                        "url": url,
                        "saved_file": saved_path
                    }
                    results.append(result)
                    consecutive_errors = 0

                except Exception as e:
                    print(f"       [ERR] Error processing track: {e}")
                    consecutive_errors += 1

                    # Restart browser if session died
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"\n[RECOVERY] {consecutive_errors} consecutive errors detected. Restarting browser...")
                        try:
                            self.driver.quit()
                        except Exception:
                            pass
                        time.sleep(3)
                        self.driver = self._setup_driver()
                        consecutive_errors = 0
                        print("[RECOVERY] Browser restarted successfully.\n")

                # Save result immediately (only if we got a new result)
                if result:
                    self._save_result(result)

                # Small pause between tracks
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user.")
        finally:
            self.driver.quit()
            self._git_push()
            print("[DONE] Script finished.")

    def _save_result(self, result):
        if not result:
            return

        fieldnames = ["timestamp", "song_title", "artist", "streams", "url", "saved_file"]
        file_exists = os.path.exists(self.results_csv_path)

        try:
            with open(self.results_csv_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                if not file_exists:
                    writer.writeheader()
                writer.writerow(result)
        except Exception as e:
            print(f"[ERR] Failed to save result to CSV: {e}")

    def _git_push(self):
        """Commit and push results to git repository."""
        git_push(self.results_csv_path, base_dir=self.base_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SB19 Selenium RPA - Scrape Spotify track streams")
    parser.add_argument("tracks_csv", nargs="?", default=None,
                        help="Path to custom tracks CSV file (default: tracks.csv)")
    parser.add_argument("--output", "-o", default=None,
                        help="Path to output results CSV file (default: selenium_results.csv)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force scrape even if Spotify data appears stale (bypasses freshness check)")
    parser.add_argument("--skip-check", "-s", action="store_true",
                        help="Skip the freshness check entirely (same as --force but clearer intent)")
    parser.add_argument("--date", "-d", default=None,
                        help="Override date for timestamps (format: YYYY-MM-DD, e.g., 2026-01-29)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (no visible window)")
    args = parser.parse_args()

    rpa = SB19SeleniumRPA(
        tracks_csv=args.tracks_csv,
        results_csv=args.output,
        skip_freshness_check=args.skip_check,
        override_date=args.date,
        headless=args.headless,
    )
    rpa.run(force=args.force)
