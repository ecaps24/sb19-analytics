#!/usr/bin/env python3
"""
Monthly Listeners Agent - Comprehensive analyzer for Spotify monthly listener data.
Tracks growth trends, compares artists, generates reports, and provides insights.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ArtistSnapshot:
    """Represents an artist's monthly listeners at a point in time."""
    artist_name: str
    monthly_listeners: int
    timestamp: str
    date: str  # Extracted date portion


@dataclass
class ArtistTrend:
    """Represents an artist's growth trend over a period."""
    artist_name: str
    current_listeners: int
    previous_listeners: int
    change: int
    change_percent: float
    period_days: int
    trend: str  # 'growing', 'declining', 'stable'


@dataclass
class ArtistRanking:
    """Represents an artist's ranking among tracked artists."""
    rank: int
    artist_name: str
    monthly_listeners: int
    change_from_previous: Optional[int]
    previous_rank: Optional[int]


@dataclass
class OutlierRecord:
    """Represents a detected outlier record."""
    artist_name: str
    date: str
    timestamp: str
    value: int
    previous_value: int
    change_percent: float
    reason: str


class MonthlyListenersAgent:
    """Analyzes monthly listener data and generates insights."""

    # Artist groups for categorization
    ARTIST_GROUPS = {
        'sb19_members': ['SB19', 'PABLO', 'JOSH CULLEN', 'Stell', 'Felip', 'justin', 'FINIX'],
        'ppop': ['SB19', 'BINI', 'G22', 'ALAMAT', 'BGYO', 'Press Hit Play'],
        'opm_legends': ['Eraserheads', 'Rivermaya', 'Parokya Ni Edgar', 'Sponge Cola',
                        'The Itchyworms', 'Orange & Lemons', 'Silent Sanctuary'],
        'opm_modern': ['Ben&Ben', 'Cup of Joe', 'Dionela', 'Zack Tabudlo', 'Moira Dela Torre',
                       'Arthur Nery', 'juan karlos', 'Dilaw', 'Lola Amour', 'December Avenue']
    }

    # Outlier detection threshold (percentage)
    OUTLIER_THRESHOLD = 30.0

    def __init__(self, csv_path: str = None, filter_outliers: bool = False, outlier_threshold: float = None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.csv_path = csv_path or os.path.join(self.base_dir, "monthly_listeners.csv")
        self.data: list[ArtistSnapshot] = []
        self.raw_data: list[ArtistSnapshot] = []  # Unfiltered data
        self.artists: set[str] = set()
        self.outliers: list[OutlierRecord] = []
        self.filter_outliers = filter_outliers
        self.outlier_threshold = outlier_threshold or self.OUTLIER_THRESHOLD
        self._load_data()

    def _load_data(self):
        """Load monthly listeners data from CSV."""
        if not os.path.exists(self.csv_path):
            print(f"[ERROR] Data file not found: {self.csv_path}")
            return

        try:
            with open(self.csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        listeners = int(row.get('monthly_listeners', 0))
                        timestamp = row.get('timestamp', '')
                        date = timestamp.split('_')[0] if '_' in timestamp else timestamp[:8]

                        snapshot = ArtistSnapshot(
                            artist_name=row.get('artist_name', 'Unknown'),
                            monthly_listeners=listeners,
                            timestamp=timestamp,
                            date=date
                        )
                        self.raw_data.append(snapshot)
                        self.artists.add(snapshot.artist_name)
                    except (ValueError, KeyError):
                        continue

            # Detect and optionally filter outliers
            if self.filter_outliers:
                self._detect_and_filter_outliers()
            else:
                self.data = self.raw_data.copy()

            outlier_msg = f" ({len(self.outliers)} outliers filtered)" if self.outliers else ""
            print(f"[INFO] Loaded {len(self.data)} records for {len(self.artists)} artists{outlier_msg}")
        except Exception as e:
            print(f"[ERROR] Failed to load data: {e}")

    def _detect_and_filter_outliers(self):
        """Detect outliers based on percentage change threshold and filter them out."""
        # Group data by artist
        artist_data = defaultdict(list)
        for snapshot in self.raw_data:
            artist_data[snapshot.artist_name].append(snapshot)

        # Sort each artist's data by timestamp
        for artist in artist_data:
            artist_data[artist].sort(key=lambda x: x.timestamp)

        # Detect outliers for each artist
        outlier_timestamps = set()

        for artist, snapshots in artist_data.items():
            # Get unique daily records (latest per day)
            daily_records = {}
            for s in snapshots:
                if s.date not in daily_records or s.timestamp > daily_records[s.date].timestamp:
                    daily_records[s.date] = s

            sorted_dates = sorted(daily_records.keys())

            for i in range(1, len(sorted_dates)):
                prev_date = sorted_dates[i - 1]
                curr_date = sorted_dates[i]
                prev_snapshot = daily_records[prev_date]
                curr_snapshot = daily_records[curr_date]

                prev_val = prev_snapshot.monthly_listeners
                curr_val = curr_snapshot.monthly_listeners

                if prev_val > 0:
                    change_pct = abs(curr_val - prev_val) / prev_val * 100

                    if change_pct > self.outlier_threshold:
                        # Determine which value is the outlier
                        # If current is much smaller (likely OCR error), mark current as outlier
                        # If current is much larger than reasonable, also mark as outlier
                        if curr_val < prev_val * 0.01:  # Current is <1% of previous (likely partial read)
                            reason = f"Value too small (likely OCR error): {curr_val:,} vs prev {prev_val:,}"
                            outlier_timestamps.add(curr_snapshot.timestamp)
                            self.outliers.append(OutlierRecord(
                                artist_name=artist,
                                date=curr_date,
                                timestamp=curr_snapshot.timestamp,
                                value=curr_val,
                                previous_value=prev_val,
                                change_percent=change_pct,
                                reason=reason
                            ))
                        elif change_pct > self.outlier_threshold:
                            # Check if next day returns to normal (confirming this is outlier)
                            if i + 1 < len(sorted_dates):
                                next_date = sorted_dates[i + 1]
                                next_snapshot = daily_records[next_date]
                                next_val = next_snapshot.monthly_listeners

                                # If next value is closer to previous, current is the outlier
                                if abs(next_val - prev_val) < abs(curr_val - prev_val):
                                    reason = f"Spike/drop ({change_pct:.1f}% change), next day normal"
                                    outlier_timestamps.add(curr_snapshot.timestamp)
                                    self.outliers.append(OutlierRecord(
                                        artist_name=artist,
                                        date=curr_date,
                                        timestamp=curr_snapshot.timestamp,
                                        value=curr_val,
                                        previous_value=prev_val,
                                        change_percent=change_pct,
                                        reason=reason
                                    ))

        # Filter out outliers from data
        self.data = [s for s in self.raw_data if s.timestamp not in outlier_timestamps]

    def detect_outliers(self, threshold: float = None) -> list[OutlierRecord]:
        """Detect outliers without filtering (for analysis)."""
        threshold = threshold or self.outlier_threshold
        outliers = []

        # Group data by artist
        artist_data = defaultdict(list)
        for snapshot in self.raw_data:
            artist_data[snapshot.artist_name].append(snapshot)

        for artist, snapshots in artist_data.items():
            # Get unique daily records
            daily_records = {}
            for s in snapshots:
                if s.date not in daily_records or s.timestamp > daily_records[s.date].timestamp:
                    daily_records[s.date] = s

            sorted_dates = sorted(daily_records.keys())

            for i in range(1, len(sorted_dates)):
                prev_date = sorted_dates[i - 1]
                curr_date = sorted_dates[i]
                prev_snapshot = daily_records[prev_date]
                curr_snapshot = daily_records[curr_date]

                prev_val = prev_snapshot.monthly_listeners
                curr_val = curr_snapshot.monthly_listeners

                if prev_val > 0:
                    change_pct = abs(curr_val - prev_val) / prev_val * 100

                    if change_pct > threshold:
                        reason = f"{change_pct:.1f}% change: {prev_val:,} -> {curr_val:,}"
                        outliers.append(OutlierRecord(
                            artist_name=artist,
                            date=curr_date,
                            timestamp=curr_snapshot.timestamp,
                            value=curr_val,
                            previous_value=prev_val,
                            change_percent=change_pct,
                            reason=reason
                        ))

        return sorted(outliers, key=lambda x: x.change_percent, reverse=True)

    def cleanup_csv(self, output_path: str = None, threshold: float = None, dry_run: bool = False) -> dict:
        """
        Clean up CSV by removing outlier records.
        Returns summary of cleanup operation.
        """
        threshold = threshold or self.outlier_threshold
        output_path = output_path or self.csv_path

        # Detect all outliers
        outliers = self.detect_outliers(threshold)
        outlier_timestamps = {o.timestamp for o in outliers}

        # Also mark records with suspiciously low values as outliers
        # (values that are less than 1000 when previous/next are in millions)
        artist_data = defaultdict(list)
        for snapshot in self.raw_data:
            artist_data[snapshot.artist_name].append(snapshot)

        additional_outliers = set()
        for artist, snapshots in artist_data.items():
            snapshots_sorted = sorted(snapshots, key=lambda x: x.timestamp)
            for i, s in enumerate(snapshots_sorted):
                # Check if this value is suspiciously low
                if s.monthly_listeners < 1000:
                    # Check neighbors
                    neighbors = []
                    if i > 0:
                        neighbors.append(snapshots_sorted[i - 1].monthly_listeners)
                    if i < len(snapshots_sorted) - 1:
                        neighbors.append(snapshots_sorted[i + 1].monthly_listeners)

                    if neighbors and all(n > 10000 for n in neighbors):
                        additional_outliers.add(s.timestamp)
                        outliers.append(OutlierRecord(
                            artist_name=artist,
                            date=s.date,
                            timestamp=s.timestamp,
                            value=s.monthly_listeners,
                            previous_value=neighbors[0] if neighbors else 0,
                            change_percent=9999.0,
                            reason=f"Suspiciously low value ({s.monthly_listeners}) compared to neighbors"
                        ))

        outlier_timestamps.update(additional_outliers)

        # Filter clean records
        clean_records = [s for s in self.raw_data if s.timestamp not in outlier_timestamps]

        summary = {
            'total_records': len(self.raw_data),
            'outliers_found': len(outlier_timestamps),
            'clean_records': len(clean_records),
            'removed_percentage': round(len(outlier_timestamps) / len(self.raw_data) * 100, 2) if self.raw_data else 0,
            'outliers': [asdict(o) for o in outliers[:50]],  # Top 50 for summary
            'output_path': output_path,
            'dry_run': dry_run
        }

        if dry_run:
            print(f"[DRY RUN] Would remove {len(outlier_timestamps)} outlier records")
            print(f"[DRY RUN] Would keep {len(clean_records)} clean records")
        else:
            # Write cleaned CSV
            backup_path = output_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

            # Backup original
            if os.path.exists(output_path) and output_path == self.csv_path:
                import shutil
                shutil.copy(output_path, backup_path)
                print(f"[INFO] Backup created: {backup_path}")

            # Write clean data
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['artist_name', 'monthly_listeners', 'timestamp'])
                for record in sorted(clean_records, key=lambda x: (x.timestamp, x.artist_name)):
                    writer.writerow([record.artist_name, record.monthly_listeners, record.timestamp])

            print(f"[INFO] Cleaned CSV written to: {output_path}")
            print(f"[INFO] Removed {len(outlier_timestamps)} outlier records ({summary['removed_percentage']}%)")

        return summary

    def _get_latest_by_date(self, date: str = None) -> dict[str, ArtistSnapshot]:
        """Get the latest snapshot for each artist on a specific date."""
        if date is None:
            # Get the most recent date
            dates = sorted(set(s.date for s in self.data), reverse=True)
            date = dates[0] if dates else None

        if not date:
            return {}

        result = {}
        for snapshot in self.data:
            if snapshot.date == date:
                if snapshot.artist_name not in result or snapshot.timestamp > result[snapshot.artist_name].timestamp:
                    result[snapshot.artist_name] = snapshot

        return result

    def _get_available_dates(self) -> list[str]:
        """Get list of available dates sorted descending."""
        return sorted(set(s.date for s in self.data), reverse=True)

    def get_current_rankings(self, limit: int = None, group: str = None) -> list[ArtistRanking]:
        """Get current artist rankings by monthly listeners."""
        dates = self._get_available_dates()
        if len(dates) < 1:
            return []

        current = self._get_latest_by_date(dates[0])
        previous = self._get_latest_by_date(dates[1]) if len(dates) > 1 else {}

        # Filter by group if specified
        if group and group in self.ARTIST_GROUPS:
            group_artists = set(self.ARTIST_GROUPS[group])
            current = {k: v for k, v in current.items() if k in group_artists}

        # Sort by listeners
        sorted_current = sorted(current.values(), key=lambda x: x.monthly_listeners, reverse=True)
        sorted_previous = sorted(previous.values(), key=lambda x: x.monthly_listeners, reverse=True) if previous else []

        # Build previous rankings map
        prev_ranks = {s.artist_name: i + 1 for i, s in enumerate(sorted_previous)}
        prev_listeners = {s.artist_name: s.monthly_listeners for s in sorted_previous}

        rankings = []
        for i, snapshot in enumerate(sorted_current):
            if limit and i >= limit:
                break

            prev_count = prev_listeners.get(snapshot.artist_name)
            change = (snapshot.monthly_listeners - prev_count) if prev_count else None

            rankings.append(ArtistRanking(
                rank=i + 1,
                artist_name=snapshot.artist_name,
                monthly_listeners=snapshot.monthly_listeners,
                change_from_previous=change,
                previous_rank=prev_ranks.get(snapshot.artist_name)
            ))

        return rankings

    def get_artist_trend(self, artist_name: str, days: int = 7) -> Optional[ArtistTrend]:
        """Get growth trend for a specific artist over a period."""
        dates = self._get_available_dates()

        if not dates:
            return None

        current_date = dates[0]
        current = self._get_latest_by_date(current_date).get(artist_name)

        if not current:
            return None

        # Find data from approximately 'days' ago
        target_date = (datetime.strptime(current_date, "%Y%m%d") - timedelta(days=days)).strftime("%Y%m%d")

        # Find closest available date
        previous = None
        for date in reversed(dates):
            if date <= target_date:
                prev_data = self._get_latest_by_date(date).get(artist_name)
                if prev_data:
                    previous = prev_data
                    break

        if not previous:
            # Use earliest available data
            for date in reversed(dates):
                prev_data = self._get_latest_by_date(date).get(artist_name)
                if prev_data and prev_data.date != current_date:
                    previous = prev_data
                    break

        if not previous:
            return ArtistTrend(
                artist_name=artist_name,
                current_listeners=current.monthly_listeners,
                previous_listeners=current.monthly_listeners,
                change=0,
                change_percent=0.0,
                period_days=0,
                trend='stable'
            )

        change = current.monthly_listeners - previous.monthly_listeners
        change_pct = (change / previous.monthly_listeners * 100) if previous.monthly_listeners > 0 else 0

        actual_days = (datetime.strptime(current.date, "%Y%m%d") -
                       datetime.strptime(previous.date, "%Y%m%d")).days

        if change_pct > 1:
            trend = 'growing'
        elif change_pct < -1:
            trend = 'declining'
        else:
            trend = 'stable'

        return ArtistTrend(
            artist_name=artist_name,
            current_listeners=current.monthly_listeners,
            previous_listeners=previous.monthly_listeners,
            change=change,
            change_percent=round(change_pct, 2),
            period_days=actual_days,
            trend=trend
        )

    def get_sb19_overview(self) -> dict:
        """Get overview of SB19 and all member solo accounts."""
        members = self.ARTIST_GROUPS['sb19_members']

        overview = {
            'date': None,
            'total_combined': 0,
            'group_account': None,
            'members': [],
            'trends': []
        }

        dates = self._get_available_dates()
        if not dates:
            return overview

        overview['date'] = dates[0]
        current = self._get_latest_by_date(dates[0])

        for member in members:
            if member in current:
                snapshot = current[member]
                trend = self.get_artist_trend(member, days=7)

                member_data = {
                    'name': member,
                    'monthly_listeners': snapshot.monthly_listeners,
                    'trend': trend.trend if trend else 'unknown',
                    'change': trend.change if trend else 0,
                    'change_percent': trend.change_percent if trend else 0
                }

                if member == 'SB19':
                    overview['group_account'] = member_data
                else:
                    overview['members'].append(member_data)

                overview['total_combined'] += snapshot.monthly_listeners

        # Sort members by listeners
        overview['members'].sort(key=lambda x: x['monthly_listeners'], reverse=True)

        return overview

    def compare_artists(self, artists: list[str], days: int = 30) -> dict:
        """Compare multiple artists over a time period."""
        comparison = {
            'period_days': days,
            'date': None,
            'artists': []
        }

        dates = self._get_available_dates()
        if not dates:
            return comparison

        comparison['date'] = dates[0]

        for artist in artists:
            trend = self.get_artist_trend(artist, days=days)
            if trend:
                comparison['artists'].append({
                    'name': artist,
                    'current_listeners': trend.current_listeners,
                    'previous_listeners': trend.previous_listeners,
                    'change': trend.change,
                    'change_percent': trend.change_percent,
                    'trend': trend.trend
                })

        # Sort by current listeners
        comparison['artists'].sort(key=lambda x: x['current_listeners'], reverse=True)

        return comparison

    def get_top_gainers(self, days: int = 7, limit: int = 10) -> list[dict]:
        """Get artists with the highest growth in the period."""
        gainers = []

        for artist in self.artists:
            trend = self.get_artist_trend(artist, days=days)
            if trend and trend.change != 0:
                gainers.append({
                    'artist': artist,
                    'change': trend.change,
                    'change_percent': trend.change_percent,
                    'current': trend.current_listeners,
                    'trend': trend.trend
                })

        # Sort by absolute change
        gainers.sort(key=lambda x: x['change'], reverse=True)

        return gainers[:limit]

    def get_top_losers(self, days: int = 7, limit: int = 10) -> list[dict]:
        """Get artists with the highest decline in the period."""
        losers = []

        for artist in self.artists:
            trend = self.get_artist_trend(artist, days=days)
            if trend and trend.change < 0:
                losers.append({
                    'artist': artist,
                    'change': trend.change,
                    'change_percent': trend.change_percent,
                    'current': trend.current_listeners,
                    'trend': trend.trend
                })

        # Sort by change (most negative first)
        losers.sort(key=lambda x: x['change'])

        return losers[:limit]

    def get_history(self, artist: str, limit: int = 30) -> list[dict]:
        """Get historical data for an artist."""
        history = []
        seen_dates = set()

        for snapshot in sorted(self.data, key=lambda x: x.timestamp, reverse=True):
            if snapshot.artist_name == artist and snapshot.date not in seen_dates:
                history.append({
                    'date': snapshot.date,
                    'monthly_listeners': snapshot.monthly_listeners,
                    'timestamp': snapshot.timestamp
                })
                seen_dates.add(snapshot.date)

                if len(history) >= limit:
                    break

        return history

    def get_data_summary(self) -> dict:
        """Get summary statistics about the data."""
        dates = self._get_available_dates()

        return {
            'total_records': len(self.data),
            'total_artists': len(self.artists),
            'date_range': {
                'earliest': dates[-1] if dates else None,
                'latest': dates[0] if dates else None,
                'total_days': len(dates)
            },
            'artists': sorted(list(self.artists)),
            'artist_groups': list(self.ARTIST_GROUPS.keys())
        }

    def generate_report(self, output_format: str = 'text',
                        artist: str = None,
                        group: str = None,
                        days: int = 7) -> str:
        """Generate a comprehensive report."""

        if output_format == 'json':
            return self._generate_json_report(artist, group, days)
        else:
            return self._generate_text_report(artist, group, days)

    def _generate_text_report(self, artist: str = None, group: str = None, days: int = 7) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 70)
        lines.append("MONTHLY LISTENERS ANALYTICS REPORT")
        lines.append("=" * 70)

        summary = self.get_data_summary()
        lines.append(f"Data Range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}")
        lines.append(f"Total Artists: {summary['total_artists']}")
        lines.append(f"Total Records: {summary['total_records']}")
        lines.append("")

        # Specific artist report
        if artist:
            lines.append(f"ARTIST FOCUS: {artist}")
            lines.append("-" * 50)

            trend = self.get_artist_trend(artist, days=days)
            if trend:
                lines.append(f"Current Listeners: {trend.current_listeners:,}")
                lines.append(f"Change ({trend.period_days}d): {trend.change:+,} ({trend.change_percent:+.2f}%)")
                lines.append(f"Trend: {trend.trend.upper()}")

            history = self.get_history(artist, limit=10)
            if history:
                lines.append("")
                lines.append("Recent History:")
                for h in history[:7]:
                    lines.append(f"  {h['date']}: {h['monthly_listeners']:,}")

            lines.append("")

        # SB19 Overview
        if not artist or artist in self.ARTIST_GROUPS['sb19_members']:
            lines.append("-" * 70)
            lines.append("SB19 & MEMBERS OVERVIEW")
            lines.append("-" * 70)

            overview = self.get_sb19_overview()
            if overview['group_account']:
                ga = overview['group_account']
                lines.append(f"SB19 (Group): {ga['monthly_listeners']:,} ({ga['change']:+,}, {ga['change_percent']:+.2f}%)")

            lines.append("")
            lines.append("Solo Artists:")
            for member in overview['members']:
                lines.append(f"  {member['name']}: {member['monthly_listeners']:,} "
                           f"({member['change']:+,}, {member['change_percent']:+.2f}%)")

            lines.append("")
            lines.append(f"Combined Total: {overview['total_combined']:,}")
            lines.append("")

        # Rankings
        lines.append("-" * 70)
        lines.append(f"TOP {10} ARTISTS (by Monthly Listeners)")
        lines.append("-" * 70)

        rankings = self.get_current_rankings(limit=10, group=group)
        for r in rankings:
            rank_change = ""
            if r.previous_rank:
                diff = r.previous_rank - r.rank
                if diff > 0:
                    rank_change = f" (+{diff})"
                elif diff < 0:
                    rank_change = f" ({diff})"

            listener_change = ""
            if r.change_from_previous is not None:
                listener_change = f" ({r.change_from_previous:+,})"

            lines.append(f"  {r.rank:2}. {r.artist_name}: {r.monthly_listeners:,}{listener_change}{rank_change}")

        lines.append("")

        # Top Gainers
        lines.append("-" * 70)
        lines.append(f"TOP GAINERS ({days} days)")
        lines.append("-" * 70)

        gainers = self.get_top_gainers(days=days, limit=5)
        for g in gainers:
            lines.append(f"  {g['artist']}: +{g['change']:,} ({g['change_percent']:+.2f}%)")

        lines.append("")

        # Top Losers
        lines.append("-" * 70)
        lines.append(f"TOP DECLINERS ({days} days)")
        lines.append("-" * 70)

        losers = self.get_top_losers(days=days, limit=5)
        for l in losers:
            lines.append(f"  {l['artist']}: {l['change']:,} ({l['change_percent']:+.2f}%)")

        lines.append("")
        lines.append("=" * 70)
        lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _generate_json_report(self, artist: str = None, group: str = None, days: int = 7) -> str:
        """Generate a JSON format report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self.get_data_summary(),
            'sb19_overview': self.get_sb19_overview(),
            'rankings': [asdict(r) for r in self.get_current_rankings(limit=20, group=group)],
            'top_gainers': self.get_top_gainers(days=days, limit=10),
            'top_losers': self.get_top_losers(days=days, limit=10)
        }

        if artist:
            report['artist_focus'] = {
                'trend': asdict(self.get_artist_trend(artist, days=days)) if self.get_artist_trend(artist, days=days) else None,
                'history': self.get_history(artist, limit=30)
            }

        return json.dumps(report, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="Monthly Listeners Agent - Analyze Spotify monthly listener data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monthly_listeners_agent.py                    # Generate full report
  python monthly_listeners_agent.py --artist SB19      # Focus on specific artist
  python monthly_listeners_agent.py --group sb19_members  # Filter by group
  python monthly_listeners_agent.py --json             # Output as JSON
  python monthly_listeners_agent.py --days 30          # Use 30-day period
  python monthly_listeners_agent.py --rankings 20      # Show top 20 rankings
  python monthly_listeners_agent.py --compare "SB19,BINI,Ben&Ben"
  python monthly_listeners_agent.py --history PABLO    # Show artist history
        """
    )

    parser.add_argument(
        "-a", "--artist",
        help="Focus report on a specific artist"
    )
    parser.add_argument(
        "-g", "--group",
        choices=['sb19_members', 'ppop', 'opm_legends', 'opm_modern'],
        help="Filter by artist group"
    )
    parser.add_argument(
        "-d", "--days",
        type=int,
        default=7,
        help="Period in days for trend analysis (default: 7)"
    )
    parser.add_argument(
        "-r", "--rankings",
        type=int,
        metavar="N",
        help="Show top N rankings only"
    )
    parser.add_argument(
        "-c", "--compare",
        help="Compare multiple artists (comma-separated)"
    )
    parser.add_argument(
        "--history",
        metavar="ARTIST",
        help="Show historical data for an artist"
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save report to file"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show summary stats"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show data summary only"
    )
    parser.add_argument(
        "--list-artists",
        action="store_true",
        help="List all tracked artists"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up CSV by removing outlier records (>30%% change)"
    )
    parser.add_argument(
        "--detect-outliers",
        action="store_true",
        help="Detect and report outliers without modifying data"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=30.0,
        help="Outlier threshold percentage (default: 30)"
    )
    parser.add_argument(
        "--filter-outliers",
        action="store_true",
        help="Filter out outliers when loading data for analysis"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without modifying files"
    )

    args = parser.parse_args()

    # Create agent with outlier filtering if requested
    agent = MonthlyListenersAgent(
        filter_outliers=args.filter_outliers,
        outlier_threshold=args.threshold
    )

    # Handle special commands
    if args.list_artists:
        summary = agent.get_data_summary()
        print("Tracked Artists:")
        for artist in summary['artists']:
            print(f"  - {artist}")
        print(f"\nTotal: {len(summary['artists'])} artists")
        return

    if args.detect_outliers:
        outliers = agent.detect_outliers(threshold=args.threshold)
        if args.json:
            print(json.dumps([asdict(o) for o in outliers], indent=2))
        else:
            print(f"Detected {len(outliers)} outliers (>{args.threshold}% change):")
            print("-" * 70)
            for o in outliers[:30]:
                print(f"  {o.artist_name} on {o.date}: {o.previous_value:,} -> {o.value:,} ({o.change_percent:.1f}%)")
            if len(outliers) > 30:
                print(f"  ... and {len(outliers) - 30} more")
        return

    if args.cleanup:
        summary = agent.cleanup_csv(threshold=args.threshold, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("=" * 70)
            print("DATA CLEANUP SUMMARY")
            print("=" * 70)
            print(f"Total records: {summary['total_records']:,}")
            print(f"Outliers found: {summary['outliers_found']:,} ({summary['removed_percentage']}%)")
            print(f"Clean records: {summary['clean_records']:,}")
            if args.dry_run:
                print("\n[DRY RUN] No changes made to files")
            else:
                print(f"\nOutput: {summary['output_path']}")
            print("\nTop outliers removed:")
            for o in summary['outliers'][:15]:
                print(f"  {o['artist_name']} on {o['date']}: {o['reason']}")
        return

    if args.summary:
        summary = agent.get_data_summary()
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("Data Summary:")
            print(f"  Total Records: {summary['total_records']}")
            print(f"  Total Artists: {summary['total_artists']}")
            print(f"  Date Range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}")
            print(f"  Days Tracked: {summary['date_range']['total_days']}")
        return

    if args.history:
        history = agent.get_history(args.history, limit=30)
        if args.json:
            print(json.dumps(history, indent=2))
        else:
            print(f"History for {args.history}:")
            for h in history:
                print(f"  {h['date']}: {h['monthly_listeners']:,}")
        return

    if args.compare:
        artists = [a.strip() for a in args.compare.split(',')]
        comparison = agent.compare_artists(artists, days=args.days)
        if args.json:
            print(json.dumps(comparison, indent=2))
        else:
            print(f"Artist Comparison ({args.days} days):")
            print("-" * 60)
            for a in comparison['artists']:
                print(f"  {a['name']}: {a['current_listeners']:,} "
                      f"({a['change']:+,}, {a['change_percent']:+.2f}%) [{a['trend']}]")
        return

    if args.rankings:
        rankings = agent.get_current_rankings(limit=args.rankings, group=args.group)
        if args.json:
            print(json.dumps([asdict(r) for r in rankings], indent=2))
        else:
            group_label = f" ({args.group})" if args.group else ""
            print(f"Top {args.rankings} Rankings{group_label}:")
            for r in rankings:
                change = f" ({r.change_from_previous:+,})" if r.change_from_previous else ""
                print(f"  {r.rank:2}. {r.artist_name}: {r.monthly_listeners:,}{change}")
        return

    # Generate full report
    output_format = 'json' if args.json else 'text'
    report = agent.generate_report(
        output_format=output_format,
        artist=args.artist,
        group=args.group,
        days=args.days
    )

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
