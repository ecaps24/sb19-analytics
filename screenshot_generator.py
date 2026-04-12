"""
Screenshot Generator - Standalone functions for capturing social media card screenshots.

Extracted from SocialMediaAgent class. Each function generates HTML, renders it
in a headless Edge browser, and saves a screenshot.

All functions share a common pattern via _render_html_to_screenshot().
"""

import base64
import csv
import os
import time
from datetime import datetime

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService

from config import (
    SCRIPT_DIR,
    ALBUM_IMAGE_DIR,
    ALBUM_IMAGE_PATH,
    TOP10_IMAGE_PATH,
    SOLO_TOP10_IMAGE_PATH,
    LISTENERS_IMAGE_PATH,
    OPM_TOP_IMAGE_PATH,
    PPOP_TOP_IMAGE_PATH,
    OPM_TOP_TRACKS_IMAGE_PATH,
    OPM_TOP_STREAMS_IMAGE_PATH,
    YT_EMOJI_IMAGE_PATH,
    YT_CHANNEL_IMAGE_PATH,
    SPOTIFY_VISA_IMAGE_PATH,
    YT_STREAMS_CSV,
    MEMBER_PHOTOS_DIR,
    MEMBER_PHOTO_FILES,
    MEMBER_BAR_COLORS,
    WAS_ALBUM_IMAGE_PATH,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _render_html_to_screenshot(html, temp_filename, output_path,
                               window_width=1200, window_height=3000,
                               max_img_width=3200, max_attempts=1,
                               label="screenshot"):
    """Render HTML to a screenshot via headless Edge browser.

    Args:
        html: Full HTML string to render.
        temp_filename: Name for the temporary HTML file (e.g. "_top10_card.html").
        output_path: Path where the screenshot PNG will be saved.
        window_width: Browser window width.
        window_height: Browser window height.
        max_img_width: Maximum image width; downscale if exceeded.
        max_attempts: Number of retry attempts.
        label: Label for log messages.

    Returns:
        True on success, False on failure.
    """
    os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)
    temp_html = os.path.join(SCRIPT_DIR, temp_filename)
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html)

    try:
        for attempt in range(1, max_attempts + 1):
            try:
                options = EdgeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--force-device-scale-factor=2")
                options.add_argument("--disable-notifications")
                options.add_argument("--disable-blink-features=AutomationControlled")
                if max_attempts > 1:
                    options.add_argument("--disable-gpu")
                    options.add_argument("--no-sandbox")
                    options.add_argument("--disable-dev-shm-usage")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)

                service = EdgeService()
                driver = None
                try:
                    driver = webdriver.Edge(service=service, options=options)
                    driver.set_window_size(window_width, window_height)

                    driver.get(f"file:///{temp_html.replace(os.sep, '/')}")
                    time.sleep(4 if max_attempts > 1 else 3)

                    card = driver.find_element(By.ID, "card")
                    card.screenshot(output_path)

                    img = Image.open(output_path)
                    if img.width > max_img_width:
                        ratio = max_img_width / img.width
                        img = img.resize((max_img_width, int(img.height * ratio)), Image.LANCZOS)
                        img.save(output_path)
                    print(f"[INFO] Screenshot dimensions: {img.width}x{img.height}")
                    print(f"[SUCCESS] {label} saved: {output_path}")
                    return True
                except Exception as e:
                    print(f"[ERR] {label} attempt {attempt}/{max_attempts} failed: {e}")
                    if attempt < max_attempts:
                        print("[INFO] Retrying in 3 seconds...")
                        time.sleep(3)
                finally:
                    if driver:
                        try:
                            driver.quit()
                        except Exception:
                            pass
            except Exception as e:
                print(f"[ERR] {label} setup attempt {attempt}/{max_attempts} failed: {e}")
                if attempt < max_attempts:
                    time.sleep(3)

        if max_attempts > 1:
            print(f"[ERR] {label} failed after all attempts")
        return False
    finally:
        try:
            os.remove(temp_html)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Shared HTML helpers (used by multiple screenshot functions)
# ---------------------------------------------------------------------------

def _rank_change_html_with_streak(rc, streak=1):
    if rc is not None and rc > 0:
        return f'<span class="rank-up">&#9650;{rc}</span>'
    elif rc is not None and rc < 0:
        return f'<span class="rank-down">&#9660;{abs(rc)}</span>'
    elif rc == 0 and streak > 1:
        return f'<span class="rank-same">{streak}d</span>'
    else:
        return '<span class="rank-same">\u2015</span>'


def _rank_change_html_simple(rc):
    if rc is not None and rc > 0:
        return f'<span class="rank-up">&#9650;{rc}</span>'
    elif rc is not None and rc < 0:
        return f'<span class="rank-down">&#9660;{abs(rc)}</span>'
    else:
        return '<span class="rank-same">\u2015</span>'


def _change_html(change):
    if change > 0:
        return f'<span class="change-up">+{change:,}</span>'
    elif change < 0:
        return f'<span class="change-down">{change:,}</span>'
    return '<span class="change-same">\u2015</span>'


def _delta_html(delta):
    """Format delta as a small arrow indicator for screenshots."""
    if delta is None:
        return ""
    if delta > 0:
        return f'<span class="delta-up">\u25b2+{delta:,}</span>'
    elif delta < 0:
        return f'<span class="delta-down">\u25bc{delta:,}</span>'
    return ""


# ---------------------------------------------------------------------------
# 1. capture_top10_screenshot
# ---------------------------------------------------------------------------

def capture_top10_screenshot(top3_data=None, table_data=None,
                             total_added=0, date_str=""):
    """Capture a social-media-friendly SB19 top tracks card.

    Section A: Top 3 as equal-width podium bars.
    Section B: Remaining tracks as compact table.
    """
    print("[INFO] Capturing top tracks screenshot...")
    if not top3_data:
        print("[ERR] No track data for top tracks card")
        return False

    podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]

    top3_rows = ""
    for i, t in enumerate(top3_data):
        color = podium_colors[i]
        streams_str = f"{t['streams']:,}"
        ch_html = _change_html(t["change"])
        rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))

        top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['song']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

    table_rows = ""
    if table_data:
        for t in table_data:
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))
            table_rows += f"""
                <tr>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

    total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 380px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Top Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_top10_card.html", TOP10_IMAGE_PATH,
        label="Top tracks screenshot",
    )


# ---------------------------------------------------------------------------
# 2. capture_solo_top10_screenshot
# ---------------------------------------------------------------------------

def capture_solo_top10_screenshot(top3_data=None, table_data=None,
                                  total_added=0, date_str=""):
    """Capture a social-media-friendly solo top tracks card."""
    print("[INFO] Capturing solo top tracks screenshot...")
    if not top3_data:
        print("[ERR] No track data for solo top tracks card")
        return False

    podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]

    top3_rows = ""
    for i, t in enumerate(top3_data):
        color = podium_colors[i]
        artist_color = MEMBER_BAR_COLORS.get(t["artist"], "#3b82f6")
        streams_str = f"{t['streams']:,}"
        ch_html = _change_html(t["change"])
        rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))
        badge_html = (
            f'<span class="artist-badge" style="background: {artist_color};">'
            f'{t["artist"]}</span>'
        )
        top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['song']}</span>
                        {badge_html}
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {artist_color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

    table_rows = ""
    if table_data:
        for t in table_data:
            artist_color = MEMBER_BAR_COLORS.get(t["artist"], "#3b82f6")
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))
            table_rows += f"""
                <tr>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-artist" style="color: {artist_color};">{t['artist']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

    total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.artist-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    flex-shrink: 0;
    opacity: 0.9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
}}
td.col-artist {{
    font-weight: 600;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Solo Top Tracks by Daily Streams</div>
        <div class="card-subtitle">As of {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th>Artist</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_solo_top10_card.html", SOLO_TOP10_IMAGE_PATH,
        label="Solo top tracks screenshot",
    )


# ---------------------------------------------------------------------------
# 3. capture_opm_top_screenshot
# ---------------------------------------------------------------------------

def capture_opm_top_screenshot(table_data=None, sb19_data=None,
                               total_artists=0, date_str=""):
    """Capture OPM leaderboard ranked by daily streams (matching P-Pop style)."""
    print("[INFO] Capturing OPM leaderboard screenshot...")
    if not table_data:
        print("[ERR] No data for OPM leaderboard")
        return False

    def _fmt_num(n):
        absn = abs(n)
        if absn >= 1e9:
            return f"{absn/1e9:.1f}B"
        if absn >= 1e6:
            return f"{absn/1e6:.1f}M"
        if absn >= 1e3:
            return f"{absn/1e3:.1f}K"
        return f"{absn:,}"

    def _opm_change_html(change):
        if change > 0:
            absn = abs(change)
            s = _fmt_num(change) if absn >= 10000 else f"{change:,}"
            return f'<span class="change-up">+{s}</span>'
        elif change < 0:
            absn = abs(change)
            s = _fmt_num(change) if absn >= 10000 else f"{absn:,}"
            return f'<span class="change-down">-{s}</span>'
        return '<span class="change-same">\u2015</span>'

    def _daily_html(daily, daily_change):
        if not daily:
            return '<span class="change-same">\u2015</span>'
        prefix = "+" if daily > 0 else ""
        cls = "change-up" if daily > 0 else "change-down" if daily < 0 else "change-same"
        html = f'<span class="{cls}">{prefix}{daily:,}</span>'
        if daily_change:
            dc_prefix = "+" if daily_change > 0 else ""
            dc_cls = "change-up" if daily_change > 0 else "change-down"
            html += f' <span class="{dc_cls}" style="font-size:11px">({dc_prefix}{_fmt_num(daily_change)})</span>'
        return html

    medal_colors = [
        ("#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.35)"),
        ("#94a3b8", "rgba(148, 163, 184, 0.10)", "rgba(148, 163, 184, 0.30)"),
        ("#cd7f32", "rgba(205, 127, 50, 0.10)", "rgba(205, 127, 50, 0.30)"),
    ]
    top3 = table_data[:3]
    remaining = table_data[3:]

    # Podium order: 2nd, 1st, 3rd (center elevated)
    podium_order = [1, 0, 2] if len(top3) >= 3 else list(range(len(top3)))

    def _build_medal_card(t, idx):
        color, bg, border = medal_colors[idx]
        listeners_str = f"{t['listeners']:,}"
        ch_html = _opm_change_html(t["change"])
        total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "\u2015"
        daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
        followers_str = f"{t['followers']:,}" if t.get("followers") else "\u2015"
        extra_cls = " medal-gold" if idx == 0 else " medal-silver" if idx == 1 else " medal-bronze"
        return f"""
            <div class="medal-card{extra_cls}" style="background: {bg}; border-color: {border};">
                <div class="medal-circle" style="background: {color}; box-shadow: 0 0 20px {color}40;">
                    <span class="medal-rank">{t['rank']}</span>
                </div>
                <div class="medal-name">{t['artist']}</div>
                <div class="medal-row">
                    <span class="medal-label">Daily Streams</span>
                    <span class="medal-daily">{daily_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Monthly Listeners</span>
                    <span class="medal-value">{listeners_str}</span>
                    <span class="medal-change">{ch_html}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Total Streams</span>
                    <span class="medal-value">{total_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Followers</span>
                    <span class="medal-value-sm">{followers_str}</span>
                </div>
            </div>"""

    top3_html = ""
    for pi in podium_order:
        top3_html += _build_medal_card(top3[pi], pi)

    table_rows = ""
    for t in remaining:
        listeners_str = f"{t['listeners']:,}"
        ch_html = _opm_change_html(t["change"])
        followers_str = f"{t['followers']:,}" if t.get("followers") else "\u2015"
        total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "\u2015"
        daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
        is_sb19 = t["artist"].upper() == "SB19"
        row_class = ' class="sb19-row"' if is_sb19 else ""
        table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{t.get('genre', '')}</td>
                    <td class="col-listeners">{listeners_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-followers">{followers_str}</td>
                    <td class="col-total-streams">{total_str}</td>
                    <td class="col-daily">{daily_str}</td>
                </tr>"""

    sb19_section = ""
    if sb19_data:
        sb19_listeners_str = f"{sb19_data['listeners']:,}"
        sb19_ch_html = _opm_change_html(sb19_data["change"])
        sb19_followers_str = f"{sb19_data['followers']:,}" if sb19_data.get("followers") else "\u2015"
        sb19_total_str = f"{sb19_data['total_streams']:,}" if sb19_data.get("total_streams") else "\u2015"
        sb19_daily_str = _daily_html(sb19_data.get("daily_streams", 0), sb19_data.get("daily_change", 0))
        sb19_section = f"""
    <div class="sb19-extra-section">
        <div class="sb19-divider"></div>
        <div class="sb19-extra-label">SB19</div>
        <table class="sb19-extra-table">
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-listeners">Monthly Listeners</th>
                    <th class="col-change">Change</th>
                    <th class="col-followers">Followers</th>
                    <th class="col-total-streams">Total Streams</th>
                    <th class="col-daily">Daily Streams</th>
                </tr>
            </thead>
            <tbody>
                <tr class="sb19-row">
                    <td class="col-rank">{sb19_data['rank']}</td>
                    <td class="col-artist">SB19</td>
                    <td class="col-genre">P-Pop</td>
                    <td class="col-listeners">{sb19_listeners_str}</td>
                    <td class="col-change">{sb19_ch_html}</td>
                    <td class="col-followers">{sb19_followers_str}</td>
                    <td class="col-total-streams">{sb19_total_str}</td>
                    <td class="col-daily">{sb19_daily_str}</td>
                </tr>
            </tbody>
        </table>
    </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1200px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 40px 44px 36px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 28px;
    padding-bottom: 22px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 28px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 6px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 16px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 14px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 32px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 13px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.stat-detail {{
    font-size: 12px;
    color: #475569;
    margin-top: 1px;
}}
.medal-section {{
    display: flex;
    gap: 20px;
    margin-bottom: 28px;
    align-items: flex-end;
}}
.medal-card {{
    flex: 1;
    border: 1px solid;
    border-radius: 16px;
    padding: 20px 18px 16px;
    text-align: center;
    position: relative;
}}
.medal-gold {{
    padding-top: 28px;
    padding-bottom: 20px;
}}
.medal-silver, .medal-bronze {{
    margin-top: 40px;
}}
.medal-gold .medal-circle {{
    width: 60px;
    height: 60px;
}}
.medal-gold .medal-rank {{
    font-size: 28px;
}}
.medal-gold .medal-name {{
    font-size: 22px;
}}
.medal-circle {{
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
}}
.medal-rank {{
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
}}
.medal-name {{
    font-size: 20px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.medal-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    gap: 6px;
}}
.medal-label {{
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
}}
.medal-value {{
    font-size: 15px;
    font-weight: 700;
    color: #e2e8f0;
}}
.medal-value-sm {{
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
}}
.medal-change {{
    font-size: 12px;
    font-weight: 500;
}}
.medal-daily {{
    font-size: 13px;
    font-weight: 600;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 0 0 20px;
}}
.section-label {{
    font-size: 14px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 8px 8px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank {{ text-align: right; width: 36px; }}
th.col-listeners, th.col-change, th.col-followers, th.col-total-streams, th.col-daily {{
    text-align: right;
}}
td {{
    font-size: 13px;
    padding: 6px 8px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 36px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
}}
td.col-genre {{
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
}}
td.col-listeners {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
td.col-followers {{
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-total-streams {{
    font-weight: 600;
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-daily {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-listeners {{
    color: #22d3ee;
}}
.sb19-extra-section {{
    margin-top: 8px;
}}
.sb19-divider {{
    border-top: 2px dashed rgba(6, 182, 212, 0.3);
    margin: 16px 0 12px;
}}
.sb19-extra-label {{
    font-size: 16px;
    font-weight: 600;
    color: #22d3ee;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
}}
.sb19-extra-table {{
    width: 100%;
    border-collapse: collapse;
}}
.sb19-extra-table td {{
    font-size: 13px;
    padding: 6px 8px;
    border-bottom: none;
}}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 22px;
    padding-top: 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 13px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
.footer-note {{
    font-size: 12px;
    color: #64748b;
    font-style: italic;
    margin-bottom: 6px;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Leaderboard</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">20</div>
                <div class="stat-label">Top Artists</div>
                <div class="stat-detail">of {total_artists} artists tracked</div>
            </div>
        </div>
    </div>
    <div class="medal-section">{top3_html}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Artists</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-listeners">Monthly Listeners</th>
                    <th class="col-change">Change</th>
                    <th class="col-followers">Followers</th>
                    <th class="col-total-streams">Total Streams</th>
                    <th class="col-daily">Daily Streams</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    {sb19_section}
    <div class="footer">
        <div class="footer-note">*Ranked by daily streams</div>
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_opm_top_card.html", OPM_TOP_IMAGE_PATH,
        label="OPM top screenshot",
    )


# ---------------------------------------------------------------------------
# 4. capture_opm_top_tracks_screenshot
# ---------------------------------------------------------------------------

def capture_opm_top_tracks_screenshot(top3_data=None, table_data=None,
                                      total_added=0, total_tracks=0, date_str=""):
    """Capture a social-media-friendly OPM top tracks by daily streams card."""
    print("[INFO] Capturing OPM top tracks screenshot...")
    if not top3_data:
        print("[ERR] No track data for OPM top tracks card")
        return False

    podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]
    sb19_color = "#06b6d4"

    top3_rows = ""
    for i, t in enumerate(top3_data):
        is_sb19 = t.get("is_sb19", False)
        color = sb19_color if is_sb19 else podium_colors[i]
        streams_str = f"{t['streams']:,}"
        ch_html = _change_html(t["change"])
        rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))
        podium_class = f"podium-row podium-{i+1}"
        if is_sb19:
            podium_class += " podium-sb19"
        name_style = ' style="color: #22d3ee;"' if is_sb19 else ""
        artist_style = ' style="color: #67e8f9;"' if is_sb19 else ""
        top3_rows += f"""
            <div class="{podium_class}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name"{name_style}>{t['song']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-artist"{artist_style}>{t['artist']}</div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

    table_rows = ""
    if table_data:
        for t in table_data:
            is_sb19 = t.get("is_sb19", False)
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html_with_streak(t.get("rank_change"), t.get("streak", 1))
            row_class = ' class="sb19-row"' if is_sb19 else ""
            table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

    total_str = f"+{total_added:,}" if total_added > 0 else f"{total_added:,}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-value-blue {{
    font-size: 36px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-sb19 {{
    background: rgba(6, 182, 212, 0.10) !important;
    border: 1px solid rgba(6, 182, 212, 0.25) !important;
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-sb19 .podium-rank {{ color: #06b6d4 !important; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-artist {{
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-track {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 260px;
}}
td.col-artist {{
    font-size: 13px;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 160px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-track {{
    color: #22d3ee;
}}
tr.sb19-row td.col-artist {{
    color: #67e8f9;
}}
tr.sb19-row td.col-streams {{
    color: #22d3ee;
}}
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Top Tracks by Daily Streams</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-value-blue">{total_tracks:,}</div>
                <div class="stat-label">Tracks Tracked</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th>Artist</th>
                    <th class="col-change">Change</th>
                    <th class="col-streams">Streams</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_opm_top_tracks_card.html", OPM_TOP_TRACKS_IMAGE_PATH,
        max_attempts=3,
        label="OPM top tracks screenshot",
    )


# ---------------------------------------------------------------------------
# 5. capture_opm_top_streams_screenshot
# ---------------------------------------------------------------------------

def capture_opm_top_streams_screenshot(top3_data=None, table_data=None,
                                       sb19_data=None, grand_total=0,
                                       total_artists=0, date_str=""):
    """Capture OPM top artists by daily streams card."""
    print("[INFO] Capturing OPM top streams screenshot...")
    if not top3_data:
        print("[ERR] No data for OPM top streams card")
        return False

    podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]
    sb19_color = "#06b6d4"

    top3_rows = ""
    for i, t in enumerate(top3_data):
        is_sb19 = t.get("is_sb19", False)
        color = sb19_color if is_sb19 else podium_colors[i]
        streams_str = f"{t['total_streams']:,}"
        ch_html = _change_html(t["change"])
        rc_html = _rank_change_html_simple(t.get("rank_change"))
        genre_label = t.get("genre", "")
        track_badge = f'<span class="track-badge">{t["track_count"]} tracks</span>'
        podium_class = f"podium-row podium-{i+1}"
        if is_sb19:
            podium_class += " podium-sb19"
        name_style = ' style="color: #22d3ee;"' if is_sb19 else ""
        top3_rows += f"""
            <div class="{podium_class}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name"{name_style}>{t['artist']}</span>
                        <span class="podium-rc">{rc_html}</span>
                    </div>
                    <div class="podium-meta">
                        <span class="podium-genre">{genre_label}</span>
                        {track_badge}
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: 100%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-streams">{streams_str}</span>
                        <span class="podium-change">{ch_html}</span>
                    </div>
                </div>
            </div>"""

    table_rows = ""
    if table_data:
        for t in table_data:
            is_sb19 = t.get("is_sb19", False)
            streams_str = f"{t['total_streams']:,}"
            ch_html = _change_html(t["change"])
            rc_html = _rank_change_html_simple(t.get("rank_change"))
            genre_label = t.get("genre", "")
            row_class = ' class="sb19-row"' if is_sb19 else ""
            table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{genre_label}</td>
                    <td class="col-streams">{streams_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-tracks">{t['track_count']}</td>
                    <td class="col-rc">{rc_html}</td>
                </tr>"""

    sb19_section = ""
    if sb19_data:
        sb19_streams_str = f"{sb19_data['total_streams']:,}"
        sb19_ch_html = _change_html(sb19_data["change"])
        sb19_rc_html = _rank_change_html_simple(sb19_data.get("rank_change"))
        sb19_section = f"""
    <div class="sb19-extra-section">
        <div class="sb19-divider"></div>
        <div class="sb19-extra-label">SB19</div>
        <table class="sb19-extra-table">
            <tr class="sb19-row">
                <td class="col-rank">{sb19_data['rank']}</td>
                <td class="col-artist">SB19</td>
                <td class="col-genre">P-Pop</td>
                <td class="col-streams">{sb19_streams_str}</td>
                <td class="col-change">{sb19_ch_html}</td>
                <td class="col-tracks">{sb19_data['track_count']}</td>
                <td class="col-rc">{sb19_rc_html}</td>
            </tr>
        </table>
    </div>"""

    grand_total_str = f"{grand_total:,}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(16, 185, 129, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 30px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}}
.stat-value-blue {{
    font-size: 36px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.podium-section {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 8px;
}}
.podium-row {{
    display: flex;
    align-items: center;
    gap: 18px;
    border-radius: 14px;
    padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-sb19 {{
    background: rgba(6, 182, 212, 0.10) !important;
    border: 1px solid rgba(6, 182, 212, 0.25) !important;
}}
.podium-rank {{
    font-size: 32px;
    font-weight: 800;
    width: 48px;
    text-align: center;
    flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-sb19 .podium-rank {{ color: #06b6d4 !important; }}
.podium-content {{
    flex: 1;
    min-width: 0;
}}
.podium-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
}}
.podium-name {{
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;
}}
.podium-rc {{
    font-size: 14px;
    font-weight: 600;
}}
.podium-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.podium-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.track-badge {{
    font-size: 11px;
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.12);
    padding: 2px 8px;
    border-radius: 10px;
}}
.podium-bar-container {{
    height: 38px;
    background: rgba(51, 65, 85, 0.5);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%;
    border-radius: 8px;
}}
.podium-stats {{
    display: flex;
    align-items: center;
    gap: 14px;
}}
.podium-streams {{
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}}
.podium-change {{
    font-size: 14px;
    font-weight: 500;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change, th.col-tracks, th.col-rc {{
    text-align: right;
}}
td {{
    font-size: 14px;
    padding: 7px 10px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 50px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 260px;
}}
td.col-genre {{
    font-size: 12px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
td.col-streams {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 13px;
    white-space: nowrap;
}}
td.col-tracks {{
    text-align: right;
    font-size: 13px;
    color: #94a3b8;
    width: 60px;
}}
td.col-rc {{
    text-align: right;
    font-size: 13px;
    width: 60px;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-streams {{
    color: #22d3ee;
}}
.sb19-extra-section {{
    margin-top: 8px;
}}
.sb19-divider {{
    border-top: 2px dashed rgba(6, 182, 212, 0.3);
    margin: 16px 0 12px;
}}
.sb19-extra-label {{
    font-size: 16px;
    font-weight: 600;
    color: #22d3ee;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 10px;
}}
.sb19-extra-table {{
    width: 100%;
    border-collapse: collapse;
}}
.sb19-extra-table td {{
    font-size: 14px;
    padding: 7px 10px;
    border-bottom: none;
}}
.rank-up {{ color: #34d399; }}
.rank-down {{ color: #f87171; }}
.rank-same {{ color: #9ca3af; }}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #10b981;
    font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">OPM Top Artists by Daily Streams</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{grand_total_str}</div>
                <div class="stat-label">Total Daily Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-value-blue">{total_artists}</div>
                <div class="stat-label">Artists Tracked</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Artists</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-streams">Daily Streams</th>
                    <th class="col-change">vs Prev Day</th>
                    <th class="col-tracks">Tracks</th>
                    <th class="col-rc">Rank</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    {sb19_section}
    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_opm_top_streams_card.html", OPM_TOP_STREAMS_IMAGE_PATH,
        label="OPM top streams screenshot",
    )


# ---------------------------------------------------------------------------
# 6. capture_ppop_top_screenshot
# ---------------------------------------------------------------------------

def capture_ppop_top_screenshot(table_data=None,
                                ppop_count=0, total_artists=0, date_str=""):
    """Capture P-Pop leaderboard as a flat table sorted by daily streams."""
    print("[INFO] Capturing P-Pop leaderboard screenshot...")
    if not table_data:
        print("[ERR] No data for P-Pop leaderboard")
        return False

    def _fmt_num(n):
        absn = abs(n)
        if absn >= 1e9:
            return f"{absn/1e9:.1f}B"
        if absn >= 1e6:
            return f"{absn/1e6:.1f}M"
        if absn >= 1e3:
            return f"{absn/1e3:.1f}K"
        return f"{absn:,}"

    def _ppop_change_html(change):
        if change > 0:
            absn = abs(change)
            s = _fmt_num(change) if absn >= 10000 else f"{change:,}"
            return f'<span class="change-up">+{s}</span>'
        elif change < 0:
            absn = abs(change)
            s = _fmt_num(change) if absn >= 10000 else f"{absn:,}"
            return f'<span class="change-down">-{s}</span>'
        return '<span class="change-same">\u2015</span>'

    def _daily_html(daily, daily_change):
        if not daily:
            return '<span class="change-same">\u2015</span>'
        prefix = "+" if daily > 0 else ""
        cls = "change-up" if daily > 0 else "change-down" if daily < 0 else "change-same"
        html = f'<span class="{cls}">{prefix}{daily:,}</span>'
        if daily_change:
            dc_prefix = "+" if daily_change > 0 else ""
            dc_cls = "change-up" if daily_change > 0 else "change-down"
            html += f' <span class="{dc_cls}" style="font-size:11px">({dc_prefix}{_fmt_num(daily_change)})</span>'
        return html

    medal_colors = [
        ("#fbbf24", "rgba(251, 191, 36, 0.12)", "rgba(251, 191, 36, 0.35)"),
        ("#94a3b8", "rgba(148, 163, 184, 0.10)", "rgba(148, 163, 184, 0.30)"),
        ("#cd7f32", "rgba(205, 127, 50, 0.10)", "rgba(205, 127, 50, 0.30)"),
    ]
    top3_html = ""
    top3_data = table_data[:3]
    remaining_data = table_data[3:]

    for i, t in enumerate(top3_data):
        color, bg, border = medal_colors[i]
        listeners_str = f"{t['listeners']:,}"
        ch_html = _ppop_change_html(t["change"])
        total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "\u2015"
        daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
        followers_str = f"{t['followers']:,}" if t.get("followers") else "\u2015"
        top3_html += f"""
            <div class="medal-card" style="background: {bg}; border-color: {border};">
                <div class="medal-circle" style="background: {color}; box-shadow: 0 0 20px {color}40;">
                    <span class="medal-rank">{t['rank']}</span>
                </div>
                <div class="medal-name">{t['artist']}</div>
                <div class="medal-row">
                    <span class="medal-label">Daily Streams</span>
                    <span class="medal-daily">{daily_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Monthly Listeners</span>
                    <span class="medal-value">{listeners_str}</span>
                    <span class="medal-change">{ch_html}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Total Streams</span>
                    <span class="medal-value">{total_str}</span>
                </div>
                <div class="medal-row">
                    <span class="medal-label">Followers</span>
                    <span class="medal-value-sm">{followers_str}</span>
                </div>
            </div>"""

    table_rows = ""
    for t in remaining_data:
        listeners_str = f"{t['listeners']:,}"
        ch_html = _ppop_change_html(t["change"])
        followers_str = f"{t['followers']:,}" if t.get("followers") else "\u2015"
        total_str = f"{t['total_streams']:,}" if t.get("total_streams") else "\u2015"
        daily_str = _daily_html(t.get("daily_streams", 0), t.get("daily_change", 0))
        is_sb19 = t["artist"].lower() == "sb19"
        row_class = ' class="sb19-row"' if is_sb19 else ""
        table_rows += f"""
                <tr{row_class}>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-artist">{t['artist']}</td>
                    <td class="col-genre">{t.get('genre', 'P-Pop')}</td>
                    <td class="col-listeners">{listeners_str}</td>
                    <td class="col-change">{ch_html}</td>
                    <td class="col-followers">{followers_str}</td>
                    <td class="col-total-streams">{total_str}</td>
                    <td class="col-daily">{daily_str}</td>
                </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1200px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(6, 182, 212, 0.2);
    border-radius: 20px;
    padding: 40px 44px 36px;
    box-shadow: 0 0 60px rgba(6, 182, 212, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 28px;
    padding-bottom: 22px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.card-title {{
    font-size: 28px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 6px;
    letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 16px;
    color: #94a3b8;
    font-weight: 400;
}}
.stats-row {{
    display: flex;
    justify-content: center;
    gap: 48px;
    margin-top: 14px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 32px;
    font-weight: 800;
    color: #06b6d4;
    letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 13px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}}
.stat-detail {{
    font-size: 12px;
    color: #475569;
    margin-top: 1px;
}}
.medal-section {{
    display: flex;
    gap: 20px;
    margin-bottom: 28px;
}}
.medal-card {{
    flex: 1;
    border: 1px solid;
    border-radius: 16px;
    padding: 20px 18px 16px;
    text-align: center;
    position: relative;
}}
.medal-circle {{
    width: 52px;
    height: 52px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
}}
.medal-rank {{
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
}}
.medal-name {{
    font-size: 20px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.medal-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    gap: 6px;
}}
.medal-label {{
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
}}
.medal-value {{
    font-size: 15px;
    font-weight: 700;
    color: #e2e8f0;
}}
.medal-value-sm {{
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
}}
.medal-change {{
    font-size: 12px;
    font-weight: 500;
}}
.medal-daily {{
    font-size: 13px;
    font-weight: 600;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 0 0 20px;
}}
.section-label {{
    font-size: 14px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 12px;
}}
.table-section {{
    width: 100%;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th {{
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 8px 8px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank {{ text-align: right; width: 36px; }}
th.col-listeners, th.col-change, th.col-followers, th.col-total-streams, th.col-daily {{
    text-align: right;
}}
td {{
    font-size: 13px;
    padding: 6px 8px;
    color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700;
    color: #64748b;
    text-align: right;
    width: 36px;
}}
td.col-artist {{
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
}}
td.col-genre {{
    font-size: 11px;
    color: #64748b;
    white-space: nowrap;
}}
td.col-listeners {{
    font-weight: 600;
    color: #e2e8f0;
    text-align: right;
    white-space: nowrap;
}}
td.col-change {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
td.col-followers {{
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-total-streams {{
    font-weight: 600;
    color: #94a3b8;
    text-align: right;
    white-space: nowrap;
}}
td.col-daily {{
    text-align: right;
    font-size: 12px;
    white-space: nowrap;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
tr.sb19-row {{
    background: rgba(6, 182, 212, 0.10);
}}
tr.sb19-row td.col-artist {{
    color: #22d3ee;
}}
tr.sb19-row td.col-listeners {{
    color: #22d3ee;
}}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.footer {{
    text-align: center;
    margin-top: 22px;
    padding-top: 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 13px;
    color: #475569;
    letter-spacing: 0.5px;
}}
.footer-site {{
    color: #06b6d4;
    font-weight: 600;
}}
.footer-note {{
    font-size: 12px;
    color: #64748b;
    font-style: italic;
    margin-bottom: 6px;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">P-Pop Leaderboard</div>
        <div class="card-subtitle">Spotify | {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{ppop_count}</div>
                <div class="stat-label">P-Pop Groups</div>
                <div class="stat-detail">of {total_artists} artists tracked</div>
            </div>
        </div>
    </div>
    <div class="medal-section">{top3_html}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Groups</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Artist</th>
                    <th>Genre</th>
                    <th class="col-listeners">Monthly Listeners</th>
                    <th class="col-change">Change</th>
                    <th class="col-followers">Followers</th>
                    <th class="col-total-streams">Total Streams</th>
                    <th class="col-daily">Daily Streams</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-note">*Ranked by daily streams</div>
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_ppop_top_card.html", PPOP_TOP_IMAGE_PATH,
        label="P-Pop top screenshot",
    )


# ---------------------------------------------------------------------------
# 7. capture_youtube_visa_screenshot
# ---------------------------------------------------------------------------

def compute_hourly_deltas():
    """Read yt_visa_streams.csv and compute hourly view deltas for the chart."""
    from datetime import datetime as _dt
    if not os.path.exists(YT_STREAMS_CSV):
        return [], []
    rows = []
    with open(YT_STREAMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if len(rows) < 2:
        return [], []

    hourly = {}
    for row in rows:
        ts = row.get("timestamp", "").strip()
        try:
            dt = _dt.strptime(ts, "%Y-%m-%d %H:%M:%S")
            slot = (dt.hour // 4) * 4
            hour_key = f"{dt.strftime('%Y-%m-%d')} {slot:02d}"
        except ValueError:
            continue
        v = int(row.get("views", 0))
        if hour_key not in hourly or v > hourly[hour_key]:
            hourly[hour_key] = v

    sorted_hours = sorted(hourly.keys())
    labels = []
    deltas = []
    def _fmt_h(h):
        h12 = h % 12 or 12
        ap = 'p' if h >= 12 else 'a'
        return f"{h12}{ap}"
    for i in range(1, len(sorted_hours)):
        delta = hourly[sorted_hours[i]] - hourly[sorted_hours[i - 1]]
        if delta < 0:
            delta = 0
        prev_hour = int(sorted_hours[i - 1][-2:])
        curr_hour = int(sorted_hours[i][-2:])
        labels.append(f"{_fmt_h(prev_hour)}-{_fmt_h(curr_hour)}")
        deltas.append(delta)

    if len(labels) > 6:
        labels = labels[-6:]
        deltas = deltas[-6:]

    return labels, deltas


def capture_youtube_visa_screenshot(views, likes, comments,
                                    view_change, like_change,
                                    comment_change, now_str):
    """Capture a social-media-friendly YouTube EMOJI stats card."""
    print("[INFO] Capturing YouTube EMOJI screenshot...")
    os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

    emoji_img_path = os.path.join(SCRIPT_DIR, "photos", "emoji.png")
    bg_data_uri = ""
    if os.path.exists(emoji_img_path):
        with open(emoji_img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            bg_data_uri = f"data:image/png;base64,{b64}"

    def stat_with_change(value, change):
        val_str = f"{value:,}"
        if change > 0:
            return val_str, f"+{change:,}"
        elif change < 0:
            return val_str, f"{change:,}"
        return val_str, ""

    def format_k(v):
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v / 1_000:.1f}K"
        return str(v)

    v_str, v_chg = stat_with_change(views, view_change)
    l_str, l_chg = stat_with_change(likes, like_change)
    c_str, c_chg = stat_with_change(comments, comment_change)

    chg_color_v = "#34d399" if view_change >= 0 else "#f87171"
    chg_color_l = "#34d399" if like_change >= 0 else "#f87171"
    chg_color_c = "#34d399" if comment_change >= 0 else "#f87171"

    v_chg_html = f'<div class="stat-change" style="color:{chg_color_v}">{v_chg}</div>' if v_chg else ""
    l_chg_html = f'<div class="stat-change" style="color:{chg_color_l}">{l_chg}</div>' if l_chg else ""
    c_chg_html = f'<div class="stat-change" style="color:{chg_color_c}">{c_chg}</div>' if c_chg else ""

    chart_labels, chart_deltas = compute_hourly_deltas()
    projection = 0
    if chart_deltas:
        recent = chart_deltas[-3:] if len(chart_deltas) >= 3 else chart_deltas
        projection = int(sum(recent) / len(recent))

    all_values = chart_deltas + ([projection] if projection > 0 else [])
    max_delta = max(all_values) if all_values else 1
    chart_bars_html = ""
    if chart_deltas:
        bars = []
        for i, (label, delta) in enumerate(zip(chart_labels, chart_deltas)):
            pct = max(int((delta / max_delta) * 100), 4) if max_delta > 0 else 4
            val_label = format_k(delta) if delta > 0 else ""
            bars.append(
                f'<div class="bar-col">'
                f'<div class="bar-val">{val_label}</div>'
                f'<div class="bar" style="height:{pct}%"></div>'
                f'<div class="bar-label">{label}</div>'
                f'</div>'
            )
        if projection > 0:
            last_lbl = chart_labels[-1] if chart_labels else ""
            _parts = last_lbl.split("-")
            if len(_parts) == 2:
                _end_part = _parts[1]
                _eh = int(_end_part[:-1])
                _eap = _end_part[-1]
                _end24 = (_eh + 12) if _eap == 'p' and _eh != 12 else (0 if _eap == 'a' and _eh == 12 else _eh)
                _next_end = (_end24 + 4) % 24
                _fh = lambda h: f"{h % 12 or 12}{'p' if h >= 12 else 'a'}"
                next_label = f"~{_fh(_end24)}-{_fh(_next_end)}"
            else:
                next_label = "~next"
            proj_pct = max(int((projection / max_delta) * 100), 4)
            proj_val = f"~{format_k(projection)}"
            bars.append(
                f'<div class="bar-col">'
                f'<div class="bar-val bar-val-proj">{proj_val}</div>'
                f'<div class="bar bar-proj" style="height:{proj_pct}%"></div>'
                f'<div class="bar-label">{next_label}</div>'
                f'</div>'
            )
        trend_svg = ""
        n_real = len(chart_deltas)
        if n_real >= 2 and max_delta > 0:
            n_total = n_real + (1 if projection > 0 else 0)
            sum_x = sum(range(n_real))
            sum_y = sum(chart_deltas)
            sum_xy = sum(i * v for i, v in enumerate(chart_deltas))
            sum_x2 = sum(i * i for i in range(n_real))
            slope = (n_real * sum_xy - sum_x * sum_y) / (n_real * sum_x2 - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n_real
            y_start = max(0, intercept)
            y_end = max(0, slope * (n_real - 1) + intercept)
            x1_pct = 0.5 / n_total * 100
            x2_pct = (n_real - 0.5) / n_total * 100
            y1_pct = max(4, min(100, y_start / max_delta * 100))
            y2_pct = max(4, min(100, y_end / max_delta * 100))
            y1_px = 200 - (y1_pct / 100 * 200)
            y2_px = 200 - (y2_pct / 100 * 200)
            trend_svg = (
                f'<svg class="trend-svg" xmlns="http://www.w3.org/2000/svg">'
                f'<line x1="{x1_pct:.1f}%" y1="{y1_px:.0f}" x2="{x2_pct:.1f}%" y2="{y2_px:.0f}" /></svg>'
            )

        chart_bars_html = f"""
        <div class="chart-section">
            <div class="chart-title">Views per 4 Hours</div>
            <div class="chart-row-wrap">
                <div class="chart-row">{"".join(bars)}</div>
                {trend_svg}
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f172a; font-family: 'Inter', -apple-system, system-ui, sans-serif; color: #f1f5f9; display: flex; justify-content: center; padding: 0; }}
.card {{ width: 1080px; height: 1080px; background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%); border-radius: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; }}
.bg-image {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: brightness(0.3); transform: scale(1.1); }}
.bg-overlay {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15,23,42,0.6) 0%, rgba(15,23,42,0.4) 25%, rgba(15,23,42,0.7) 55%, rgba(15,23,42,0.95) 100%); }}
.content {{ position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 60px 24px; text-align: center; }}
.header-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 32px; }}
.yt-icon {{ width: 48px; height: 34px; background: #ff0000; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.yt-icon::after {{ content: ''; display: block; width: 0; height: 0; border-left: 15px solid white; border-top: 9px solid transparent; border-bottom: 9px solid transparent; margin-left: 3px; }}
.title {{ font-size: 64px; font-weight: 900; color: #fff; letter-spacing: 6px; line-height: 1; text-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
.artist {{ font-size: 22px; color: rgba(255,255,255,0.5); font-weight: 600; letter-spacing: 4px; text-transform: uppercase; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; width: 100%; max-width: 780px; margin-bottom: 0; }}
.stat-box {{ text-align: center; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 24px 16px; }}
.stat-value {{ font-size: 40px; font-weight: 800; color: #fff; letter-spacing: -1px; line-height: 1.1; }}
.stat-label {{ font-size: 12px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 2px; margin-top: 6px; }}
.stat-change {{ font-size: 16px; font-weight: 600; margin-top: 4px; }}
.chart-section {{ width: 100%; max-width: 780px; margin-top: 28px; }}
.chart-title {{ font-size: 11px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; margin-bottom: 12px; text-align: left; }}
.chart-row-wrap {{ position: relative; height: 200px; width: 100%; }}
.chart-row {{ display: flex; align-items: flex-end; gap: 10px; height: 200px; width: 100%; }}
.trend-svg {{ position: absolute; top: 0; left: 0; width: 100%; height: 200px; pointer-events: none; }}
.trend-svg line {{ stroke: rgba(251,191,36,0.5); stroke-width: 2px; stroke-dasharray: 6 3; }}
.bar-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; min-width: 0; }}
.bar {{ width: 60%; border-radius: 20px; background: linear-gradient(180deg, rgba(56,189,248,0.9) 0%, rgba(59,130,246,0.5) 100%); min-height: 4px; }}
.bar-val {{ font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.7); margin-bottom: 4px; white-space: nowrap; }}
.bar-label {{ font-size: 9px; color: rgba(255,255,255,0.35); margin-top: 5px; font-weight: 500; }}
.bar-proj {{ background: none; border: 2px dashed rgba(56,189,248,0.5); opacity: 0.7; }}
.bar-val-proj {{ color: rgba(56,189,248,0.6); font-style: italic; }}
.footer {{ position: relative; z-index: 1; text-align: center; padding: 20px 60px 28px; border-top: 1px solid rgba(255,255,255,0.06); }}
.footer-text {{ font-size: 14px; color: #64748b; letter-spacing: 0.5px; }}
.footer-site {{ color: #3b82f6; font-weight: 600; }}
</style></head><body>
<div class="card" id="card">
    {"<img src='" + bg_data_uri + "' class='bg-image' />" if bg_data_uri else ""}
    <div class="bg-overlay"></div>
    <div class="content">
        <div class="header-row">
            <div class="yt-icon"></div>
            <div class="title">EMOJI</div>
            <div class="artist">&nbsp;&middot;&nbsp;SB19</div>
        </div>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{v_str}</div>
                <div class="stat-label">Views</div>
                {v_chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{l_str}</div>
                <div class="stat-label">Likes</div>
                {l_chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{c_str}</div>
                <div class="stat-label">Comments</div>
                {c_chg_html}
            </div>
        </div>{chart_bars_html}
    </div>
    <div class="footer">
        <div class="footer-text">As of {now_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_yt_emoji_card.html", YT_EMOJI_IMAGE_PATH,
        window_width=1200, window_height=1200,
        max_img_width=2400,
        label="YouTube EMOJI screenshot",
    )


# ---------------------------------------------------------------------------
# 8. capture_youtube_channel_screenshot
# ---------------------------------------------------------------------------

def capture_youtube_channel_screenshot(subscribers, views,
                                       sub_change, view_change,
                                       view_change_delta=None,
                                       audience_display=None, audience_change=0,
                                       mv_views=None,
                                       views_history=None, now_str=""):
    """Capture YouTube channel stats card with historical views chart + MV rankings."""
    print("[INFO] Capturing YouTube channel screenshot...")
    os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

    bg_img_path = os.path.join(SCRIPT_DIR, "profiles", "sb19.jpg")
    bg_data_uri = ""
    if os.path.exists(bg_img_path):
        with open(bg_img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            bg_data_uri = f"data:image/jpeg;base64,{b64}"

    def stat_with_change(value, change):
        val_str = f"{value:,}"
        if change > 0:
            return val_str, f"+{change:,}"
        elif change < 0:
            return val_str, f"{change:,}"
        return val_str, ""

    # Format subscribers as compact (e.g. 4.2M)
    def format_compact(n):
        if n >= 1_000_000_000:
            return f"{n / 1_000_000_000:.2f}B"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    v_str = f"{views:,}"
    v_delta_html = _delta_html(view_change_delta)

    s_display = format_compact(subscribers)

    # --- Build top panel: daily added views chart with total views info ---
    # Compute daily gains from absolute history
    daily_gains = []
    if views_history and len(views_history) >= 2:
        for i in range(1, len(views_history)):
            gain = views_history[i]["views"] - views_history[i - 1]["views"]
            daily_gains.append({"date": views_history[i]["date"], "gain": gain})

    # Today's daily gain from history (proper full-day value)
    today_daily = daily_gains[-1]["gain"] if daily_gains else view_change
    if today_daily > 0:
        daily_chg_str = f"+{today_daily:,}"
        daily_chg_color = "#34d399"
    elif today_daily < 0:
        daily_chg_str = f"{today_daily:,}"
        daily_chg_color = "#f87171"
    else:
        daily_chg_str = "0"
        daily_chg_color = "#64748b"

    chart_html = ""
    if daily_gains:
        vals = [g["gain"] for g in daily_gains]
        n = len(vals)
        chart_w, chart_h = 640, 170
        pad_l, pad_r, pad_t, pad_b = 70, 20, 15, 35
        plot_w = chart_w - pad_l - pad_r
        plot_h = chart_h - pad_t - pad_b

        val_min, val_max = min(vals), max(vals)
        margin = max((val_max - val_min) * 0.15, max(abs(val_max), 1) * 0.05)
        y_min = val_min - margin
        y_max = val_max + margin
        y_range = y_max - y_min if y_max != y_min else 1

        points = []
        for i, v in enumerate(vals):
            x = pad_l + (i / max(n - 1, 1)) * plot_w
            y = pad_t + plot_h - ((v - y_min) / y_range) * plot_h
            points.append((x, y))

        line_parts = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
        for x, y in points[1:]:
            line_parts.append(f"L {x:.1f},{y:.1f}")
        line_path = " ".join(line_parts)
        area_path = (
            line_path
            + f" L {points[-1][0]:.1f},{pad_t + plot_h}"
            + f" L {points[0][0]:.1f},{pad_t + plot_h} Z"
        )

        grid_lines = ""
        for i in range(3):
            gy = pad_t + (i / 2) * plot_h
            gval = y_max - (i / 2) * y_range
            grid_lines += (
                f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
                f'y2="{gy:.1f}" stroke="rgba(255,255,255,0.08)" stroke-width="1" stroke-dasharray="4,4"/>'
            )
            label = format_compact(gval)
            grid_lines += (
                f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" '
                f'text-anchor="end" fill="rgba(255,255,255,0.3)" font-size="11" '
                f'font-family="Inter, system-ui, sans-serif">{label}</text>'
            )

        dots = ""
        for i, (x, y) in enumerate(points):
            r = "5" if i == n - 1 else "3"
            opacity = "1" if i == n - 1 else "0.6"
            dots += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                f'fill="#ff4444" opacity="{opacity}"/>'
            )
        lx, ly = points[-1]
        dots += f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="10" fill="#ff4444" opacity="0.2"/>'

        x_labels = ""
        label_count = min(n, 5)
        for li in range(label_count):
            idx = int(li * (n - 1) / max(label_count - 1, 1)) if label_count > 1 else 0
            x = points[idx][0]
            raw_date = daily_gains[idx]["date"]
            try:
                dt = datetime.strptime(raw_date, "%Y%m%d")
                dlabel = dt.strftime("%b %d")
            except ValueError:
                dlabel = raw_date
            x_labels += (
                f'<text x="{x:.1f}" y="{pad_t + plot_h + 24}" '
                f'text-anchor="middle" fill="rgba(255,255,255,0.3)" font-size="11" '
                f'font-family="Inter, system-ui, sans-serif">{dlabel}</text>'
            )

        svg_chart = f"""
                <svg width="{chart_w}" height="{chart_h}" viewBox="0 0 {chart_w} {chart_h}"
                     xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="#ff4444" stop-opacity="0.2"/>
                            <stop offset="100%" stop-color="#ff4444" stop-opacity="0.02"/>
                        </linearGradient>
                    </defs>
                    {grid_lines}
                    <path d="{area_path}" fill="url(#areaGrad)"/>
                    <path d="{line_path}" stroke="#ff4444" stroke-width="2.5"
                          fill="none" stroke-linejoin="round" stroke-linecap="round"/>
                    {dots}
                    {x_labels}
                </svg>"""

        chart_html = f"""
        <div class="top-panel">
            <div class="top-total">{v_str} <span class="top-total-label">total views</span></div>
            <div class="top-daily">
                <span style="color:{daily_chg_color}">{daily_chg_str} today</span>
                <span class="stat-delta">{v_delta_html}</span>
            </div>
            <div class="chart-label">Daily Added Views &middot; Last {n + 1} Days</div>
            <div class="chart-wrap">{svg_chart}</div>
        </div>"""
    else:
        # Fallback: no chart, just show total views
        chart_html = f"""
        <div class="top-panel">
            <div class="top-total">{v_str} <span class="top-total-label">total views</span></div>
            <div class="top-daily">
                <span style="color:{daily_chg_color}">{daily_chg_str} today</span>
                <span class="stat-delta">{v_delta_html}</span>
            </div>
        </div>"""

    # Row 2: Subscribers + Monthly Audience side by side
    audience_box_html = ""
    if audience_display:
        aud_chg_html = ""
        if audience_change > 0:
            aud_chg_html = f'<div class="stat-change" style="color:#34d399">+{audience_change:,}</div>'
        elif audience_change < 0:
            aud_chg_html = f'<div class="stat-change" style="color:#f87171">{audience_change:,}</div>'
        audience_box_html = f"""
            <div class="stat-box">
                <div class="stat-value">{audience_display}</div>
                <div class="stat-label">YT Music Audience</div>
                {aud_chg_html}
            </div>"""

    # MV leaderboard with change deltas
    mv_html = ""
    if mv_views:
        max_views = mv_views[0][1] if mv_views else 1
        rows = []
        for i, item in enumerate(mv_views):
            name, v = item[0], item[1]
            chg = item[2] if len(item) > 2 else 0
            chg_delta = item[3] if len(item) > 3 else None
            pct = max(int((v / max_views) * 100), 3) if max_views > 0 else 3
            if v >= 1_000_000:
                v_display = f"{v / 1_000_000:.1f}M"
            elif v >= 1_000:
                v_display = f"{v / 1_000:.0f}K"
            else:
                v_display = str(v)
            # Format change
            chg_html = ""
            if chg > 0:
                if chg >= 1_000_000:
                    chg_display = f"+{chg / 1_000_000:.1f}M"
                elif chg >= 1_000:
                    chg_display = f"+{chg / 1_000:.1f}K"
                else:
                    chg_display = f"+{chg:,}"
                chg_html = f'<span class="mv-change mv-change-up">{chg_display}</span>'
            elif chg < 0:
                abs_chg = abs(chg)
                if abs_chg >= 1_000_000:
                    chg_display = f"-{abs_chg / 1_000_000:.1f}M"
                elif abs_chg >= 1_000:
                    chg_display = f"-{abs_chg / 1_000:.1f}K"
                else:
                    chg_display = f"{chg:,}"
                chg_html = f'<span class="mv-change mv-change-down">{chg_display}</span>'
            delta_html = f' <span class="mv-delta">{_delta_html(chg_delta)}</span>' if chg_delta is not None else ""
            rows.append(
                f'<div class="mv-row">'
                f'<div class="mv-rank">{i + 1}</div>'
                f'<div class="mv-info">'
                f'<div class="mv-name">{name}</div>'
                f'<div class="mv-bar-wrap"><div class="mv-bar" style="width:{pct}%"></div></div>'
                f'</div>'
                f'<div class="mv-stats"><span class="mv-views">{v_display}</span>{chg_html}{delta_html}</div>'
                f'</div>'
            )
        mv_html = f"""
        <div class="mv-section">
            <div class="mv-title">Music Video Views</div>
            {"".join(rows)}
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f172a; font-family: 'Inter', -apple-system, system-ui, sans-serif; color: #f1f5f9; display: flex; justify-content: center; padding: 0; }}
.card {{ width: 1080px; min-height: 1080px; background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%); border-radius: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; }}
.bg-image {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: brightness(0.2); transform: scale(1.1); }}
.bg-overlay {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.3) 20%, rgba(15,23,42,0.85) 50%, rgba(15,23,42,0.98) 100%); }}
.content {{ position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; align-items: center; padding: 44px 60px 20px; text-align: center; }}
.header-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 10px; }}
.yt-icon {{ width: 44px; height: 32px; background: #ff0000; border-radius: 7px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.yt-icon::after {{ content: ''; display: block; width: 0; height: 0; border-left: 13px solid white; border-top: 8px solid transparent; border-bottom: 8px solid transparent; margin-left: 3px; }}
.title {{ font-size: 50px; font-weight: 900; color: #fff; letter-spacing: 5px; line-height: 1; text-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
.subtitle {{ font-size: 15px; color: rgba(255,255,255,0.4); font-weight: 600; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 28px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; width: 100%; max-width: 720px; }}
.stat-box {{ text-align: center; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 22px 16px; }}
.stat-box-wide {{ grid-column: 1 / -1; padding: 18px 16px; }}
.stat-value {{ font-size: 38px; font-weight: 800; color: #fff; letter-spacing: -1px; line-height: 1.1; }}
.stat-box-wide .stat-value {{ font-size: 32px; }}
.stat-label {{ font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 2px; margin-top: 6px; }}
.stat-change {{ font-size: 15px; font-weight: 600; margin-top: 4px; }}
.stat-delta {{ font-size: 12px; font-weight: 600; margin-left: 4px; }}
.top-panel {{
    width: 100%; max-width: 720px;
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 24px 28px 18px; margin-bottom: 20px;
}}
.top-total {{ font-size: 36px; font-weight: 800; color: #fff; letter-spacing: -1px; line-height: 1; }}
.top-total-label {{ font-size: 14px; font-weight: 400; color: rgba(255,255,255,0.4); letter-spacing: 0; }}
.top-daily {{ font-size: 16px; font-weight: 600; margin-top: 6px; margin-bottom: 18px; }}
.chart-label {{ font-size: 11px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; margin-bottom: 10px; text-align: left; }}
.chart-wrap {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 14px 12px 8px; }}
.mv-section {{ width: 100%; max-width: 720px; margin-top: 24px; }}
.mv-title {{ font-size: 11px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; margin-bottom: 14px; text-align: left; }}
.mv-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
.mv-rank {{ font-size: 14px; font-weight: 700; color: rgba(255,255,255,0.3); width: 20px; text-align: right; flex-shrink: 0; }}
.mv-info {{ flex: 1; min-width: 0; }}
.mv-name {{ font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 4px; text-align: left; }}
.mv-bar-wrap {{ height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden; }}
.mv-bar {{ height: 100%; border-radius: 3px; background: linear-gradient(90deg, rgba(255,0,0,0.7) 0%, rgba(255,60,60,0.4) 100%); }}
.mv-stats {{ text-align: right; flex-shrink: 0; min-width: 100px; }}
.mv-views {{ font-size: 15px; font-weight: 700; color: rgba(255,255,255,0.6); }}
.mv-change {{ display: block; font-size: 11px; font-weight: 600; margin-top: 1px; }}
.mv-change-up {{ color: #34d399; }}
.mv-change-down {{ color: #f87171; }}
.mv-delta {{ font-size: 10px; font-weight: 600; }}
.delta-up {{ color: #34d399; }}
.delta-down {{ color: #f87171; }}
.footer {{ position: relative; z-index: 1; text-align: center; padding: 18px 60px 24px; border-top: 1px solid rgba(255,255,255,0.06); }}
.footer-text {{ font-size: 13px; color: #64748b; letter-spacing: 0.5px; }}
.footer-site {{ color: #3b82f6; font-weight: 600; }}
</style></head><body>
<div class="card" id="card">
    {"<img src='" + bg_data_uri + "' class='bg-image' />" if bg_data_uri else ""}
    <div class="bg-overlay"></div>
    <div class="content">
        <div class="header-row">
            <div class="yt-icon"></div>
            <div class="title">SB19</div>
        </div>
        <div class="subtitle">Official YouTube Channel</div>
        {chart_html}
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{s_display}</div>
                <div class="stat-label">Subscribers</div>
            </div>{audience_box_html}
        </div>{mv_html}
    </div>
    <div class="footer">
        <div class="footer-text">As of {now_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_yt_channel_card.html", YT_CHANNEL_IMAGE_PATH,
        window_width=1200, window_height=1400,
        max_img_width=2400,
        label="YouTube channel screenshot",
    )


# ---------------------------------------------------------------------------
# 9. capture_spotify_visa_screenshot
# ---------------------------------------------------------------------------

def capture_spotify_visa_screenshot(total_streams, daily_gain,
                                    stream_change, daily_labels,
                                    daily_deltas, now_str):
    """Capture a Spotify VISA daily stats card."""
    print("[INFO] Capturing Spotify VISA screenshot...")
    os.makedirs(ALBUM_IMAGE_DIR, exist_ok=True)

    visa_img_path = os.path.join(SCRIPT_DIR, "photos", "visa.png")
    bg_data_uri = ""
    if os.path.exists(visa_img_path):
        with open(visa_img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            bg_data_uri = f"data:image/png;base64,{b64}"

    def format_k(v):
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v / 1_000:.1f}K"
        return str(v)

    total_str = f"{total_streams:,}"
    daily_str = f"{daily_gain:,}"

    if stream_change > 0:
        chg_str = f"+{stream_change:,}"
        chg_color = "#1db954"
    elif stream_change < 0:
        chg_str = f"{stream_change:,}"
        chg_color = "#f87171"
    else:
        chg_str = ""
        chg_color = "#1db954"

    chg_html = f'<div class="stat-change" style="color:{chg_color}">{chg_str}</div>' if chg_str else ""

    max_delta = max(daily_deltas) if daily_deltas else 1
    chart_bars_html = ""
    if daily_deltas:
        bars = []
        for label, delta in zip(daily_labels, daily_deltas):
            pct = max(int((delta / max_delta) * 100), 4) if max_delta > 0 else 4
            val_label = format_k(delta) if delta > 0 else ""
            bars.append(
                f'<div class="bar-col">'
                f'<div class="bar-val">{val_label}</div>'
                f'<div class="bar" style="height:{pct}%"></div>'
                f'<div class="bar-label">{label}</div>'
                f'</div>'
            )

        trend_svg = ""
        n_real = len(daily_deltas)
        if n_real >= 2 and max_delta > 0:
            sum_x = sum(range(n_real))
            sum_y = sum(daily_deltas)
            sum_xy = sum(i * v for i, v in enumerate(daily_deltas))
            sum_x2 = sum(i * i for i in range(n_real))
            denom = n_real * sum_x2 - sum_x * sum_x
            if denom != 0:
                slope = (n_real * sum_xy - sum_x * sum_y) / denom
                intercept = (sum_y - slope * sum_x) / n_real
                y_start = max(0, intercept)
                y_end = max(0, slope * (n_real - 1) + intercept)
                x1_pct = 0.5 / n_real * 100
                x2_pct = (n_real - 0.5) / n_real * 100
                y1_pct = max(4, min(100, y_start / max_delta * 100))
                y2_pct = max(4, min(100, y_end / max_delta * 100))
                y1_px = 200 - (y1_pct / 100 * 200)
                y2_px = 200 - (y2_pct / 100 * 200)
                trend_svg = (
                    f'<svg class="trend-svg" xmlns="http://www.w3.org/2000/svg">'
                    f'<line x1="{x1_pct:.1f}%" y1="{y1_px:.0f}" x2="{x2_pct:.1f}%" y2="{y2_px:.0f}" /></svg>'
                )

        chart_bars_html = f"""
        <div class="chart-section">
            <div class="chart-title">Daily Streams</div>
            <div class="chart-row-wrap">
                <div class="chart-row">{"".join(bars)}</div>
                {trend_svg}
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f172a; font-family: 'Inter', -apple-system, system-ui, sans-serif; color: #f1f5f9; display: flex; justify-content: center; padding: 0; }}
.card {{ width: 1080px; height: 1080px; background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%); border-radius: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; }}
.bg-image {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: brightness(0.3) blur(2px); transform: scale(1.1); }}
.bg-overlay {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15,23,42,0.6) 0%, rgba(15,23,42,0.4) 25%, rgba(15,23,42,0.7) 55%, rgba(15,23,42,0.95) 100%); }}
.content {{ position: relative; z-index: 1; flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 60px 24px; text-align: center; }}
.header-row {{ display: flex; align-items: center; gap: 14px; margin-bottom: 32px; }}
.sp-icon {{ width: 48px; height: 48px; background: #1db954; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
.sp-icon svg {{ width: 28px; height: 28px; fill: white; }}
.title {{ font-size: 64px; font-weight: 900; color: #fff; letter-spacing: 6px; line-height: 1; text-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
.artist {{ font-size: 22px; color: rgba(255,255,255,0.5); font-weight: 600; letter-spacing: 4px; text-transform: uppercase; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; width: 100%; max-width: 580px; margin-bottom: 0; }}
.stat-box {{ text-align: center; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 24px 16px; }}
.stat-value {{ font-size: 40px; font-weight: 800; color: #fff; letter-spacing: -1px; line-height: 1.1; }}
.stat-label {{ font-size: 12px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 2px; margin-top: 6px; }}
.stat-change {{ font-size: 16px; font-weight: 600; margin-top: 4px; }}
.chart-section {{ width: 100%; max-width: 780px; margin-top: 28px; }}
.chart-title {{ font-size: 11px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; margin-bottom: 12px; text-align: left; }}
.chart-row-wrap {{ position: relative; height: 200px; width: 100%; }}
.chart-row {{ display: flex; align-items: flex-end; gap: 10px; height: 200px; width: 100%; }}
.trend-svg {{ position: absolute; top: 0; left: 0; width: 100%; height: 200px; pointer-events: none; }}
.trend-svg line {{ stroke: rgba(251,191,36,0.5); stroke-width: 2px; stroke-dasharray: 6 3; }}
.bar-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; min-width: 0; }}
.bar {{ width: 60%; border-radius: 20px; background: linear-gradient(180deg, rgba(29,185,84,0.9) 0%, rgba(29,185,84,0.4) 100%); min-height: 4px; }}
.bar-val {{ font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.7); margin-bottom: 4px; white-space: nowrap; }}
.bar-label {{ font-size: 9px; color: rgba(255,255,255,0.35); margin-top: 5px; font-weight: 500; }}
.footer {{ position: relative; z-index: 1; text-align: center; padding: 20px 60px 28px; border-top: 1px solid rgba(255,255,255,0.06); }}
.footer-text {{ font-size: 14px; color: #64748b; letter-spacing: 0.5px; }}
.footer-site {{ color: #1db954; font-weight: 600; }}
</style></head><body>
<div class="card" id="card">
    {"<img src='" + bg_data_uri + "' class='bg-image' />" if bg_data_uri else ""}
    <div class="bg-overlay"></div>
    <div class="content">
        <div class="header-row">
            <div class="sp-icon"><svg viewBox="0 0 24 24"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg></div>
            <div class="title">VISA</div>
            <div class="artist">&nbsp;&middot;&nbsp;SB19</div>
        </div>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Streams</div>
                {chg_html}
            </div>
            <div class="stat-box">
                <div class="stat-value">{daily_str}</div>
                <div class="stat-label">Daily Gain</div>
            </div>
        </div>{chart_bars_html}
    </div>
    <div class="footer">
        <div class="footer-text">As of {now_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_sp_visa_card.html", SPOTIFY_VISA_IMAGE_PATH,
        window_width=1200, window_height=1200,
        max_img_width=2400,
        label="Spotify VISA screenshot",
    )


# ---------------------------------------------------------------------------
# 9. capture_album_screenshot
# ---------------------------------------------------------------------------

def capture_album_screenshot(track_list=None, total_streams=0,
                             total_change=0, date_str=""):
    """Capture a social-media-friendly album card screenshot."""
    print("[INFO] Capturing album screenshot...")
    if not track_list:
        print("[ERR] No track data for album card")
        return False

    max_streams = max(t["streams"] for t in track_list) if track_list else 1
    bar_colors = [
        "#ec4899", "#6366f1", "#10b981", "#f59e0b", "#a855f7",
        "#eab308", "#ef4444", "#14b8a6", "#3b82f6", "#f97316",
        "#8b5cf6", "#06b6d4", "#84cc16", "#e11d4f", "#0ea5e9",
        "#d946ef", "#22c55e", "#fb923c", "#64748b",
    ]

    track_rows = ""
    for i, t in enumerate(track_list):
        pct = (t["streams"] / max_streams) * 100
        color = bar_colors[i % len(bar_colors)]
        change_str = f"+{t['change']:,}" if t["change"] > 0 else f"{t['change']:,}"
        track_rows += f"""
            <div class="track-row">
                <div class="track-rank">{i + 1}</div>
                <div class="track-info">
                    <div class="track-name">{t['name']}</div>
                    <div class="track-bar-container">
                        <div class="track-bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                </div>
                <div class="track-stats">
                    <div class="track-streams">{t['streams']:,}</div>
                    <div class="track-change">{change_str}</div>
                </div>
            </div>"""

    total_str = f"{total_streams:,}"
    change_display = f"+{total_change:,}" if total_change > 0 else f"{total_change:,}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f172a; font-family: 'Inter', -apple-system, system-ui, sans-serif; color: #f1f5f9; display: flex; justify-content: center; padding: 0; }}
.card {{ width: 1080px; background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 20px; padding: 48px 56px 40px; box-shadow: 0 0 60px rgba(59, 130, 246, 0.08); }}
.header {{ text-align: center; margin-bottom: 36px; padding-bottom: 28px; border-bottom: 1px solid rgba(148, 163, 184, 0.15); }}
.album-title {{ font-size: 30px; font-weight: 700; color: #f8fafc; margin-bottom: 18px; letter-spacing: -0.3px; }}
.stats-row {{ display: flex; justify-content: center; gap: 48px; }}
.stat-box {{ text-align: center; }}
.stat-value {{ font-size: 38px; font-weight: 800; color: #3b82f6; letter-spacing: -0.5px; }}
.stat-label {{ font-size: 14px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}
.stat-change {{ font-size: 38px; font-weight: 800; color: #10b981; letter-spacing: -0.5px; }}
.tracks {{ display: flex; flex-direction: column; gap: 8px; }}
.track-row {{ display: flex; align-items: center; gap: 16px; padding: 9px 0; }}
.track-rank {{ font-size: 18px; font-weight: 700; color: #475569; width: 30px; text-align: right; flex-shrink: 0; }}
.track-info {{ flex: 1; min-width: 0; }}
.track-name {{ font-size: 19px; font-weight: 600; color: #e2e8f0; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.track-bar-container {{ height: 8px; background: rgba(51, 65, 85, 0.5); border-radius: 3px; overflow: hidden; }}
.track-bar {{ height: 100%; border-radius: 3px; transition: width 0.3s ease; }}
.track-stats {{ text-align: right; flex-shrink: 0; min-width: 120px; }}
.track-streams {{ font-size: 19px; font-weight: 700; color: #f1f5f9; }}
.track-change {{ font-size: 14px; color: #10b981; font-weight: 500; }}
.footer {{ text-align: center; margin-top: 28px; padding-top: 20px; border-top: 1px solid rgba(148, 163, 184, 0.15); }}
.footer-text {{ font-size: 14px; color: #475569; letter-spacing: 0.5px; }}
.footer-site {{ color: #3b82f6; font-weight: 600; }}
.track-row:nth-child(even) {{ filter: blur(3px); opacity: 0.7; }}
.cta-footer {{ text-align: center; margin-top: 20px; font-size: 16px; color: #94a3b8; font-weight: 500; letter-spacing: 0.3px; }}
.cta-footer span {{ color: #3b82f6; font-weight: 700; }}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="album-title">Simula at Wakas Tour Kickoff Concert Album</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-value">{total_str}</div>
                <div class="stat-label">Total Streams</div>
            </div>
            <div class="stat-box">
                <div class="stat-change">{change_display}</div>
                <div class="stat-label">Daily Change</div>
            </div>
        </div>
    </div>
    <div class="tracks">{track_rows}
    </div>
    <div class="cta-footer">Full details at <span>opminsights.com</span></div>
    <div class="footer">
        <div class="footer-text">As of {date_str} &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_album_card.html", ALBUM_IMAGE_PATH,
        window_width=1200, window_height=1800,
        max_img_width=2400,
        label="Album screenshot",
    )


# ---------------------------------------------------------------------------
# 9b. capture_was_album_screenshot  (Wakas At Simula studio album)
# ---------------------------------------------------------------------------

def capture_was_album_screenshot(top3_data=None, table_data=None,
                                 total_daily=0, total_delta=None, date_str=""):
    """Capture a WAS album leaderboard card ranked by daily streams."""
    print("[INFO] Capturing Wakas At Simula album screenshot...")
    if not top3_data:
        print("[ERR] No track data for WAS album card")
        return False

    podium_colors = ["#fbbf24", "#94a3b8", "#cd7f32"]

    top3_rows = ""
    max_daily = top3_data[0]["change"] if top3_data else 1
    for i, t in enumerate(top3_data):
        color = podium_colors[i]
        ch_html = _change_html(t["change"])
        streams_str = f"{t['streams']:,}"
        daily_str = f"+{t['change']:,}" if t["change"] > 0 else f"{t['change']:,}"
        delta_tag = _delta_html(t.get("change_delta"))
        pct = (t["change"] / max_daily) * 100 if max_daily > 0 else 0
        feat = f'<span class="podium-feat"> ft. {t["feat"]}</span>' if t.get("feat") else ""
        top3_rows += f"""
            <div class="podium-row podium-{i+1}">
                <div class="podium-rank">{t['rank']}</div>
                <div class="podium-content">
                    <div class="podium-header">
                        <span class="podium-name">{t['song']}{feat}</span>
                    </div>
                    <div class="podium-bar-container">
                        <div class="podium-bar" style="width: {pct}%; background: {color};"></div>
                    </div>
                    <div class="podium-stats">
                        <span class="podium-daily">{daily_str}</span>
                        <span class="podium-delta">{delta_tag}</span>
                        <span class="podium-streams">{streams_str} total</span>
                    </div>
                </div>
            </div>"""

    table_rows = ""
    if table_data:
        for t in table_data:
            streams_str = f"{t['streams']:,}"
            ch_html = _change_html(t["change"])
            delta_tag = _delta_html(t.get("change_delta"))
            feat = f' <span class="feat-sm">ft. {t["feat"]}</span>' if t.get("feat") else ""
            table_rows += f"""
                <tr>
                    <td class="col-rank">{t['rank']}</td>
                    <td class="col-track">{t['song']}{feat}</td>
                    <td class="col-change">{ch_html} <span class="delta-sm">{delta_tag}</span></td>
                    <td class="col-streams">{streams_str}</td>
                </tr>"""

    daily_display = f"+{total_daily:,}" if total_daily > 0 else f"{total_daily:,}"
    total_delta_tag = _delta_html(total_delta)
    track_count = len(top3_data) + (len(table_data) if table_data else 0)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0f172a;
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: #f1f5f9;
    display: flex;
    justify-content: center;
    padding: 0;
}}
.card {{
    width: 1080px;
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 20px;
    padding: 48px 56px 40px;
    box-shadow: 0 0 60px rgba(59, 130, 246, 0.08);
}}
.header {{
    text-align: center;
    margin-bottom: 36px;
    padding-bottom: 28px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}}
.album-label {{
    font-size: 13px; font-weight: 700; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 3px; margin-bottom: 8px;
}}
.card-title {{
    font-size: 30px; font-weight: 700; color: #f8fafc;
    margin-bottom: 8px; letter-spacing: -0.3px;
}}
.card-subtitle {{
    font-size: 18px; color: #94a3b8; font-weight: 400; margin-bottom: 22px;
}}
.stats-row {{
    display: flex; justify-content: center; gap: 48px; margin-top: 18px;
}}
.stat-box {{ text-align: center; }}
.stat-value {{
    font-size: 36px; font-weight: 800; color: #3b82f6; letter-spacing: -0.5px;
}}
.stat-daily {{
    font-size: 36px; font-weight: 800; color: #10b981; letter-spacing: -0.5px;
}}
.stat-tracks {{
    font-size: 36px; font-weight: 800; color: #3b82f6; letter-spacing: -0.5px;
}}
.stat-label {{
    font-size: 14px; color: #64748b; text-transform: uppercase;
    letter-spacing: 1px; margin-top: 2px;
}}
.podium-section {{
    display: flex; flex-direction: column; gap: 10px; margin-bottom: 8px;
}}
.podium-row {{
    display: flex; align-items: center; gap: 18px;
    border-radius: 14px; padding: 16px 20px;
}}
.podium-1 {{
    background: rgba(251, 191, 36, 0.10);
    border: 1px solid rgba(251, 191, 36, 0.25);
}}
.podium-2 {{
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.20);
}}
.podium-3 {{
    background: rgba(205, 127, 50, 0.08);
    border: 1px solid rgba(205, 127, 50, 0.20);
}}
.podium-rank {{
    font-size: 32px; font-weight: 800; width: 48px;
    text-align: center; flex-shrink: 0;
}}
.podium-1 .podium-rank {{ color: #fbbf24; }}
.podium-2 .podium-rank {{ color: #94a3b8; }}
.podium-3 .podium-rank {{ color: #cd7f32; }}
.podium-content {{ flex: 1; min-width: 0; }}
.podium-header {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
}}
.podium-name {{
    font-size: 22px; font-weight: 700; color: #f1f5f9;
}}
.podium-feat {{
    font-size: 15px; font-weight: 400; color: rgba(241,245,249,0.45);
}}
.podium-bar-container {{
    height: 38px; background: rgba(51, 65, 85, 0.5);
    border-radius: 8px; overflow: hidden; margin-bottom: 6px;
}}
.podium-bar {{
    height: 100%; border-radius: 8px;
}}
.podium-stats {{
    display: flex; align-items: center; gap: 14px;
}}
.podium-daily {{
    font-size: 22px; font-weight: 700; color: #34d399;
}}
.podium-streams {{
    font-size: 14px; font-weight: 500; color: #64748b;
}}
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18);
    margin: 24px 0 20px;
}}
.section-label {{
    font-size: 16px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px;
}}
.table-section {{ width: 100%; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{
    font-size: 12px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: 1px;
    padding: 8px 10px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    text-align: left;
}}
th.col-rank, th.col-streams, th.col-change {{
    text-align: right;
}}
td {{
    font-size: 14px; padding: 7px 10px; color: #cbd5e1;
    border-bottom: 1px solid rgba(51, 65, 85, 0.4);
}}
td.col-rank {{
    font-weight: 700; color: #64748b; text-align: right; width: 50px;
}}
td.col-track {{
    font-weight: 600; color: #e2e8f0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 360px;
}}
.feat-sm {{
    font-size: 12px; font-weight: 400; color: rgba(226,232,240,0.4);
}}
td.col-streams {{
    font-weight: 600; color: #94a3b8; text-align: right; white-space: nowrap;
}}
td.col-change {{
    text-align: right; font-size: 13px; white-space: nowrap;
}}
tr:nth-child(even) {{
    background: rgba(51, 65, 85, 0.15);
}}
.change-up {{ color: #34d399; }}
.change-down {{ color: #f87171; }}
.change-same {{ color: #9ca3af; }}
.podium-delta {{
    font-size: 14px; font-weight: 600; margin-left: 2px;
}}
.delta-up {{ color: #34d399; }}
.delta-down {{ color: #f87171; }}
.delta-sm {{
    font-size: 11px; font-weight: 600;
}}
.stat-delta {{
    font-size: 16px; font-weight: 600; margin-top: 2px;
}}
.footer {{
    text-align: center; margin-top: 28px; padding-top: 20px;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
}}
.footer-text {{
    font-size: 14px; color: #475569; letter-spacing: 0.5px;
}}
.footer-site {{
    color: #3b82f6; font-weight: 600;
}}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="album-label">SB19 &middot; Album</div>
        <div class="card-title">Wakas At Simula</div>
        <div class="card-subtitle">Ranked by Daily Streams &middot; {date_str}</div>
        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-tracks">{track_count}</div>
                <div class="stat-label">Tracks</div>
            </div>
            <div class="stat-box">
                <div class="stat-daily">{daily_display}</div>
                <div class="stat-delta">{total_delta_tag}</div>
                <div class="stat-label">Daily Streams</div>
            </div>
        </div>
    </div>
    <div class="podium-section">{top3_rows}
    </div>
    <div class="section-divider"></div>
    <div class="section-label">Remaining Tracks</div>
    <div class="table-section">
        <table>
            <thead>
                <tr>
                    <th class="col-rank">#</th>
                    <th>Track</th>
                    <th class="col-change">Daily</th>
                    <th class="col-streams">Total</th>
                </tr>
            </thead>
            <tbody>{table_rows}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <div class="footer-text">*Ranked by daily streams &middot; <span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_was_album_card.html", WAS_ALBUM_IMAGE_PATH,
        window_width=1200, window_height=2000,
        max_img_width=2400,
        label="WAS Album screenshot",
    )


# ---------------------------------------------------------------------------
# 10. capture_listeners_screenshot
# ---------------------------------------------------------------------------

def capture_listeners_screenshot(sb19_history=None, sb19_change=0,
                                 sb19_change_delta=None, solo_data=None,
                                 date_str=""):
    """Capture monthly listeners card with SB19 14-day history + solo members.

    Args:
        sb19_history: List of dicts with 'date' (YYYYMMDD), 'listeners' keys.
        sb19_change: Daily change for SB19 (latest vs previous day).
        solo_data: List of dicts with 'artist', 'listeners', 'change' keys.
        date_str: Formatted date string for the card subtitle.

    Returns:
        True on success, False on failure.
    """
    print("[INFO] Capturing monthly listeners screenshot...")
    if not sb19_history:
        print("[ERR] No SB19 history data for listeners card")
        return False

    # --- Load member photos ---
    photo_data_uris = {}
    for artist_name, photo_file in MEMBER_PHOTO_FILES.items():
        photo_path = os.path.join(MEMBER_PHOTOS_DIR, photo_file)
        if os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = photo_file.rsplit(".", 1)[-1].lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            photo_data_uris[artist_name] = f"data:{mime};base64,{b64}"

    # --- SB19 photo ---
    sb19_photo_uri = photo_data_uris.get("SB19", "")
    sb19_photo_html = (
        f'<img class="sb19-photo" src="{sb19_photo_uri}" alt="SB19" />'
        if sb19_photo_uri
        else '<div class="sb19-photo" style="background:#3b82f6;"></div>'
    )

    # --- SB19 current stats ---
    sb19_current = sb19_history[-1]["listeners"]
    sb19_listeners_str = f"{sb19_current:,}"
    if sb19_change > 0:
        sb19_change_str = f"+{sb19_change:,}"
        sb19_change_color = "#10b981"
    elif sb19_change < 0:
        sb19_change_str = f"{sb19_change:,}"
        sb19_change_color = "#ef4444"
    else:
        sb19_change_str = "0"
        sb19_change_color = "#64748b"
    sb19_delta_html = _delta_html(sb19_change_delta)

    # --- Build SVG line chart for 14-day history ---
    values = [h["listeners"] for h in sb19_history]
    n = len(values)
    chart_w, chart_h = 920, 220
    pad_l, pad_r, pad_t, pad_b = 90, 30, 25, 45
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    val_min = min(values)
    val_max = max(values)
    margin = max((val_max - val_min) * 0.15, 1)
    y_min = val_min - margin
    y_max = val_max + margin
    y_range = y_max - y_min if y_max != y_min else 1

    # Map data points to SVG coordinates
    points = []
    for i, v in enumerate(values):
        x = pad_l + (i / max(n - 1, 1)) * plot_w
        y = pad_t + plot_h - ((v - y_min) / y_range) * plot_h
        points.append((x, y))

    # SVG line path
    line_parts = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
    for x, y in points[1:]:
        line_parts.append(f"L {x:.1f},{y:.1f}")
    line_path = " ".join(line_parts)

    # Area fill path (line + bottom edge)
    area_path = (
        line_path
        + f" L {points[-1][0]:.1f},{pad_t + plot_h}"
        + f" L {points[0][0]:.1f},{pad_t + plot_h} Z"
    )

    # Horizontal grid lines (3 evenly spaced)
    grid_lines = ""
    for i in range(4):
        gy = pad_t + (i / 3) * plot_h
        gval = y_max - (i / 3) * y_range
        grid_lines += (
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
            f'y2="{gy:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        if gval >= 1_000_000:
            label = f"{gval / 1_000_000:.2f}M"
        elif gval >= 1_000:
            label = f"{gval / 1_000:.0f}K"
        else:
            label = f"{gval:.0f}"
        grid_lines += (
            f'<text x="{pad_l - 10}" y="{gy + 5:.1f}" '
            f'text-anchor="end" fill="#64748b" font-size="13" '
            f'font-family="Inter, system-ui, sans-serif">{label}</text>'
        )

    # Data point dots
    dots = ""
    for i, (x, y) in enumerate(points):
        r = "6" if i == n - 1 else "3.5"
        opacity = "1" if i == n - 1 else "0.7"
        dots += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
            f'fill="#3b82f6" opacity="{opacity}"/>'
        )
    # Highlight latest point with glow
    lx, ly = points[-1]
    dots += (
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="12" '
        f'fill="#3b82f6" opacity="0.2"/>'
    )

    # X-axis date labels (show ~5 evenly spaced)
    x_labels = ""
    label_count = min(n, 5)
    for li in range(label_count):
        idx = int(li * (n - 1) / max(label_count - 1, 1)) if label_count > 1 else 0
        x = points[idx][0]
        raw_date = sb19_history[idx]["date"]
        try:
            dt = datetime.strptime(raw_date, "%Y%m%d")
            dlabel = dt.strftime("%b %d")
        except ValueError:
            dlabel = raw_date
        x_labels += (
            f'<text x="{x:.1f}" y="{pad_t + plot_h + 30}" '
            f'text-anchor="middle" fill="#64748b" font-size="13" '
            f'font-family="Inter, system-ui, sans-serif">{dlabel}</text>'
        )

    svg_chart = f"""
    <svg width="{chart_w}" height="{chart_h}" viewBox="0 0 {chart_w} {chart_h}"
         xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.25"/>
                <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"/>
            </linearGradient>
        </defs>
        {grid_lines}
        <path d="{area_path}" fill="url(#areaGrad)"/>
        <path d="{line_path}" stroke="#3b82f6" stroke-width="3"
              fill="none" stroke-linejoin="round" stroke-linecap="round"/>
        {dots}
        {x_labels}
    </svg>"""

    # --- Solo member rows (current format) ---
    solo_rows = ""
    if solo_data:
        max_solo = max(d["listeners"] for d in solo_data)
        for d in solo_data:
            matched_key = None
            for key in MEMBER_PHOTO_FILES:
                if key.upper() == d["artist"].upper():
                    matched_key = key
                    break
            photo_uri = photo_data_uris.get(matched_key, "")
            color = MEMBER_BAR_COLORS.get(matched_key, "#3b82f6")
            pct = (d["listeners"] / max_solo) * 100 if max_solo else 0
            listeners_str = f"{d['listeners']:,}"
            change = d["change"]
            if change > 0:
                ch_str = f"+{change:,}"
                ch_color = "#10b981"
            elif change < 0:
                ch_str = f"{change:,}"
                ch_color = "#ef4444"
            else:
                ch_str = "0"
                ch_color = "#64748b"
            delta_tag = _delta_html(d.get("change_delta"))

            if photo_uri:
                ph_html = f'<img class="artist-photo" src="{photo_uri}" alt="{d["artist"]}" />'
            else:
                ph_html = f'<div class="artist-photo" style="background:{color};"></div>'

            solo_rows += f"""
                <div class="artist-row">
                    <div class="artist-left">
                        {ph_html}
                        <div class="artist-name">{d['artist']}</div>
                    </div>
                    <div class="artist-middle">
                        <div class="bar-container">
                            <div class="bar" style="width: {pct}%; background: {color};"></div>
                        </div>
                    </div>
                    <div class="artist-right">
                        <div class="artist-listeners">{listeners_str}</div>
                        <div class="artist-change" style="color: {ch_color};">{ch_str} <span class="solo-delta">{delta_tag}</span></div>
                    </div>
                </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f172a; font-family: 'Inter', -apple-system, system-ui, sans-serif; color: #f1f5f9; display: flex; justify-content: center; padding: 0; }}
.card {{ width: 1080px; background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 20px; padding: 48px 56px 40px; box-shadow: 0 0 60px rgba(59, 130, 246, 0.08); }}
.header {{ text-align: center; margin-bottom: 36px; padding-bottom: 28px; border-bottom: 1px solid rgba(148, 163, 184, 0.15); }}
.card-title {{ font-size: 32px; font-weight: 700; color: #f8fafc; margin-bottom: 8px; letter-spacing: -0.3px; }}
.card-title .spotify {{ color: #1db954; }}
.card-date {{ font-size: 18px; color: #94a3b8; font-weight: 400; }}

/* --- Top Panel: SB19 History --- */
.sb19-panel {{ margin-bottom: 12px; }}
.sb19-info {{
    display: flex; align-items: center; gap: 24px; margin-bottom: 24px;
}}
.sb19-photo {{
    width: 100px; height: 100px; border-radius: 50%; object-fit: cover;
    border: 3px solid rgba(59, 130, 246, 0.8);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.4), 0 0 40px rgba(59, 130, 246, 0.15);
    flex-shrink: 0;
}}
.sb19-details {{ flex: 1; }}
.sb19-name {{ font-size: 36px; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px; }}
.sb19-listeners {{ font-size: 28px; font-weight: 700; color: #e2e8f0; margin-top: 2px; }}
.sb19-listeners span {{ font-size: 16px; font-weight: 400; color: #94a3b8; margin-left: 4px; }}
.sb19-change {{ font-size: 18px; font-weight: 600; margin-top: 4px; }}
.chart-label {{
    font-size: 13px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px;
}}
.chart-container {{
    background: rgba(30, 41, 59, 0.6); border-radius: 14px;
    padding: 20px 16px 12px; border: 1px solid rgba(51, 65, 85, 0.5);
}}

/* --- Divider --- */
.section-divider {{
    border-top: 2px dashed rgba(148, 163, 184, 0.18); margin: 28px 0 24px;
}}
.section-label {{
    font-size: 16px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 20px;
}}

/* --- Bottom Panel: Solo Members --- */
.artists {{ display: flex; flex-direction: column; gap: 20px; }}
.artist-row {{ display: flex; align-items: center; gap: 20px; }}
.artist-left {{ display: flex; align-items: center; gap: 16px; width: 240px; flex-shrink: 0; }}
.artist-photo {{ width: 64px; height: 64px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid rgba(148, 163, 184, 0.2); }}
.artist-name {{ font-size: 22px; font-weight: 600; color: #e2e8f0; white-space: nowrap; }}
.artist-middle {{ flex: 1; min-width: 0; }}
.bar-container {{ height: 28px; background: rgba(51, 65, 85, 0.5); border-radius: 6px; overflow: hidden; }}
.bar {{ height: 100%; border-radius: 6px; }}
.artist-right {{ text-align: right; flex-shrink: 0; min-width: 160px; }}
.artist-listeners {{ font-size: 24px; font-weight: 700; color: #f1f5f9; }}
.artist-change {{ font-size: 16px; font-weight: 500; margin-top: 2px; }}
.sb19-delta {{ font-size: 14px; font-weight: 600; margin-left: 2px; }}
.solo-delta {{ font-size: 12px; font-weight: 600; margin-left: 2px; }}
.delta-up {{ color: #34d399; }}
.delta-down {{ color: #f87171; }}

/* --- Footer --- */
.footer {{ text-align: center; margin-top: 32px; padding-top: 20px; border-top: 1px solid rgba(148, 163, 184, 0.15); }}
.footer-text {{ font-size: 14px; color: #475569; letter-spacing: 0.5px; }}
.footer-site {{ color: #3b82f6; font-weight: 600; }}
</style></head><body>
<div class="card" id="card">
    <div class="header">
        <div class="card-title">SB19 Monthly Listeners on <span class="spotify">Spotify</span></div>
        <div class="card-date">As of {date_str}</div>
    </div>

    <div class="sb19-panel">
        <div class="sb19-info">
            {sb19_photo_html}
            <div class="sb19-details">
                <div class="sb19-name">SB19</div>
                <div class="sb19-listeners">{sb19_listeners_str} <span>monthly listeners</span></div>
                <div class="sb19-change" style="color: {sb19_change_color};">{sb19_change_str} from previous day <span class="sb19-delta">{sb19_delta_html}</span></div>
            </div>
        </div>
        <div class="chart-label">Last {n} Days</div>
        <div class="chart-container">
            {svg_chart}
        </div>
    </div>

    <div class="section-divider"></div>
    <div class="section-label">Solo Members</div>
    <div class="artists">{solo_rows}
    </div>

    <div class="footer">
        <div class="footer-text"><span class="footer-site">opminsights.com</span></div>
    </div>
</div>
</body></html>"""

    return _render_html_to_screenshot(
        html, "_listeners_card.html", LISTENERS_IMAGE_PATH,
        window_width=1200, window_height=1400,
        max_img_width=2400,
        label="Listeners screenshot",
    )
