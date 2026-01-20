"""
Visual Change Detection Agent for SB19 Dashboard

This agent monitors the dashboard for visual changes by:
1. Capturing screenshots of different dashboard views
2. Comparing screenshots against baseline images
3. Detecting and highlighting visual differences
4. Generating reports on visual changes
5. Maintaining a history of visual snapshots
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Configuration
CONFIG = {
    # Dashboard URL (file path for local HTML)
    'dashboard_path': 'index.html',

    # Screenshot settings
    'screenshot_dir': 'visual_snapshots',
    'baseline_dir': 'visual_baselines',
    'diff_dir': 'visual_diffs',

    # Browser settings
    'window_width': 1920,
    'window_height': 1080,
    'page_load_wait': 5,  # seconds to wait for page to fully load

    # Comparison thresholds
    'diff_threshold_percent': 1.0,  # Flag if more than 1% of pixels differ
    'pixel_tolerance': 10,  # RGB tolerance for "same" pixels (0-255)

    # Views to capture
    'dashboard_views': [
        {'name': 'overview', 'hash': '', 'description': 'Main dashboard overview'},
        {'name': 'sb19_tracks', 'hash': '#sb19', 'description': 'SB19 group tracks view'},
        {'name': 'pablo_tracks', 'hash': '#pablo', 'description': 'Pablo solo tracks'},
        {'name': 'stell_tracks', 'hash': '#stell', 'description': 'Stell solo tracks'},
        {'name': 'felip_tracks', 'hash': '#felip', 'description': 'Felip solo tracks'},
        {'name': 'josh_tracks', 'hash': '#josh-cullen', 'description': 'Josh Cullen solo tracks'},
        {'name': 'justin_tracks', 'hash': '#justin', 'description': 'Justin solo tracks'},
    ],
}


class VisualChangeAgent:
    def __init__(self, data_dir: str = '.'):
        self.data_dir = Path(data_dir)
        self.dashboard_path = self.data_dir / CONFIG['dashboard_path']
        self.screenshot_dir = self.data_dir / CONFIG['screenshot_dir']
        self.baseline_dir = self.data_dir / CONFIG['baseline_dir']
        self.diff_dir = self.data_dir / CONFIG['diff_dir']

        self.driver = None
        self.issues: List[Dict] = []
        self.results: List[Dict] = []

        # Create directories if they don't exist
        self.screenshot_dir.mkdir(exist_ok=True)
        self.baseline_dir.mkdir(exist_ok=True)
        self.diff_dir.mkdir(exist_ok=True)

    def check_dependencies(self) -> bool:
        """Check if required dependencies are installed"""
        missing = []

        if not PIL_AVAILABLE:
            missing.append('Pillow (pip install Pillow)')

        if not SELENIUM_AVAILABLE:
            missing.append('selenium (pip install selenium)')

        if missing:
            print("ERROR: Missing required dependencies:")
            for dep in missing:
                print(f"  - {dep}")
            print("\nInstall with: pip install Pillow selenium")
            return False

        return True

    def _find_edge_driver(self) -> Optional[str]:
        """Find Microsoft Edge WebDriver"""
        possible_paths = [
            r'C:\Windows\System32\msedgedriver.exe',
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedgedriver.exe',
            os.path.expanduser('~\\msedgedriver.exe'),
            'msedgedriver.exe',  # In PATH
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Try to find via where command
        try:
            result = subprocess.run(['where', 'msedgedriver'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass

        return None

    def setup_browser(self) -> bool:
        """Initialize the browser for screenshots"""
        print("Setting up browser...")

        try:
            options = EdgeOptions()
            options.add_argument('--headless=new')
            options.add_argument(f'--window-size={CONFIG["window_width"]},{CONFIG["window_height"]}')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--force-device-scale-factor=1')

            # Try to find Edge driver
            driver_path = self._find_edge_driver()
            if driver_path:
                service = EdgeService(executable_path=driver_path)
                self.driver = webdriver.Edge(service=service, options=options)
            else:
                # Let Selenium find it automatically
                self.driver = webdriver.Edge(options=options)

            self.driver.set_window_size(CONFIG['window_width'], CONFIG['window_height'])
            print(f"  Browser initialized ({CONFIG['window_width']}x{CONFIG['window_height']})")
            return True

        except Exception as e:
            print(f"ERROR: Failed to initialize browser: {e}")
            print("\nMake sure Microsoft Edge WebDriver is installed.")
            print("Download from: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            return False

    def close_browser(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def capture_screenshot(self, view: Dict) -> Optional[Path]:
        """Capture a screenshot of a specific dashboard view"""
        if not self.driver:
            return None

        view_name = view['name']
        view_hash = view['hash']

        # Build URL
        dashboard_url = self.dashboard_path.absolute().as_uri()
        full_url = f"{dashboard_url}{view_hash}"

        print(f"  Capturing: {view_name}...", end=' ')

        try:
            # Navigate to the view
            self.driver.get(full_url)

            # Wait for page to load
            import time
            time.sleep(CONFIG['page_load_wait'])

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{view_name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            # Take screenshot
            self.driver.save_screenshot(str(filepath))
            print(f"OK ({filepath.name})")

            return filepath

        except Exception as e:
            print(f"FAILED ({e})")
            return None

    def capture_all_views(self) -> List[Dict]:
        """Capture screenshots of all configured dashboard views"""
        print("\nCapturing dashboard views...")

        captured = []
        for view in CONFIG['dashboard_views']:
            filepath = self.capture_screenshot(view)
            if filepath:
                captured.append({
                    'view': view,
                    'filepath': filepath,
                    'timestamp': datetime.now().isoformat()
                })

        print(f"\nCaptured {len(captured)}/{len(CONFIG['dashboard_views'])} views")
        return captured

    def get_baseline(self, view_name: str) -> Optional[Path]:
        """Get the baseline image for a view"""
        baseline_path = self.baseline_dir / f"{view_name}_baseline.png"
        if baseline_path.exists():
            return baseline_path
        return None

    def set_baseline(self, view_name: str, screenshot_path: Path) -> Path:
        """Set a screenshot as the new baseline for a view"""
        baseline_path = self.baseline_dir / f"{view_name}_baseline.png"

        # Copy the screenshot to baseline
        img = Image.open(screenshot_path)
        img.save(baseline_path)

        return baseline_path

    def compare_images(self, current: Path, baseline: Path, view_name: str) -> Dict:
        """Compare two images and return difference metrics"""
        img_current = Image.open(current).convert('RGB')
        img_baseline = Image.open(baseline).convert('RGB')

        # Resize if dimensions don't match
        if img_current.size != img_baseline.size:
            img_baseline = img_baseline.resize(img_current.size, Image.Resampling.LANCZOS)

        # Calculate difference
        diff = ImageChops.difference(img_current, img_baseline)

        # Count different pixels (above tolerance)
        diff_pixels = 0
        total_pixels = img_current.width * img_current.height
        diff_data = diff.getdata()

        for pixel in diff_data:
            if max(pixel) > CONFIG['pixel_tolerance']:
                diff_pixels += 1

        diff_percent = (diff_pixels / total_pixels) * 100
        has_changes = diff_percent > CONFIG['diff_threshold_percent']

        # Generate diff image if there are changes
        diff_image_path = None
        if has_changes:
            diff_image_path = self._generate_diff_image(img_current, img_baseline, diff, view_name)

        return {
            'view_name': view_name,
            'current_path': str(current),
            'baseline_path': str(baseline),
            'diff_pixels': diff_pixels,
            'total_pixels': total_pixels,
            'diff_percent': round(diff_percent, 2),
            'has_changes': has_changes,
            'diff_image': str(diff_image_path) if diff_image_path else None
        }

    def _generate_diff_image(self, current: Image.Image, baseline: Image.Image,
                             diff: Image.Image, view_name: str) -> Path:
        """Generate a visual diff image highlighting changes"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        diff_path = self.diff_dir / f"{view_name}_diff_{timestamp}.png"

        # Create a side-by-side comparison
        width = current.width
        height = current.height

        # Create composite image: baseline | current | diff highlighted
        composite = Image.new('RGB', (width * 3, height + 40), 'white')

        # Add labels
        draw = ImageDraw.Draw(composite)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        draw.text((width // 2 - 40, 10), "Baseline", fill='black', font=font)
        draw.text((width + width // 2 - 40, 10), "Current", fill='black', font=font)
        draw.text((width * 2 + width // 2 - 60, 10), "Differences", fill='red', font=font)

        # Paste images
        composite.paste(baseline, (0, 40))
        composite.paste(current, (width, 40))

        # Create highlighted diff (red overlay on changed pixels)
        diff_highlight = current.copy()
        diff_draw = ImageDraw.Draw(diff_highlight)
        diff_data = diff.getdata()

        for i, pixel in enumerate(diff_data):
            if max(pixel) > CONFIG['pixel_tolerance']:
                x = i % width
                y = i // width
                diff_draw.point((x, y), fill=(255, 0, 0))

        composite.paste(diff_highlight, (width * 2, 40))

        composite.save(diff_path)
        return diff_path

    def compare_all_views(self, screenshots: List[Dict]) -> List[Dict]:
        """Compare all captured screenshots against baselines"""
        print("\nComparing against baselines...")

        comparisons = []
        for item in screenshots:
            view_name = item['view']['name']
            current_path = item['filepath']
            baseline_path = self.get_baseline(view_name)

            if baseline_path:
                print(f"  Comparing: {view_name}...", end=' ')
                result = self.compare_images(current_path, baseline_path, view_name)

                if result['has_changes']:
                    print(f"CHANGED ({result['diff_percent']}% different)")
                    self.issues.append({
                        'severity': 'warning',
                        'type': 'visual_change',
                        'view': view_name,
                        'message': f"Visual change detected: {result['diff_percent']}% pixels different",
                        'diff_image': result['diff_image']
                    })
                else:
                    print(f"OK ({result['diff_percent']}% different)")

                comparisons.append(result)
            else:
                print(f"  No baseline for: {view_name} (use --update-baseline to create)")
                self.issues.append({
                    'severity': 'info',
                    'type': 'missing_baseline',
                    'view': view_name,
                    'message': f"No baseline image found for {view_name}"
                })

        return comparisons

    def update_baselines(self, screenshots: List[Dict], views: Optional[List[str]] = None):
        """Update baseline images from current screenshots"""
        print("\nUpdating baselines...")

        for item in screenshots:
            view_name = item['view']['name']

            # If specific views requested, only update those
            if views and view_name not in views:
                continue

            print(f"  Setting baseline: {view_name}...", end=' ')
            baseline_path = self.set_baseline(view_name, item['filepath'])
            print(f"OK ({baseline_path.name})")

    def generate_report(self, comparisons: List[Dict], output_file: Optional[str] = None) -> str:
        """Generate a visual change report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            "=" * 60,
            "VISUAL CHANGE DETECTION REPORT",
            f"Generated: {timestamp}",
            "=" * 60,
            ""
        ]

        # Summary
        total_views = len(comparisons)
        changed_views = sum(1 for c in comparisons if c.get('has_changes'))

        lines.extend([
            "SUMMARY",
            "-" * 40,
            f"Total views checked: {total_views}",
            f"Views with changes: {changed_views}",
            f"Views unchanged: {total_views - changed_views}",
            ""
        ])

        # Detailed results
        if changed_views > 0:
            lines.extend([
                "VISUAL CHANGES DETECTED",
                "-" * 40
            ])

            for comp in comparisons:
                if comp.get('has_changes'):
                    lines.extend([
                        f"\nView: {comp['view_name']}",
                        f"  Difference: {comp['diff_percent']}%",
                        f"  Changed pixels: {comp['diff_pixels']:,} / {comp['total_pixels']:,}",
                        f"  Diff image: {comp['diff_image']}"
                    ])

            lines.append("")

        # Issues
        if self.issues:
            lines.extend([
                "ISSUES",
                "-" * 40
            ])

            for issue in self.issues:
                severity = issue['severity'].upper()
                lines.append(f"[{severity}] {issue['view']}: {issue['message']}")

            lines.append("")

        lines.extend([
            "=" * 60,
            "END OF REPORT",
            "=" * 60
        ])

        report = '\n'.join(lines)

        # Write to file if specified
        if output_file:
            output_path = self.data_dir / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to: {output_path}")

        return report

    def run(self, update_baseline: bool = False, specific_views: Optional[List[str]] = None,
            report_file: Optional[str] = None, quiet: bool = False) -> int:
        """Run the visual change detection agent"""
        print("=" * 50)
        print("Visual Change Detection Agent")
        print("=" * 50)

        # Check dependencies
        if not self.check_dependencies():
            return 1

        # Verify dashboard exists
        if not self.dashboard_path.exists():
            print(f"ERROR: Dashboard not found: {self.dashboard_path}")
            return 1

        # Setup browser
        if not self.setup_browser():
            return 1

        try:
            # Capture screenshots
            screenshots = self.capture_all_views()

            if not screenshots:
                print("ERROR: No screenshots captured")
                return 1

            if update_baseline:
                # Update baselines mode
                self.update_baselines(screenshots, specific_views)
                print("\nBaselines updated successfully!")
            else:
                # Compare mode
                comparisons = self.compare_all_views(screenshots)

                # Generate report
                report = self.generate_report(comparisons, report_file)

                if not quiet:
                    print("\n" + report)

                # Return code based on changes detected
                changed = sum(1 for c in comparisons if c.get('has_changes'))
                return 1 if changed > 0 else 0

            return 0

        finally:
            self.close_browser()


def main():
    parser = argparse.ArgumentParser(
        description='Visual Change Detection Agent for SB19 Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python visual_change_agent.py                    # Compare against baselines
  python visual_change_agent.py --update-baseline  # Set current as new baseline
  python visual_change_agent.py --views overview   # Check specific view only
  python visual_change_agent.py --report report.txt  # Save report to file
  python visual_change_agent.py --quiet            # Only show summary
        '''
    )

    parser.add_argument('--update-baseline', '-u', action='store_true',
                        help='Update baseline images with current screenshots')
    parser.add_argument('--views', '-v', nargs='+',
                        help='Specific views to check (e.g., overview sb19_tracks)')
    parser.add_argument('--report', '-r', type=str,
                        help='Output report to file')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Minimal output')
    parser.add_argument('--list-views', '-l', action='store_true',
                        help='List all available views')
    parser.add_argument('--json', '-j', type=str,
                        help='Export results to JSON file')

    args = parser.parse_args()

    # List views mode
    if args.list_views:
        print("Available dashboard views:")
        for view in CONFIG['dashboard_views']:
            print(f"  {view['name']:20} - {view['description']}")
        return 0

    # Run agent
    agent = VisualChangeAgent()
    exit_code = agent.run(
        update_baseline=args.update_baseline,
        specific_views=args.views,
        report_file=args.report,
        quiet=args.quiet
    )

    # Export to JSON if requested
    if args.json:
        json_data = {
            'timestamp': datetime.now().isoformat(),
            'issues': agent.issues,
            'results': agent.results
        }
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        print(f"Results exported to: {args.json}")

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
