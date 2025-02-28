import re
import asyncio
import datetime
from discord.ext import tasks

import utility.globals as globals
import config.config as cfg
import state.state as st
from utility.logger import get_logger
log = get_logger()

import utility.helper_functions as helpers

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
            log.debug(f"Task background_chat_update_task: Chat window in channel {channel_id} expired.")
            return

        # Otherwise, update the message
        lines = helpers.get_recent_chat_lines(10)
        joined = "\n".join(lines)
        new_content = f"```text\n{joined}\n```"
        try:
            await data["message"].edit(content=new_content)
        except Exception as e:
            log.error(f"Task background_chat_update_task: Failed to edit chat window in channel {channel_id}: {e}")
            # Remove and stop
            del globals.chat_windows[channel_id]
            return

                
@tasks.loop(minutes=1)
async def clear_daily_state():
    """Removes players in players_today stat from state"""
    log.debug("Task clear_daily_state: Running Task")
    now = datetime.datetime.now()
    if now.hour == 0 and now.minute == 0: # Run at midnight
        st.state.mc_players_today.clear()
        st.save_state()
        
        

@tasks.loop(minutes=1) # Has to run every 1 minute. Logic assumes that each element in globals.lag_history is 1 minute apart
async def update_lag_history():
    """Updates global variable lag_history with lag data from the log file"""
    log.debug("Task update_lag_history: Running Task")
    now = datetime.datetime.now()
    one_minute_ago = now - datetime.timedelta(minutes=cfg.config.notifications.check_last_min)# Calculate time 1 minute ago to filter logs
    
    # Read log file
    with open(cfg.config.minecraft.log_file_path, 'r') as log_file:
        log_contents = log_file.read()

    lag_line_regex = re.compile(
        r'^\[(?P<day>\d{1,2})(?P<month>[a-zA-Z]{3})\.?(?P<year>\d{4}) (?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\.(?P<millis>\d+)] .*?Running (?P<ms>\d+)ms or \d+ ticks behind'
    )

    # Parse log lines for lag entries within the last minute
    total_lag_this_minute = 0  

    for line in log_contents.splitlines():
        match = lag_line_regex.match(line)
        if match:
            # Extract matched timestamp
            log_day = match.group("day")
            log_month = match.group("month").capitalize()
            log_year = match.group("year")
            log_time = f"{match.group('hour')}:{match.group('minute')}:{match.group('second')}.{match.group('millis')}"

            log_timestamp_str = f"{log_day}{log_month}{log_year} {log_time}"
            log_timestamp = datetime.datetime.strptime(log_timestamp_str, "%d%b%Y %H:%M:%S.%f")

            # Check if the entry is within the last minute
            if log_timestamp >= one_minute_ago:
                lag_ms = int(match.group("ms"))
                total_lag_this_minute += lag_ms / 1000  # Convert ms to seconds

    # Add the current minute's lag to history
    globals.lag_history.append(total_lag_this_minute)

    # Keep only the last lag_window_minutes of lag data
    if len(globals.lag_history) > 280: # 280 minutes = 4 hours
        globals.lag_history.pop(0)

