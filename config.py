import os

# ──────────────────────────
# Configuration Variables
# ──────────────────────────

# Required Configuration:  
BOT_TOKEN = "MTA4MTg1Nzc5OTc5NDk4NzA0OQ.GY1gHU.Zr8kWU4WXIN_Yx2JAjr3M3J2NBjVw8XkO4noC8"

MC_SERVER_PATH = "/mnt/SSD120GB/phonix/PhoenixDenPack2025"
SERVICE_NAME = "phoenix.service"  # Parameterize your MC service name here
BACKUP_PATH = "/var/mcbackup/"
MODPACK_URL = "https://www.curseforge.com/minecraft/modpacks/the-phoenix-den-pack"

# Optional Configuration:
STAT_CSV_INTERVAL = 900 # How often in seconds to check for players to store in CSV for player graph
LATEST_LOG_LINES = 10    # How many lines of log to provide in /status command.
PRESENCE_UPDATE_INTERVAL = 3 # How often in seconds to update the bot's presence "Playing X players online..."
CHAT_UPDATE_INTERVAL = 5 # How often to refresh the chat window in seconds
CHAT_DURATION = 900 # How long the chat window remains active in seconds (15 minutes)
CHAT_LINES = 10 # How many lines of chat in code block
DISCORD_CHAR_LIMIT = 2000

# For the commands that cause changes:
ADMIN_USERS = [
               257785837813497856, # TwistedAro
               209382762971398144, # Algodoogle
               300930955579752448, # EarthFishy
               191561233755799554, # JonShard
            ]
STAT_CSV_PATH = "stats.csv"
PLAYER_COUNT_PNG = "stat_players.png"


# Derived paths
LOGS_DIR = os.path.join(MC_SERVER_PATH, "logs")
CRASH_REPORTS_DIR = os.path.join(MC_SERVER_PATH, "crash-reports")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "latest.log")

# ──────────────────────────
# Global RCON + Discord Setup
# ──────────────────────────

player_count = 0
ext_chunk_count = 0

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
