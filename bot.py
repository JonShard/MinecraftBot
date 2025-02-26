import os
import asyncio
import discord
from discord.ext import commands

import config.config as cfg
import state.state as st
from utility.logger import get_logger
log = get_logger()


# ──────────────────────────
# Load Config Before Creating the Bot
# ──────────────────────────
async def load_config_early():
    log.info("############### Minecraft Bot Start ###############")
    if not await cfg.load_config():
        log.error("ERROR: Failed to load configuration. An error occured. Exiting...")
        exit(1)  # Stop execution if config failed to load
    if cfg.config is None:
        log.error("ERROR: Failed to load configuration. config is None Exiting...")
        exit(1)  # Stop execution if config failed to load

# Run the config load early
asyncio.run(load_config_early())

# Create bot instance
intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents) 

# Register commands from all .py files in the commands folder
commands_dir = "./commands"  # Path to the command files
for filename in os.listdir(commands_dir):
    if filename.endswith(".py") and not filename.startswith("_"):
        module_name = filename[:-3]  # Remove .py extension
        try:
            # Import the module dynamically
            module = __import__(f"commands.{module_name}", fromlist=["register_commands"])
            
            # Call the `register_commands()` function in the module
            if hasattr(module, "register_commands"):
                module.register_commands(bot)
                log.debug(f"Registered commands from {module_name}")
            else:
                log.warning(f"No register() function in {module_name}, skipping.")
        except Exception as e:
            log.error(f"Error loading {module_name}: {e}")


async def start_tasks():
    import tasks.background_tasks as bg_tasks
    import tasks.ops_tasks as ops_tasks
    import tasks.notification_tasks as noti_tasks
    # State gathering tasks
    bg_tasks.player_count_logger_task.start() # Start the new CSV logger in the background
    bg_tasks.update_lag_history.start()
    bg_tasks.clear_daily_state.start()
    # Ops tasks
    ops_tasks.update_bot_presence_task.start(bot)
    ops_tasks.backup_task.start()
    ops_tasks.restart_task.start()
    # Notification tasks
    noti_tasks.notify_player_join.start(bot)     # Player joined
    noti_tasks.notify_server_behind.start(bot)   # Server is lagging
    noti_tasks.notify_external_chunks.start(bot) # external chunks might be causing lag
    noti_tasks.notify_generic_errors.start(bot)    # chunks might be broken, player base might be affected
    
# ──────────────────────────
# Bot Lifecycle
# ──────────────────────────
@bot.event
async def on_ready():
    # Generate state.yaml if it doesn't already exist
    await st.load_state()
    st.save_state()
    
    if cfg.config.bot.sync_commands:
        try:
            log.info("Attempting to sync commands...")
            synced_commands = await bot.tree.sync()        
            log.info(f"Synced {len(synced_commands)} commands.")        
        except Exception as e:
            log.error(f"Error syncing slash commands: {e}")
    else:
        log.info("Skipping commands sync.")
        
    await start_tasks()
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

bot.run(cfg.config.bot.bot_token)
