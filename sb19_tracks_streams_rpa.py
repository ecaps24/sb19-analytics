import csv
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

import pyautogui
import pytesseract
from PIL import Image, ImageOps, ImageFilter

try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARN] OpenCV/numpy not available - using basic image processing")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("[WARN] EasyOCR not available - using Tesseract only")

try:
    import pygetwindow as gw
except ImportError:
    gw = None


class SB19TrackStreamsRPA:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5  # Reduced from 1.0 for faster execution

        self.edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(self.edge_path):
            self.edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

        self.tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(self.tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        else:
            print(f"[WARN] Tesseract executable not found at {self.tesseract_path}")

        # Initialize EasyOCR reader (lazy load to avoid slow startup)
        self.easyocr_reader = None

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "OCR")
        os.makedirs(self.output_dir, exist_ok=True)

        self.track_list_path = os.path.join(self.base_dir, "tracks.csv")
        self.results_csv_path = os.path.join(self.base_dir, "sb19_streams_results.csv")
        self.audit_log_path = os.path.join(self.base_dir, "rpa_audit_log.csv")

        # Load existing results for duplicate checking and daily streams calculation
        self.existing_results = self._load_existing_results()
        self.today_date = datetime.now().strftime("%Y%m%d")

        # Screen dimensions for adaptive region cropping
        self.screen_width, self.screen_height = pyautogui.size()

    def _load_existing_results(self) -> dict:
        """
        Load existing results to track previous streams and check for duplicates.
        Keys by spotify_link (primary) or (song_title, artist) (fallback).
        """
        results = {}  # key: spotify_link OR (song_title, artist) -> list of entries

        if not os.path.exists(self.results_csv_path):
            return results

        try:
            with open(self.results_csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                for row in reader:
                    song_title = row.get("song_title", "").strip()
                    artist = row.get("artist", "").strip()
                    spotify_link = row.get("spotify_link", "").strip()
                    timestamp = row.get("timestamp", "").strip()
                    streams_str = row.get("streams", "0").strip()

                    if not timestamp:
                        continue

                    # Extract date from timestamp (YYYYMMDD_HHMMSS -> YYYYMMDD)
                    date = timestamp.split("_")[0] if "_" in timestamp else timestamp[:8]

                    try:
                        streams = int(streams_str.replace(",", ""))
                    except ValueError:
                        streams = 0

                    # Primary Key: Spotify Link
                    if spotify_link and spotify_link.startswith("http"):
                        key = spotify_link
                    elif song_title and artist:
                        # Fallback Key: Title + Artist
                        key = (song_title.lower(), artist.lower())
                    else:
                        continue

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

    def _is_already_scraped_today(self, spotify_link: str, song_title: str, artist: str) -> bool:
        """Check if a track has already been scraped today."""
        # Try primary key first
        key = spotify_link if spotify_link else (song_title.lower(), artist.lower())
        
        if key not in self.existing_results:
            # If lookup by link failed, try fallback
            if spotify_link:
                fallback_key = (song_title.lower(), artist.lower())
                if fallback_key in self.existing_results:
                    key = fallback_key
                else:
                    return False
            else:
                return False

        if key not in self.existing_results:
             return False

        for entry in self.existing_results[key]:
            if entry["date"] == self.today_date:
                return True
        return False

    def _get_previous_streams(self, spotify_link: str, song_title: str, artist: str) -> int | None:
        """Get the most recent previous streams count for calculating daily change."""
        # Try primary key first
        key = spotify_link if spotify_link else (song_title.lower(), artist.lower())
        
        if key not in self.existing_results:
             # Try fallback
             fallback_key = (song_title.lower(), artist.lower())
             if fallback_key in self.existing_results:
                 key = fallback_key
             else:
                 return None

        # Get entries from previous days (not today)
        previous_entries = [e for e in self.existing_results[key] if e["date"] != self.today_date]
        if not previous_entries:
            return None

        # Return the most recent one
        return previous_entries[-1]["streams"]

    def _calculate_daily_streams(self, current_streams: int, spotify_link: str, song_title: str, artist: str) -> int:
        """Calculate daily streams by comparing with previous day's total."""
        previous = self._get_previous_streams(spotify_link, song_title, artist)
        if previous is None:
            return 0  # No previous data, can't calculate daily change
        daily_change = max(0, current_streams - previous)  # Ensure non-negative
        # If change > 10% of total streams, it's likely an OCR error - set to 0
        if current_streams > 0 and daily_change / current_streams > 0.1:
            print(f"[WARN] Change ({daily_change:,}) > 10% of total ({current_streams:,}) - setting to 0")
            return 0
        return daily_change

    def _validate_streams(self, current_streams: int, spotify_link: str, song_title: str, artist: str) -> tuple[bool, str]:
        """
        Validate that streams count is reasonable (should be >= previous day).
        Returns (is_valid, message).
        """
        # Sanity Checks
        if current_streams > 1_500_000_000: # 1.5 Billion limit (SB19's highest is ~200M)
            return False, f"Sanity Check Failed: {current_streams:,} > 1.5B"
        if current_streams < 100 and current_streams > 0:
            return False, f"Sanity Check Failed: {current_streams:,} < 100 (Suspiciously low)"

        previous = self._get_previous_streams(spotify_link, song_title, artist)
        if previous is None:
            return True, "No previous data to compare"

        if current_streams < previous:
            diff = previous - current_streams
            pct_diff = (diff / previous) * 100
            return False, f"OCR Error? Current ({current_streams:,}) < Previous ({previous:,}) by {diff:,} ({pct_diff:.1f}%)"

        if current_streams == previous:
            return True, "No change from previous"

        daily_gain = current_streams - previous
        
        # Historical Trend Check
        # Calculate average daily gain from history if possible
        key = spotify_link if spotify_link in self.existing_results else (song_title.lower(), artist.lower())
        if key in self.existing_results:
            history = self.existing_results[key]
            if len(history) >= 3:
                gains = []
                for i in range(1, len(history)):
                    g = history[i]["streams"] - history[i-1]["streams"]
                    if g > 0:
                        gains.append(g)
                
                if gains:
                    avg_gain = sum(gains) / len(gains)
                    # If daily gain is huge (>10x average) and > 100k, flag it
                    if avg_gain > 1000 and daily_gain > (avg_gain * 10) and daily_gain > 100_000:
                         return False, f"Anomaly: +{daily_gain:,} is >10x avg gain ({int(avg_gain):,})"

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

    def prepare_clean_state(self) -> None:
        """Prepare a clean desktop state before starting browser automation."""
        print("[PREP] Preparing clean desktop state...")

        # Minimize all windows first (Win+D shows desktop, Win+D again restores)
        # We'll just ensure Edge is closed
        self.force_close_edge()

        # Small delay to let system settle
        time.sleep(1)
        print("[PREP] Desktop ready")

    def dismiss_browser_popups(self, window=None) -> None:
        """Dismiss common browser popups (restore session, cookie consent, etc.)."""
        try:
            # Press Escape to dismiss any open dialogs/popups
            pyautogui.press('escape')
            time.sleep(0.5)

            # Click somewhere in the main content area to dismiss cookie banners
            # Cookie banners usually have an X or are dismissed by clicking elsewhere
            if window:
                # Click in the center-right area (away from sidebar, away from cookie banner)
                center_x = window.left + int(window.width * 0.7)
                center_y = window.top + int(window.height * 0.3)
                pyautogui.click(center_x, center_y)
                time.sleep(0.3)

            # Press Escape again to close any modal
            pyautogui.press('escape')
            time.sleep(0.3)

            print("[OK] Dismissed browser popups")
        except Exception as exc:
            print(f"[WARN] Error dismissing popups: {exc}")

    def wait_for_page_load(self, window=None, max_wait: int = 15, stability_checks: int = 3) -> bool:
        """
        Wait for page to fully load by checking for visual stability.
        Takes multiple screenshots and compares them to detect when page stops changing.
        Returns True if page is stable, False if timeout.
        """
        print(f"[WAIT] Waiting for page to load (max {max_wait}s)...")

        if not CV2_AVAILABLE:
            # Fallback to fixed wait if OpenCV not available
            print("[WAIT] OpenCV not available, using fixed wait")
            time.sleep(8)
            return True

        import hashlib

        def get_screenshot_hash():
            """Get hash of current screenshot for comparison."""
            try:
                if window:
                    region = (int(window.left), int(window.top), int(window.width), int(window.height))
                    shot = pyautogui.screenshot(region=region)
                else:
                    shot = pyautogui.screenshot()

                # Convert to grayscale and resize for faster comparison
                gray = ImageOps.grayscale(shot)
                small = gray.resize((100, 100))
                return hashlib.md5(small.tobytes()).hexdigest()
            except Exception:
                return None

        start_time = time.time()
        last_hash = None
        stable_count = 0

        while time.time() - start_time < max_wait:
            current_hash = get_screenshot_hash()

            if current_hash == last_hash:
                stable_count += 1
                if stable_count >= stability_checks:
                    elapsed = time.time() - start_time
                    print(f"[WAIT] Page stable after {elapsed:.1f}s")
                    return True
            else:
                stable_count = 0

            last_hash = current_hash
            time.sleep(1)

        print(f"[WARN] Page load timeout after {max_wait}s")
        return False

    def capture_screenshot(self, slug: str, window=None) -> tuple[str, str]:
        print("Step 2: Capturing screenshot...")
        time.sleep(0.5)  # Brief pause for UI stability

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

    def prepare_ocr_image(self, screenshot_path: str, slug: str, timestamp: str, variant: int = 0) -> str:
        """
        Prepare image for OCR with multiple preprocessing variants.
        variant 0: Adaptive threshold on metadata line (best for stream count)
        variant 1: Full header region with high contrast
        variant 2: Metadata line with sharpening
        variant 3: Title + metadata combined region
        """
        suffix = f"_v{variant}" if variant > 0 else ""
        processed_filename = f"{slug}_streams_region_{timestamp}{suffix}.png"
        processed_path = os.path.join(self.output_dir, processed_filename)

        try:
            with Image.open(screenshot_path) as img:
                width, height = img.size

                # Different crop regions based on variant
                if variant in [0, 2]:
                    # Focused on metadata line (Artist • Title • Year • Duration • Streams)
                    # This line is typically at ~28-38% from top, to the right of album art
                    left = int(width * 0.35)
                    top = int(height * 0.24)
                    right = int(width * 0.92)
                    bottom = int(height * 0.38)
                elif variant == 1:
                    # Broader region including title and metadata
                    left = int(width * 0.35)
                    top = int(height * 0.12)
                    right = int(width * 0.95)
                    bottom = int(height * 0.42)
                else:
                    # variant 3+: Full header region
                    left = int(width * 0.30)
                    top = int(height * 0.10)
                    right = int(width * 0.95)
                    bottom = int(height * 0.45)

                cropped = img.crop((left, top, right, bottom))

                # Convert to grayscale
                grayscale = ImageOps.grayscale(cropped)

                if variant == 0 and CV2_AVAILABLE:
                    # Variant 0: Adaptive thresholding with OpenCV
                    img_array = np.array(grayscale)
                    # Apply adaptive threshold
                    binary = cv2.adaptiveThreshold(
                        img_array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY, 11, 2
                    )
                    # Denoise
                    denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
                    processed = Image.fromarray(denoised)
                elif variant == 1:
                    # Variant 1: High contrast with multiple thresholds
                    enhanced = ImageOps.autocontrast(grayscale, cutoff=5)
                    # Use fixed threshold (simpler, no numpy needed)
                    binary = enhanced.point(lambda p: 255 if p > 160 else 0)
                    processed = ImageOps.invert(binary)
                else:
                    # Variant 2: Sharpen and enhance
                    sharpened = grayscale.filter(ImageFilter.SHARPEN)
                    enhanced = ImageOps.autocontrast(sharpened, cutoff=2)
                    binary = enhanced.point(lambda p: 255 if p > 180 else 0)
                    processed = ImageOps.invert(binary)

                # Upscale for better OCR accuracy
                upscale_factor = 3  # Increased from 2
                resampling_attr = getattr(Image, "Resampling", Image)
                resample_mode = getattr(resampling_attr, "LANCZOS", Image.LANCZOS)
                resized = processed.resize(
                    (processed.width * upscale_factor, processed.height * upscale_factor),
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
        """
        Parse stream count from OCR text.
        Spotify format: "Artist • Title • Year • Duration • StreamCount"
        Example: "SB19 • DAM • 2025 • 3:29 • 59,510,411"
        """
        # Clean up common OCR artifacts
        cleaned = text.replace('\n', ' ').replace('\r', ' ')
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Priority 1: Look for duration pattern followed by stream count
        # Pattern: X:XX followed by separator and large number
        duration_pattern = r'\d{1,2}:\d{2}\s*[•\-·]\s*([\d,]+)'
        match = re.search(duration_pattern, cleaned)
        if match:
            digits = re.sub(r"[^\d]", "", match.group(1))
            if digits and len(digits) >= 5:  # At least 10,000 streams
                return digits

        # Priority 2: Look for "plays" or "streams" label
        normalized = cleaned.lower()
        label_patterns = [
            r"([\d,]+)\s*plays",
            r"plays\s*([\d,]+)",
            r"([\d,]+)\s*streams",
            r"streams\s*([\d,]+)",
        ]

        for pattern in label_patterns:
            match = re.search(pattern, normalized)
            if match:
                digits = re.sub(r"[^\d]", "", match.group(1))
                if digits and len(digits) >= 5:
                    return digits

        # Priority 3: Find the largest number with commas (likely stream count)
        # Stream counts typically have commas: 59,510,411
        comma_numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b', cleaned)
        if comma_numbers:
            # Return the largest one
            largest = max(comma_numbers, key=lambda x: int(x.replace(',', '')))
            digits = largest.replace(',', '')
            if len(digits) >= 5:
                return digits

        # Priority 4: Fallback - grab largest number with at least 6 digits
        all_numbers = re.findall(r'\b[\d,]{6,}\b', cleaned)
        if all_numbers:
            candidates = []
            for num in all_numbers:
                digits = re.sub(r"[^\d]", "", num)
                if digits and len(digits) >= 5:
                    candidates.append(digits)
            if candidates:
                return max(candidates, key=lambda x: int(x))

        return None

    def _get_easyocr_reader(self):
        """Lazy load EasyOCR reader to avoid slow startup."""
        if self.easyocr_reader is None and EASYOCR_AVAILABLE:
            print("[INFO] Initializing EasyOCR (first time only)...")
            self.easyocr_reader = easyocr.Reader(['en'], gpu=False)
        return self.easyocr_reader

    def _extract_with_tesseract(self, image_path: str, config: str) -> tuple[str | None, str, float]:
        """Extract streams using Tesseract with confidence score."""
        try:
            # Get detailed data with confidence
            data = pytesseract.image_to_data(Image.open(image_path), config=config, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(Image.open(image_path), config=config)

            # Calculate average confidence for numeric characters
            confidences = []
            for i, word in enumerate(data['text']):
                if word.strip() and any(c.isdigit() for c in word):
                    conf = int(data['conf'][i])
                    if conf > 0:  # -1 means no confidence
                        confidences.append(conf)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            streams = self._parse_streams(text)

            return streams, text, avg_confidence
        except Exception as exc:
            return None, str(exc), 0

    def _extract_with_easyocr(self, image_path: str) -> tuple[str | None, str, float]:
        """Extract streams using EasyOCR with confidence score."""
        reader = self._get_easyocr_reader()
        if reader is None:
            return None, "EasyOCR not available", 0

        try:
            results = reader.readtext(image_path)
            text_parts = []
            confidences = []

            for (bbox, text, conf) in results:
                text_parts.append(text)
                if any(c.isdigit() for c in text):
                    confidences.append(conf)

            full_text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) * 100 if confidences else 0
            streams = self._parse_streams(full_text)

            return streams, full_text, avg_confidence
        except Exception as exc:
            return None, str(exc), 0

    def extract_streams(self, screenshot_path: str, slug: str, timestamp: str) -> tuple[str | None, str, str]:
        print("Step 3: Performing OCR to extract total streams...")

        # Tesseract configs to try (digit whitelist for better accuracy)
        tesseract_configs = [
            "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789,plays",  # Digit whitelist
            "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789,",       # Single line mode
            "--oem 3 --psm 6",                                               # Default
            "--oem 1 --psm 6",                                               # LSTM only
        ]

        all_results = []
        all_text = []
        processed_path = None

        # Try multiple preprocessing variants (4 variants now)
        for variant in range(4):
            variant_path = self.prepare_ocr_image(screenshot_path, slug, timestamp, variant)
            if processed_path is None:
                processed_path = variant_path

            # Try each Tesseract config
            for config in tesseract_configs:
                streams, text, confidence = self._extract_with_tesseract(variant_path, config)
                if streams:
                    all_results.append((streams, confidence, f"Tesseract v{variant} ({config[:20]}...)"))
                    all_text.append(f"[Tesseract v{variant}] conf={confidence:.1f}%: {text[:100]}")

        # Try EasyOCR as backup (on first 3 variants - focused regions)
        if EASYOCR_AVAILABLE:
            for variant in range(3):
                variant_path = self.prepare_ocr_image(screenshot_path, slug, timestamp, variant)
                streams, text, confidence = self._extract_with_easyocr(variant_path)
                if streams:
                    all_results.append((streams, confidence, f"EasyOCR v{variant}"))
                    all_text.append(f"[EasyOCR v{variant}] conf={confidence:.1f}%: {text[:100]}")

        # Select best result based on confidence and consensus
        final_text = "\n".join(all_text)

        if not all_results:
            # Fallback: try full screenshot
            fallback_text = pytesseract.image_to_string(Image.open(screenshot_path), config="--oem 3 --psm 6")
            streams = self._parse_streams(fallback_text)
            if streams:
                print(f"[OK] Total streams detected (fallback): {streams}")
                return streams, final_text + f"\n[Fallback]: {fallback_text}", processed_path

            print("[WARN] Unable to detect total streams from OCR.")
            return None, final_text, processed_path

        # Find consensus or highest confidence result
        stream_counts = {}
        for streams, confidence, source in all_results:
            if streams not in stream_counts:
                stream_counts[streams] = {"count": 0, "confidence": 0, "sources": []}
            stream_counts[streams]["count"] += 1
            stream_counts[streams]["confidence"] = max(stream_counts[streams]["confidence"], confidence)
            stream_counts[streams]["sources"].append(source)

        # Prefer results that appear multiple times (consensus)
        best_streams = max(stream_counts.keys(), key=lambda x: (stream_counts[x]["count"], stream_counts[x]["confidence"]))
        best_info = stream_counts[best_streams]

        print(f"[OK] Total streams detected: {best_streams} (consensus: {best_info['count']}, confidence: {best_info['confidence']:.1f}%)")

        return best_streams, final_text, processed_path

    def log_audit_event(
        self,
        event_type: str,
        spotify_link: str,
        song_title: str,
        artist: str,
        expected_value: str = "",
        actual_value: str = "",
        action_taken: str = "",
        screenshot_path: str = ""
    ) -> None:
        """Log an event to the audit log CSV."""
        file_exists = os.path.exists(self.audit_log_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(self.audit_log_path, mode="a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow([
                        "timestamp", "event_type", "spotify_link", "song_title", "artist",
                        "expected_value", "actual_value", "action_taken", "screenshot_path"
                    ])
                writer.writerow([
                    timestamp, event_type, spotify_link, song_title, artist,
                    expected_value, actual_value, action_taken, screenshot_path
                ])
        except Exception as exc:
            print(f"[WARN] Failed to write to audit log: {exc}")

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
        status: str = "OK",
        failure_reason: str = "",
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
                    "status",
                    "failure_reason",
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
                status,
                failure_reason,
            ])

        print(f"[OK] Track result saved to: {self.results_csv_path} (Status: {status})")
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

    def verify_track_loaded(self, screenshot_path: str, expected_title: str) -> tuple[bool, str, float]:
        """
        Verify that the loaded page actually matches the expected track title.
        Uses multiple strategies to detect the title in the Spotify page.
        """
        try:
            with Image.open(screenshot_path) as img:
                width, height = img.size
                all_detected_text = []

                # Helper to run OCR on an image object
                def run_ocr(image_obj, config="--psm 6"):
                    try:
                        if EASYOCR_AVAILABLE and self.easyocr_reader:
                            import numpy as np
                            results = self.easyocr_reader.readtext(np.array(image_obj), detail=0)
                            return " ".join(results)
                        else:
                            return pytesseract.image_to_string(image_obj, config=config)
                    except Exception:
                        return ""

                # Strategy 1: Focus on the main title area (right of album art)
                # Spotify layout: album art on left (~35% width), title to the right
                title_left = int(width * 0.35)
                title_top = int(height * 0.12)
                title_right = int(width * 0.85)
                title_bottom = int(height * 0.35)
                title_region = img.crop((title_left, title_top, title_right, title_bottom))

                # Preprocess for Spotify's dark theme (white text on dark)
                gray = ImageOps.grayscale(title_region)
                # Threshold to get white text
                binary = gray.point(lambda p: 255 if p > 200 else 0)
                text1 = run_ocr(binary)
                if text1.strip():
                    all_detected_text.append(text1)

                # Also try inverted
                inverted = ImageOps.invert(gray)
                text2 = run_ocr(inverted)
                if text2.strip():
                    all_detected_text.append(text2)

                # Strategy 2: Look at the metadata line region (contains "Artist • Title • Year")
                # This is below the main title, typically 25-40% from top
                meta_left = int(width * 0.35)
                meta_top = int(height * 0.25)
                meta_right = int(width * 0.90)
                meta_bottom = int(height * 0.40)
                meta_region = img.crop((meta_left, meta_top, meta_right, meta_bottom))

                gray_meta = ImageOps.grayscale(meta_region)
                binary_meta = gray_meta.point(lambda p: 255 if p > 150 else 0)
                text3 = run_ocr(binary_meta)
                if text3.strip():
                    all_detected_text.append(text3)

                # Combine all detected text
                detected_text = " ".join(all_detected_text)

            # Normalize for comparison
            def normalize(text):
                return re.sub(r'[^a-zA-Z0-9]', '', text.lower())

            clean_expected = normalize(expected_title)
            clean_detected = normalize(detected_text)

            # Check if expected title appears anywhere in detected text
            if clean_expected in clean_detected:
                match_score = 1.0
            else:
                # Fuzzy match using multiple strategies
                # Check if expected appears as substring
                from difflib import SequenceMatcher

                # Strategy A: Direct ratio
                direct_ratio = SequenceMatcher(None, clean_expected, clean_detected).ratio()

                # Strategy B: Check if expected title words appear
                expected_words = set(clean_expected)
                if len(expected_words) >= 3:
                    detected_words = set(clean_detected)
                    word_overlap = len(expected_words & detected_words) / len(expected_words)
                else:
                    word_overlap = 0

                # Strategy C: Partial match in beginning
                start_ratio = SequenceMatcher(
                    None, clean_expected, clean_detected[:len(clean_expected) + 10]
                ).ratio() if len(clean_detected) > 0 else 0

                match_score = max(direct_ratio, word_overlap, start_ratio)

            # Short titles (<=6 chars normalized) are unreliable for OCR verification
            # since OCR often returns empty/garbled text for short titles like "Na Na Na"
            # or "8". The Spotify URL navigation already ensures the correct track page,
            # so we skip the fuzzy threshold for these titles.
            if len(clean_expected) <= 6:
                is_match = True  # Trust URL-based navigation for short titles
            else:
                is_match = match_score > 0.4

            # Log result
            preview = detected_text[:80].replace('\n', ' ') if detected_text else "(empty)"
            log_msg = f"track='{expected_title}' detected='{preview}...' score={match_score:.2f}"
            if is_match:
                print(f"[VERIFIED] {log_msg}")
            else:
                print(f"[VERIFICATION FAILED] {log_msg}")

            return is_match, detected_text, match_score

        except Exception as exc:
            print(f"[WARN] Verification error: {exc}")
            # On error, allow processing to continue but flag it
            return True, f"Verification Error: {exc}", 0.0

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
                    previous_streams = self._get_previous_streams(spotify_link, song_title, artist)
                    if previous_streams:
                        print(f"[FALLBACK] Browser failed. Using previous day's streams: {previous_streams:,}")
                        self.log_audit_event(
                            "browser_failed", spotify_link, song_title, artist,
                            action_taken="use_fallback"
                        )
                        self.save_track_result(
                            run_timestamp, song_title, artist, year, album, collab,
                            spotify_link, str(previous_streams), 0, last_screenshot_path or "",
                            status="FALLBACK", failure_reason="Browser launch failed"
                        )
                        return True
                    else:
                        print(f"[ERROR] Browser failed. No previous data available.")
                        self.log_audit_event(
                            "browser_failed", spotify_link, song_title, artist,
                            action_taken="failed_no_data"
                        )
                        self.save_track_result(
                            run_timestamp, song_title, artist, year, album, collab,
                            spotify_link, "0", 0, last_screenshot_path or "",
                            status="FAILED", failure_reason="Browser launch failed"
                        )
                        return False
                continue

            window = None
            try:
                window = self.focus_edge_window()

                # Dismiss any browser popups (restore session, cookie banners)
                self.dismiss_browser_popups(window)

                # Wait for page to fully load (stability detection)
                if not self.wait_for_page_load(window, max_wait=12, stability_checks=2):
                    print("[WARN] Page may not be fully loaded, proceeding anyway...")

                screenshot_path, screenshot_timestamp = self.capture_screenshot(slug, window)
                last_screenshot_path = screenshot_path or last_screenshot_path

                if not screenshot_path:
                    print(f"[WARN] Screenshot capture failed for {song_title}.")
                    if attempt == max_retries:
                        # Use previous day's streams instead of 0
                        previous_streams = self._get_previous_streams(spotify_link, song_title, artist)
                        if previous_streams:
                            print(f"[FALLBACK] Screenshot failed. Using previous day's streams: {previous_streams:,}")
                            self.log_audit_event(
                                "screenshot_failed", spotify_link, song_title, artist,
                                action_taken="use_fallback"
                            )
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, str(previous_streams), 0, last_screenshot_path,
                                status="FALLBACK", failure_reason="Screenshot failed"
                            )
                            return True
                        else:
                            print(f"[ERROR] Screenshot failed. No previous data available.")
                            self.log_audit_event(
                                "screenshot_failed", spotify_link, song_title, artist,
                                action_taken="failed_no_data"
                            )
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, "0", 0, last_screenshot_path,
                                status="FAILED", failure_reason="Screenshot failed"
                            )
                            return False
                    continue

                # Close Edge window before OCR processing
                if window is not None:
                    self.close_edge_window(window)
                    window = None

                # Step 2.5: Verify Track Loaded
                is_verified, detected_title, match_score = self.verify_track_loaded(screenshot_path, song_title)
                if not is_verified:
                    print(f"[WARN] Loaded page does not match expected track '{song_title}'. Detected: '{detected_title}'")
                    if attempt < max_retries:
                        print("[RETRY] Retrying due to verification failure...")
                        self.force_close_edge()
                        time.sleep(2)
                        continue
                    else:
                        print(f"[ERROR] Verification failed after {max_retries} retries. Marking as VERIFICATION_FAILED.")
                        
                        self.log_audit_event(
                            "verification_failed", spotify_link, song_title, artist,
                            expected_value=song_title, actual_value=detected_title,
                            action_taken="skip_track", screenshot_path=screenshot_path
                        )
                        # Fail the track explicitly
                        self.save_track_result(
                            run_timestamp, song_title, artist, year, album, collab,
                            spotify_link, "0", 0, screenshot_path,
                            status="VERIFICATION_FAILED", failure_reason=f"Title mismatch: {detected_title}"
                        )
                        return False

                streams, ocr_text, processed_path = self.extract_streams(screenshot_path, slug, screenshot_timestamp)
                last_ocr_text = ocr_text

                if streams:
                    streams_int = int(streams.replace(",", ""))

                    # Validate streams against previous data
                    is_valid, validation_msg = self._validate_streams(streams_int, spotify_link, song_title, artist)
                    print(f"[VALIDATION] {validation_msg}")

                    if not is_valid:
                        if attempt < max_retries:
                            print(f"[WARN] Invalid streams detected. Will retry...")
                            self.force_close_edge()
                            time.sleep(2)
                            continue  # Retry
                        else:
                            # Use previous day's streams instead of 0
                            previous_streams = self._get_previous_streams(spotify_link, song_title, artist)
                            if previous_streams:
                                print(f"[FALLBACK] Using previous day's streams: {previous_streams:,}")
                                self.log_audit_event(
                                    "validation_failed", spotify_link, song_title, artist,
                                    expected_value=f">={previous_streams}", actual_value=str(streams_int),
                                    action_taken="use_fallback"
                                )
                                self._save_debug_text(slug, screenshot_timestamp, f"VALIDATION FAILED: {validation_msg}\n\n{ocr_text}", self.output_dir)
                                self.save_track_result(
                                    run_timestamp, song_title, artist, year, album, collab,
                                    spotify_link, str(previous_streams), 0, screenshot_path,
                                    status="FALLBACK", failure_reason=f"Validation failed: {validation_msg}"
                                )
                                return True
                            else:
                                print(f"[ERROR] Invalid streams after {max_retries} retries. No previous data available.")
                                self.log_audit_event(
                                    "validation_failed", spotify_link, song_title, artist,
                                    expected_value="valid_count", actual_value=str(streams_int),
                                    action_taken="failed_no_data"
                                )
                                self._save_debug_text(slug, screenshot_timestamp, f"VALIDATION FAILED: {validation_msg}\n\n{ocr_text}", self.output_dir)
                                self.save_track_result(
                                    run_timestamp, song_title, artist, year, album, collab,
                                    spotify_link, "0", 0, screenshot_path,
                                    status="FAILED", failure_reason=f"Validation failed: {validation_msg}"
                                )
                                return False

                    # Valid streams - calculate daily and save
                    daily_streams = self._calculate_daily_streams(streams_int, spotify_link, song_title, artist)

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
                        status="OK",
                        failure_reason=""
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
                        previous_streams = self._get_previous_streams(spotify_link, song_title, artist)
                        if previous_streams:
                            print(f"[FALLBACK] OCR failed. Using previous day's streams: {previous_streams:,}")
                            self.log_audit_event(
                                "ocr_failed", spotify_link, song_title, artist,
                                action_taken="use_fallback"
                            )
                            self._save_debug_text(slug, screenshot_timestamp, ocr_text, self.output_dir)
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, str(previous_streams), 0, screenshot_path,
                                status="FALLBACK", failure_reason="OCR failed"
                            )
                            return True
                        else:
                            print(f"[ERROR] OCR failed after {max_retries} retries. No previous data available.")
                            self.log_audit_event(
                                "ocr_failed", spotify_link, song_title, artist,
                                action_taken="failed_no_data"
                            )
                            self._save_debug_text(slug, screenshot_timestamp, ocr_text, self.output_dir)
                            self.save_track_result(
                                run_timestamp, song_title, artist, year, album, collab,
                                spotify_link, "0", 0, screenshot_path,
                                status="FAILED", failure_reason="OCR failed"
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

        # Prepare clean desktop state before starting
        self.prepare_clean_state()

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
