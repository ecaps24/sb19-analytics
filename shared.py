"""
Shared utilities for SB19 Analytics RPA scripts.

Consolidates duplicated code from:
- sb19_selenium_rpa.py
- artist_monthly_listeners_rpa.py
- track_discovery_rpa.py
- x_browser_poster.py

Usage:
    from shared import setup_driver, slugify, git_push, load_csv
"""

import csv
import os
import re
import subprocess
import unicodedata

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService

from config import USER_AGENT


def setup_driver(headless=False, profile_dir=None):
    """
    Create and return a configured Edge WebDriver instance.

    Args:
        headless: Run browser without visible UI.
        profile_dir: Path to Edge user profile directory (for authenticated sessions).

    Returns:
        Configured webdriver.Edge instance.
    """
    options = EdgeOptions()

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENT}")
    else:
        options.add_argument("--start-maximized")

    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")

    options.add_argument("--disable-notifications")
    # Anti-detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = EdgeService()
    try:
        driver = webdriver.Edge(service=service, options=options)
        if headless:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
        return driver
    except Exception as e:
        print(f"[ERR] Failed to initialize Edge Driver: {e}")
        raise


def slugify(text):
    """
    Create a filename-safe slug from text.

    Normalizes unicode, strips non-alphanumeric chars, lowercases.
    Example: "JOSH CULLEN" -> "josh_cullen"
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def load_csv(filepath, delimiter=None):
    """
    Load a CSV file and return list of dicts.

    Auto-detects delimiter if not provided (checks first line for semicolons).

    Args:
        filepath: Path to CSV file.
        delimiter: CSV delimiter. Auto-detected if None.

    Returns:
        List of OrderedDict rows.
    """
    if not os.path.exists(filepath):
        print(f"[WARN] CSV file not found: {filepath}")
        return []

    if delimiter is None:
        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline()
            delimiter = ";" if ";" in first_line else ","

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader)


def append_csv(filepath, rows, fieldnames, delimiter=";"):
    """
    Append rows to a CSV file. Creates the file with headers if it doesn't exist.

    Args:
        filepath: Path to CSV file.
        rows: List of dicts to append.
        fieldnames: List of column names.
        delimiter: CSV delimiter.
    """
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def git_push(files, commit_msg="Auto-push data update", base_dir=None):
    """
    Stage, commit, and push files to git.

    Args:
        files: Single filename or list of filenames to stage.
        commit_msg: Commit message.
        base_dir: Directory to run git commands in. Defaults to script dir.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    if isinstance(files, str):
        files = [files]

    print(f"\n[GIT] Pushing data update to repository...")
    try:
        os.chdir(base_dir)

        for f in files:
            subprocess.run(
                ["git", "add", os.path.basename(f)],
                check=True, capture_output=True
            )

        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            print(f"[GIT] Committed: {commit_msg}")
            push_result = subprocess.run(
                ["git", "push"], capture_output=True, text=True
            )
            if push_result.returncode == 0:
                print("[GIT] Successfully pushed to remote.")
            else:
                print(f"[GIT] Push failed: {push_result.stderr.strip()}")
        elif "nothing to commit" in (result.stdout + result.stderr):
            print("[GIT] No changes to commit.")
        else:
            print(f"[GIT] Commit failed: {result.stderr.strip()}")

    except subprocess.CalledProcessError as e:
        print(f"[GIT] Git operation failed: {e}")
    except Exception as e:
        print(f"[GIT] Error during git push: {e}")


def format_number(n):
    """Format large numbers for compact display (e.g. 1.25M)."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_with_commas(n):
    """Format number with comma separators."""
    return f"{n:,}"


def scroll_and_wait(driver, scroll_amount=500, wait_seconds=2):
    """Scroll page down and wait for content to load."""
    import time
    driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
    time.sleep(wait_seconds)
