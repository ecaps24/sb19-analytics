import csv
import re

def normalize(s):
    return s.lower().strip()

def load_csv_tracks(filepath):
    tracks = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        # Check delimiter
        line = f.readline()
        f.seek(0)
        delimiter = ';' if ';' in line else ','
        
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            title = row.get('Song Title', '').strip()
            if title:
                tracks[normalize(title)] = title
    return tracks

def load_playlist_tracks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def compare(csv_path, playlist_path):
    csv_tracks = load_csv_tracks(csv_path)
    playlist_tracks = load_playlist_tracks(playlist_path)
    
    found_matches = []
    missing_in_csv = []
    
    # Heuristics for matching
    # 1. Exact match
    # 2. Split by ' – ' (en dash) or ' - ' (hyphen) if it looks like "Title - Artist"
    # 3. Remove (feat. X)
    
    print(f"Loaded {len(csv_tracks)} tracks from CSV.")
    print(f"Loaded {len(playlist_tracks)} tracks from playlist.")
    print("-" * 40)

    for p_track in playlist_tracks:
        norm_p = normalize(p_track)
        match_found = None
        
        # 1. Exact match
        if norm_p in csv_tracks:
            match_found = csv_tracks[norm_p]
        
        # 2. Split by ' – ' (en dash) - common for "Title – Artist"
        if not match_found and ' – ' in p_track:
            part = p_track.split(' – ')[0]
            if normalize(part) in csv_tracks:
                match_found = csv_tracks[normalize(part)]
        
        # 3. Handle " - From THE FIRST TAKE" if strict match failed but maybe CSV has the base song?
        # Actually CSV seems to have "Title - From THE FIRST TAKE" sometimes. 
        # But if the playlist has it and CSV doesn't, maybe we check for base title?
        # Let's keep it simplest: if we verify it's the SAME song, it's a match.
        
        # 4. Remove (feat. ...)
        if not match_found:
            # Try removing (feat. ...) from the start part if we split by dash
            # Or from the whole string if no dash
            
            # Case A: Title (feat. X) – Artist
            if ' – ' in p_track:
                part = p_track.split(' – ')[0] # "Burn The Flame (feat. SB19)"
                # Remove (feat. ...)
                clean_part = re.sub(r'\s*\(feat\..*?\)', '', part, flags=re.IGNORECASE)
                if normalize(clean_part) in csv_tracks:
                     match_found = csv_tracks[normalize(clean_part)]
            else:
                # Case B: Title (feat. X)
                clean_p = re.sub(r'\s*\(feat\..*?\)', '', p_track, flags=re.IGNORECASE)
                if normalize(clean_p) in csv_tracks:
                    match_found = csv_tracks[normalize(clean_p)]

        if match_found:
            found_matches.append((p_track, match_found))
        else:
            missing_in_csv.append(p_track)

    print(f"Matched: {len(found_matches)}")
    print(f"Missing in CSV: {len(missing_in_csv)}")
    
    if missing_in_csv:
        print("\n=== Missing in CSV ===")
        for t in missing_in_csv:
            print(f"- {t}")

if __name__ == "__main__":
    compare('d:\\dev\\SB19\\tracks.csv', 'd:\\dev\\SB19\\playlist_tracks.txt')
