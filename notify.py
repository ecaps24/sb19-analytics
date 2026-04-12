"""
Simple notification utility for scheduled task failures.
Logs to notifications.log and optionally shows a Windows toast notification.

Usage:
    python notify.py "FAILED: task_name at date time"
"""

import sys
import os
from datetime import datetime


def notify(message: str) -> None:
    """Log the message and attempt to show a Windows toast notification."""
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notifications.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"

    # Always log to file
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)

    print(log_entry.strip())

    # Try Windows toast notification via plyer
    try:
        from plyer import notification as toast
        toast.notify(
            title="SB19 Analytics Alert",
            message=message[:256],  # Toast messages have length limits
            app_name="SB19 Analytics",
            timeout=10,
        )
    except ImportError:
        pass  # plyer not installed, log-only mode
    except Exception:
        pass  # Toast failed (e.g., no GUI), log-only mode


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python notify.py \"message\"")
        sys.exit(1)
    notify(" ".join(sys.argv[1:]))
