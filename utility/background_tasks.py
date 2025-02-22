import re
import asyncio
import datetime
import discord
from discord.ext import tasks

import config.config as cfg
import state.state as st
from utility.logger import get_logger
log = get_logger()

import utility.globals as globals

import utility.rcon_helpers as rcon_helpers
import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers

# ──────────────────────────
# Background Task: Status Presence
# ──────────────────────────
@tasks.loop(seconds=cfg.config.bot.presence.update_interval_sec)
async def update_bot_presence_task(bot):
    last_lag_timestamp = None  # Timestamp of the last detected lag from the log
    last_lag_ms = None  # Last lag value in milliseconds
    lag_display_duration = 300  # 5 minutes in seconds

    lag_line_regex = re.compile(
        r'^\[(?P<datetime>\d{1,2}[A-Za-z]{3}\d{4} \d{2}:\d{2}:\d{2}\.\d+)] .*?Running (?P<ms>\d+)ms or \d+ ticks behind'
    )

    try:
        # Check if the service is running without verifying the service file and reloading config every few seconds
        if await ops_helpers.is_service_running(True):
            players = await rcon_helpers.get_players()
        
        # If RCON fails to get a count, set status to offline
        if players is None:
            status_message = "Server is offline"
            players = []
        else:
            # Update global player count
            globals.player_count = len(players)
            # Add player to state lists while keeping names unique
            st.state.mc_players_ever = list(set(st.state.mc_players_ever) | set(players)) 
            st.state.mc_players_today = list(set(st.state.mc_players_today) | set(players)) 
            st.save_state()
            
            # Read the log file and check for external chunk saving or lag
            with open(cfg.config.minecraft.log_file_path, 'r') as log_file:
                log_contents = log_file.read()
            globals.ext_chunk_count = len(re.findall(r'Saving oversized chunk', log_contents))

            if globals.ext_chunk_count:
                status_message = f"External chunks! ({globals.ext_chunk_count})"
            else:
                lines = log_contents.splitlines()
                latest_lag_line = None

                # Parse log lines for lag entries
                for line in reversed(lines):
                    match = lag_line_regex.match(line)
                    if match:
                        latest_lag_line = match
                        break

                if latest_lag_line:
                    # Extract the log timestamp and lag value
                    log_timestamp_str = latest_lag_line.group("datetime")
                    log_timestamp = datetime.datetime.strptime(log_timestamp_str, "%d%b%Y %H:%M:%S.%f")
                    lag_ms = int(latest_lag_line.group("ms"))

                    # Update the lag status if the timestamp is newer
                    if last_lag_timestamp is None or log_timestamp > last_lag_timestamp:
                        last_lag_timestamp = log_timestamp
                        last_lag_ms = lag_ms

                    time_since_lag = (datetime.datetime.now() - last_lag_timestamp).total_seconds()
                    if time_since_lag <= lag_display_duration:
                        status_message = (
                            f"{globals.player_count} players online ({last_lag_ms / 1000:.1f} sec behind, "
                            f"{int(lag_display_duration - time_since_lag)} seconds remaining)"
                        )
                    else:
                        # Lag display duration expired
                        last_lag_timestamp = None
                        last_lag_ms = None
                        status_message = f"{globals.player_count} players online"
                else:
                    # No lag detected in the latest logs
                    last_lag_timestamp = None
                    last_lag_ms = None
                    status_message = f"{globals.player_count} players online"

    except Exception as e:
        log.error(f"Error updating status: {e}")
        status_message = "Server is offline"
    
    # Update bot presence with the current status message
    await bot.change_presence(activity=discord.Game(status_message))

@tasks.loop(minutes=cfg.config.stats.csv_interval_min)
async def player_count_logger_task():
    """
    A background task that runs indefinitely,
    logging the player count to a CSV file every 15 minutes.
    """
    # Store how many players are currently online in the csv file
    helpers.update_csv_player_count()

async def background_chat_update_task(channel_id: int):
    """
    Repeatedly update the chat window in this channel
    until the 5-minute timer expires.
    """
    while True:
        await asyncio.sleep(cfg.config.bot.chat.update_interval_sec)
        # If the window is missing or removed from dict, stop
        if channel_id not in globals.chat_windows:
            return
        
        data = globals.chat_windows[channel_id]
        now = asyncio.get_event_loop().time()

        # Time up?
        if now > data["expires_at"]:
            # Delete the chat message
            try:
                await data["message"].delete()
            except Exception as e:
                log.error(f"Failed to delete expired chat window in channel {channel_id}: {e}")
            del globals.chat_windows[channel_id]
            log.debug(f"Chat window in channel {channel_id} expired.")
            return

        # Otherwise, update the message
        lines = helpers.get_recent_chat_lines(10)
        joined = "\n".join(lines)
        new_content = f"```text\n{joined}\n```"
        try:
            await data["message"].edit(content=new_content)
        except Exception as e:
            log.error(f"Failed to edit chat window in channel {channel_id}: {e}")
            # Remove and stop
            del globals.chat_windows[channel_id]
            return


@tasks.loop(minutes=cfg.config.minecraft.backup.interval_min)
async def backup_task():
    if cfg.config.minecraft.backup.enabled:
        await ops_helpers.async_create_backup("backup")
    else:
        log.info("Backup task disabled, skipping.")
    await ops_helpers.async_delete_old_backups()


@tasks.loop(minutes=1)
async def restart_task():
    log.debug("Running Task: restart_task")
    current_time = datetime.datetime.now().strftime("%H:%M") # Get current system time in HH:MM format, Ex: 22:33
    for time in cfg.config.minecraft.restart.times:
        if current_time == time:
            await ops_helpers.async_service_control("stop")
            if cfg.config.minecraft.restart.cold_backup_on_restart:
                await ops_helpers.async_create_backup("cold_backup")
            await ops_helpers.async_service_control("start")
                
@tasks.loop(minutes=1)
async def clear_daily_state():
    """Removes players in players_today stat from state"""
    log.debug("Running Task: clear_daily_state")
    now = datetime.datetime.now()
    if now.hour == 0 and now.minute == 0: # Run at midnight
        st.state.mc_players_today.clear()
        st.save_state()
        
tracked_players = []
@tasks.loop(minutes=1)
async def notify_player_join(bot):
    """Uses state to send DM to users who as subscriberd to being updated when a player joins"""
    global tracked_players
    log.debug("Running Task: notify_player_join")
    # Check if any new players have joined
    players = await rcon_helpers.get_players()    
    if players is None:
        return
    new_players = []
    for player in players:
        if player not in tracked_players:
            new_players.append(player)
            
    # If new players notify discord users (in a list if many new players: 'user1, user2, and user3 joined')
    if new_players:
        joined_players = ", ".join(new_players[:-1]) + " and " + new_players[-1] if len(new_players) > 1 else new_players[0]
        notified_count = 0
        for user_info in st.state.join_subed_users:
            user_id, username = user_info.split('.')
            if username in new_players and len(new_players) == 1:
                log.debug(f"Ignoring self-notify user {username} (ID: {user_id}) that player(s) {new_players} joined,")
                continue
            log.debug(f"Notifying user {username} (ID: {user_id}) that player(s) {new_players} joined")
            user = await bot.fetch_user(int(user_id))
            await user.send(f"📢 `{joined_players}` joined the Minecraft Server")
            notified_count += 1
        log.info(f"Player {player} joined. Notified {notified_count} users")

        # TODO: update CSV to only log players_today when increased, graph must be compatible