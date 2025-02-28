import re
import datetime
from discord.ext import tasks

import utility.globals as globals
import config.config as cfg
import state.state as st
from utility.logger import get_logger
log = get_logger()

import utility.rcon_helpers as rcon_helpers
import utility.helper_functions as helpers


first_run = True # Flag to skip notifications on the first run
tracked_players = []
@tasks.loop(minutes=1)
async def notify_player_join(bot):
    """Uses state to send DM to users who as subscriberd to being updated when a player joins"""
    global tracked_players, first_run
    log.debug("Task notify_player_join: Running Task. Tracked players: " + str(tracked_players))
    # Check if any new players have joined
    players = await rcon_helpers.get_players()    
    if players is None:
        return
    new_players = []
    for player in players:
        if player not in tracked_players:
            new_players.append(player)
            log.debug("Task notify_player_join: New user detected: " + player)
            
    tracked_players = players
    
    # Don't notify on the first run, if the bot was just restarted, we don't want to spam users
    if first_run:
        log.debug("Task notify_player_join: Skipping first run.")
        first_run = False
        return
    
    # If new players notify discord users (in a list if many new players: 'user1, user2, and user3 joined')
    if new_players:
        joined_players = ", ".join(new_players[:-1]) + " and " + new_players[-1] if len(new_players) > 1 else new_players[0]
        notified_count = 0
        for user_info in st.state.join_subed_users:
            # Handle both cases for if the user_info is just the userID or userID.username
            log.debug("Handling user_info: " + str(user_info))
            if isinstance(user_info, str) and '.' in user_info:
                user_id, username = user_info.split('.')
            else:
                user_id = str(user_info)  # Ensure it's a string
                username = None
            
            if username and username in new_players and len(new_players) == 1:
                log.debug(f"Task notify_player_join: Ignoring self-notify user {username} (ID: {user_id}) that player(s) {new_players} joined,")
                continue
            log.debug(f"Task notify_player_join: Notifying user {username} (userID: {user_id}) that player(s) {new_players} joined")
            user = await bot.fetch_user(int(user_id))
            await user.send(f"📢 `{joined_players}` joined the Minecraft Server")
            notified_count += 1
        log.info(f"Task notify_player_join: Player {player} joined. Notified {notified_count} users")



# Global state for tracking lag history and cooldown
behind_notification_cooldown_until = None  # Time until we allow the next notification
@tasks.loop(minutes=cfg.config.notifications.check_last_min)
async def notify_server_behind(bot):
    """
    Uses state to send a DM to users subscribed to lag updates.
    The function reads the Minecraft server log, checks lag history over the last N minutes, 
    and sends notifications if cumulative lag exceeds the threshold.
    Implements a cooldown of N minutes between notifications.
    """
    global behind_notification_cooldown_until
    # Check if notifications are enabled
    if not cfg.config.notifications.errors_enabled:
        log.debug("Task notify_server_behind: Notifications are disabled.")
        return
    
    # Check cooldown before proceeding
    now = datetime.datetime.now()
    if behind_notification_cooldown_until and now < behind_notification_cooldown_until:
        log.debug(f"Task notify_server_behind: Skipping check. Notifications on cooldown until {behind_notification_cooldown_until}.")
        return
    
    log.debug("Task notify_server_behind: Running Task")

    # Take a slice of the last cfg.config.notifications.lag_window_min out of globals.lag_history
    lag_history_slice = globals.lag_history[-cfg.config.notifications.lag_window_min:]
    
    # Calculate total lag over the last N minutes using the slice
    total_lag_in_window = sum(lag_history_slice)

    log.debug(f"Task notify_server_behind: Total lag last {cfg.config.notifications.lag_window_min} min: {total_lag_in_window} sec (Threshold: {cfg.config.notifications.threshold_sec})")

    # If cumulative lag exceeds the threshold, notify users
    if total_lag_in_window > cfg.config.notifications.threshold_sec:
        notified_count = 0
        for user_id in st.state.error_subed_users:
            user = await bot.fetch_user(int(user_id))
            await user.send(
                f"🚨 The Minecraft Server is lagging!\n"
                f" In the last `{cfg.config.notifications.lag_window_min}` min, the MC server has been running `{total_lag_in_window:.1f}` sec behind!"
            )
            log.debug(f"Task notify_server_behind: Notifying lag userID: {user_id} that the server is lagging")
            notified_count += 1

        log.info(f"Task notify_server_behind: Server is lagging. Notified {notified_count} users")

        # Set a cooldown of N minutes before the next notification
        behind_notification_cooldown_until = now + datetime.timedelta(minutes=cfg.config.notifications.notification_cooldown_min)




ext_chunk_notification_cooldown_until = None  # Time until we allow the next notification
@tasks.loop(minutes=cfg.config.notifications.check_last_min)
async def notify_external_chunks(bot):
    """
    Uses state to send a DM to users subscribed to external chunk updates.
    The function checks the global external chunk count and sends notifications if any external chunks are detected.
    Implements a cooldown of N minutes between notifications.
    """
    global ext_chunk_notification_cooldown_until

     # Check if notifications are enabled
    if not cfg.config.notifications.errors_enabled:
        log.debug("Task notify_external_chunks: Notifications are disabled.")
        return
    
    # Check cooldown before proceeding
    now = datetime.datetime.now()
    if ext_chunk_notification_cooldown_until and now < ext_chunk_notification_cooldown_until:
        log.debug(f"Task notify_server_behind: Skipping check. Notifications on cooldown until {behind_notification_cooldown_until}.")
        return
    
    log.debug("Task notify_external_chunks: Running Task")
    
    if globals.ext_chunk_count:
        notified_count = 0
        for user_id in st.state.error_subed_users:
            user = await bot.fetch_user(int(user_id))
            await user.send(
                f"⚠️ The Minecraft Server has external chunks!\n"
                f"This means that the server is saving oversized chunks. This is likely causing lag and performance issues."
            )
            log.debug(f"Task notify_external_chunks: Notifying lag userID: {user_id} that the server is lagging")
            notified_count += 1

        log.info(f"Task notify_external_chunks: Server is has external chunks. Notified {notified_count} users")

        # Set a cooldown of N minutes before the next notification
        ext_chunk_notification_cooldown_until = now + datetime.timedelta(minutes=cfg.config.notifications.notification_cooldown_min)




generic_error_notification_cooldown_until = None  # Time until the next notification
@tasks.loop(minutes=cfg.config.notifications.check_last_min)
async def notify_generic_errors(bot):
    """
    Checks for chunk-related errors and other generic errors in latest.log and sends notifications to subscribed users.
    Implements a cooldown to avoid spam.
    """
    global generic_error_notification_cooldown_until

    # Check if notifications are enabled
    if not cfg.config.notifications.errors_enabled:
        log.debug("Task notify_generic_errors: Notifications are disabled.")
        return

    # Check cooldown before proceeding
    now = datetime.datetime.now()
    one_minute_ago = now - datetime.timedelta(minutes=cfg.config.notifications.check_last_min)# Calculate time 1 minute ago to filter logs
    if generic_error_notification_cooldown_until and now < generic_error_notification_cooldown_until:
        log.debug(f"Task notify_generic_errors: Skipping check. Notifications on cooldown until {generic_error_notification_cooldown_until}.")
        return

    log.debug("Task notify_generic_errors: Running Task")

    # Compile MC log error patterns from config file
    # Error message search patterns and explanations separated by colon (':')
    generic_error_patterns = cfg.config.notifications.generic_error_patterns
    escaped_patterns = [re.escape(pattern) for pattern in generic_error_patterns.keys()]
    generic_error_regex = re.compile(r"(" + "|".join(escaped_patterns) + r")")
    # log.debug(f"Generic Error Patterns: {generic_error_patterns}")
    
    # Read latest.log file
    with open(cfg.config.minecraft.log_file_path, 'r', encoding='utf-8', errors='ignore') as log_file:
        log_contents = log_file.readlines()
    
    scanned_lines = 0
    detected_messages = []
    for line in log_contents:
        # Check if the entry is within the last minute, if old, skip
        log_timestamp =helpers.extract_timestamp(line)
        if log_timestamp and log_timestamp < one_minute_ago:
            # log.debug(f"Skipping old line from: {log_timestamp}") # Spammy
            continue
        
        # Search for generic errors in the log line
        # log.debug(f"Checking line: {line}")
        error_match = generic_error_regex.search(line)
        if error_match:
            log.debug(f"Task notify_generic_errors: Detected generic error in line: {line}")
            useful_message = re.sub(r"^.*\[.*?\] \[.*?\] \[.*?/\]: ", "", line.strip())
            explanation = generic_error_patterns.get(error_match.group(0), "Unknown error detected.")
            detected_messages.append((useful_message, explanation))
        scanned_lines += 1
    # Notify users if any errors were detected
    if detected_messages:
        notified_count = 0
        for user_id in st.state.error_subed_users:
            user = await bot.fetch_user(int(user_id))
            for msg, explanation in detected_messages:
                await user.send(f"⚠️ Error detected on the Minecraft server!\n```log\n{msg}\n```{explanation}")
                log.debug(f"Task notify_generic_errors: Notifying generic error to userID: {user_id}")
                notified_count += 1

        log.info(f"Task notify_generic_errors: Generic Errors detected. Notified {notified_count} users.")

        # Set a cooldown before the next notification
        generic_error_notification_cooldown_until = now + datetime.timedelta(minutes=cfg.config.notifications.notification_cooldown_min)# Error message search patterns and explanations separated by colon (':')
    log.debug(f"Task notify_generic_errors: Scanned {scanned_lines} lines. Detected {len(detected_messages)} error messages.")