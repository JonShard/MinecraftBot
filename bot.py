import os
import re
import subprocess
import asyncio

import discord
from discord.ext import commands
from discord import app_commands
from mcrcon import MCRcon

# ──────────────────────────
# Configuration Variables
# ──────────────────────────

BOT_TOKEN = "MTA4MTg1Nzc5OTc5NDk4NzA0OQ.GY1gHU.Zr8kWU4WXIN_Yx2JAjr3M3J2NBjVw8XkO4noC8"
SERVER_IP = "192.168.50.213"
RCON_PORT = 25575
RCON_PASSWORD = "srep"  # RCON password

MC_SERVER_PATH = "/mnt/SSD120GB/phonix/PhoenixDenPack2025"
LOGS_DIR = os.path.join(MC_SERVER_PATH, "logs")
CRASH_REPORTS_DIR = os.path.join(MC_SERVER_PATH, "crash-reports")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "latest.log")

BACKUP_PATH = "/var/mcbackup/"
DISK_PATHS = ["/dev/sda2", "/dev/sdb"]
LATEST_LOG_LINES = 4
UPDATE_INTERVAL = 3

# How often to refresh the chat window in seconds
CHAT_UPDATE_INTERVAL = 5
# How long the chat window remains active in seconds (15 minutes)
CHAT_DURATION = 900

# ──────────────────────────
# Global RCON + Discord Setup
# ──────────────────────────

player_count = 0
ext_chunk_count = 0
mcr_connection = None

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

# For the /command whitelist:
ALLOWED_USERS = [123456789012345678, 987654321098765432]

# ──────────────────────────
# Single Chat Window *per channel*
# ──────────────────────────
# We'll store data in a dictionary keyed by channel ID:
#   channel_id -> {
#       "message": discord.Message,
#       "expires_at": float,
#       "task": asyncio.Task
#   }

CHAT_WINDOWS = {}

# ──────────────────────────
# RCON Utilities
# ──────────────────────────

def ensure_rcon_connection():
    """Ensure we have a persistent RCON connection."""
    global mcr_connection
    if mcr_connection is not None:
        return
    try:
        conn = MCRcon(SERVER_IP, RCON_PASSWORD, port=RCON_PORT)
        conn.connect()
        mcr_connection = conn
        print("RCON: Connected successfully.")
    except Exception as e:
        print(f"RCON: Failed to connect: {e}")
        mcr_connection = None

def close_rcon_connection():
    """Close the RCON connection if open."""
    global mcr_connection
    if mcr_connection:
        try:
            mcr_connection.disconnect()
        except Exception as e:
            print(f"RCON: Error while disconnecting: {e}")
        mcr_connection = None

def get_player_count_from_rcon():
    """Get the current online player count from 'list'."""
    global mcr_connection
    ensure_rcon_connection()
    if mcr_connection is None:
        return None
    try:
        response = mcr_connection.command("list")
        match = re.search(r"There are (\d+) of a max of \d+ players online", response)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"RCON: Command error: {e}")
        close_rcon_connection()
    return None

# ──────────────────────────
# Chat Log Scraping
# ──────────────────────────

def get_recent_chat_lines(limit=10):
    """
    Use zgrep to find lines containing <Name>, [Rcon], or [Server].
    Tail the last 'limit' lines, remove timestamps/prefix.
    """
    chat_pattern = r'Server thread/INFO\] \[net\.minecraft\.server\.MinecraftServer/\]: (\[Rcon\]|<|\[Server\])'

    try:
        # Search .log and .log.gz files in LOGS_DIR:
        # -E extended regex, -h (omit filenames), tail -n {limit}
        cmd = f'zgrep -Eh "{chat_pattern}" "{LOGS_DIR}"/*.log* | tail -n {limit}'
        chat_lines = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode(errors="ignore")
    except subprocess.CalledProcessError:
        # No matches
        return ["No recent chat lines found."]
    except Exception as e:
        return [f"Error retrieving chat lines: {e}"]

    if not chat_lines.strip():
        return ["No recent chat lines found."]

    # Remove everything before the actual chat portion
    cleaned = []
    line_pattern = re.compile(r'^.*MinecraftServer/\]:\s+(.*)$')
    for line in chat_lines.splitlines():
        m = line_pattern.match(line)
        if m:
            cleaned.append(m.group(1).strip())
        else:
            cleaned.append(line.strip())

    return cleaned[-limit:]

# ──────────────────────────
# Chat Window Logic
# ──────────────────────────

async def post_or_refresh_chat_window(channel: discord.abc.Messageable):
    """
    If a chat window exists in this channel, delete it.
    Post a fresh code block, and start a background task
    to update it for 5 minutes.
    """
    channel_id = channel.id

    # 1) Clear out old window if it exists
    if channel_id in CHAT_WINDOWS:
        old_data = CHAT_WINDOWS[channel_id]
        try:
            await old_data["message"].delete()
        except Exception as e:
            print(f"Could not delete old chat window in channel {channel_id}: {e}")

        # Stop the old task
        if old_data["task"]:
            old_data["task"].cancel()
        del CHAT_WINDOWS[channel_id]

    # 2) Create a new message
    lines = get_recent_chat_lines(10)
    joined = "\n".join(lines)
    content = f"```text\n{joined}\n```"

    new_msg = await channel.send(content=content)

    # 3) Setup state in CHAT_WINDOWS
    expires_at = asyncio.get_event_loop().time() + CHAT_DURATION
    task = bot.loop.create_task(background_chat_update_task(channel_id))

    CHAT_WINDOWS[channel_id] = {
        "message": new_msg,
        "expires_at": expires_at,
        "task": task
    }

async def background_chat_update_task(channel_id: int):
    """
    Repeatedly update the chat window in this channel
    until the 5-minute timer expires.
    """
    while True:
        await asyncio.sleep(CHAT_UPDATE_INTERVAL)
        # If the window is missing or removed from dict, stop
        if channel_id not in CHAT_WINDOWS:
            return

        data = CHAT_WINDOWS[channel_id]
        now = asyncio.get_event_loop().time()

        # Time up?
        if now > data["expires_at"]:
            # Delete the chat message
            try:
                await data["message"].delete()
            except Exception as e:
                print(f"Failed to delete expired chat window in channel {channel_id}: {e}")
            del CHAT_WINDOWS[channel_id]
            print(f"Chat window in channel {channel_id} expired.")
            return

        # Otherwise, update the message
        lines = get_recent_chat_lines(10)
        joined = "\n".join(lines)
        new_content = f"```text\n{joined}\n```"
        try:
            await data["message"].edit(content=new_content)
        except Exception as e:
            print(f"Failed to edit chat window in channel {channel_id}: {e}")
            # Remove and stop
            del CHAT_WINDOWS[channel_id]
            return

# ──────────────────────────
# Slash Commands
# ──────────────────────────

@bot.tree.command(name="chat", description="Show a single chat window for the last 10 lines.")
async def slash_chat(interaction: discord.Interaction):
    """
    Creates (or recreates) one chat window in this channel (DM or text).
    Keeps refreshing for 5 minutes.
    """
    # Acknowledge command
    await interaction.response.defer(ephemeral=False, thinking=True)
    # Post/refresh
    await post_or_refresh_chat_window(interaction.channel)
    # Let user know
    await interaction.followup.send("Chat window created or refreshed for this channel.", ephemeral=False)

@bot.tree.command(name="say", description="Send a chat message to the server from Discord.")
@app_commands.describe(message="The message to send")
async def slash_say(interaction: discord.Interaction, message: str):
    """
    Send /say to the server with a color-coded prefix,
    then move the chat window to the bottom if it exists in this channel.
    """
    ensure_rcon_connection()
    if mcr_connection is None:
        await interaction.response.send_message("Could not connect to RCON. Try again later.", ephemeral=True)
        return

    try:
        # Format text for Minecraft
        say_string = f"§7§o{interaction.user.name}: {message}§r"
        mcr_connection.command(f"say {say_string}")
        await interaction.response.send_message(
            f"Sent to server chat:\n`{interaction.user.name}: {message}`",
            ephemeral=False
        )
    except Exception as e:
        close_rcon_connection()
        await interaction.response.send_message(f"Failed to send message: {e}", ephemeral=True)
        return

    # "Move" the chat window if it exists in this channel
    channel_id = interaction.channel.id
    if channel_id in CHAT_WINDOWS:
        # Extend the timer (reset 5-minute countdown)
        CHAT_WINDOWS[channel_id]["expires_at"] = asyncio.get_event_loop().time() + CHAT_DURATION
        # Delete and repost to put it at the bottom
        await post_or_refresh_chat_window(interaction.channel)
        print(f"Chat window moved to bottom after /say in channel {channel_id}.")





@bot.tree.command(name="command", description="Execute an RCON command on the server")
@app_commands.describe(rcon_command="The RCON command to run on the server.")
async def slash_rcon_command(interaction: discord.Interaction, rcon_command: str):
    """Runs an RCON command if the user is on the ALLOWED_USERS whitelist."""
    if interaction.user.id not in ALLOWED_USERS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.", ephemeral=True)
        return

    ensure_rcon_connection()
    if mcr_connection is None:
        await interaction.response.send_message("Could not connect to RCON. Try again later.", ephemeral=True)
        return

    try:
        response = mcr_connection.command(rcon_command)
        reply = f"Command executed: `{rcon_command}`"
        if response.strip():
            reply += f"\nResponse: ```{response}```"
        await interaction.response.send_message(reply, ephemeral=False)
    except Exception as e:
        close_rcon_connection()
        await interaction.response.send_message(f"RCON command failed: {e}", ephemeral=True)

@bot.tree.command(name="status", description="Show the Minecraft server status")
async def slash_status(interaction: discord.Interaction):
    """Same logic you already have for /status."""
    try:
        # ... your existing code ...
        await interaction.response.send_message("Status placeholder", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# ──────────────────────────
# Background Task: Status Presence
# ──────────────────────────

async def update_server_status():
    global player_count, ext_chunk_count
    while True:
        try:
            count = get_player_count_from_rcon()
            if count is not None:
                player_count = count

            with open(LOG_FILE_PATH, 'r') as log_file:
                log_contents = log_file.read()
            ext_chunk_count = len(re.findall(r'Saving oversized chunk', log_contents))

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

        await bot.change_presence(activity=discord.Game(status_message))
        await asyncio.sleep(UPDATE_INTERVAL)

# ──────────────────────────
# Bot Lifecycle
# ──────────────────────────

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")

    ensure_rcon_connection()
    bot.loop.create_task(update_server_status())
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

bot.run(BOT_TOKEN)
