"""
Data Cleanup Agent for SB19 Dashboard

This agent validates and cleans up data used in the dashboard by:
1. Detecting anomalous data (unusually large increases/decreases)
2. Finding zero, blank, or missing values
3. Identifying stale data (values that haven't changed)
4. Comparing current data with historical trends
5. Generating detailed reports of data quality issues
"""

import csv
import os
import sys
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
import argparse
import json

# Configuration thresholds
CONFIG = {
    # Stream anomaly detection
    'max_daily_increase_percent': 200,  # Flag if daily increase > 200% of average
    'max_daily_increase_absolute': 500000,  # Flag if daily increase > 500k streams
    'min_expected_daily_streams': 100,  # Flag if daily streams < 100 for active tracks

    # Monthly listeners anomaly detection
    'max_listener_change_percent': 50,  # Flag if change > 50% in one day
    'min_expected_listeners': 1000,  # Flag if listeners < 1000 for main artists

    # Stale data detection
    'stale_days_threshold': 3,  # Flag if no change for 3+ consecutive days

    # Main artists to monitor closely
    'main_artists': ['SB19', 'PABLO', 'FELIP', 'STELL', 'JOSH CULLEN', 'JUSTIN'],
}


class DataCleanupAgent:
    def __init__(self, data_dir: str = '.'):
        self.data_dir = data_dir
        self.streams_file = os.path.join(data_dir, 'sb19_streams_results.csv')
        self.listeners_file = os.path.join(data_dir, 'monthly_listeners.csv')
        self.tracks_file = os.path.join(data_dir, 'tracks.csv')

        self.streams_data: List[Dict] = []
        self.listeners_data: List[Dict] = []
        self.tracks_data: List[Dict] = []

        self.issues: List[Dict] = []

    def load_data(self):
        """Load all data files"""
        print("Loading data files...")

        # Load streams data
        if os.path.exists(self.streams_file):
            with open(self.streams_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.streams_data = list(reader)
            print(f"  Loaded {len(self.streams_data)} stream records")
        else:
            print(f"  WARNING: Streams file not found: {self.streams_file}")

        # Load monthly listeners data
        if os.path.exists(self.listeners_file):
            with open(self.listeners_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.listeners_data = list(reader)
            print(f"  Loaded {len(self.listeners_data)} listener records")
        else:
            print(f"  WARNING: Listeners file not found: {self.listeners_file}")

        # Load tracks metadata
        if os.path.exists(self.tracks_file):
            with open(self.tracks_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.tracks_data = list(reader)
            print(f"  Loaded {len(self.tracks_data)} track records")
        else:
            print(f"  WARNING: Tracks file not found: {self.tracks_file}")

    def _parse_timestamp(self, timestamp: str) -> Optional[datetime]:
        """Parse timestamp in YYYYMMDD_HHMMSS format"""
        try:
            if '_' in timestamp:
                return datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            else:
                return datetime.strptime(timestamp, '%Y%m%d')
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: str) -> int:
        """Parse integer, handling commas and empty values"""
        if not value or value.strip() == '':
            return 0
        try:
            return int(str(value).replace(',', '').strip())
        except (ValueError, TypeError):
            return 0

    def _get_date_key(self, timestamp: str) -> str:
        """Extract YYYYMMDD from timestamp"""
        if '_' in timestamp:
            return timestamp.split('_')[0]
        return timestamp[:8] if len(timestamp) >= 8 else timestamp

    def _add_issue(self, category: str, severity: str, message: str, data: Dict = None):
        """Add an issue to the issues list"""
        self.issues.append({
            'category': category,
            'severity': severity,  # 'critical', 'warning', 'info'
            'message': message,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        })

    def check_stream_anomalies(self):
        """Check for anomalous stream counts"""
        print("\nChecking stream anomalies...")

        # Group streams by track (song_title + artist)
        tracks_history: Dict[str, List[Dict]] = defaultdict(list)

        for row in self.streams_data:
            song_title = row.get('song_title', '').strip()
            artist = row.get('artist', '').strip()
            if song_title and artist:
                key = f"{song_title}|{artist}".lower()
                tracks_history[key].append(row)

        # Sort each track's history by timestamp
        for key in tracks_history:
            tracks_history[key].sort(key=lambda x: x.get('timestamp', ''))

        anomaly_count = 0

        for key, history in tracks_history.items():
            song_title, artist = key.split('|')

            for i in range(1, len(history)):
                prev = history[i-1]
                curr = history[i]

                prev_streams = self._parse_int(prev.get('streams', '0'))
                curr_streams = self._parse_int(curr.get('streams', '0'))
                daily_streams = self._parse_int(curr.get('daily_streams', '0'))

                prev_date = self._get_date_key(prev.get('timestamp', ''))
                curr_date = self._get_date_key(curr.get('timestamp', ''))

                # Check 1: Streams decreased (should never happen)
                if curr_streams < prev_streams:
                    self._add_issue(
                        'stream_anomaly',
                        'critical',
                        f"Streams DECREASED for '{song_title}' by {artist}: "
                        f"{prev_streams:,} -> {curr_streams:,} "
                        f"(diff: {curr_streams - prev_streams:,})",
                        {
                            'song_title': song_title,
                            'artist': artist,
                            'prev_streams': prev_streams,
                            'curr_streams': curr_streams,
                            'prev_date': prev_date,
                            'curr_date': curr_date
                        }
                    )
                    anomaly_count += 1

                # Check 2: Unusually large daily increase
                if prev_streams > 0:
                    increase = curr_streams - prev_streams
                    increase_percent = (increase / prev_streams) * 100

                    if increase > CONFIG['max_daily_increase_absolute']:
                        self._add_issue(
                            'stream_anomaly',
                            'warning',
                            f"Large daily increase for '{song_title}' by {artist}: "
                            f"+{increase:,} streams ({increase_percent:.1f}%)",
                            {
                                'song_title': song_title,
                                'artist': artist,
                                'increase': increase,
                                'increase_percent': increase_percent,
                                'curr_date': curr_date
                            }
                        )
                        anomaly_count += 1

        print(f"  Found {anomaly_count} stream anomalies")

    def check_zero_blank_values(self):
        """Check for zero, blank, or missing values"""
        print("\nChecking for zero/blank values...")

        zero_blank_count = 0

        # Check streams data
        for row in self.streams_data:
            song_title = row.get('song_title', '').strip()
            artist = row.get('artist', '').strip()
            streams = self._parse_int(row.get('streams', '0'))
            timestamp = row.get('timestamp', '')
            date_key = self._get_date_key(timestamp)

            # Missing song title
            if not song_title:
                self._add_issue(
                    'missing_value',
                    'critical',
                    f"Missing song title in streams data at {timestamp}",
                    {'row': row}
                )
                zero_blank_count += 1

            # Missing artist
            if not artist:
                self._add_issue(
                    'missing_value',
                    'critical',
                    f"Missing artist for '{song_title}' at {timestamp}",
                    {'song_title': song_title, 'timestamp': timestamp}
                )
                zero_blank_count += 1

            # Zero streams
            if streams == 0 and song_title:
                self._add_issue(
                    'zero_value',
                    'warning',
                    f"Zero streams for '{song_title}' by {artist} on {date_key}",
                    {'song_title': song_title, 'artist': artist, 'date': date_key}
                )
                zero_blank_count += 1

            # Check for very low daily streams on main artists
            daily_streams = self._parse_int(row.get('daily_streams', '0'))
            if (daily_streams < CONFIG['min_expected_daily_streams'] and
                artist.upper() in [a.upper() for a in CONFIG['main_artists']]):
                self._add_issue(
                    'low_value',
                    'info',
                    f"Low daily streams ({daily_streams:,}) for '{song_title}' by {artist} on {date_key}",
                    {'song_title': song_title, 'artist': artist, 'daily_streams': daily_streams, 'date': date_key}
                )
                zero_blank_count += 1

        # Check monthly listeners data
        for row in self.listeners_data:
            artist = row.get('artist_name', '').strip()
            listeners = self._parse_int(row.get('monthly_listeners', '0'))
            timestamp = row.get('timestamp', '')
            date_key = self._get_date_key(timestamp)

            # Missing artist
            if not artist:
                self._add_issue(
                    'missing_value',
                    'critical',
                    f"Missing artist name in listeners data at {timestamp}",
                    {'row': row}
                )
                zero_blank_count += 1

            # Zero listeners for main artists
            if (listeners == 0 and
                artist.upper() in [a.upper() for a in CONFIG['main_artists']]):
                self._add_issue(
                    'zero_value',
                    'critical',
                    f"Zero monthly listeners for {artist} on {date_key}",
                    {'artist': artist, 'date': date_key}
                )
                zero_blank_count += 1

            # Low listeners for main artists
            if (0 < listeners < CONFIG['min_expected_listeners'] and
                artist.upper() in [a.upper() for a in CONFIG['main_artists']]):
                self._add_issue(
                    'low_value',
                    'warning',
                    f"Unusually low listeners ({listeners:,}) for {artist} on {date_key}",
                    {'artist': artist, 'listeners': listeners, 'date': date_key}
                )
                zero_blank_count += 1

        print(f"  Found {zero_blank_count} zero/blank/low value issues")

    def check_stale_data(self):
        """Check for data that hasn't changed from previous days"""
        print("\nChecking for stale data...")

        stale_count = 0

        # Check streams - group by track
        tracks_history: Dict[str, List[Dict]] = defaultdict(list)

        for row in self.streams_data:
            song_title = row.get('song_title', '').strip()
            artist = row.get('artist', '').strip()
            if song_title and artist:
                key = f"{song_title}|{artist}".lower()
                tracks_history[key].append(row)

        for key in tracks_history:
            tracks_history[key].sort(key=lambda x: x.get('timestamp', ''))

        for key, history in tracks_history.items():
            song_title, artist = key.split('|')

            # Check for consecutive days with same stream count
            consecutive_same = 0
            last_streams = None
            same_start_date = None

            for row in history:
                streams = self._parse_int(row.get('streams', '0'))
                date_key = self._get_date_key(row.get('timestamp', ''))

                if streams == last_streams and streams > 0:
                    consecutive_same += 1
                    if consecutive_same == 1:
                        same_start_date = date_key
                else:
                    if consecutive_same >= CONFIG['stale_days_threshold']:
                        self._add_issue(
                            'stale_data',
                            'warning',
                            f"Stale streams for '{song_title}' by {artist}: "
                            f"{last_streams:,} unchanged for {consecutive_same + 1} days "
                            f"starting {same_start_date}",
                            {
                                'song_title': song_title,
                                'artist': artist,
                                'streams': last_streams,
                                'consecutive_days': consecutive_same + 1,
                                'start_date': same_start_date
                            }
                        )
                        stale_count += 1
                    consecutive_same = 0
                    same_start_date = None

                last_streams = streams

            # Check final consecutive run
            if consecutive_same >= CONFIG['stale_days_threshold']:
                self._add_issue(
                    'stale_data',
                    'warning',
                    f"Stale streams for '{song_title}' by {artist}: "
                    f"{last_streams:,} unchanged for {consecutive_same + 1} days "
                    f"starting {same_start_date} (ongoing)",
                    {
                        'song_title': song_title,
                        'artist': artist,
                        'streams': last_streams,
                        'consecutive_days': consecutive_same + 1,
                        'start_date': same_start_date,
                        'ongoing': True
                    }
                )
                stale_count += 1

        # Check monthly listeners - group by artist
        artist_history: Dict[str, List[Dict]] = defaultdict(list)

        for row in self.listeners_data:
            artist = row.get('artist_name', '').strip().upper()
            if artist:
                artist_history[artist].append(row)

        for artist in artist_history:
            artist_history[artist].sort(key=lambda x: x.get('timestamp', ''))

        for artist, history in artist_history.items():
            consecutive_same = 0
            last_listeners = None
            same_start_date = None

            for row in history:
                listeners = self._parse_int(row.get('monthly_listeners', '0'))
                date_key = self._get_date_key(row.get('timestamp', ''))

                if listeners == last_listeners and listeners > 0:
                    consecutive_same += 1
                    if consecutive_same == 1:
                        same_start_date = date_key
                else:
                    if (consecutive_same >= CONFIG['stale_days_threshold'] and
                        artist in [a.upper() for a in CONFIG['main_artists']]):
                        self._add_issue(
                            'stale_data',
                            'warning',
                            f"Stale listeners for {artist}: "
                            f"{last_listeners:,} unchanged for {consecutive_same + 1} days "
                            f"starting {same_start_date}",
                            {
                                'artist': artist,
                                'listeners': last_listeners,
                                'consecutive_days': consecutive_same + 1,
                                'start_date': same_start_date
                            }
                        )
                        stale_count += 1
                    consecutive_same = 0
                    same_start_date = None

                last_listeners = listeners

            # Check final consecutive run
            if (consecutive_same >= CONFIG['stale_days_threshold'] and
                artist in [a.upper() for a in CONFIG['main_artists']]):
                self._add_issue(
                    'stale_data',
                    'warning',
                    f"Stale listeners for {artist}: "
                    f"{last_listeners:,} unchanged for {consecutive_same + 1} days "
                    f"starting {same_start_date} (ongoing)",
                    {
                        'artist': artist,
                        'listeners': last_listeners,
                        'consecutive_days': consecutive_same + 1,
                        'start_date': same_start_date,
                        'ongoing': True
                    }
                )
                stale_count += 1

        print(f"  Found {stale_count} stale data issues")

    def check_listener_anomalies(self):
        """Check for anomalous monthly listener changes"""
        print("\nChecking listener anomalies...")

        anomaly_count = 0

        # Group by artist
        artist_history: Dict[str, List[Dict]] = defaultdict(list)

        for row in self.listeners_data:
            artist = row.get('artist_name', '').strip()
            if artist:
                artist_history[artist.upper()].append(row)

        for artist in artist_history:
            artist_history[artist].sort(key=lambda x: x.get('timestamp', ''))

        for artist, history in artist_history.items():
            for i in range(1, len(history)):
                prev = history[i-1]
                curr = history[i]

                prev_listeners = self._parse_int(prev.get('monthly_listeners', '0'))
                curr_listeners = self._parse_int(curr.get('monthly_listeners', '0'))

                if prev_listeners > 0:
                    change = curr_listeners - prev_listeners
                    change_percent = abs(change / prev_listeners) * 100

                    if change_percent > CONFIG['max_listener_change_percent']:
                        prev_date = self._get_date_key(prev.get('timestamp', ''))
                        curr_date = self._get_date_key(curr.get('timestamp', ''))
                        direction = "increased" if change > 0 else "decreased"

                        self._add_issue(
                            'listener_anomaly',
                            'warning',
                            f"Large listener change for {artist}: "
                            f"{prev_listeners:,} -> {curr_listeners:,} "
                            f"({direction} {change_percent:.1f}%) from {prev_date} to {curr_date}",
                            {
                                'artist': artist,
                                'prev_listeners': prev_listeners,
                                'curr_listeners': curr_listeners,
                                'change': change,
                                'change_percent': change_percent,
                                'prev_date': prev_date,
                                'curr_date': curr_date
                            }
                        )
                        anomaly_count += 1

        print(f"  Found {anomaly_count} listener anomalies")

    def check_missing_data(self):
        """Check for missing expected data (gaps in dates)"""
        print("\nChecking for missing data...")

        missing_count = 0

        # Get all dates in the streams data
        stream_dates: Dict[str, set] = defaultdict(set)
        for row in self.streams_data:
            artist = row.get('artist', '').strip().upper()
            if artist and artist in [a.upper() for a in CONFIG['main_artists']]:
                date_key = self._get_date_key(row.get('timestamp', ''))
                stream_dates[artist].add(date_key)

        # Get all dates in the listeners data
        listener_dates: Dict[str, set] = defaultdict(set)
        for row in self.listeners_data:
            artist = row.get('artist_name', '').strip().upper()
            if artist and artist in [a.upper() for a in CONFIG['main_artists']]:
                date_key = self._get_date_key(row.get('timestamp', ''))
                listener_dates[artist].add(date_key)

        # Check for date gaps in main artists' data
        for artist in [a.upper() for a in CONFIG['main_artists']]:
            if artist in listener_dates and len(listener_dates[artist]) > 1:
                dates = sorted(listener_dates[artist])
                for i in range(1, len(dates)):
                    prev_date = datetime.strptime(dates[i-1], '%Y%m%d')
                    curr_date = datetime.strptime(dates[i], '%Y%m%d')
                    gap = (curr_date - prev_date).days

                    if gap > 1:
                        self._add_issue(
                            'missing_data',
                            'info',
                            f"Gap in listener data for {artist}: "
                            f"{gap - 1} day(s) missing between {dates[i-1]} and {dates[i]}",
                            {
                                'artist': artist,
                                'from_date': dates[i-1],
                                'to_date': dates[i],
                                'missing_days': gap - 1
                            }
                        )
                        missing_count += 1

        print(f"  Found {missing_count} missing data gaps")

    def check_duplicate_entries(self):
        """Check for duplicate entries on the same date"""
        print("\nChecking for duplicate entries...")

        duplicate_count = 0

        # Check streams data
        stream_entries: Dict[str, List[Dict]] = defaultdict(list)
        for row in self.streams_data:
            song_title = row.get('song_title', '').strip().lower()
            artist = row.get('artist', '').strip().lower()
            date_key = self._get_date_key(row.get('timestamp', ''))
            key = f"{song_title}|{artist}|{date_key}"
            stream_entries[key].append(row)

        for key, entries in stream_entries.items():
            if len(entries) > 1:
                parts = key.split('|')
                song_title, artist, date = parts[0], parts[1], parts[2]

                # Check if the streams values differ
                streams_values = [self._parse_int(e.get('streams', '0')) for e in entries]
                if len(set(streams_values)) > 1:
                    self._add_issue(
                        'duplicate_entry',
                        'warning',
                        f"Duplicate entries with different values for '{song_title}' by {artist} on {date}: "
                        f"streams values = {streams_values}",
                        {
                            'song_title': song_title,
                            'artist': artist,
                            'date': date,
                            'count': len(entries),
                            'values': streams_values
                        }
                    )
                else:
                    self._add_issue(
                        'duplicate_entry',
                        'info',
                        f"Duplicate entries (same values) for '{song_title}' by {artist} on {date}: "
                        f"{len(entries)} entries",
                        {
                            'song_title': song_title,
                            'artist': artist,
                            'date': date,
                            'count': len(entries)
                        }
                    )
                duplicate_count += 1

        print(f"  Found {duplicate_count} duplicate entry issues")

    def check_zero_change_tracks(self) -> List[Dict]:
        """Check for tracks with zero change between the last two days (likely OCR fallback)"""
        print("\nChecking for zero-change tracks...")

        zero_change_tracks = []

        # Group streams by track (spotify_link as unique identifier)
        tracks_by_link: Dict[str, List[Dict]] = defaultdict(list)

        for row in self.streams_data:
            spotify_link = row.get('spotify_link', '').strip()
            if spotify_link:
                tracks_by_link[spotify_link].append(row)

        # Sort each track's history by timestamp
        for link in tracks_by_link:
            tracks_by_link[link].sort(key=lambda x: x.get('timestamp', ''))

        # Get the two most recent dates in the data
        all_dates = set()
        for row in self.streams_data:
            date_key = self._get_date_key(row.get('timestamp', ''))
            if date_key:
                all_dates.add(date_key)

        if len(all_dates) < 2:
            print("  Not enough dates to check for zero-change")
            return zero_change_tracks

        sorted_dates = sorted(all_dates, reverse=True)
        latest_date = sorted_dates[0]
        previous_date = sorted_dates[1]

        print(f"  Comparing {latest_date} vs {previous_date}")

        for link, history in tracks_by_link.items():
            # Get entries for the two most recent dates
            latest_entry = None
            previous_entry = None

            for row in history:
                date_key = self._get_date_key(row.get('timestamp', ''))
                if date_key == latest_date:
                    latest_entry = row
                elif date_key == previous_date:
                    previous_entry = row

            if latest_entry and previous_entry:
                latest_streams = self._parse_int(latest_entry.get('streams', '0'))
                previous_streams = self._parse_int(previous_entry.get('streams', '0'))

                # Zero change indicates likely OCR fallback
                if latest_streams == previous_streams and latest_streams > 0:
                    song_title = latest_entry.get('song_title', '').strip()
                    artist = latest_entry.get('artist', '').strip()

                    zero_change_tracks.append({
                        'song_title': song_title,
                        'artist': artist,
                        'spotify_link': link,
                        'streams': latest_streams,
                        'date': latest_date
                    })

                    self._add_issue(
                        'zero_change',
                        'warning',
                        f"Zero change for '{song_title}' by {artist}: "
                        f"{latest_streams:,} streams unchanged from {previous_date} to {latest_date}",
                        {
                            'song_title': song_title,
                            'artist': artist,
                            'spotify_link': link,
                            'streams': latest_streams,
                            'previous_date': previous_date,
                            'latest_date': latest_date
                        }
                    )

        print(f"  Found {len(zero_change_tracks)} zero-change tracks")
        return zero_change_tracks

    def get_zero_change_tracks(self) -> List[Dict]:
        """Get list of zero-change tracks with full metadata for RPA"""
        zero_change = self.check_zero_change_tracks()

        # Enrich with track metadata from tracks.csv
        tracks_meta = {}
        for track in self.tracks_data:
            link = track.get('Spotify Link', '').strip()
            if link:
                tracks_meta[link] = track

        enriched_tracks = []
        for item in zero_change:
            link = item['spotify_link']
            if link in tracks_meta:
                meta = tracks_meta[link]
                enriched_tracks.append({
                    'song_title': meta.get('Song Title', item['song_title']),
                    'artist': meta.get('Artist', item['artist']),
                    'year': meta.get('Year', ''),
                    'album': meta.get('Album/EP/Single', ''),
                    'collaborating_artists': meta.get('Collaborating Artist(s)', ''),
                    'spotify_link': link,
                    'streams': item['streams']
                })

        return enriched_tracks

    def fix_zero_change_tracks(self, dry_run: bool = False) -> Tuple[int, int]:
        """
        Fix zero-change tracks by running the RPA scraper.

        Returns: (processed_count, failed_count)
        """
        zero_change = self.get_zero_change_tracks()

        if not zero_change:
            print("\nNo zero-change tracks to fix.")
            return 0, 0

        print(f"\nFound {len(zero_change)} zero-change tracks to fix")

        if dry_run:
            print("\n[DRY RUN] Would fix the following tracks:")
            for track in zero_change:
                print(f"  - {track['song_title']} by {track['artist']}")
            return len(zero_change), 0

        # Create temporary CSV for RPA
        temp_csv_path = os.path.join(self.data_dir, 'temp_zero_change_tracks.csv')

        with open(temp_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Song Title', 'Artist', 'Year', 'Album/EP/Single',
                           'Collaborating Artist(s)', 'Spotify Link', 'Streams'])
            for track in zero_change:
                writer.writerow([
                    track['song_title'],
                    track['artist'],
                    track['year'],
                    track['album'],
                    track['collaborating_artists'],
                    track['spotify_link'],
                    ''
                ])

        print(f"Created temporary track list: {temp_csv_path}")
        print(f"\nRunning RPA for {len(zero_change)} tracks...")
        print("=" * 60)

        # Run the RPA script
        rpa_script = os.path.join(self.data_dir, 'sb19_tracks_streams_rpa.py')

        if not os.path.exists(rpa_script):
            print(f"ERROR: RPA script not found: {rpa_script}")
            return 0, len(zero_change)

        try:
            result = subprocess.run(
                [sys.executable, rpa_script, temp_csv_path, '--force'],
                cwd=self.data_dir,
                capture_output=False,  # Show output in real-time
                text=True
            )

            if result.returncode == 0:
                print("\n" + "=" * 60)
                print(f"RPA completed successfully for {len(zero_change)} tracks")
                return len(zero_change), 0
            else:
                print(f"\nRPA completed with errors (exit code: {result.returncode})")
                return len(zero_change), 0  # RPA handles failures internally

        except Exception as e:
            print(f"Error running RPA: {e}")
            return 0, len(zero_change)

        finally:
            # Clean up temp file
            if os.path.exists(temp_csv_path):
                try:
                    os.remove(temp_csv_path)
                    print(f"Cleaned up temporary file: {temp_csv_path}")
                except Exception:
                    pass

    def run_all_checks(self, skip_zero_change: bool = False):
        """Run all data quality checks"""
        print("\n" + "="*60)
        print("SB19 Dashboard Data Cleanup Agent")
        print("="*60)

        self.load_data()

        self.check_stream_anomalies()
        self.check_listener_anomalies()
        self.check_zero_blank_values()
        self.check_stale_data()
        self.check_missing_data()
        self.check_duplicate_entries()

        if not skip_zero_change:
            self.check_zero_change_tracks()

        return self.issues

    def generate_report(self, output_file: str = None) -> str:
        """Generate a detailed report of all issues found"""
        report_lines = []
        report_lines.append("\n" + "="*60)
        report_lines.append("DATA QUALITY REPORT")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("="*60)

        # Summary by severity
        critical = [i for i in self.issues if i['severity'] == 'critical']
        warnings = [i for i in self.issues if i['severity'] == 'warning']
        info = [i for i in self.issues if i['severity'] == 'info']

        report_lines.append(f"\nSUMMARY:")
        report_lines.append(f"  Critical issues: {len(critical)}")
        report_lines.append(f"  Warnings: {len(warnings)}")
        report_lines.append(f"  Info: {len(info)}")
        report_lines.append(f"  Total issues: {len(self.issues)}")

        # Summary by category
        categories = defaultdict(list)
        for issue in self.issues:
            categories[issue['category']].append(issue)

        report_lines.append(f"\nISSUES BY CATEGORY:")
        for cat, issues in sorted(categories.items()):
            report_lines.append(f"  {cat}: {len(issues)}")

        # Detail sections
        if critical:
            report_lines.append("\n" + "-"*60)
            report_lines.append("CRITICAL ISSUES (require immediate attention)")
            report_lines.append("-"*60)
            for i, issue in enumerate(critical, 1):
                report_lines.append(f"\n{i}. [{issue['category']}] {issue['message']}")

        if warnings:
            report_lines.append("\n" + "-"*60)
            report_lines.append("WARNINGS (should be reviewed)")
            report_lines.append("-"*60)
            for i, issue in enumerate(warnings, 1):
                report_lines.append(f"\n{i}. [{issue['category']}] {issue['message']}")

        if info:
            report_lines.append("\n" + "-"*60)
            report_lines.append("INFO (for awareness)")
            report_lines.append("-"*60)
            for i, issue in enumerate(info, 1):
                report_lines.append(f"\n{i}. [{issue['category']}] {issue['message']}")

        report_lines.append("\n" + "="*60)
        report_lines.append("END OF REPORT")
        report_lines.append("="*60 + "\n")

        report = '\n'.join(report_lines)

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to: {output_file}")

        return report

    def export_issues_json(self, output_file: str):
        """Export issues to JSON for programmatic processing"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'generated': datetime.now().isoformat(),
                'summary': {
                    'critical': len([i for i in self.issues if i['severity'] == 'critical']),
                    'warning': len([i for i in self.issues if i['severity'] == 'warning']),
                    'info': len([i for i in self.issues if i['severity'] == 'info']),
                    'total': len(self.issues)
                },
                'issues': self.issues
            }, f, indent=2)
        print(f"Issues exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='SB19 Dashboard Data Cleanup Agent - Validates and reports data quality issues'
    )
    parser.add_argument(
        '--data-dir', '-d',
        default='.',
        help='Directory containing the data files (default: current directory)'
    )
    parser.add_argument(
        '--report', '-r',
        default='data_quality_report.txt',
        help='Output file for the text report (default: data_quality_report.txt)'
    )
    parser.add_argument(
        '--json', '-j',
        default=None,
        help='Output file for JSON export of issues (optional)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Only output the final report summary'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix zero-change tracks by running RPA'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without actually running RPA (use with --fix)'
    )

    args = parser.parse_args()

    # Run the agent
    agent = DataCleanupAgent(data_dir=args.data_dir)

    if args.fix:
        # Load data first
        agent.load_data()

        # Fix zero-change tracks
        processed, failed = agent.fix_zero_change_tracks(dry_run=args.dry_run)

        if not args.dry_run and processed > 0:
            print(f"\nFixed {processed} tracks. Re-running checks...")
            # Reload data and run checks
            agent.streams_data = []
            agent.issues = []
            issues = agent.run_all_checks()
        else:
            # Just run checks without fixing
            agent.issues = []
            issues = agent.run_all_checks(skip_zero_change=True)
    else:
        issues = agent.run_all_checks()

    # Generate report
    report = agent.generate_report(output_file=args.report)

    if not args.quiet:
        print(report)

    # Export JSON if requested
    if args.json:
        agent.export_issues_json(args.json)

    # Return exit code based on critical issues
    critical_count = len([i for i in issues if i['severity'] == 'critical'])
    if critical_count > 0:
        print(f"\n!!! {critical_count} CRITICAL issues found - manual review required !!!")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
