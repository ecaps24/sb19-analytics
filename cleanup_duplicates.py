"""Clean up duplicate track names in selenium_results.csv by normalizing to tracks.csv titles."""
import csv
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
tracks_csv = os.path.join(base_dir, "tracks.csv")
results_csv = os.path.join(base_dir, "selenium_results.csv")

# Build a mapping of Spotify URL to canonical track name from tracks.csv
url_to_title = {}
with open(tracks_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        url = row.get('Spotify Link', '').strip()
        title = row.get('Song Title', '').strip()
        if url and title:
            # Extract track ID from URL
            track_id = url.split('/')[-1].split('?')[0]
            url_to_title[track_id] = title

print(f"Loaded {len(url_to_title)} track mappings from tracks.csv")

# Also create a case-insensitive mapping for common variations
title_mappings = {
    # Old Spotify titles -> Canonical titles from tracks.csv
    "GENTO": "Gento",
    "I WANT YOU": "I Want You",
    "ILAW": "Ilaw",
    "CRIMZONE": "Crimzone",
    "FREEDOM": "Freedom",
    "DUNGKA!": "Dungka!",
    "WIN YOUR HEART": "Win Your Heart",
    "CHRISTMAS PARTY - SB19 VƎRSION": "Christmas Party (SB19 Version)",
    "MAPA (Indonesian Ver.)": "MAPA (Indonesian Version)",
    "Burn The Flame (feat. SB19)": "Burn The Flame",
    "Burn The Flame (Taglish Version) (feat. SB19)": "Burn The Flame (Taglish Version)",
    "Burn The Flame (Karaoke Version) (feat. SB19)": "Burn The Flame (Karaoke Version)",
    "Burn The Flame (Instrumental) (feat. SB19)": "Burn The Flame (Instrumental)",
    "Love Yours (feat. SB19)": "Love Yours",
    "Kapangyarihan - feat. SB19": "Kapangyarihan",
    "Tara, Summer Na! (feat. SB19)": "Tara, Summer Na!",
    "Tahanan (feat. SB19)": "Tahanan",
    "We Wish You A Merry GCash (feat. SB19)": "We Wish You A Merry GCash",
    "Ready, Set, G! (feat. SB19 & GCash Jr.)": "Ready, Set, G!",
    "Make It Merry, I-GCash Mo (feat. SB19)": "Make It Merry, I-GCash Mo",
    "G Pa Rin Ang Pasko (feat. SB19)": "G Pa Rin Ang Pasko",
    "Reset (feat. SB19 & Sandara Park)": "Reset",
    "Love Yours (feat. SB19) - DIOR & RealBros Remix": "Love Yours (DIOR & RealBros Remix)",
    "Love Goes - EDM Version": "Love Goes (EDM Version)",
    "Tilaluha - Instrumental": "Tilaluha (Instrumental)",
    "Hanggang Sa Huli - Instrumental": "Hanggang Sa Huli (Instrumental)",
    "Wag Mong Ikunot Ang Iyong Noo": "'Wag Mong Ikunot Ang Iyong Noo",
    "Umaaligid - Extended Ver.": "Umaaligid (Extended Ver.)",
    "No Stopping You - Remix": "No Stopping You",  # Remove this duplicate entry
    # Liwanag title normalization
    'Liwanag sa Dilim - from "Incognito"': "Liwanag sa Dilim (from Incognito)",
}

# Tracks that need to be renamed based on Spotify URL (same title, different tracks)
url_based_renames = {
    "2UH7vzHodDdXtNyPEeHkb7": "La Luna (2022)",  # PABLO's 2022 single version
}

# Read and update results
rows = []
with open(results_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    fieldnames = [f for f in reader.fieldnames if f]  # Filter out None/empty fieldnames
    for row in reader:
        title = row.get('song_title', '')
        source = row.get('source_file', '')

        # Check for URL-based renames (for tracks with same title but different Spotify URLs)
        for track_id, new_title in url_based_renames.items():
            if track_id in source:
                row['song_title'] = new_title
                break
        else:
            # Apply title mapping only if no URL-based rename was done
            if title in title_mappings:
                row['song_title'] = title_mappings[title]

        # Only keep fields that are in fieldnames
        clean_row = {k: v for k, v in row.items() if k in fieldnames}
        rows.append(clean_row)

print(f"Read {len(rows)} rows from selenium_results.csv")

# Write back
with open(results_csv, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(rows)

print("Cleanup complete!")
