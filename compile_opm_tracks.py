"""Compile individual OPM artist track CSVs into a single opm_all_tracks.csv.

Reads opm_artists_spotify.csv for the artist list, finds each artist's
{artist}_tracks.csv file, and concatenates them into one file suitable
for the Selenium RPA scraper.

Usage:
    python compile_opm_tracks.py              # Compile all OPM artist tracks
    python compile_opm_tracks.py --dry-run    # Preview without writing
"""

import argparse
import csv
import os
import re
import unicodedata


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARTISTS_CSV = os.path.join(SCRIPT_DIR, "opm_artists_spotify.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "opm_all_tracks.csv")

# Genres to exclude (scraped separately by the SB19 RPA)
EXCLUDE_GENRES = {"SB19 Solo"}
EXCLUDE_ARTISTS = {"SB19"}

HEADER = "Song Title;Artist;Year;Album/EP/Single;Collaborating Artist(s);Spotify Link;Streams"


def normalize_filename(name):
    """Generate candidate filenames for an artist name.

    Returns a list of possible filenames to try, most likely first.
    """
    candidates = []

    # Strategy 1: lowercase, spaces → underscores, remove most special chars
    clean = name.lower()
    clean = clean.replace("&", "_and_").replace(".", "_").replace(":", "").replace("!", "")
    clean = clean.replace("•", "").replace("'", "_")
    clean = re.sub(r"[^a-z0-9_\-]", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    candidates.append(f"{clean}_tracks.csv")

    # Strategy 2: lowercase, & → _, . → _, drop special chars
    clean2 = name.lower()
    clean2 = clean2.replace("&", "_").replace(".", "_").replace(":", "").replace("!", "i")
    clean2 = clean2.replace("•", "").replace("'", "_")
    clean2 = re.sub(r"[^a-z0-9_\-]", "_", clean2)
    clean2 = re.sub(r"_+", "_", clean2).strip("_")
    candidates.append(f"{clean2}_tracks.csv")

    # Strategy 3: lowercase, spaces → underscores, keep hyphens, drop dots/special
    clean3 = name.lower()
    clean3 = clean3.replace(".", "_").replace(":", "").replace("!", "")
    clean3 = clean3.replace("•", "").replace("&", "").replace("'", "_")
    clean3 = re.sub(r"\s+", "_", clean3)
    clean3 = re.sub(r"_+", "_", clean3).strip("_")
    candidates.append(f"{clean3}_tracks.csv")

    # Strategy 4: original name with spaces, lowered
    clean4 = name.lower()
    candidates.append(f"{clean4}_tracks.csv")

    # Strategy 5: unicode-stripped, lowercase
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    clean5 = ascii_name.lower().replace(" ", "_").replace(".", "_")
    clean5 = re.sub(r"[^a-z0-9_\-]", "", clean5)
    clean5 = re.sub(r"_+", "_", clean5).strip("_")
    candidates.append(f"{clean5}_tracks.csv")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def find_tracks_file(artist_name):
    """Find the tracks CSV file for a given artist, trying multiple naming conventions."""
    candidates = normalize_filename(artist_name)
    for candidate in candidates:
        path = os.path.join(SCRIPT_DIR, candidate)
        if os.path.exists(path):
            return path
    return None


def load_artists():
    """Load artist list from opm_artists_spotify.csv, excluding SB19 solo members and SB19."""
    artists = []
    with open(ARTISTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["artist_name"].strip()
            genre = row.get("genre", "").strip()
            if genre in EXCLUDE_GENRES:
                continue
            if name in EXCLUDE_ARTISTS:
                continue
            artists.append({"name": name, "genre": genre})
    return artists


def compile_tracks(dry_run=False):
    """Compile all individual track CSVs into one opm_all_tracks.csv."""
    artists = load_artists()
    print(f"[INFO] Loaded {len(artists)} OPM artists (excluding SB19 + solo members)")

    found = []
    missing = []
    total_tracks = 0
    all_rows = []

    for artist in artists:
        path = find_tracks_file(artist["name"])
        if path:
            found.append(artist["name"])
            track_count = 0
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    link = row.get("Spotify Link", "").strip()
                    if not link or not link.startswith("http"):
                        continue
                    all_rows.append(row)
                    track_count += 1
            total_tracks += track_count
        else:
            missing.append(artist["name"])

    print(f"\n[RESULTS]")
    print(f"  Artists found:   {len(found)}/{len(artists)}")
    print(f"  Artists missing: {len(missing)}")
    print(f"  Total tracks:    {total_tracks}")

    if missing:
        print(f"\n[MISSING] These artists have no tracks CSV:")
        for name in missing:
            candidates = normalize_filename(name)
            print(f"  - {name} (tried: {candidates[0]})")

    if dry_run:
        print(f"\n[DRY RUN] Would write {total_tracks} tracks to {OUTPUT_CSV}")
        return

    # Write output
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        f.write(HEADER + "\n")
        for row in all_rows:
            fields = [
                row.get("Song Title", ""),
                row.get("Artist", ""),
                row.get("Year", ""),
                row.get("Album/EP/Single", ""),
                row.get("Collaborating Artist(s)", ""),
                row.get("Spotify Link", ""),
                row.get("Streams", ""),
            ]
            f.write(";".join(fields) + "\n")

    print(f"\n[SUCCESS] Wrote {total_tracks} tracks to {OUTPUT_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile OPM artist track CSVs into one file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    compile_tracks(dry_run=args.dry_run)
