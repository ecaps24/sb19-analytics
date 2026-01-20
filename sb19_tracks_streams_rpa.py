import csv
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime

import pyautogui
import pytesseract
from PIL import Image, ImageOps

try:
    import pygetwindow as gw
except ImportError:
    gw = None


class SB19TrackStreamsRPA:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0

        self.edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(self.edge_path):
            self.edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

        self.tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(self.tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        else:
            print(f"[WARN] Tesseract executable not found at {self.tesseract_path}")

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "OCR")
        os.makedirs(self.output_dir, exist_ok=True)

        self.track_list_path = os.path.join(self.base_dir, "tracks.csv")
        self.results_csv_path = os.path.join(self.base_dir, "sb19_streams_results.csv")

        # Load existing results for duplicate checking and daily streams calculation
        self.existing_results = self._load_existing_results()
        self.today_date = datetime.now().strftime("%Y%m%d")

    def _load_existing_results(self) -> dict:
        """Load existing results to track previous streams and check for duplicates."""
        results = {}  # key: (song_title, artist) -> list of {date, streams}

        if not os.path.exists(self.results_csv_path):
            return results

        try:
            with open(self.results_csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                for row in reader:
                    song_title = row.get("song_title", "").strip()
                    artist = row.get("artist", "").strip()
                    timestamp = row.get("timestamp", "").strip()
                    streams_str = row.get("streams", "0").strip()

                    if not song_title or not timestamp:
                        continue

                    # Extract date from timestamp (YYYYMMDD_HHMMSS -> YYYYMMDD)
                    date = timestamp.split("_")[0] if "_" in timestamp else timestamp[:8]

                    try:
                        streams = int(streams_str.replace(",", ""))
                    except ValueError:
                        streams = 0

                    key = (song_title.lower(), artist.lower())
                    if key not in results:
                        results[key] = []
                    results[key].append({"date": date, "streams": streams, "timestamp": timestamp})

            # Sort each track's history by timestamp
            for key in results:
                results[key].sort(key=lambda x: x["timestamp"])

            print(f"[OK] Loaded history for {len(results)} tracks")
        except Exception as exc:
            print(f"[WARN] Unable to load existing results: {exc}")

        return results

    def _is_already_scraped_today(self, song_title: str, artist: str) -> bool:
        """Check if a track has already been scraped today."""
        key = (song_title.lower(), artist.lower())
        if key not in self.existing_results:
            return False

        for entry in self.existing_results[key]:
            if entry["date"] == self.today_date:
                return True
        return False

    def _get_previous_streams(self, song_title: str, artist: str) -> int | None:
        """Get the most recent previous streams count for calculating daily change."""
        key = (song_title.lower(), artist.lower())
        if key not in self.existing_results:
            return None

        # Get entries from previous days (not today)
        previous_entries = [e for e in self.existing_results[key] if e["date"] != self.today_date]
        if not previous_entries:
            return None

        # Return the most recent one
        return previous_entries[-1]["streams"]

    def _calculate_daily_streams(self, current_streams: int, song_title: str, artist: str) -> int:
        """Calculate daily streams by comparing with previous day's total."""
        previous = self._get_previous_streams(song_title, artist)
        if previous is None:
            return 0  # No previous data, can't calculate daily change
        daily_change = max(0, current_streams - previous)  # Ensure non-negative
        # If change > 10% of total streams, it's likely an OCR error - set to 0
        if current_streams > 0 and daily_change / current_streams > 0.1:
            print(f"[WARN] Change ({daily_change:,}) > 10% of total ({current_streams:,}) - setting to 0")
            return 0
        return daily_change

    def _validate_streams(self, current_streams: int, song_title: str, artist: str) -> tuple[bool, str]:
        """
        Validate that streams count is reasonable (should be >= previous day).
        Returns (is_valid, message).
        """
        previous = self._get_previous_streams(song_title, artist)
        if previous is None:
            return True, "No previous data to compare"

        if current_streams < previous:
            diff = previous - current_streams
            pct_diff = (diff / previous) * 100
            return False, f"OCR Error? Current ({current_streams:,}) < Previous ({previous:,}) by {diff:,} ({pct_diff:.1f}%)"

        if current_streams == previous:
            return True, "No change from previous"

        daily_gain = current_streams - previous
        return True, f"Valid: +{daily_gain:,} from previous"

    @staticmethod
    def _slugify(*parts: str) -> str:
        merged = "_".join(parts)
        normalized = unicodedata.normalize("NFKD", merged)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
        return slug or "item"

    def load_tracks(self, csv_path: str | None = None) -> list[dict[str, str]]:
        path = csv_path or self.track_list_path
        tracks: list[dict[str, str]] = []

        if not os.path.exists(path):
            print(f"[WARN] Track list not found at {path}")
            return tracks

        try:
            with open(path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                for row in reader:
                    song_title = (row.get("Song Title") or "").strip()
                    artist = (row.get("Artist") or "").strip()
                    year = (row.get("Year") or "").strip()
                    album = (row.get("Album/EP/Single") or "").strip()
                    collab = (row.get("Collaborating Artist(s)") or "").strip()
                    spotify_link = (row.get("Spotify Link") or "").strip()

                    # Skip rows without valid Spotify URL
                    if not song_title or not spotify_link or not spotify_link.startswith("http"):
                        continue

                    tracks.append({
                        "song_title": song_title,
                        "artist": artist,
                        "year": year,
                        "album": album,
                        "collaborating_artists": collab,
                        "spotify_link": spotify_link,
                    })
        except Exception as exc:
            print(f"[WARN] Unable to read track CSV ({exc})")

        if not tracks:
            print(f"[WARN] No valid track entries found in {path}")
        else:
            print(f"[OK] Loaded {len(tracks)} tracks from {path}")
        return tracks

    def open_edge_with_url(self, url: str) -> bool:
        print("Step 1: Opening Spotify track in Edge...")
        print(f"URL: {url}")

        try:
            subprocess.Popen([self.edge_path, "--new-window", "--start-maximized", url])
            print("[OK] Edge launch requested (new window)")
            time.sleep(10)
            return True
        except FileNotFoundError:
            print(f"Edge executable not found at: {self.edge_path}")
            print("Attempting to use default browser instead...")
            import webbrowser
            webbrowser.open(url)
            time.sleep(10)
            return True
        except Exception as exc:
            print(f"Error launching browser: {exc}")
            return False

    def focus_edge_window(self):
        if gw is None:
            print("[WARN] pygetwindow not available; relying on active window.")
            return None

        try:
            for title in ["Spotify", "Microsoft Edge", "Edge"]:
                windows = gw.getWindowsWithTitle(title)
                if not windows:
                    continue
                window = windows[0]
                if window.isMinimized:
                    window.restore()
                    time.sleep(1)
                try:
                    window.maximize()
                    time.sleep(1)
                except Exception:
                    pass
                window.activate()
                time.sleep(2)
                print(f"[OK] Focused window titled '{window.title}'")
                return window
            print("[WARN] No Edge window found to focus.")
            return None
        except Exception as exc:
            print(f"[WARN] Unable to focus Edge window: {exc}")
            return None

    @staticmethod
    def close_edge_window(window=None):
        try:
            if window is not None:
                window.close()
            else:
                pyautogui.hotkey("alt", "f4")
            time.sleep(2)
        except Exception as exc:
            print(f"[WARN] Unable to close Edge window cleanly: {exc}")
            pyautogui.hotkey("alt", "f4")
            time.sleep(2)

    def force_close_edge(self):
        """Force close all Edge windows/processes to ensure clean state for next track."""
        closed_any = False

        # First try closing via pygetwindow
        if gw is not None:
            try:
                for title in ["Spotify", "Microsoft Edge", "Edge"]:
                    for window in gw.getWindowsWithTitle(title):
                        try:
                            window.close()
                            closed_any = True
                        except Exception:
                            continue
            except Exception as exc:
                print(f"[WARN] Unable to close Edge via pygetwindow: {exc}")

        # Then force kill via taskkill to ensure complete closure
        try:
            result = subprocess.run(
                ["taskkill", "/IM", "msedge.exe", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            output_text = f"{result.stdout or ''}{result.stderr or ''}".lower()
            if result.returncode == 0:
                closed_any = True
            elif "not found" not in output_text:
                err_text = (result.stderr or result.stdout or "").strip()
                print(f"[WARN] taskkill exited with code {result.returncode}: {err_text}")
        except FileNotFoundError:
            print("[WARN] taskkill command not available; cannot force-close Edge.")
        except Exception as exc:
            print(f"[WARN] Unable to force close Edge: {exc}")

        if closed_any:
            print("[OK] Edge browser closed.")

        # Wait for Edge to fully close before continuing
        time.sleep(3)

    def capture_screenshot(self, slug: str, window=None) -> tuple[str, str]:
        print("Step 2: Capturing screenshot...")
        time.sleep(3)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_screenshot_{timestamp}.png"
        screenshot_path = os.path.join(self.output_dir, filename)

        try:
            if window:
                try:
                    region = (int(window.left), int(window.top), int(window.width), int(window.height))
                    shot = pyautogui.screenshot(region=region)
                except Exception as exc:
                    print(f"[WARN] Window capture failed ({exc}); capturing full screen instead.")
                    shot = pyautogui.screenshot()
            else:
                shot = pyautogui.screenshot()

            shot.save(screenshot_path)
            print(f"[OK] Screenshot saved: {screenshot_path}")
            return screenshot_path, timestamp
        except Exception as exc:
            print(f"Error capturing screenshot: {exc}")
            return "", timestamp

    def prepare_ocr_image(self, screenshot_path: str, slug: str, timestamp: str) -> str:
        processed_filename = f"{slug}_streams_region_{timestamp}.png"
        processed_path = os.path.join(self.output_dir, processed_filename)

        try:
            with Image.open(screenshot_path) as img:
                width, height = img.size

                # Crop to region where stream count typically appears
                left = int(width * 0.40)
                top = int(height * 0.12)
                right = int(width * 0.95)
                bottom = int(height * 0.40)
                cropped = img.crop((left, top, right, bottom))

                # Image preprocessing for better OCR
                grayscale = ImageOps.grayscale(cropped)
                enhanced = ImageOps.autocontrast(grayscale)
                binary = enhanced.point(lambda p: 255 if p > 180 else 0)
                inverted = ImageOps.invert(binary)

                # Upscale for better OCR accuracy
                upscale_factor = 2
                resampling_attr = getattr(Image, "Resampling", Image)
                resample_mode = getattr(resampling_attr, "LANCZOS", Image.LANCZOS)
                resized = inverted.resize(
                    (inverted.width * upscale_factor, inverted.height * upscale_factor),
                    resample=resample_mode,
                )
                resized.save(processed_path)

            print(f"[INFO] Prepared OCR image: {processed_path}")
            return processed_path
        except Exception as exc:
            print(f"[WARN] Unable to preprocess screenshot for OCR: {exc}")
            return screenshot_path

    @staticmethod
    def _parse_streams(text: str) -> str | None:
        normalized = text.lower()

        patterns = [
            r"([\d,]+\s*plays)",
            r"plays\s*([\d,]+)",
            r"([\d,]+\s*streams)",
            r"streams\s*([\d,]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                digits = re.sub(r"[^\d]", "", match.group(1))
                if digits:
                    return digits

        # Fallback: grab first number with at least six digits
        fallback = re.search(r"\b[\d,]{6,}\b", text)
        if fallback:
            digits = re.sub(r"[^\d]", "", fallback.group())
            if digits:
                return digits
        return None

    def extract_streams(self, screenshot_path: str, slug: str, timestamp: str) -> tuple[str | None, str, str]:
        print("Step 3: Performing OCR to extract total streams...")
        processed_path = self.prepare_ocr_image(screenshot_path, slug, timestamp)

        try:
            text = pytesseract.image_to_string(Image.open(processed_path), config="--oem 3 --psm 6")
            streams = self._parse_streams(text)

            # Fallback: try full screenshot if cropped region fails
            if not streams and processed_path != screenshot_path:
                fallback_text = pytesseract.image_to_string(Image.open(screenshot_path), config="--oem 3 --psm 6")
                streams = self._parse_streams(fallback_text)
                text = text + "\n----\nFallback:\n" + fallback_text

            if streams:
                print(f"[OK] Total streams detected: {streams}")
            else:
                print("[WARN] Unable to detect total streams from OCR.")

            return streams, text, processed_path
        except Exception as exc:
            print(f"Error during OCR: {exc}")
            return None, "", processed_path

    def save_track_result(
        self,
        run_timestamp: str,
        song_title: str,
        artist: str,
        year: str,
        album: str,
        collaborating_artists: str,
        spotify_link: str,
        streams: str,
        daily_streams: int,
        screenshot_path: str,
    ) -> None:
        file_exists = os.path.exists(self.results_csv_path)

        with open(self.results_csv_path, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            if not file_exists:
                writer.writerow([
                    "timestamp",
                    "song_title",
                    "artist",
                    "year",
                    "album",
                    "collaborating_artists",
                    "spotify_link",
                    "streams",
                    "daily_streams",
                    "screenshot_path",
                ])
            writer.writerow([
                run_timestamp,
                song_title,
                artist,
                year,
                album,
                collaborating_artists,
                spotify_link,
                streams,
                daily_streams,
                screenshot_path,
            ])

        print(f"[OK] Track result saved to: {self.results_csv_path}")
        if daily_streams > 0:
            print(f"[OK] Daily streams: +{daily_streams:,}")

    @staticmethod
    def _save_debug_text(slug: str, timestamp: str, text: str, directory: str) -> None:
        if not text:
            return
        debug_path = os.path.join(directory, f"{slug}_ocr_debug_{timestamp}.txt")
        try:
            with open(debug_path, "w", encoding="utf-8") as handle:
                handle.write(text)
            print(f"[INFO] OCR debug output saved to: {debug_path}")
        except Exception as exc:
            print(f"[WARN] Unable to write OCR debug text: {exc}")

    def process_track(self, track: dict[str, str], run_timestamp: str, force: bool = False, max_retries: int = 2) -> bool:
        """Process a single track. Returns True if processed, False if skipped."""
        song_title = track["song_title"]
        artist = track["artist"]
        year = track["year"]
        album = track["album"]
        collab = track["collaborating_artists"]
        spotify_link = track["spotify_link"]

        separator = "=" * 70
        print(separator)
        # Handle Unicode characters that can't be displayed in Windows console
        try:
            print(f"Processing: {song_title} by {artist} ({year}) - {album}")
            if collab:
                print(f"Featuring: {collab}")
        except UnicodeEncodeError:
            print(f"Processing: {song_title.encode('ascii', 'replace').decode()} by {artist} ({year}) - {album}")
            if collab:
                print(f"Featuring: {collab.encode('ascii', 'replace').decode()}")
        print(separator)

        # Always scrape - dashboard will use latest entry per track

        slug = self._slugify(artist, song_title, year)

        last_screenshot_path = ""
        last_ocr_text = ""

        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"\n[RETRY {attempt}/{max_retries}] Re-attempting OCR...")

            if not self.open_edge_with_url(spotify_link):
                print(f"[WARN] Browser launch failed for {song_title}.")
                self.force_close_edge()
                if attempt == max_retries:
                    # Use previous day's streams instead of 0
                    previous_streams = self._get_previous_streams(song_title, artist)
                    if previous_streams:
                        print(f"[FALLBACK] Browser failed. Using previous day's streams: {previous_streams:,}")
                        self.save_track_result(
                            run_timestamp, song_title, artist, year, album, collab,
                            spotify_link, str(previous_streams), 0, last_screenshot_path or "",
                        )
                        return True
                    else:
                        print(f"[ERROR] Browser failed. No previous data available.")
                        self.save_track_result(
                            run_timestamp, song_title, artist, year, album, collab,
                            spotify_link, "0", 0, last_screenshot_path or "",
                        )
                        return False
                continue

            window = None
            try:
                window = self.focus_edge_window()

                screenshot_path, screenshot_timestamp = self.capture_screenshot(slug, window)
                last_screenshot_path = screenshot_path or last_screenshot_path

                if not screenshot_path:
                    print(f"[WARN] Screenshot capture failed for {song_title}.")
                    if attempt == max_retries:
                        # Use previous day's streams instead of 0
                        previous_streams = self._get_previous_streams(song_title, artist)
                        if previous_streams:
                            print(f"[FALLBACK] Screenshot failed. Using previous day's streams: {previous_streams:,}")
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, str(previous_streams), 0, last_screenshot_path,
                            )
                            return True
                        else:
                            print(f"[ERROR] Screenshot failed. No previous data available.")
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, "0", 0, last_screenshot_path,
                            )
                            return False
                    continue

                # Close Edge window before OCR processing
                if window is not None:
                    self.close_edge_window(window)
                    window = None

                streams, ocr_text, processed_path = self.extract_streams(screenshot_path, slug, screenshot_timestamp)
                last_ocr_text = ocr_text

                if streams:
                    streams_int = int(streams.replace(",", ""))

                    # Validate streams against previous data
                    is_valid, validation_msg = self._validate_streams(streams_int, song_title, artist)
                    print(f"[VALIDATION] {validation_msg}")

                    if not is_valid:
                        if attempt < max_retries:
                            print(f"[WARN] Invalid streams detected. Will retry...")
                            self.force_close_edge()
                            time.sleep(2)
                            continue  # Retry
                        else:
                            # Use previous day's streams instead of 0
                            previous_streams = self._get_previous_streams(song_title, artist)
                            if previous_streams:
                                print(f"[FALLBACK] Using previous day's streams: {previous_streams:,}")
                                self._save_debug_text(slug, screenshot_timestamp, f"VALIDATION FAILED: {validation_msg}\n\n{ocr_text}", self.output_dir)
                                self.save_track_result(
                                    run_timestamp, song_title, artist, year, album, collab,
                                    spotify_link, str(previous_streams), 0, screenshot_path,
                                )
                                return True
                            else:
                                print(f"[ERROR] Invalid streams after {max_retries} retries. No previous data available.")
                                self._save_debug_text(slug, screenshot_timestamp, f"VALIDATION FAILED: {validation_msg}\n\n{ocr_text}", self.output_dir)
                                self.save_track_result(
                                    run_timestamp, song_title, artist, year, album, collab,
                                    spotify_link, "0", 0, screenshot_path,
                                )
                                return False

                    # Valid streams - calculate daily and save
                    daily_streams = self._calculate_daily_streams(streams_int, song_title, artist)

                    self.save_track_result(
                        run_timestamp,
                        song_title,
                        artist,
                        year,
                        album,
                        collab,
                        spotify_link,
                        streams,
                        daily_streams,
                        screenshot_path,
                    )
                    return True
                else:
                    if attempt < max_retries:
                        print(f"[WARN] OCR failed to detect streams. Will retry...")
                        self.force_close_edge()
                        time.sleep(2)
                        continue  # Retry
                    else:
                        # Use previous day's streams instead of 0
                        previous_streams = self._get_previous_streams(song_title, artist)
                        if previous_streams:
                            print(f"[FALLBACK] OCR failed. Using previous day's streams: {previous_streams:,}")
                            self._save_debug_text(slug, screenshot_timestamp, ocr_text, self.output_dir)
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, str(previous_streams), 0, screenshot_path,
                            )
                            return True
                        else:
                            print(f"[ERROR] OCR failed after {max_retries} retries. No previous data available.")
                            self._save_debug_text(slug, screenshot_timestamp, ocr_text, self.output_dir)
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, "0", 0, screenshot_path,
                            )
                            return False
            finally:
                # Always ensure Edge is closed after each attempt
                if window is not None:
                    self.close_edge_window(window)
                self.force_close_edge()

        print("[OK] Edge closed, ready for next track.\n")
        return False

    def run(self, track_csv_path: str | None = None, force: bool = False) -> None:
        print("=" * 70)
        print("SB19 Track Streams Automation")
        print("=" * 70)
        print()

        tracks = self.load_tracks(track_csv_path)
        if not tracks:
            print("No tracks to process; exiting.")
            return

        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"Run timestamp: {run_timestamp}")
        print(f"Today's date: {self.today_date}")
        print(f"Total tracks in list: {len(tracks)}")
        print("[MODE] Always scrape - dashboard uses latest entry per track")
        print()

        processed = 0
        failed = 0

        for idx, track in enumerate(tracks, start=1):
            print(f"\n[{idx}/{len(tracks)}]")
            result = self.process_track(track, run_timestamp, force=force)
            if result:
                processed += 1
            else:
                failed += 1

        print("\n" + "=" * 70)
        print("Run Complete!")
        print("=" * 70)
        print(f"Processed: {processed}")
        print(f"Failed: {failed}")
        print(f"Results CSV: {self.results_csv_path}")
        print(f"Screenshots: {self.output_dir}")


if __name__ == "__main__":
    import sys

    force_mode = "--force" in sys.argv or "-f" in sys.argv

    # Check for custom CSV path
    csv_path = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and arg.endswith(".csv"):
            csv_path = arg
            break

    rpa = SB19TrackStreamsRPA()
    rpa.run(track_csv_path=csv_path, force=force_mode)
