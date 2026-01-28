import csv
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from bs4 import BeautifulSoup

class ArtistMonthlyListenersRPA:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "monthly listeners")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.artists_csv_path = os.path.join(self.base_dir, "artists.csv")
        self.results_csv_path = os.path.join(self.base_dir, "monthly_listeners.csv")
        
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
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            return filepath
        except Exception as e:
            print(f"[ERR] Failed to save page source: {e}")
            return None

    def extract_monthly_listeners(self, html_content):
        """
        Extract 'Monthly Listeners' count from HTML source using regex.
        """
        try:
            # Clean up text for easier regex matching
            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
            
            # Pattern: Look for number followed by "monthly listeners"
            # Example: "1,234,567 monthly listeners"
            pattern = r'([\d,]+)\s+monthly listeners'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            if matches:
                # If multiple matches, usually the first one or the specific one in the header is correct.
                # Given the structure, likely the first valid large number is it.
                # Let's filter for just numbers.
                for match in matches:
                    clean_count = match.replace(',', '')
                    if clean_count.isdigit():
                        return clean_count
            
        except Exception as e:
            print(f"[ERR] Extraction failed: {e}")
            
        return None

    def load_artists(self):
        artists = []
        if not os.path.exists(self.artists_csv_path):
            print(f"[ERR] Artists file not found: {self.artists_csv_path}")
            return []
            
        with open(self.artists_csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("artist_url", "").startswith("http"):
                    artists.append(row)
        return artists

    def run(self):
        print(f"[START] Processing artists from {self.artists_csv_path}")
        artists = self.load_artists()
        print(f"[INFO] Found {len(artists)} artists.")
        
        results = []
        
        try:
            for i, artist_data in enumerate(artists):
                name = artist_data.get("artist_name", "Unknown")
                url = artist_data.get("artist_url")
                slug = self._slugify(name)
                
                print(f"\n[{i+1}/{len(artists)}] Processing: {name}")
                print(f"       URL: {url}")
                
                try:
                    self.driver.get(url)
                    time.sleep(5) # Wait for initial load
                    
                    # Scroll down a bit
                    self.driver.execute_script("window.scrollBy(0, 300);")
                    time.sleep(2)
                    
                    page_source = self.driver.page_source
                    saved_path = self.save_page_source(page_source, slug)
                    
                    listeners = self.extract_monthly_listeners(page_source)
                    
                    if listeners:
                        print(f"       [SUCCESS] Monthly Listeners: {listeners}")
                    else:
                        print(f"       [WARN] Could not extract monthly listeners.")
                        listeners = "N/A"
                        
                    results.append({
                        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),

                        "artist_name": name,
                        "monthly_listeners": listeners,
                        "url": url,
                        "saved_file": saved_path
                    })
                    
                except Exception as e:
                    print(f"       [ERR] Error processing artist: {e}")
                    
                # Save result immediately
                self._save_result(results[-1])
                
                # Small pause between artists
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

        fieldnames = ["artist_name", "monthly_listeners", "timestamp"]
        file_exists = os.path.exists(self.results_csv_path)

        try:
            with open(self.results_csv_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=',', extrasaction='ignore')

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
            subprocess.run(["git", "add", "monthly_listeners.csv"], check=True, capture_output=True)

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
    rpa = ArtistMonthlyListenersRPA()
    rpa.run()
