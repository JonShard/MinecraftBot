import os
import re
import subprocess
import asyncio
import discord
from mcrcon import MCRcon

# ──────────────────────────
# Configuration Variables
# ──────────────────────────

BOT_TOKEN = "MTA4MTg1Nzc5OTc5NDk4NzA0OQ.GY1gHU.Zr8kWU4WXIN_Yx2JAjr3M3J2NBjVw8XkO4noC8"
SERVER_IP = "192.168.50.213"
RCON_PORT = 25575
RCON_PASSWORD = "srep"  # Replace with your RCON password

MC_SERVER_PATH = "/mnt/SSD120GB/phonix/PhoenixDenPack2025"  # Base directory for Minecraft server
LOGS_DIR = os.path.join(MC_SERVER_PATH, "logs")
CRASH_REPORTS_DIR = os.path.join(MC_SERVER_PATH, "crash-reports")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "latest.log")

BACKUP_PATH = "/var/mcbackup/"
DISK_PATHS = ["/dev/sda2", "/dev/sdb"]
LATEST_LOG_LINES = 4       # Number of latest log lines to include
UPDATE_INTERVAL = 3        # Seconds between status updates

# ──────────────────────────
# Global State
# ──────────────────────────
player_count = 0
ext_chunk_count = 0
mcr_connection = None  # Global RCON connection

intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)

# ──────────────────────────
# RCON Connection Utilities
# ──────────────────────────

def ensure_rcon_connection():
    """
    Ensures there is an active RCON connection in `mcr_connection`.
    If the connection is missing or broken, it attempts to (re)connect.
    """
    global mcr_connection

    # If we already have a connection, assume it's still good
    if mcr_connection is not None:
        return

    # Otherwise, create a new connection
    try:
        temp_conn = MCRcon(SERVER_IP, RCON_PASSWORD, port=RCON_PORT)
        temp_conn.connect()
        mcr_connection = temp_conn
        print("RCON: Connected successfully.")
    except Exception as e:
        print(f"RCON: Failed to connect: {e}")
        mcr_connection = None

def get_player_count_from_rcon():
    """
    Uses the persistent RCON connection to run 'list' and parse the online player count.
    Returns an integer count or None if there was a failure.
    """
    global mcr_connection

    ensure_rcon_connection()
    if mcr_connection is None:
        return None  # Could not connect

    try:
        response = mcr_connection.command("list")
        match = re.search(r"There are (\d+) of a max of \d+ players online", response)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"RCON: Command error: {e}")
        # If there's an error, close the connection so next time we try again
        close_rcon_connection()

    return None

def close_rcon_connection():
    """
    Closes the global RCON connection if it's open.
    """
    global mcr_connection
    if mcr_connection:
        try:
            mcr_connection.disconnect()
        except Exception as e:
            print(f"RCON: Error while disconnecting: {e}")
        mcr_connection = None

# ──────────────────────────
# Discord Bot
# ──────────────────────────

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    global ext_chunk_count

    if message.content in ("!status", "stat"):
        print("!status")
        try:
            # Gather system/server information
            ps_output = subprocess.check_output(['ps', '-eo', 'pid,comm,etime']).decode()
            java_process_line = [line for line in ps_output.split('\n') if 'java' in line][0]
            uptime = java_process_line.split()[-1]

            disk_space = subprocess.check_output(['df'] + DISK_PATHS + ['-h']).decode()
            backup_size = subprocess.check_output(['du', BACKUP_PATH, '-sch']).decode()
            machine_uptime = subprocess.check_output(['uptime']).decode()
            memory_usage = subprocess.check_output(['free', '-h']).decode()
            latest_logs = subprocess.check_output(['tail', '-n', str(LATEST_LOG_LINES), LOG_FILE_PATH]).decode()

            # Players who joined today
            players_today_cmd = (
                f"(zcat {LOGS_DIR}/$(date +'%Y-%m'-%d)*.log.gz && cat {os.path.join(LOGS_DIR, 'latest.log')}) "
                f"| grep joined | awk '{{print $6}}' | sort -u"
            )
            players_today = subprocess.check_output([players_today_cmd], shell=True).decode()
            players_today_count = players_today.count("\n")

            # Crash reports
            crashes_cmd = (
                f"head -n 4 {CRASH_REPORTS_DIR}/* | grep -E 'Time: ' | awk '{{print $2 \" \" $3}}' | tail -n 5"
            )
            crashes_times = subprocess.check_output([crashes_cmd], shell=True).decode() or "No crashes yet! <3"

            # Detect lag occurrences
            with open(LOG_FILE_PATH, 'r') as log_file:
                log_contents = log_file.read()
            lag_occurrences = len(re.findall(r'Running \d+ms or \d+ ticks behind', log_contents))

            # Average ms behind
            ms_values = [int(match) for match in re.findall(r'Running (\d+)ms or \d+ ticks behind', log_contents)]
            average_ms = sum(ms_values) / len(ms_values) if ms_values else 0

            # Total missed ticks
            total_missed_ticks = sum(
                int(match) for match in re.findall(r'Running \d+ms or (\d+) ticks behind', log_contents)
            )

            output = (
                f"MC Uptime: `{uptime}`\n"
                f"Player Count: `{player_count}`\n"
                # Keep the trailing space before the code block for Discord formatting:
                f"Players Today: `{players_today_count}` ```\n{players_today} ```"
                f"Last 5 crashes: ```\n{crashes_times}\n```"
                f"Disk space:```\n{disk_space}```"
                f"Backup size:```\n{backup_size}```"
                f"Machine uptime:```\n{machine_uptime}```"
                f"Memory usage:```\n{memory_usage}```"
                f"Latest logs:```\n{latest_logs}```"
                f"Running behind count: `{lag_occurrences}`\n"
                f"Average ms: `{average_ms:.0f}` ms\n"
                f"Total missed seconds: `{total_missed_ticks * 50 / 1000}`\n"
                f"Saving external chunk log count: `{ext_chunk_count}`"
            )
        except Exception as e:
            output = f"An error occurred: {str(e)}"

        await message.channel.send(output)
        print("Done")


async def update_server_status():
    global player_count
    global ext_chunk_count

    try:
        # Use persistent RCON connection to get player count
        count = get_player_count_from_rcon()
        if count is not None:
            player_count = count

        # Check for external chunk saving
        with open(LOG_FILE_PATH, 'r') as log_file:
            log_contents = log_file.read()
        ext_chunk_count = len(re.findall(r'Saving oversized chunk', log_contents))

        # Construct presence message
        if ext_chunk_count:
            status_message = f"External chunks! ({ext_chunk_count})"
        else:
            lines = log_contents.splitlines()
            latest_log = lines[-1] if lines else ""
            lag_ms_match = re.search(r'Running (\d+)ms or \d+ ticks behind', latest_log)

            if lag_ms_match:
                ms_value = int(lag_ms_match.group(1))
                status_message = f"{player_count} players online ({ms_value / 1000:.1f} sec behind)"
            else:
                status_message = f"{player_count} players online"

    except Exception as e:
        print(f"Error updating status: {e}")
        status_message = "Server is offline"

    await client.change_presence(activity=discord.Game(status_message))

async def main():
    # Connect once at startup (will retry if needed later)
    ensure_rcon_connection()

    # Start the bot
    asyncio.create_task(client.start(BOT_TOKEN))
    await asyncio.sleep(10)  # Give the bot time to connect

    # Periodically update server status
    while True:
        asyncio.create_task(update_server_status())
        await asyncio.sleep(UPDATE_INTERVAL)

asyncio.run(main())
