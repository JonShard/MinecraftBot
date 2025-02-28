import os
import re
import subprocess
import asyncio
import datetime
import csv
import discord

import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

import config.config as cfg
from utility.logger import get_logger
log = get_logger()
import utility.globals as globals

import tasks.background_tasks as tasks

def get_command(interaction: discord.Interaction) -> str:
    param_values = []
    for param in interaction.command.parameters:
        param_name = param.name  # Get the parameter's name
        param_value = getattr(interaction.namespace, param_name, None)  # Fetch its value
        param_values.append(f"'{param_name}={param_value}'")
    param_string = " ".join(param_values)
    command_string = f"/{interaction.command.qualified_name} {param_string.strip()}"    
    return command_string

async def authorize_interaction(interaction: discord.Interaction) -> bool:
    """
    Checks if the user has at least one of the required admin roles.

    Args:
        interaction (discord.Interaction): The interaction object from the command.

    Returns:
        bool: True if authorized, False if not.
    """
    
   # Is admin whitelisted user?
    if interaction.user.id in cfg.config.bot.admin_users:
        log.info(f"[Auth] Allowed: {interaction.user.name} - {get_command(interaction)}")
        return True
    
    # Has an admin role?
    if interaction.guild is not None:
        # Get the user's roles
        member = await interaction.guild.fetch_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("⛔ Could not find any admin roles for your user.", ephemeral=True)
            log.warning(f"[Auth] DENIED: {interaction.user.name} - {get_command(interaction)}")
            return False
        
        # Check if the user has any of the required admin roles
        admin_role_ids = cfg.config.bot.admin_roles
        if any(role.id in admin_role_ids for role in member.roles):
            log.info(f"[Auth] Allowed: {interaction.user.name} - {get_command(interaction)}")
            return True  # User is authorized
   
    await interaction.response.send_message("⛔ Sorry, you are not authorized to use this command.", ephemeral=True)
    log.warning(f"[Auth] DENIED: {interaction.user.name} - {get_command(interaction)}")
    return False


async def log_interaction(interaction: discord.Interaction):
    log.info(f"[Auth] Open:    {interaction.user.name} - {get_command(interaction)}")


def update_csv_player_count():
        # Attempt to get the latest player count from your global or via RCON
        # (Here we assume you already update 'player_count' in update_server_status,
        #  so we just read that global variable.)

        # If player_count is None or invalid, you could skip or set it to 0
        if globals.player_count is None:
            count_to_log = 0
            log.warning("Warning. Playercount is None")
        else:
            count_to_log = globals.player_count

        # Prepare CSV row data
        # Example: 2025-01-19 20:45, 5
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        row = [timestamp, count_to_log]

        # Write (or append) to the CSV
        write_player_count_csv(row)

def write_player_count_csv(row):
    """
    Appends a single row [timestamp, player_count] to STAT_CSV_PATH.
    If the file doesn't exist, writes a header first.
    """
    log.debug(f"Writing row to {cfg.config.stats.csv_path}: {row}")  # Debug
    file_exists = os.path.isfile(cfg.config.stats.csv_path)

    with open(cfg.config.stats.csv_path, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # If it's a new file, write a header
        if not file_exists:
            writer.writerow(["Timestamp", "PlayerCount"])

        # Append our new row
        writer.writerow(row)


def generate_player_count_graph(graph_window_days = 30):
    """
    Reads the CSV (Timestamp, PlayerCount), groups by day to calculate daily max,
    and plots a column chart (bar chart) saved to PLAYER_COUNT_PNG with a dark theme.
    """
    
    daily_counts = {}

    # 1) Read the CSV data
    if not os.path.isfile(cfg.config.stats.csv_path):
        log.warning("No CSV found to plot.")
        return

    with open(cfg.config.stats.csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)  # Skip header row if present
        for row in reader:
            if len(row) < 2:
                continue
            timestamp_str, count_str = row[0], row[1]
            try:
                # Skip data older than a month
                if (datetime.datetime.now() - datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")).days > graph_window_days:
                    continue
                dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
                count = int(count_str)
            except ValueError:
                continue

            # Group by date (YYYY-MM-DD) and calculate daily max
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in daily_counts:
                daily_counts[date_str] = count
            else:
                daily_counts[date_str] = max(daily_counts[date_str], count)

    # Ensure today's date is included in the plot
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if today not in daily_counts:
        daily_counts[today] = 0  # Assume 0 players for today if no data exists

    if not daily_counts:
        log.warning("No data in CSV to plot.")
        return

    # 2) Prepare data for plotting
    dates = sorted(daily_counts.keys())  # Ensure dates are sorted
    max_counts = [daily_counts[date] for date in dates]

    # Format the dates into the desired format: "short_weekday DD.MM"
    formatted_dates = [
        datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m %a")
        for date in dates
    ]

    # 3) Use a dark style for Discord
    plt.style.use('dark_background')

    plt.figure(figsize=(10, 4))
    plt.bar(formatted_dates, max_counts, color="#00b0f4", label="Daily Max Players", zorder=3)

    # 4) Set the title, labels, and color them white
    plt.title("Daily Max Player Count", color="white")
    plt.xlabel(f"Date ({datetime.datetime.now().year})", color="white")
    plt.ylabel("Players Online", color="white")

    # Rotate x-ticks for readability
    plt.xticks(rotation=45, color="white")

    # Force y-axis ticks to integers
    ax = plt.gca()
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.yticks(color="white")

    # Offset the x-tick labels to align better with the ticks
    for label in ax.get_xticklabels():
        label.set_ha('right')  # Horizontal alignment (use 'left' or 'center')
        label.set_position((0.09, 0))  # Adjust x and y offset 
    
    # Change the color of Sunday labels to red
    for label, date in zip(ax.get_xticklabels(), dates):
        if datetime.datetime.strptime(date, "%Y-%m-%d").weekday() == 6:  # 6 is Sunday
            label.set_color("salmon")
    # Change the color of Sunday bars to a slightly darker blue
    for bar, date in zip(ax.patches, dates):
        if datetime.datetime.strptime(date, "%Y-%m-%d").weekday() == 6:  # 6 is Sunday
            bar.set_color("#005f99")  # Slightly darker blue

    # Add a grid (light gray for contrast)
    plt.grid(True, color="gray", alpha=0.3)

    # Legend with a Discord-like dark gray background
    plt.legend(facecolor="#2f3136", edgecolor="none")

    plt.tight_layout()
    plt.savefig(cfg.config.stats.player_count_png)
    plt.close()
    log.info(f"Saved bar chart to {cfg.config.stats.player_count_png}.")



def generate_lag_graph():
    """
    Plots a bar chart of lag data from globals.lag_history,
    showing seconds of lag per minute over time.
    The X-axis represents time in hours ago format.
    The Y-axis represents lag in seconds.
    """

    now = datetime.datetime.now()
    MAX_MINUTES = 180  # Rolling window of last 6 hours

    # Ensure a full 6-hour window (one timestamp per minute)
    timestamps = [now - datetime.timedelta(minutes=i) for i in range(MAX_MINUTES)][::-1]

    # Ensure lag data has 360 values (older data pushed left, new data added)
    lag_data = ([0] * (MAX_MINUTES - len(globals.lag_history))) + globals.lag_history[-MAX_MINUTES:]

    # Use a dark theme
    plt.style.use("dark_background")

    plt.figure(figsize=(12, 4))
    plt.bar(range(MAX_MINUTES), lag_data, color="#ff4500", label="Lag (seconds)", zorder=3)

    # Format timestamps for major ticks (every hour)
    def format_time(ts):
        delta = now - ts
        hours_ago = int(delta.total_seconds() // 3600)
        return "Now" if ts >= now - datetime.timedelta(minutes=1) else f"{hours_ago +1}h ago"

    tick_positions = list(range(0, MAX_MINUTES, 60)) + [MAX_MINUTES - 1]  # Every hour + "Now" at the last position
    tick_labels = [format_time(timestamps[i]) for i in tick_positions]

    ax = plt.gca()

    # Set major ticks (hourly labels) and minor ticks (every minute)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, color="white")

    ax.set_xticks(range(MAX_MINUTES), minor=True)
    ax.tick_params(axis="x", which="minor", length=3, color="gray")  # Small ticks for each minute

    plt.yticks(color="white")
    plt.xlabel("Time", color="white")
    plt.ylabel("Seconds of Lag", color="white")
    plt.title("Running Behind Errors", color="white")

    # Grid and legend
    plt.grid(True, color="gray", alpha=0.3)
    plt.legend(facecolor="#2f3136", edgecolor="none")

    plt.tight_layout()
    plt.savefig(cfg.config.stats.lag_png)
    plt.close()
    log.info(f"Saved lag chart to {cfg.config.stats.lag_png}.")
    

# ──────────────────────────
# Chat Window Logic
# ──────────────────────────
async def post_or_refresh_chat_window(bot, channel: discord.abc.Messageable):
    """
    If a chat window exists in this channel, delete it.
    Post a fresh code block, and start a background task
    to update it for 5 minutes.
    """

    # 1) Clear out old window if it exists
    if channel.id in globals.chat_windows:
        old_data = globals.chat_windows[channel.id]
        try:
            await old_data["message"].delete()
        except Exception as e:
            log.error(f"Could not delete old chat window in channel {channel.id}: {e}")

        # Stop the old task
        if old_data["task"]:
            old_data["task"].cancel()
        del globals.chat_windows[channel.id]

    # 2) Create a new message
    lines = get_recent_chat_lines(cfg.config.bot.chat.lines)
    joined = "\n".join(lines)
    content = f"```text\n{joined}\n```"

    new_msg = await channel.send(content=content)

    # 3) Setup state in CHAT_WINDOWS
    expires_at = asyncio.get_event_loop().time() + cfg.config.bot.chat.duration_min * 60 # 60 sec in a minute
    task = bot.loop.create_task(tasks.background_chat_update_task(channel.id))

    globals.chat_windows[channel.id] = {
        "message": new_msg,
        "expires_at": expires_at,
        "task": task
    }

# ──────────────────────────
# Chat Log Scraping
# ──────────────────────────

def get_recent_chat_lines(limit=10):
    """
    - Gathers lines from *.log / *.log.gz (excluding debug logs).
    - Extracts the date/time from each line (e.g. "[19Jan2025 20:04:15.335]").
    - Sorts all matching lines chronologically by that datetime.
    - Returns the last `limit` lines, each formatted as "HH:MM <chat>".
    """
    # Matches lines containing <Name>, [Rcon], or [Server]
    chat_pattern = r'Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (\[Rcon\]|<|\[Server\])'

    # Full pattern to parse date/time:
    # e.g., [19Jan2025 20:04:15.335] [Server thread/INFO] ...
    # We'll capture group(1) as "19Jan2025 20:04:15.335"
    # Later we'll parse that into a datetime object
    full_line_regex = re.compile(
        r'^\[(?P<date>[\d]{1,2}[A-Za-z]{3}\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+)\]\s.*MinecraftServer/\]:\s+(?P<chat>.*)$'
    )

    try:
        # 1) Build file list for *.log* (including .log.gz), excluding debug
        logs_cmd = f'ls -1 "{cfg.config.minecraft.logs_dir}"/*.log* 2>/dev/null || true'
        logs_list = subprocess.check_output(logs_cmd, shell=True).decode(errors="ignore").split()

        # Exclude debug logs
        filtered_logs = [f for f in logs_list if "debug" not in os.path.basename(f).lower()]
        if not filtered_logs:
            return ["No recent chat lines found (no suitable log files)."]

        # 2) zgrep lines matching chat_pattern from all these logs
        #    We won't pipe to `tail` here because we need to parse and globally sort.
        file_paths = " ".join(f'"{path}"' for path in filtered_logs)
        grep_cmd = f'zgrep -Eh "{chat_pattern}" {file_paths}'
        raw_output = subprocess.check_output(grep_cmd, shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore")

        if not raw_output.strip():
            return ["No recent chat lines found."]
    except subprocess.CalledProcessError:
        return ["No recent chat lines found."]
    except Exception as e:
        return [f"Error retrieving chat lines: {e}"]

    # 3) Parse each line, extracting date/time + chat text
    lines_with_dt = []
    for line in raw_output.splitlines():
        m = full_line_regex.match(line)
        if not m:
            # If the line doesn't match exactly, skip or do a fallback
            # We'll do a fallback parse that tries to remove the prefix
            fallback_chat = re.sub(r'^.*MinecraftServer/\]:\s+', '', line).strip()
            # We'll store "None" for dt so we can still keep the line if needed
            lines_with_dt.append((None, fallback_chat))
            continue

        date_str = m.group("date")   # e.g. "19Jan2025 20:04:15.335"
        chat_msg = m.group("chat")   # e.g. "[Rcon]  jonshard: test5"

        # 4) Convert date_str into a Python datetime. For example "19Jan2025 20:04:15.335"
        #    We'll parse "DDMonYYYY HH:MM:SS.mmm"
        #    Example format: "19Jan2025 20:04:15.335"
        try:
            # Build a datetime format string: day(2) abbreviated month(3) year(4) hour(2):minute(2):second(2).millis
            dt = datetime.datetime.strptime(date_str, "%d%b%Y %H:%M:%S.%f")
        except ValueError:
            # Fallback if we can't parse for some reason
            dt = None

        # Store (dt, chat_msg) for sorting
        lines_with_dt.append((dt, chat_msg.strip()))

    # 5) Sort lines by dt (None goes first). We'll ensure lines with valid dt are at the end:
    #    We want chronological order, so we can do:
    lines_with_dt.sort(key=lambda x: (x[0] is None, x[0]))

    # 6) Keep only the last `limit` lines
    #    i.e. the most recent lines
    lines_with_dt = lines_with_dt[-limit:]

    # 7) Format each line as "HH:MM <chat>"
    #    If dt is None, we omit the time or do "??:??"
    final = []
    for (dt, msg) in lines_with_dt:
        if dt is not None:
            hhmm = dt.strftime("%H:%M")
            final.append(f"{hhmm} {msg}")
        else:
            final.append(msg)

    return final


async def repost_chat_window(bot, interaction):
        # "Move" the chat window if it exists in this channel
        channel_id = interaction.channel.id
        if channel_id in globals.chat_windows:
            # Extend the timer (reset 5-minute countdown)
            globals.chat_windows[channel_id]["expires_at"] = asyncio.get_event_loop().time() + cfg.config.bot.chat.duration_min * 60 # 60 sec in a minute
            # Delete and repost to put it at the bottom
            await post_or_refresh_chat_window(bot, interaction.channel)
            log.info(f"Chat window moved to bottom after /say in channel {channel_id}.")


def validate_string(
    name: str, 
    min_length: int = 1, 
    max_length: int = 20, 
    strict_alphanumeric: bool = True, 
    strict_spaces: bool = False
) -> str:
    """
    Validates a name string based on given criteria.
    
    Args:
        name (str): The name to validate.
        min_length (int): The minimum allowed length.
        max_length (int): The maximum allowed length.
        strict_alphanumeric (bool): If True, restrict to letters, numbers, dashes, and underscores.
        strict_spaces (bool): If False, spaces are allowed in the name.

    Returns:
        str: An error message if invalid; otherwise, an empty string.
    """
    # Check length constraints
    if len(name) < min_length:
        return f"Name must be at least {min_length} characters long."
    if len(name) > max_length:
        return f"Name cannot exceed {max_length} characters."

    # Construct regex based on `allow_spaces`
    pattern = r"^[a-zA-Z0-9 _-]+$" if not strict_spaces else r"^[a-zA-Z0-9_-]+$"

    # Check strict alphanumeric restriction
    if strict_alphanumeric and not re.match(pattern, name):
        if not strict_spaces:
            return "Name can only contain letters, numbers, dashes, underscores, and spaces."
        else:
            return "Name can only contain letters, numbers, dashes, and underscores."

    # If all checks pass
    return ""



def sanitize_string(name: str, replace_whitespace: bool = True, to_lowercase: bool = False) -> str:
    """
    Sanitizes a name by optionally replacing whitespace with underscores and converting to lowercase.

    Args:
        name (str): The name to sanitize.
        replace_whitespace (bool): If True, replaces spaces, tabs, and other whitespace with underscores.
        to_lowercase (bool): If True, converts the input string to lowercase.

    Returns:
        str: The sanitized name.
    """
    # Replace whitespace with underscores if enabled
    if replace_whitespace:
        name = re.sub(r"\s+", "_", name)  # Replace all whitespace (spaces, tabs, etc.) with underscores
    
    # Convert to lowercase if enabled
    if to_lowercase:
        name = name.lower()
    
    # Remove newlines and carriage returns
    sanitized = name.replace("\n", "").replace("\r", "")
    
    return sanitized


def validate_timestamp(before_date: str) -> datetime:
    """
    Validates and parses a timestamp string into a datetime object.

    Supported formats:
    - HH:MM
    - H:MM (adds leading 0 if missing)
    - DD-MM
    - HH:MM DD-MM
    - H:MM DD-MM (adds leading 0 if missing)
    - DD-MM-YYYY

    Args:
        before_date (str): The input string to validate and parse.

    Returns:
        datetime: The parsed timestamp.

    Raises:
        ValueError: If the format is invalid or the date is in the future.
    """
    now = datetime.datetime.now()

    if before_date:
        # Add leading zero to hour if missing
        before_date = re.sub(r"(^|\s)(\d):", r"\g<1>0\g<2>:", before_date)

        # Handle HH:MM format
        if re.match(r"^\d{2}:\d{2}$", before_date):
            time_part = datetime.datetime.strptime(before_date, "%H:%M").time()
            timestamp = datetime.datetime.combine(now.date(), time_part)

        # Handle DD-MM format
        elif re.match(r"^\d{2}-\d{2}$", before_date):
            timestamp = datetime.datetime.strptime(before_date, "%d-%m").replace(year=now.year)

        # Handle HH:MM DD-MM format
        elif re.match(r"^\d{2}:\d{2} \d{2}-\d{2}$", before_date):
            time_str, date_str = before_date.split(" ")
            time_part = datetime.datetime.strptime(time_str, "%H:%M").time()
            date_part = datetime.datetime.strptime(date_str, "%d-%m").replace(year=now.year)
            timestamp = datetime.datetime.combine(date_part, time_part)

        # Handle DD-MM-YYYY format
        elif re.match(r"^\d{2}-\d{2}-\d{4}$", before_date):
            timestamp = datetime.datetime.strptime(before_date, "%d-%m-%Y")

        else:
            raise ValueError("Invalid format")

        # Ensure the timestamp is not in the future
        if timestamp > now:
            raise ValueError("Specified time cannot be in the future.")

        return timestamp
    return now


timestamp_regex = None
def extract_timestamp(log_line):
    global timestamp_regex
    if timestamp_regex is None:
        timestamp_regex = re.compile(
            r'^\[(?P<day>\d{1,2})(?P<month>[a-zA-Z]{3})\.?(?P<year>\d{4}) (?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\.(?P<millis>\d+)\]'
        )
    # Extract matched timestamp
    ts_match = timestamp_regex.match(log_line)
    if ts_match:
        log_day = ts_match.group("day")
        log_month = ts_match.group("month").capitalize()
        log_year = ts_match.group("year")
        log_time = f"{ts_match.group('hour')}:{ts_match.group('minute')}:{ts_match.group('second')}.{ts_match.group('millis')}"

        log_timestamp_str = f"{log_day}{log_month}{log_year} {log_time}"
        return datetime.datetime.strptime(log_timestamp_str, "%d%b%Y %H:%M:%S.%f")
    return None