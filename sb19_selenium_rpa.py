import argparse
import csv
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from bs4 import BeautifulSoup


class SB19SeleniumRPA:
    def __init__(self, tracks_csv=None, results_csv=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.saved_pages_dir = os.path.join(self.base_dir, "saved_pages")
        os.makedirs(self.saved_pages_dir, exist_ok=True)

        self.tracks_csv_path = tracks_csv or os.path.join(self.base_dir, "tracks.csv")
        self.results_csv_path = results_csv or os.path.join(self.base_dir, "selenium_results.csv")
        
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

    def run(self):
        print(f"[START] Processing tracks from {self.tracks_csv_path}")
        tracks = self.load_tracks()
        print(f"[INFO] Found {len(tracks)} tracks.")
        
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
                        
                    results.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SB19 Selenium RPA - Scrape Spotify track streams")
    parser.add_argument("tracks_csv", nargs="?", default=None,
                        help="Path to custom tracks CSV file (default: tracks.csv)")
    parser.add_argument("--output", "-o", default=None,
                        help="Path to output results CSV file (default: selenium_results.csv)")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Force re-scrape (currently always scrapes all tracks)")
    args = parser.parse_args()

    rpa = SB19SeleniumRPA(tracks_csv=args.tracks_csv, results_csv=args.output)
    rpa.run()
