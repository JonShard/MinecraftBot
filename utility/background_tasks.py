import re
import asyncio
import datetime
import discord
from discord.ext import tasks

from config import *
import utility.rcon_helpers as rcon_helpers
import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers

# ──────────────────────────
# Background Task: Status Presence
# ──────────────────────────
@tasks.loop(seconds=PRESENCE_UPDATE_INTERVAL_SEC)
async def update_bot_presence_task(bot):
    global player_count, ext_chunk_count
    last_lag_timestamp = None  # Timestamp of the last detected lag from the log
    last_lag_ms = None  # Last lag value in milliseconds
    lag_display_duration = 300  # 5 minutes in seconds

    lag_line_regex = re.compile(
        r'^\[(?P<datetime>\d{1,2}[A-Za-z]{3}\d{4} \d{2}:\d{2}:\d{2}\.\d+)] .*?Running (?P<ms>\d+)ms or \d+ ticks behind'
    )

    try:
        # Try fetching the player count from RCON
        count = rcon_helpers.get_player_count_from_rcon()

        # If RCON fails to get a count, set status to offline
        if count is None:
            status_message = "Server is offline"
        else:
            # Update global player count
            player_count = count

            # Read the log file and check for external chunk saving or lag
            with open(LOG_FILE_PATH, 'r') as log_file:
                log_contents = log_file.read()
            ext_chunk_count = len(re.findall(r'Saving oversized chunk', log_contents))

            if ext_chunk_count:
                status_message = f"External chunks! ({ext_chunk_count})"
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
                            f"{player_count} players online ({last_lag_ms / 1000:.1f} sec behind, "
                            f"{int(lag_display_duration - time_since_lag)} seconds remaining)"
                        )
                    else:
                        # Lag display duration expired
                        last_lag_timestamp = None
                        last_lag_ms = None
                        status_message = f"{player_count} players online"
                else:
                    # No lag detected in the latest logs
                    last_lag_timestamp = None
                    last_lag_ms = None
                    status_message = f"{player_count} players online"

    except Exception as e:
        print(f"Error updating status: {e}")
        status_message = "Server is offline"

    # Update bot presence with the current status message
    await bot.change_presence(activity=discord.Game(status_message))

@tasks.loop(minutes=STAT_CSV_INTERVAL_MIN)
async def player_count_logger_task():
    """
    A background task that runs indefinitely,
    logging the player count to a CSV file every 15 minutes.
    """
    # Store how many players are currently online in the csv file
    helpers.update_csv_player_count()
    # After writing the row, generate a fresh graph
    helpers.generate_player_count_graph()



async def background_chat_update_task(channel_id: int):
    """
    Repeatedly update the chat window in this channel
    until the 5-minute timer expires.
    """
    while True:
        await asyncio.sleep(CHAT_UPDATE_INTERVAL_SEC)
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
        lines = helpers.get_recent_chat_lines(10)
        joined = "\n".join(lines)
        new_content = f"```text\n{joined}\n```"
        try:
            await data["message"].edit(content=new_content)
        except Exception as e:
            print(f"Failed to edit chat window in channel {channel_id}: {e}")
            # Remove and stop
            del CHAT_WINDOWS[channel_id]
            return


@tasks.loop(minutes=BACKUP_INTERVAL_MIN)
async def backup_task():
    await ops_helpers.async_create_backup("backup")