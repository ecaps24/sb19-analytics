import os
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_PAGES_DIR = os.path.join(BASE_DIR, "saved_pages")
OFFLINE_CSV_PATH = os.path.join(BASE_DIR, "offline_results.csv")
TRACKS_CSV_PATH = os.path.join(BASE_DIR, "tracks.csv")

def load_tracks_metadata():
    """Load tracks.csv into a dictionary keyed by Spotify Link."""
    metadata = {}
    if not os.path.exists(TRACKS_CSV_PATH):
        print(f"[WARN] Tracks file not found: {TRACKS_CSV_PATH}")
        return metadata

    try:
        with open(TRACKS_CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                url = row.get("Spotify Link", "").strip()
                if url:
                    # Normalize URL slightly ensuring no trailing slashes or params if we want strictly matching
                    # But usually exact match is fine if input was clean.
                    # Let's strip query params just in case tracks.csv has them but canonical doesn't, or vice versa.
                    clean_url = url.split('?')[0]
                    metadata[clean_url] = {
                        "song_title": row.get("Song Title", "Unknown"),
                        "artist": row.get("Artist", "Unknown")
                    }
    except Exception as e:
        print(f"[ERR] Failed to load tracks metadata: {e}")
    return metadata

def extract_streams_from_html(html_content):
    """
    Same logic as SB19SeleniumRPA.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
        
        # Regex to find a timestamp (M:SS) followed by a large number
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

        # Fallback
        plays_pattern = r'([\d,]+)\s+(?:plays|streams)'
        plays_matches = re.findall(plays_pattern, text, re.IGNORECASE)
        if plays_matches:
           vals = [int(p.replace(',', '')) for p in plays_matches if p.replace(',', '').isdigit()]
           if vals:
               return f"{max(vals)}"
               
        # Deep Fallback
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
        
    return "N/A"

def extract_canonical_url(html_content):
    """Extract the canonical URL from the <link rel='canonical'> tag."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        link_tag = soup.find("link", rel="canonical")
        if link_tag and link_tag.get("href"):
            return link_tag.get("href").split('?')[0] # Clean params
    except:
        pass
    return None

def extract_metadata_fallback(html_content):
    """
    Try to extract Song Title and Artist from the <title> tag.
    Spotify Title Format: "Song Title - Song by Artist | Spotify"
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            full_title = title_tag.get_text().strip()
            # Remove " | Spotify"
            clean_title = full_title.replace(" | Spotify", "").replace(" - Spotify", "")
            
            # Split by " - "
            parts = clean_title.split(" - ")
            if len(parts) >= 2:
                song = parts[0].strip()
                artist_part = parts[1].strip()
                artist = artist_part.replace("Song by ", "")
                return song, artist
            
            return clean_title, "Unknown"
            
    except Exception as e:
        pass
    return "Unknown", "Unknown"

def run():
    print(f"[START] Processing saved pages from: {SAVED_PAGES_DIR}")
    
    if not os.path.exists(SAVED_PAGES_DIR):
        print("[ERR] Saved pages directory not found.")
        return

    # Load lookup table
    track_lookup = load_tracks_metadata()
    print(f"[INFO] Loaded metadata for {len(track_lookup)} tracks.")

    files = [f for f in os.listdir(SAVED_PAGES_DIR) if f.endswith(".html")]
    print(f"[INFO] Found {len(files)} HTML files.")
    
    results = []
    
    for i, filename in enumerate(files):
        filepath = os.path.join(SAVED_PAGES_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            streams = extract_streams_from_html(content)
            canonical_url = extract_canonical_url(content)
            
            song = "Unknown"
            artist = "Unknown"
            final_url = canonical_url if canonical_url else "OFFLINE_FILE"
            
            # Lookup
            if canonical_url and canonical_url in track_lookup:
                meta = track_lookup[canonical_url]
                song = meta["song_title"]
                artist = meta["artist"]
            elif canonical_url:
                 # Try finding with https vs http or www or open.spotify.com
                 # A simple fuzzy check might be needed if exact match fail?
                 # Usually exact match works if split('?')[0] is used.
                 pass
            
            if song == "Unknown":
                # Fallback to scraping title tag
                s, a = extract_metadata_fallback(content)
                if s != "Unknown":
                    song, artist = s, a

            # File timestamp extraction from filename
            # filename format: slug_YYYYMMDD_HHMMSS.html
            file_timestamp = "Unknown"
            try:
                match = re.search(r'_(\d{8}_\d{6})\.html', filename)
                if match:
                    ts_str = match.group(1)
                    dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    file_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

            print(f"[{i+1}/{len(files)}] {filename} -> {song} ({artist}): {streams}")
            
            results.append({
                "timestamp": file_timestamp,
                "song_title": song,
                "artist": artist,
                "streams": streams,
                "url": final_url,
                "saved_file": filepath
            })
            
        except Exception as e:
            print(f"[ERR] Failed to process {filename}: {e}")

    # Save to CSV
    fieldnames = ["timestamp", "song_title", "artist", "streams", "url", "saved_file"]
    with open(OFFLINE_CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(results)
        
    print(f"[DONE] Processed {len(results)} files. Saved to {OFFLINE_CSV_PATH}")

if __name__ == "__main__":
    run()
