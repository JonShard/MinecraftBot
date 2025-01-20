#!/usr/bin/env python3

import os
import re
import tarfile
import csv
import datetime
import gzip

# ─────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────

LOGS_DIR = "/mnt/SSD120GB/phonix/PhoenixDenPack2025/logs/"          # Directory containing *.tar.gz files
OUTPUT_CSV = "stats_rebuilt.csv"    # The CSV we want to populate with historical data

# Regex to capture bracketed date/time plus "username joined/left the game"
# Example lines:
# [20Jan2025 11:24:46.081] [Server thread/INFO] [...]: jonemartin joined the game
# [20Jan2025 11:24:18.509] [Server thread/INFO] [...]: jonemartin left the game
JOIN_LEFT_PATTERN = re.compile(
    r'^\[(?P<dt>\d{1,2}[A-Za-z]{3}\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+)\]\s.*?:\s+(?P<user>\S+)\s+(?P<action>joined|left)\sthe game'
)

# Regex to detect server restarts
# Example:
# [20Jan2025 05:00:41.632] [Server thread/WARN] [ModernFix/]: Dedicated server took 37.64 seconds to load
RESTART_PATTERN = re.compile(
    r'^\[(?P<dt>\d{1,2}[A-Za-z]{3}\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+)\].*Dedicated server took .* to load'
)

DATETIME_FORMAT = "%d%b%Y %H:%M:%S.%f"  # e.g. 20Jan2025 11:24:46.081

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    # 1. Collect all .log.gz files
    gz_files = sorted(
        f for f in os.listdir(LOGS_DIR)
        if f.endswith(".log.gz")
    )
    if not gz_files:
        print(f"No *.log.gz files found in {LOGS_DIR}.")
        return

    # We'll store all events in memory to sort them by time:
    # events = [ (datetime_obj, "join"/"left"/"restart", username_or_None) ]
    events = []

    # 2. Parse each .log.gz for joined/left/restart lines
    for filename in gz_files:
        full_path = os.path.join(LOGS_DIR, filename)
        print(f"Reading {full_path}...")
        with gzip.open(full_path, "rt", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")

                # joined/left
                m_jl = JOIN_LEFT_PATTERN.match(line)
                if m_jl:
                    dt_str = m_jl.group("dt")
                    user = m_jl.group("user")
                    action = m_jl.group("action")  # "joined" or "left"
                    dt_obj = parse_datetime(dt_str)
                    if dt_obj:
                        etype = "join" if action == "joined" else "left"
                        events.append((dt_obj, etype, user))
                    continue

                # restart
                m_rs = RESTART_PATTERN.match(line)
                if m_rs:
                    dt_str = m_rs.group("dt")
                    dt_obj = parse_datetime(dt_str)
                    if dt_obj:
                        events.append((dt_obj, "restart", None))
                    continue

    if not events:
        print("No events found in any log. Exiting.")
        return

    # 3. Sort events by datetime
    events.sort(key=lambda x: x[0])

    # 4. Replay them => produce [timestamp, count] rows
    reconstructed = replay_events(events)

    # 5. Append to CSV
    append_to_csv(reconstructed, OUTPUT_CSV)
    print(f"Appended {len(reconstructed)} new rows to {OUTPUT_CSV}.")


def parse_datetime(dt_str):
    """Parse date/time string like '20Jan2025 11:24:46.081' -> datetime obj or None."""
    try:
        return datetime.datetime.strptime(dt_str, DATETIME_FORMAT)
    except ValueError:
        return None

def replay_events(events):
    """
    events: sorted list of (dt, evtype, user)
    evtype in ("join", "left", "restart")
    user is a string or None
    We maintain a set of online players. On 'join', add user. On 'left', remove user.
    On 'restart', clear the set.
    Each time the set size changes, record [dt_str, count].
    Return list of (timestamp_str, count).
    """
    online = set()
    output = []
    last_count = 0

    for (dt, evtype, user) in events:
        if evtype == "join":
            online.add(user)
        elif evtype == "left":
            if user in online:
                online.remove(user)
        elif evtype == "restart":
            online.clear()
        else:
            # unknown
            continue

        current_count = len(online)
        if current_count != last_count:
            # record a new row
            ts_str = dt.strftime("%Y-%m-%d %H:%M")
            output.append((ts_str, current_count))
            last_count = current_count

    return output

def append_to_csv(rows, csv_path):
    """
    rows: list of (timestamp_str, count)
    Append them to csv_path, creating a header if not found.
    """
    if not rows:
        return
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["Timestamp", "PlayerCount"])
        for (ts, cnt) in rows:
            writer.writerow([ts, cnt])

# ─────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
