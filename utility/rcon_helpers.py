import os
import re
from mcrcon import MCRcon

import config.config as cfg
from utility.logger import get_logger
log = get_logger()

mcr_connection = None


# ──────────────────────────
# RCON Utilities
# ──────────────────────────

def ensure_rcon_connection():
    """Ensure we have a persistent RCON connection."""
    global mcr_connection

    # Check if already connected
    if mcr_connection is not None:
        return

    # Default RCON port and password
    rcon_port = 25575  # Default RCON port
    rcon_password = None

    # Path to server.properties
    server_properties_path = os.path.join(cfg.config.minecraft.server_path, "server.properties")

    try:
        # Parse RCON port and password from server.properties
        with open(server_properties_path, "r") as file:
            for line in file:
                if line.startswith("rcon.port="):
                    rcon_port = int(line.split("=")[-1].strip())
                elif line.startswith("rcon.password="):
                    rcon_password = line.split("=")[-1].strip()

        if not rcon_password:
            raise ValueError("RCON password not found in server.properties.")

        # Establish the RCON connection
        conn = MCRcon("localhost", rcon_password, port=rcon_port)
        conn.connect()
        mcr_connection = conn
        log.info("RCON: Connected successfully.")
    except FileNotFoundError:
        log.error(f"RCON: server.properties not found at {server_properties_path}.")
        mcr_connection = None
    except Exception as e:
        log.error(f"RCON: Failed to connect: {e}")
        mcr_connection = None

def close_rcon_connection():
    """Close the RCON connection if open."""
    global mcr_connection
    if mcr_connection:
        try:
            mcr_connection.disconnect()
        except Exception as e:
            log.error(f"RCON: Error while disconnecting: {e}")
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
        log.error(f"RCON: Command error: {e}")
        close_rcon_connection()
    return None



