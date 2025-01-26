import os
import importlib

import discord
from discord.ext import commands

from config import *
import utility.background_tasks as tasks
import utility.helper_functions as helpers

# from discord.ui import Select, View

# class DatePickerView(View):
#     def __init__(self):
#         super().__init__()
#         options = [
#             discord.SelectOption(label="Today", value="today"),
#             discord.SelectOption(label="Tomorrow", value="tomorrow"),
#             discord.SelectOption(label="Next Week", value="next_week"),
#         ]
#         add_item(Select(placeholder="Choose a date...", options=options))

# @app_commands.command(name="pick_date", description="Pick a date for your event.")
# async def pick_date(interaction: discord.Interaction):
#     view = DatePickerView()
#     await interaction.response.send_message("Select a date:", view=view)


intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents) 

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

    bot.loop.create_task(tasks.update_bot_presence_task(bot))
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Start the new CSV logger in the background
    bot.loop.create_task(tasks.player_count_logger_task())
    helpers.generate_player_count_graph()
bot.run(BOT_TOKEN)
