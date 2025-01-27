import os


from enum import Enum

class ServerProperties(Enum):
    ALLOW_FLIGHT = "allow-flight"
    ALLOW_NETHER = "allow-nether"
    BROADCAST_CONSOLE_TO_OPS = "broadcast-console-to-ops"
    BROADCAST_RCON_TO_OPS = "broadcast-rcon-to-ops"
    DIFFICULTY = "difficulty"
    ENABLE_COMMAND_BLOCK = "enable-command-block"
    ENABLE_JMX_MONITORING = "enable-jmx-monitoring"
    ENABLE_QUERY = "enable-query"
    ENABLE_RCON = "enable-rcon"
    ENABLE_STATUS = "enable-status"
    ENFORCE_SECURE_PROFILE = "enforce-secure-profile"
    ENFORCE_WHITELIST = "enforce-whitelist"
    ENTITY_BROADCAST_RANGE_PERCENTAGE = "entity-broadcast-range-percentage"
    FORCE_GAMEMODE = "force-gamemode"
    FUNCTION_PERMISSION_LEVEL = "function-permission-level"
    GAMEMODE = "gamemode"
    GENERATE_STRUCTURES = "generate-structures"
    GENERATOR_SETTINGS = "generator-settings"
    HARDCORE = "hardcore"
    HIDE_ONLINE_PLAYERS = "hide-online-players"
    INITIAL_DISABLED_PACKS = "initial-disabled-packs"
    INITIAL_ENABLED_PACKS = "initial-enabled-packs"
    LEVEL_NAME = "level-name"
    LEVEL_SEED = "level-seed"
    LEVEL_TYPE = "level-type"
    MAX_CHAINED_NEIGHBOR_UPDATES = "max-chained-neighbor-updates"
    MAX_PLAYERS = "max-players"
    MAX_TICK_TIME = "max-tick-time"
    MAX_WORLD_SIZE = "max-world-size"
    MOTD = "motd"
    NETWORK_COMPRESSION_THRESHOLD = "network-compression-threshold"
    ONLINE_MODE = "online-mode"
    OP_PERMISSION_LEVEL = "op-permission-level"
    PLAYER_IDLE_TIMEOUT = "player-idle-timeout"
    PREVENT_PROXY_CONNECTIONS = "prevent-proxy-connections"
    PREVIEWS_CHAT = "previews-chat"
    PVP = "pvp"
    QUERY_PORT = "query.port"
    RATE_LIMIT = "rate-limit"
    RCON_PASSWORD = "rcon.password"
    RCON_PORT = "rcon.port"
    REQUIRE_RESOURCE_PACK = "require-resource-pack"
    RESOURCE_PACK = "resource-pack"
    RESOURCE_PACK_PROMPT = "resource-pack-prompt"
    RESOURCE_PACK_SHA1 = "resource-pack-sha1"
    SERVER_IP = "server-ip"
    SERVER_PORT = "server-port"
    SIMULATION_DISTANCE = "simulation-distance"
    SPAWN_ANIMALS = "spawn-animals"
    SPAWN_MONSTERS = "spawn-monsters"
    SPAWN_NPCS = "spawn-npcs"
    SPAWN_PROTECTION = "spawn-protection"
    SYNC_CHUNK_WRITES = "sync-chunk-writes"
    TEXT_FILTERING_CONFIG = "text-filtering-config"
    USE_NATIVE_TRANSPORT = "use-native-transport"
    VIEW_DISTANCE = "view-distance"
    WHITE_LIST = "white-list"


def get_server_property(property_key: ServerProperties, server_path: str) -> str:
    """
    Retrieves a property value from the Minecraft server.properties file.
    
    Args:
        property_key (ServerProperties): The property key to fetch.
        server_path (str): Path to the server.properties file.

    Returns:
        str: The value of the property or an empty string if not found.
    """
    properties_file = os.path.join(server_path, "server.properties")

    if not os.path.exists(properties_file):
        raise FileNotFoundError(f"The server.properties file was not found at {properties_file}.")

    with open(properties_file, "r") as file:
        for line in file:
            # Skip comments or empty lines
            if line.strip().startswith("#") or not line.strip():
                continue

            # Split into key and value
            if "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()

                if key == property_key.value:
                    return value

    return ""
