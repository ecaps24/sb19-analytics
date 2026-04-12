"""
Track Discovery RPA - Automated New Track Detection
Scans Spotify artist discography pages for new releases and updates track CSVs.
Designed to run weekly via Windows Task Scheduler.
"""

import argparse
import csv
import glob
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup

from shared import setup_driver, slugify, git_push
from config import (
    OPM_ARTISTS_CSV, DELIMITER_TRACKS, VARIANT_FILTERS,
    WAIT_INITIAL_PAGE_LOAD, WAIT_BETWEEN_SCROLLS, WAIT_ALBUM_PAGE_LOAD,
    WAIT_TRACK_VERIFICATION, WAIT_BETWEEN_ALBUMS, WAIT_BROWSER_RECOVERY,
    WAIT_BETWEEN_ARTISTS, MAX_CONSECUTIVE_ERRORS,
    SCROLL_STANDARD, SCROLL_LARGE, DISCOVERY_SCROLL_ITERATIONS,
)


class TrackDiscoveryRPA:
    def __init__(self, headless=True, dry_run=False):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.artists_csv = OPM_ARTISTS_CSV
        self.headless = headless
        self.dry_run = dry_run
        self.log_lines = []
        self.total_new_tracks = 0
        self.updated_files = []
        self.driver = None

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        self.log_lines.append(line)

    def _setup_driver(self):
        self.log("Setting up Edge WebDriver...")
        return setup_driver(headless=self.headless)

    def _slugify(self, text):
        return slugify(text)

    def get_artist_id(self, url):
        """Extract artist ID from Spotify URL."""
        match = re.search(r"artist/([a-zA-Z0-9]+)", url)
        return match.group(1) if match else None

    def get_tracked_artists(self):
        """Read artists CSV and find which ones have existing track CSV files."""
        artists = []
        if not os.path.exists(self.artists_csv):
            self.log(f"[ERR] Artists CSV not found: {self.artists_csv}")
            return artists

        with open(self.artists_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("artist_name", "").strip()
                url = row.get("artist_url", "").strip()
                if not name or not url:
                    continue

                # Find corresponding tracks CSV
                slug = self._slugify(name)
                tracks_csv = os.path.join(self.base_dir, f"{slug}_tracks.csv")

                # Also check for name-based CSV (e.g. "orange & lemons_tracks.csv")
                name_csv = os.path.join(self.base_dir, f"{name.lower()}_tracks.csv")

                csv_path = None
                if os.path.exists(tracks_csv):
                    csv_path = tracks_csv
                elif os.path.exists(name_csv):
                    csv_path = name_csv

                if csv_path:
                    artists.append({
                        "name": name,
                        "url": url,
                        "artist_id": self.get_artist_id(url),
                        "tracks_csv": csv_path,
                    })

        # Also check the main tracks.csv for SB19 group/solo
        main_tracks = os.path.join(self.base_dir, "tracks.csv")
        if os.path.exists(main_tracks):
            artists.append({
                "name": "SB19 (main)",
                "url": "https://open.spotify.com/artist/3g7vYcdDXnqnDKYFwqXBJP",
                "artist_id": "3g7vYcdDXnqnDKYFwqXBJP",
                "tracks_csv": main_tracks,
                "multi_artist": True,  # This CSV has multiple artists
            })

        return artists

    def get_existing_track_urls(self, csv_path):
        """Read existing track CSV and return set of Spotify track URLs."""
        urls = set()
        if not os.path.exists(csv_path):
            return urls

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                link = row.get("Spotify Link", "").strip()
                if link:
                    # Normalize URL - extract track ID
                    match = re.search(r"track/([a-zA-Z0-9]+)", link)
                    if match:
                        urls.add(match.group(1))
        return urls

    def get_existing_track_names(self, csv_path, artist_name=None):
        """Read existing track CSV and return set of normalized track names."""
        names = set()
        if not os.path.exists(csv_path):
            return names

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                title = row.get("Song Title", "").strip()
                row_artist = row.get("Artist", "").strip()
                if title:
                    if artist_name and row_artist.lower() != artist_name.lower():
                        continue
                    names.add(title.lower())
        return names

    def scrape_artist_releases(self, artist_id):
        """Visit artist discography page and extract all release URLs."""
        url = f"https://open.spotify.com/artist/{artist_id}/discography/all"
        releases = []

        try:
            self.driver.get(url)
            time.sleep(5)

            # Scroll to load more content
            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(1.5)

            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # Extract album/single links
            links = soup.find_all("a", href=True)
            seen_ids = set()
            for link in links:
                href = link.get("href", "")
                match = re.search(r"/album/([a-zA-Z0-9]+)", href)
                if match and match.group(1) not in seen_ids:
                    album_id = match.group(1)
                    seen_ids.add(album_id)

                    # Try to get release name and year from nearby text
                    text = link.get_text(strip=True)
                    releases.append({
                        "album_id": album_id,
                        "url": f"https://open.spotify.com/album/{album_id}",
                        "name": text if text else "Unknown",
                    })

        except Exception as e:
            self.log(f"  [ERR] Failed to scrape discography: {e}")

        return releases

    def scrape_album_tracks(self, album_url):
        """Visit an album/single page and extract all track data."""
        tracks = []

        try:
            self.driver.get(album_url)
            time.sleep(4)

            # Scroll for lazy-loaded content
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1.5)

            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # Extract album/release metadata from og tags
            og_title = ""
            og_desc = ""
            og_title_tag = soup.find("meta", property="og:title")
            og_desc_tag = soup.find("meta", property="og:description")
            if og_title_tag:
                og_title = og_title_tag.get("content", "")
            if og_desc_tag:
                og_desc = og_desc_tag.get("content", "")

            # Try to get release year from og:description or page text
            release_year = ""
            year_match = re.search(r"\b(20\d{2})\b", og_desc)
            if year_match:
                release_year = year_match.group(1)

            # Try to get album name
            album_name = og_title if og_title else "Unknown"
            # Clean album name - remove " - Album by Artist" or " - Single"
            album_name = re.sub(r"\s*[-–]\s*(Album|EP|Single|Compilation)\s+by\s+.*$", "", album_name, flags=re.IGNORECASE)
            album_name = re.sub(r"\s*[-–]\s*(album|single|ep)\s*$", "", album_name, flags=re.IGNORECASE)

            # Determine release type
            release_type = "Single"
            if og_desc:
                desc_lower = og_desc.lower()
                if "album" in desc_lower:
                    release_type = album_name
                elif "ep" in desc_lower:
                    release_type = album_name
                elif "compilation" in desc_lower:
                    release_type = album_name

            # Extract track links from the page
            links = soup.find_all("a", href=True)
            seen_track_ids = set()
            for link in links:
                href = link.get("href", "")
                match = re.search(r"/track/([a-zA-Z0-9]+)", href)
                if match and match.group(1) not in seen_track_ids:
                    track_id = match.group(1)
                    seen_track_ids.add(track_id)

                    # Get track name from the link text or nearby elements
                    track_name = link.get_text(strip=True)

                    if track_name:
                        tracks.append({
                            "track_id": track_id,
                            "track_name": track_name,
                            "track_url": f"https://open.spotify.com/track/{track_id}",
                            "album_name": album_name,
                            "release_type": release_type,
                            "year": release_year,
                        })

            # If only one track and it's a single, set type to "Single"
            if len(tracks) == 1:
                tracks[0]["release_type"] = "Single"
            elif len(tracks) > 1:
                for t in tracks:
                    t["release_type"] = album_name

        except Exception as e:
            self.log(f"  [ERR] Failed to scrape album: {e}")

        return tracks

    def verify_track(self, track_url):
        """Quick verification of a track URL by checking its page."""
        try:
            self.driver.get(track_url)
            time.sleep(3)
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")

            if og_title:
                title = og_title.get("content", "")
                desc = og_desc.get("content", "") if og_desc else ""
                # Extract artist from description
                artist = ""
                year = ""
                if desc:
                    # Format: "Song · Artist · Song · Year"
                    parts = [p.strip() for p in desc.split("·")]
                    if len(parts) >= 2:
                        artist = parts[0]  # First part is usually artist
                    year_match = re.search(r"\b(20\d{2})\b", desc)
                    if year_match:
                        year = year_match.group(1)

                return {
                    "title": title,
                    "artist": artist,
                    "year": year,
                    "valid": True,
                }
        except Exception:
            pass
        return {"valid": False}

    def is_filtered_variant(self, track_name):
        """Check if track is a non-original variant to be filtered out."""
        filters = [
            r"sped\s*up",
            r"slowed\s*(down|and|\+)\s*reverb",
            r"slowed\s+down",
            r"\bkaraoke\b",
            r"\b8d\s*audio\b",
            r"\bnightcore\b",
        ]
        name_lower = track_name.lower()
        for pattern in filters:
            if re.search(pattern, name_lower):
                return True
        return False

    def append_tracks_to_csv(self, csv_path, new_tracks, artist_name):
        """Append new tracks to existing CSV file."""
        if not new_tracks:
            return 0

        added = 0
        with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
            for track in new_tracks:
                title = track.get("track_name", "")
                year = track.get("year", "")
                album = track.get("release_type", "Single")
                collab = track.get("collab", "")
                url = track.get("track_url", "")

                line = f"{title};{artist_name};{year};{album};{collab};{url};\n"
                f.write(line)
                added += 1

        return added

    def process_artist(self, artist):
        """Process a single artist - check for new tracks."""
        name = artist["name"]
        artist_id = artist["artist_id"]
        csv_path = artist["tracks_csv"]
        is_multi = artist.get("multi_artist", False)

        self.log(f"Checking: {name}")

        # Get existing track IDs
        existing_urls = self.get_existing_track_urls(csv_path)
        existing_names = self.get_existing_track_names(
            csv_path, artist_name=name if is_multi else None
        )
        self.log(f"  Existing tracks: {len(existing_urls)} URLs tracked")

        # Scrape discography
        releases = self.scrape_artist_releases(artist_id)
        self.log(f"  Releases found: {len(releases)}")

        if not releases:
            return 0

        new_tracks = []
        for release in releases:
            # Scrape tracks from this release
            tracks = self.scrape_album_tracks(release["url"])

            for track in tracks:
                track_id = track["track_id"]
                track_name = track["track_name"]

                # Skip if already in CSV (by URL or name)
                if track_id in existing_urls:
                    continue
                if track_name.lower() in existing_names:
                    continue

                # Skip filtered variants
                if self.is_filtered_variant(track_name):
                    self.log(f"  [SKIP] Filtered variant: {track_name}")
                    continue

                new_tracks.append(track)

            # Rate limiting between album page loads
            time.sleep(1)

        if new_tracks:
            # Deduplicate by track_id
            seen = set()
            unique_tracks = []
            for t in new_tracks:
                if t["track_id"] not in seen:
                    seen.add(t["track_id"])
                    unique_tracks.append(t)

            self.log(f"  NEW TRACKS FOUND: {len(unique_tracks)}")
            for t in unique_tracks:
                self.log(f"    + {t['track_name']} ({t['year']}) - {t['release_type']}")

            if not self.dry_run:
                # Determine artist name for CSV
                csv_artist_name = name
                if is_multi:
                    csv_artist_name = name.replace(" (main)", "")

                added = self.append_tracks_to_csv(csv_path, unique_tracks, csv_artist_name)
                self.log(f"  Added {added} tracks to {os.path.basename(csv_path)}")
                self.total_new_tracks += added
                if csv_path not in self.updated_files:
                    self.updated_files.append(csv_path)
            else:
                self.log(f"  [DRY RUN] Would add {len(unique_tracks)} tracks")
                self.total_new_tracks += len(unique_tracks)

            return len(unique_tracks)
        else:
            self.log(f"  Up to date.")
            return 0

    def git_push_updates(self):
        """Commit and push updated CSV files."""
        if not self.updated_files:
            self.log("No files to commit.")
            return

        date_str = datetime.now().strftime("%Y-%m-%d")
        commit_msg = f"Track discovery: {self.total_new_tracks} new tracks added ({date_str})"
        git_push(self.updated_files, commit_msg=commit_msg, base_dir=self.base_dir)

    def run(self):
        """Main execution loop."""
        start_time = datetime.now()
        self.log("=" * 60)
        self.log("Track Discovery RPA - Weekly Scan")
        self.log(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("=" * 60)

        # Get tracked artists
        artists = self.get_tracked_artists()
        self.log(f"Artists with track CSVs: {len(artists)}")

        if not artists:
            self.log("[ERR] No tracked artists found.")
            return

        # Initialize driver
        self.driver = self._setup_driver()

        try:
            consecutive_errors = 0
            for i, artist in enumerate(artists, 1):
                self.log(f"\n[{i}/{len(artists)}] ---")
                try:
                    self.process_artist(artist)
                    consecutive_errors = 0
                except Exception as e:
                    self.log(f"  [ERR] Failed to process {artist['name']}: {e}")
                    consecutive_errors += 1

                    if consecutive_errors >= 3:
                        self.log("[WARN] 3 consecutive errors, restarting browser...")
                        try:
                            self.driver.quit()
                        except Exception:
                            pass
                        time.sleep(3)
                        self.driver = self._setup_driver()
                        consecutive_errors = 0

                # Rate limiting between artists
                time.sleep(2)

        finally:
            try:
                self.driver.quit()
            except Exception:
                pass

        # Git commit and push
        if not self.dry_run and self.updated_files:
            self.git_push_updates()

        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time
        self.log("\n" + "=" * 60)
        self.log("Track Discovery Complete")
        self.log("=" * 60)
        self.log(f"Artists scanned:    {len(artists)}")
        self.log(f"New tracks found:   {self.total_new_tracks}")
        self.log(f"Files updated:      {len(self.updated_files)}")
        self.log(f"Duration:           {duration}")
        self.log(f"Mode:               {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.log("=" * 60)

        # Save log
        log_path = os.path.join(self.base_dir, "track_discovery_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.log_lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track Discovery RPA")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, don't update CSVs")
    parser.add_argument("--artist", type=str, help="Scan a specific artist only")
    args = parser.parse_args()

    rpa = TrackDiscoveryRPA(headless=args.headless, dry_run=args.dry_run)

    if args.artist:
        # Single artist mode
        rpa.driver = rpa._setup_driver()
        artists = rpa.get_tracked_artists()
        target = [a for a in artists if args.artist.lower() in a["name"].lower()]
        if target:
            rpa.log(f"Single artist mode: {target[0]['name']}")
            try:
                rpa.process_artist(target[0])
            finally:
                rpa.driver.quit()
            if not rpa.dry_run and rpa.updated_files:
                rpa.git_push_updates()
        else:
            rpa.log(f"Artist not found: {args.artist}")
    else:
        rpa.run()
