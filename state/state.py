import os
import yaml
from dataclasses import dataclass, field
from typing import List, Optional

from config.root_config import *
from utility.logger import get_logger
log = get_logger()

STATE_FILE = "_data/state.yaml"
state = None

@dataclass
class State:
    join_subed_users: List[str] = field(default_factory=list)
    error_subed_users: List[str] = field(default_factory=list)
    mc_players_today: List[str] = field(default_factory=list)
    mc_players_ever: List[str] = field(default_factory=list)
    
# ──────────────────────────
# State keeping
# ──────────────────────────
async def load_state() -> bool:
    global state
    """
    Load the state from a YAML file
    Returns:
        State: data class
    """
    if not os.path.exists(STATE_FILE):
        state = State()
        return True
    try:
        with open(STATE_FILE, "r") as file:
            data = yaml.safe_load(file)
            state = State(
                join_subed_users=data.get("join_subed_users", []),
                error_subed_users=data.get("error_subed_users", []),
                mc_players_today=data.get("mc_players_today", []),
                mc_players_ever=data.get("mc_players_ever", [])
        )
    except Exception as e:
        state = State()
        log.error(f"Failed to load state: {e}")
        return False
    log.debug("Finished loading state")
    return True

def save_state():
    global state
    """
    Save the current state to a YAML file.
    """
    try:
        with open(STATE_FILE, "w") as file:
            yaml.dump(
                {
                    "join_subed_users": state.join_subed_users,
                    "error_subed_users": state.error_subed_users,
                    "mc_players_today": state.mc_players_today,
                    "mc_players_ever": state.mc_players_ever,
                },
                file,
                default_flow_style=False
            )
    except Exception as e:
        log.error(f"Failed to save state: {e}")
        
def clear_state():
    """
    Clears the current state and deletes the state file.
    """
    global state
    
    # Reset state to a fresh instance
    state = State()
    
    # Remove the state file if it exists
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            log.debug("State file deleted successfully.")
        except Exception as e:
            log.error(f"Failed to delete state file: {e}")
    else:
        log.debug("State file does not exist, nothing to delete.")
