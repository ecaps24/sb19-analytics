import argparse
import csv
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from bs4 import BeautifulSoup


class SB19SeleniumRPA:
    def __init__(self, tracks_csv=None, results_csv=None, skip_freshness_check=False, override_date=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.saved_pages_dir = os.path.join(self.base_dir, "saved_pages")
        os.makedirs(self.saved_pages_dir, exist_ok=True)

        self.tracks_csv_path = tracks_csv or os.path.join(self.base_dir, "tracks.csv")
        self.results_csv_path = results_csv or os.path.join(self.base_dir, "selenium_results.csv")
        self.skip_freshness_check = skip_freshness_check
        self.override_date = override_date  # Date string to use instead of current date (format: YYYY-MM-DD)

        # Sample tracks for freshness check (high-traffic tracks that update frequently)
        self.sample_tracks_for_check = [
            "https://open.spotify.com/track/1o6uF8VmXna99ysHTcQRI2",  # Gento
            "https://open.spotify.com/track/6Fz2TpxUD0YvAPsuG8nDMJ",  # MAPA
            "https://open.spotify.com/track/5QZw4F3N3PvuKNKHm9L20b",  # Bazinga
        ]

        # Setup Driver
        self.driver = self._setup_driver()

    def _setup_driver(self):
        print("[INIT] Setting up Edge WebDriver (using Selenium Manager)...")
        options = EdgeOptions()
        # options.add_argument("--headless=new") # Uncomment to run invisible
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        # Anti-detection (basic)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Selenium 4.6+ automatically manages drivers if Service is initialized without a path
        service = EdgeService()
        try:
            driver = webdriver.Edge(service=service, options=options)
            return driver
        except Exception as e:
            print(f"[ERR] Failed to initialize Edge Driver: {e}")
            raise

    def _slugify(self, text):
        """Create a filename-safe slug."""
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
        return slug

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

        try:
            for i, track in enumerate(tracks):
                title = track.get("Song Title", "Unknown")
                artist = track.get("Artist", "Unknown")
                url = track.get("Spotify Link")
                slug = self._slugify(f"{artist}_{title}")
                
                print(f"\n[{i+1}/{len(tracks)}] Processing: {title} - {artist}")
                print(f"       URL: {url}")
                
                try:
                    self.driver.get(url)
                    time.sleep(5) # Wait for initial load
                    
                    # Scroll down a bit to ensure lazy-loaded elements trigger (sometimes needed)
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(2)
                    
                    page_source = self.driver.page_source
                    saved_path = self.save_page_source(page_source, slug)
                    
                    streams = self.extract_streams_from_html(page_source)
                    
                    if streams:
                        print(f"       [SUCCESS] Streams: {streams}")
                    else:
                        print(f"       [WARN] Could not extract streams.")
                        streams = "N/A"
                        
                    # Use override date if provided, otherwise use current datetime
                    if self.override_date:
                        timestamp = f"{self.override_date} {datetime.now().strftime('%H:%M:%S')}"
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    results.append({
                        "timestamp": timestamp,
                        "song_title": title,
                        "artist": artist,
                        "streams": streams,
                        "url": url,
                        "saved_file": saved_path
                    })
                    
                except Exception as e:
                    print(f"       [ERR] Error processing track: {e}")
                    
                # Save result immediately
                self._save_result(results[-1])
                
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
        print("\n[GIT] Pushing data update to repository...")
        try:
            # Change to base directory
            os.chdir(self.base_dir)

            # Add the results file
            subprocess.run(["git", "add", "selenium_results.csv"], check=True, capture_output=True)

            # Commit with auto-generated message
            commit_msg = "Auto-push data update"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"[GIT] Committed: {commit_msg}")
                # Push to remote
                push_result = subprocess.run(["git", "push"], capture_output=True, text=True)
                if push_result.returncode == 0:
                    print("[GIT] Successfully pushed to remote.")
                else:
                    print(f"[GIT] Push failed: {push_result.stderr}")
            elif "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("[GIT] No changes to commit.")
            else:
                print(f"[GIT] Commit failed: {result.stderr}")

        except subprocess.CalledProcessError as e:
            print(f"[GIT] Git operation failed: {e}")
        except Exception as e:
            print(f"[GIT] Error during git push: {e}")

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
    args = parser.parse_args()

    rpa = SB19SeleniumRPA(
        tracks_csv=args.tracks_csv,
        results_csv=args.output,
        skip_freshness_check=args.skip_check,
        override_date=args.date
    )
    rpa.run(force=args.force)
