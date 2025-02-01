from dataclasses import dataclass, field
from typing import List, Optional
import os

from .restart_config import RestartConfig

@dataclass
class ChatConfig:
    update_interval_sec: int = 5
    duration_min: int = 900
    lines: int = 10

@dataclass
class PresenceConfig:
    update_interval_sec: int = 3

@dataclass
class BotConfig:
    bot_token: str = ""
    discord_char_limit: int = 2000
    discord_dropdown_limit: int = 25
    admin_users: List[int] = field(default_factory=list)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)

@dataclass
class BackupConfig:
    enabled: bool = True
    interval_min: int = 15
    path: str = "/var/mcbackup/"
    delete_frequent_after_hours: int = 24
    delete_sparse_after_days: int = 120

@dataclass
class MinecraftConfig:
    service_name: Optional[str] = None  # Private field, prevents direct access
    service_path: str = "/etc/systemd/system"
    server_path: str = "/mnt/SSD120GB/phonix/PhoenixDenPack2025"
    backup: BackupConfig = field(default_factory=BackupConfig)
    modpack_url: str = ""
    restart: RestartConfig = field(default_factory=RestartConfig)
    
    def __post_init__(self):
        """ Ensure service_name falls back to the server_path name if empty or None and ends with .service. """
        if not self.service_name or self.service_name.strip() == "":
            self.service_name = os.path.basename(self.server_path)
        # Ensure the service name always ends with ".service"
        if self.service_name and not self.service_name.endswith(".service"):
            self.service_name += ".service"
        print(f"SERVICE NAME = {self.service_name }")
    
    # Derived paths as properties
    @property
    def logs_dir(self) -> str:
        return os.path.join(self.server_path, "logs")

    @property
    def crash_reports_dir(self) -> str:
        return os.path.join(self.server_path, "crash-reports")

    @property
    def log_file_path(self) -> str:
        return os.path.join(self.logs_dir, "latest.log")
    


@dataclass
class StatsConfig:
    csv_interval_min: int = 5
    csv_path: str = "_data/stats.csv"
    player_count_png: str = "_data/stat_players.png"

@dataclass
class Config:
    bot: BotConfig = field(default_factory=BotConfig)
    minecraft: MinecraftConfig = field(default_factory=MinecraftConfig)
    stats: StatsConfig = field(default_factory=StatsConfig)
