import os
import asyncio
import discord
from discord.ext import commands

import config.config as cfg

# ──────────────────────────
# Load Config Before Creating the Bot
# ──────────────────────────
async def load_config_early():
    if not await cfg.load_config():
        print("ERROR: Failed to load configuration. An error occured. Exiting...")
        exit(1)  # Stop execution if config failed to load
    if cfg.config is None:
        print("ERROR: Failed to load configuration. config is None Exiting...")
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
                print(f"Registered commands from {module_name}")
            else:
                print(f"No register() function in {module_name}, skipping.")
        except Exception as e:
            print(f"Error loading {module_name}: {e}")


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
        print("Attempting to sync commands...")
        synced_commands = await bot.tree.sync()        
        print(f"Synced {len(synced_commands)} commands.")
        
        print("Slash commands synced.")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")

    await start_tasks()

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    
bot.run(cfg.config.bot.bot_token)
