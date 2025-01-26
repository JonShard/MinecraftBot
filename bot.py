import os
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
#         self.add_item(Select(placeholder="Choose a date...", options=options))

# @app_commands.command(name="pick_date", description="Pick a date for your event.")
# async def pick_date(interaction: discord.Interaction):
#     view = DatePickerView()
#     await interaction.response.send_message("Select a date:", view=view)


intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents) 

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

# ──────────────────────────
# Bot Lifecycle
# ──────────────────────────
GUILD_ID = 279244769807564800

@bot.event
async def on_ready():
    try:
        print("Attempting to sync guild commands...")
        synced_commands = await bot.tree.sync()        
        print(f"Synced {len(synced_commands)} commands for guild {GUILD_ID}.")
        
        print("Slash commands synced.")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")

    print("Attempting to load cogs...")
    await load_cogs()
    print("Cogs loaded.")   

    bot.loop.create_task(tasks.update_bot_presence_task(bot))
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Start the new CSV logger in the background
    bot.loop.create_task(tasks.player_count_logger_task())
    helpers.generate_player_count_graph()
bot.run(BOT_TOKEN)
