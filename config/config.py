import os
import yaml

from config.root_config import *
from utility.logger import get_logger
log = get_logger()

CONFIG_FILE = "config.yaml"
config = None

# ──────────────────────────
# Configuration Helper Functions
# ──────────────────────────
async def load_config() -> bool:
    global config
    """
    Load the configuration from a YAML file into a Config dataclass.
    Args:
        file_path (str): Path to the YAML file.
    Returns:
        Config: The loaded configuration.
    """
    if not os.path.exists(CONFIG_FILE):
        log.error(f"Config file {CONFIG_FILE} not found. Using defaults.")
        config = Config()
    try:
        log.debug("Loading config...")
        with open(CONFIG_FILE, "r") as file:
            data = yaml.safe_load(file)
            config = Config(
            bot=BotConfig(
                bot_token=data["bot"].get("bot_token", ""),
                discord_char_limit=data["bot"].get("discord_char_limit", 2000),
                discord_dropdown_limit=data["bot"].get("discord_dropdown_limit", 25),
                admin_users=data["bot"].get("admin_users", []),
                admin_roles=data["bot"].get("admin_roles", []),
                presence=PresenceConfig(**data["bot"].get("presence", {})),
                chat=ChatConfig(**data["bot"].get("chat", {})),
            ),
            minecraft=MinecraftConfig(
                service_name=data["minecraft"].get("service_name", "phoenix.service"),
                service_path=data["minecraft"].get("service_path", "/etc/systemd/system"),
                server_path=data["minecraft"].get("server_path", "/mnt/SSD120GB/phonix/PhoenixDenPack2025"),
                backup=BackupConfig(**data["minecraft"].get("backup", {})),
                modpack_url=data["minecraft"].get("modpack_url", ""),
                restart=RestartConfig(**data["minecraft"].get("restart", {})),
            ),
            curseforge=CurseForge(**data["curseforge"]),
            stats=StatsConfig(**data["stats"]),
        )
    except Exception as e:
        config = Config()
        log.error(f"Failed to load config: {e}")
        return False
    log.info("Finished loading config")
    return True

def save_config():
    global config
    """
    Save the Config dataclass to a YAML file.
    Args:
        config (Config): The configuration to save.
        file_path (str): Path to the YAML file.
    """
    with open(CONFIG_FILE, "w") as file:
        yaml.dump(
            {
                "bot": {
                    **config.bot.__dict__,
                    "presence": config.bot.presence.__dict__,
                    "chat": config.bot.chat.__dict__,
                },
                "minecraft": {
                    **config.minecraft.__dict__,
                    "backup": config.minecraft.backup.__dict__,
                    "restart": config.minecraft.restart.__dict__,
                },
                "curseforge": config.curseforge.__dict__,
                "stats": config.stats.__dict__,
            },
            file,
            default_flow_style=False,
        )
