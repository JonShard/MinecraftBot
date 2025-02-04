# logger_setup.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

# --------------------------------------------------------------------
# CONFIGURE THESE AS YOU WISH
# --------------------------------------------------------------------
LOG_DIR = "_logs"          # Directory where logfiles will go
BASE_LOG_NAME = "mc_bot"   # Base log name => _logs/mc_bot.log, etc.
LOG_LEVEL_CONSOLE = logging.INFO
LOG_LEVEL_FILE = logging.DEBUG
BACKUP_COUNT = 356           # Keep up to x old log files
# Rotate the file at midnight; add a new file each day
ROTATE_WHEN = "midnight"
ROTATE_INTERVAL = 1

# Create the directory if it doesn’t exist
os.makedirs(LOG_DIR, exist_ok=True)

# The main logger name (you can pick anything). 
# We'll attach the same handlers to it so all modules that use 
# getLogger(<NAME>) can inherit the same handlers.
LOGGER_NAME = "MineBot"

def get_logger():
    """Return a logger configured to log to console and a rotating file."""
    # 1) Create (or retrieve) the logger by name
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)  # The logger's own threshold

    # If it already has handlers, avoid adding them again
    if logger.handlers:
        return logger

    # 2) Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL_CONSOLE)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # 3) File handler with rotation
    file_path = os.path.join(LOG_DIR, f"{BASE_LOG_NAME}.log")
    file_handler = TimedRotatingFileHandler(
        filename=file_path,
        when=ROTATE_WHEN,        # "midnight", "D", "H", "M", "S", etc.
        interval=ROTATE_INTERVAL,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(LOG_LEVEL_FILE)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # 4) Add both handlers to our logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
