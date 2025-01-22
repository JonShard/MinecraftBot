import os
import re
import time
import subprocess
import asyncio
import datetime
import csv


import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

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

STAT_CSV_PATH = "stats.csv"
STAT_CSV_INTERVAL = 900
PLAYER_COUNT_PNG = "stat_players.png"

SERVICE_NAME = "phoenix.service"  # Parameterize your MC service name here

BACKUP_PATH = "/var/mcbackup/"
DISK_PATHS = ["/dev/sda2", "/dev/sdb"]
LATEST_LOG_LINES = 4
UPDATE_INTERVAL = 3

# How often to refresh the chat window in seconds
CHAT_UPDATE_INTERVAL = 5
# How long the chat window remains active in seconds (15 minutes)
CHAT_DURATION = 900
# How many lines of chat in code block
CHAT_LINES = 10 

# For the commands that cause changes:
ADMIN_USERS = [257785837813497856, # TwistedAro
               209382762971398144, # Algodoogle
               300930955579752448, # EarthFishy
               191561233755799554] # JonShard

# ──────────────────────────
# Global RCON + Discord Setup
# ──────────────────────────

player_count = 0
ext_chunk_count = 0
mcr_connection = None

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

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
        logs_cmd = f'ls -1 "{LOGS_DIR}"/*.log* 2>/dev/null || true'
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
    lines = get_recent_chat_lines(CHAT_LINES)
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


@bot.tree.command(name="kill", description="🔒 Kill specific types of entities in the Minecraft world.")
@app_commands.describe(target="What to kill (items, vanilla_animals, vanilla_monsters, vanilla_villagers).")
@app_commands.choices(target=[
    discord.app_commands.Choice(name="items", value="items"),
    discord.app_commands.Choice(name="vanilla_animals", value="vanilla_animals"),
    discord.app_commands.Choice(name="vanilla_monsters", value="vanilla_monsters"),
    discord.app_commands.Choice(name="vanilla_villagers", value="vanilla_villagers"),
])
async def slash_kill(interaction: discord.Interaction, target: str):
    """
    Kills specific types of entities in the Minecraft world based on the selected target.
    - items: Kills all dropped items.
    - vanilla_animals: Kills all passive vanilla animals and snowmen.
    - vanilla_monsters: Kills all hostile mobs.
    - vanilla_villagers: Kills villagers, wandering traders, and golems.
    """
    await interaction.response.defer(ephemeral=False, thinking=True)

    # Authorization (whitelist)
    if interaction.user.id not in ADMIN_USERS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.", ephemeral=True)
        return  

    ensure_rcon_connection()
    if mcr_connection is None:
        await interaction.followup.send("Could not connect to RCON. Try again later.", ephemeral=True)
        return

    try:
        response_lines = []
        if target == "items":
            response = mcr_connection.command("kill @e[type=minecraft:item]")
            response_lines.append(f"`{response.strip()}` - Cleared all dropped items.")

        elif target == "vanilla_animals":
            animal_types = [
                "minecraft:cow", "minecraft:sheep", "minecraft:chicken", "minecraft:pig",
                "minecraft:horse", "minecraft:donkey", "minecraft:llama", "minecraft:mooshroom",
                "minecraft:rabbit", "minecraft:cat", "minecraft:wolf", "minecraft:parrot",
                "minecraft:fox", "minecraft:frog", "minecraft:turtle", "minecraft:snow_golem"
            ]
            for entity in animal_types:
                response = mcr_connection.command(f"kill @e[type={entity}]")
                if not response.startswith("No entity was found"):
                    response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

        elif target == "vanilla_monsters":
            monster_types = [
                "minecraft:zombie", "minecraft:skeleton", "minecraft:creeper", "minecraft:spider",
                "minecraft:enderman", "minecraft:witch", "minecraft:slime", "minecraft:ghast",
                "minecraft:blaze", "minecraft:phantom", "minecraft:silverfish", "minecraft:drowned",
                "minecraft:ravager", "minecraft:vindicator", "minecraft:illusioner", "minecraft:evoker",
                "minecraft:husk", "minecraft:warden", "minecraft:zombified_piglin", "minecraft:shulker",
                "minecraft:magma_cube", "minecraft:hoglin", "minecraft:stray", "minecraft:pillager",
                "minecraft:guardian", "minecraft:elder_guardian", "minecraft:piglin", "minecraft:piglin_brute"
            ]
            for entity in monster_types:
                response = mcr_connection.command(f"kill @e[type={entity}]")
                if not response.startswith("No entity was found"):
                    response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

        elif target == "vanilla_villagers":
            villager_types = [
                "minecraft:villager", "minecraft:wandering_trader",
                "minecraft:iron_golem", "minecraft:snow_golem"
            ]
            for entity in villager_types:
                response = mcr_connection.command(f"kill @e[type={entity}]")
                if not response.startswith("No entity was found"):
                    response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

        else:
            await interaction.followup.send("Invalid target. Please choose a valid option.", ephemeral=True)
            return

        # Combine all responses into a single message
        final_response = "\n".join(response_lines) if response_lines else "No entities were found to kill."
        await interaction.followup.send(final_response, ephemeral=False)

    except Exception as e:
        close_rcon_connection()
        await interaction.followup.send(f"Failed to execute kill command: {e}", ephemeral=True)






@bot.tree.command(name="server", description="🔒 Control or check the MC server instance (stop, start, restart, status).")
@app_commands.describe(action="Choose an action for the server service.")
@app_commands.choices(action=[
    discord.app_commands.Choice(name="stop", value="stop"),
    discord.app_commands.Choice(name="start", value="start"),
    discord.app_commands.Choice(name="restart", value="restart"),
    discord.app_commands.Choice(name="status", value="status")
])
async def slash_server(interaction: discord.Interaction, action: str):
    """
    Executes 'sudo systemctl <action> SERVICE_NAME'.
    - For 'status', only show the top portion before the logs (stopping at the first blank line).
    - For stop/start/restart, confirm success or failure.
    """
    try:
        if action == "status":
            # Show the current status of the service, ephemeral
            raw_output = subprocess.check_output(
                ["sudo", "systemctl", "status", SERVICE_NAME],
                stderr=subprocess.STDOUT
            ).decode(errors="ignore")

            # Split at the first blank line to omit the trailing logs
            parts = raw_output.split("\n\n", 1)
            trimmed_output = parts[0].strip()  # Everything before the logs

            # Optionally enforce Discord's 2000-char limit if needed:
            if len(trimmed_output) > 1900:
                trimmed_output = trimmed_output[:1900] + "\n... (truncated) ..."

            await interaction.response.send_message(
                f"**Status for** `{SERVICE_NAME}`:\n```\n{trimmed_output}\n```",
                ephemeral=False
            )
        else:
            # Authorization (whitelist)
            if interaction.user.id not in ADMIN_USERS:
                await interaction.response.send_message("Sorry, you are not authorized to use this command.", ephemeral=True)
                return            
            # stop, start, or restart
            subprocess.check_output(
                ["sudo", "systemctl", action, SERVICE_NAME],
                stderr=subprocess.STDOUT
            )
            await interaction.response.send_message(
                f"Server action **{action}** completed successfully on `{SERVICE_NAME}`.",
                ephemeral=False
            )
    except subprocess.CalledProcessError as e:
        # Capture any systemctl error output
        error_output = e.output.decode(errors="ignore") if e.output else "No output"
        # Crop if it's too large
        if len(error_output) > 1900:
            error_output = error_output[:1900] + "\n... (truncated) ..."
        await interaction.response.send_message(
            f"Failed to **{action}** `{SERVICE_NAME}`.\n```\n{error_output}\n```",
            ephemeral=True
        )
    except Exception as ex:
        await interaction.response.send_message(
            f"Error running **{action}** on `{SERVICE_NAME}`: {ex}",
            ephemeral=True
        )

@bot.tree.command(name="reboot", description="🔒 Reboot the physical machine.")
async def slash_reboot(interaction: discord.Interaction):
    """
    Reboots the server by running 'sudo reboot'. Admin-only command.
    The bot logs out before executing the reboot to indicate downtime.
    """
    # Check if the user is an admin
    if interaction.user.id not in ADMIN_USERS:
        await interaction.response.send_message(
            "Sorry, you are not authorized to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=False, thinking=True)

    try:
        # Notify about the reboot
        await interaction.followup.send(
            "Rebooting the server in soon, this may take a while. 🖥️",
            ephemeral=False
        )

        # Stop the Minecraft service
        try:
            subprocess.check_output(
                ["sudo", "systemctl", "stop", SERVICE_NAME],
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            error_message = e.output.decode(errors="ignore") if e.output else "No error output"
            await interaction.followup.send(
                f"Failed to stop the Minecraft service:\n```\n{error_message}\n```",
                ephemeral=True
            )
            return

        # Wait for 30 seconds
        time.sleep(30)

        # Logout the bot
        await bot.close()

        # Execute the reboot command
        subprocess.check_output(["sudo", "reboot"], stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as e:
        error_message = e.output.decode(errors="ignore") if e.output else "No error output"
        try:
            await interaction.followup.send(
                f"Failed to reboot the server:\n```\n{error_message}\n```",
                ephemeral=True
            )
        except discord.errors.ClientException:
            print(f"Failed to send error message: {error_message}")
    except Exception as e:
        try:
            await interaction.followup.send(
                f"An unexpected error occurred while attempting to reboot the server: {e}",
                ephemeral=True
            )
        except discord.errors.ClientException:
            print(f"Failed to send unexpected error message: {e}")


@bot.tree.command(name="command", description="🔒Execute an RCON command on the server")
@app_commands.describe(rcon_command="The RCON command to run on the server.")
async def slash_rcon_command(interaction: discord.Interaction, rcon_command: str):
    """Runs an RCON command if the user is on the ADMIN_USERS whitelist."""
    if interaction.user.id not in ADMIN_USERS:
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
    """
    Slash command that responds with the server status, logs, memory, etc.
    Replicates the old !status command.
    """
    global ext_chunk_count

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

    # Respond to the slash command so everyone can see
    await interaction.response.send_message(output, ephemeral=False)


@bot.tree.command(name="players", description="Show who is online, who has joined today and how many joined yesterday.")
async def slash_players(interaction: discord.Interaction):
    """
    1) Counts how many players joined yesterday, how many are online now, and how many joined today.
    2) Displays that info at the top in plain text.
    3) Then shows two code blocks:
       - "■■■■ Players Joined Today (X) ■■■■"
       - "■■■■ Currently Online (Y) ■■■■"
    """
    await interaction.response.defer(ephemeral=False, thinking=True)

    # ─── 1) PLAYERS WHO JOINED YESTERDAY ───
    try:
        # Similar approach to the "players who joined today," but for "yesterday" logs
        # For instance, date -d '1 day ago' for the day:
        # (zcat logs/2025-01-18*.log.gz && cat logs/latest.log) ...
        players_yesterday_cmd = (
            f"(zcat {LOGS_DIR}/$(date +'%Y-%m'-%d -d '1 day ago')*.log.gz 2>/dev/null || true) "
            f"| grep joined | awk '{{print $6}}' | sort -u"
        )
        players_yesterday = subprocess.check_output(
            [players_yesterday_cmd], shell=True
        ).decode(errors="ignore").strip()
        if players_yesterday:
            players_yesterday_count = players_yesterday.count("\n") + 1
        else:
            players_yesterday_count = 0
    except Exception as e:
        print(f"Error retrieving players who joined yesterday: {e}")
        players_yesterday_count = 0

    # ─── 2) CURRENT ONLINE PLAYERS VIA RCON ───
    ensure_rcon_connection()
    if mcr_connection is None:
        # We'll still try to show the other info even if RCON is down
        player_count_now = 0
        currently_online = []
    else:
        try:
            list_response = mcr_connection.command("list")
            match = re.search(r"There are (\d+) of a max of \d+ players online:?\s*(.*)", list_response)
            if match:
                player_count_now = int(match.group(1))
                online_names_str = match.group(2).strip()
                if online_names_str:
                    currently_online = [name.strip() for name in online_names_str.split(",")]
                else:
                    currently_online = []
            else:
                player_count_now = 0
                currently_online = []
        except Exception as e:
            close_rcon_connection()
            print(f"Failed to retrieve current player list: {e}")
            player_count_now = 0
            currently_online = []

    # ─── 3) PLAYERS WHO JOINED TODAY ───
    try:
        players_today_cmd = (
            f"(zcat {LOGS_DIR}/$(date +'%Y-%m'-%d)*.log.gz && cat {os.path.join(LOGS_DIR, 'latest.log')}) "
            f"| grep joined | awk '{{print $6}}' | sort -u"
        )
        players_today_output = subprocess.check_output([players_today_cmd], shell=True).decode(errors="ignore").strip()
        if players_today_output:
            players_today_list = players_today_output.split("\n")
        else:
            players_today_list = []
    except Exception as e:
        print(f"Error retrieving players who joined today: {e}")
        players_today_list = []

    players_today_count = len(players_today_list)

    # ─── 4) BUILD TEXT OUTPUT ───

    # Top lines (plain text, no code blocks):
    # e.g.:
    # Players Yesterday: 3
    # Players Online Now: 2
    # Players Joined Today: 5
    top_text = (
        f"Players Yesterday: `{players_yesterday_count}`"
    )

    # Code block #1: Players Joined Today
    if players_today_count == 0:
        joined_today_lines = "no players today"
    else:
        joined_today_lines = "\n".join(players_today_list)

    code_block_today = (
        "```text\n"
        f"■■■■ Players Joined Today ({players_today_count}) ■■■■\n"
        f"{joined_today_lines}\n"
        "```"
    )

    # Code block #2: Currently Online
    if player_count_now == 0:
        currently_online_block = "no players currently online"
    else:
        currently_online_block = "\n".join(currently_online)

    code_block_online = (
        "```text\n"
        f"■■■■ Currently Online ({player_count_now}) ■■■■\n"
        f"{currently_online_block}\n"
        "```"
    )

    # Update / generate graph PNG
    update_csv_player_count()
    generate_player_count_graph()

    # Final response
    reply = f"{top_text}\n{code_block_today}{code_block_online}"

        # Now send the final message with an attached file
    await interaction.followup.send(
        content=reply,
        ephemeral=False,
        file=discord.File("stat_players.png", filename="stat_players.png")
    )




# ──────────────────────────
# Background Task: Status Presence
# ──────────────────────────

async def update_server_status():
    global player_count, ext_chunk_count
    while True:
        try:
            # 1) Try fetching the player count from RCON
            count = get_player_count_from_rcon()

            # 2) If we fail to get a count (i.e., None), declare "Server is offline"
            if count is None:
                status_message = "Server is offline"
            else:
                # Otherwise, update global `player_count`
                player_count = count

                # Check for external chunk saving
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

        # 3) Finally, update bot’s presence with whatever status_message we settled on
        await bot.change_presence(activity=discord.Game(status_message))
        await asyncio.sleep(UPDATE_INTERVAL)


async def player_count_logger_task():
    """
    A background task that runs indefinitely,
    logging the player count to a CSV file every 15 minutes.
    """
    while True:
        await asyncio.sleep(STAT_CSV_INTERVAL)  # 15 minutes in seconds

        # Store how many players are currently online in the csv file
        update_csv_player_count()

        # After writing the row, generate a fresh graph
        generate_player_count_graph()

def update_csv_player_count():
        # Attempt to get the latest player count from your global or via RCON
        # (Here we assume you already update 'player_count' in update_server_status,
        #  so we just read that global variable.)
        global player_count

        # If player_count is None or invalid, you could skip or set it to 0
        if player_count is None:
            count_to_log = 0
        else:
            count_to_log = player_count

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
    print(f"Writing row to {STAT_CSV_PATH}: {row}")  # Debug
    file_exists = os.path.isfile(STAT_CSV_PATH)

    with open(STAT_CSV_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # If it's a new file, write a header
        if not file_exists:
            writer.writerow(["Timestamp", "PlayerCount"])

        # Append our new row
        writer.writerow(row)


def generate_player_count_graph():
    """
    Reads the CSV (Timestamp, PlayerCount), groups by day to calculate daily max,
    and plots a column chart (bar chart) saved to PLAYER_COUNT_PNG with a dark theme.
    """
    import datetime

    daily_counts = {}

    # 1) Read the CSV data
    if not os.path.isfile(STAT_CSV_PATH):
        print("No CSV found to plot.")
        return

    with open(STAT_CSV_PATH, mode="r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)  # Skip header row if present
        for row in reader:
            if len(row) < 2:
                continue
            timestamp_str, count_str = row[0], row[1]
            try:
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
        print("No data in CSV to plot.")
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
    plt.savefig(PLAYER_COUNT_PNG)
    plt.close()
    print(f"Saved dark-themed bar chart to {PLAYER_COUNT_PNG}.")






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

    # Start the new CSV logger in the background
    bot.loop.create_task(player_count_logger_task())
    generate_player_count_graph()
bot.run(BOT_TOKEN)
