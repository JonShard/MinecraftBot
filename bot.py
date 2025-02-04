import os
import asyncio
import discord
from discord.ext import commands

import config.config as cfg
from utility.logger import get_logger
log = get_logger()


# ──────────────────────────
# Load Config Before Creating the Bot
# ──────────────────────────
async def load_config_early():
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
    import utility.background_tasks as tasks
    tasks.update_bot_presence_task.start(bot) # bot.loop.create_task(tasks.update_bot_presence_task(bot))
    tasks.player_count_logger_task.start() # Start the new CSV logger in the background
    tasks.backup_task.start()
    tasks.restart_task.start()
    
# ──────────────────────────
# Bot Lifecycle
# ──────────────────────────
@bot.event
async def on_ready():
    try:
        log.info("Attempting to sync commands...")
        synced_commands = await bot.tree.sync()        
        log.info(f"Synced {len(synced_commands)} commands.")
        
        log.info("Slash commands synced.")
    except Exception as e:
        log.error(f"Error syncing slash commands: {e}")

    await start_tasks()

    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    
bot.run(cfg.config.bot.bot_token)
