
import os
import re
import discord
from discord.embeds import Embed


import config.config as cfg
from utility.logger import get_logger, LOG_DIR, BASE_LOG_NAME
log = get_logger()


import commands.ops_commands as ops_com
import utility.helper_functions as helpers

def register_commands(bot):
    
    class QuickMenu(discord.ui.View):
        def __init__(self, time : str):
            super().__init__(timeout=None)  # No timeout, stays active
            
        @discord.ui.button(label="/status",  style=discord.ButtonStyle.danger, custom_id="delete_button")
        async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            ops_com.register_commands

    @bot.tree.command(name="help", description="Show all available commands grouped by category.")
    async def slash_help(interaction: discord.Interaction):
        await helpers.log_interaction(interaction)
        """
        Show all available commands grouped by category.
        """
        response = (
            "## **Minecraft Bot Commands**\n"
            "Commands with a 🔒 can only be used by whitelisted admins\n"
            
            "### **Modpack Commands**\n"
            "- 📥  **/modpack info**: Provides the modpack download link and server's public IP.\n\n"
            
            "### 🧑‍🤝‍🧑 **Player & Chat Commands**\n"
            "- 👥  **/rcon players**: Show who is online, who has joined today, and how many joined yesterday.\n"
            "- 💬  **/rcon chat**: Show a single chat window for the last 10 lines.\n"
            "- 🗣️  **/rcon say**: Send a chat message to the server from Discord.\n\n"
            
            "### **Notifications**\n"
            "- 🔔  **/notifications**: Show a menu where you can opt-in and out of different kinds of notifications\n\n"
            
            "### 🖥️ **Minecraft Server Admin**\n"
            "- 🌤️  **/rcon weather**: Set the weather in the Minecraft world.\n"
            "- 🔪  **/rcon kill** 🔒: Kill specific types of entities in the Minecraft world.\n"
            "- ⚙️  **/rcon command** 🔒: Execute an RCON command on the server.\n\n"

            "### 🕘 **Automatic Restarts**\n"
            "- 🖊️  **/restart add** 🔒: Add a new restart time. Ex: 05:00 or 23:00.\n"
            "- 📜  **/restart list** 🔒: Manage all restart times. Remove a time.\n\n"

            "### 💾 **Backups & Restores**\n"
            "- 📁  **/backup list**: List all backups.\n"
            "- ⬇️  **/backup now**: Create a new backup.\n"
            "- 🔄  **/backup restore** 🔒: Restore a backup.\n\n"

            "### 🛠️ **Utility Commands**\n"
            "- 📊  **/status**: Show the Minecraft server status.\n"
            "- 📰  **/logs**: Show and download recent MC server log\n"
            "- 💥  **/crashes**: Show and download recent crash reports.\n"
            "- 🎛️  **/server**: Control or check the MC server instance (stop, start, restart, status).\n"
            "- 🔌  **/reboot** 🔒: Reboot the physical machine.\n"
            "- 🗑️  **/wipe** 🔒: Delete the world. (Confirm Yes/No)\n"
            "- 🧹 **/reset** 🔒: Delete the bot's data about the MC server or its Discord users. (Confirm Yes/No)\n\n"
            
            "*Check the bot's source code here: [GitHub](https://github.com/JonShard/MinecraftBot)*"
        )
        await interaction.response.send_message(response)


    @bot.command()
    async def audit(ctx):
        log_lines = []

        # Read all matching log files
        for log_file in sorted(os.listdir(LOG_DIR)):
            if log_file.startswith(BASE_LOG_NAME):  # Ensure it matches mc_bot*.log
                with open(os.path.join(LOG_DIR, log_file), "r", encoding="utf-8") as file:
                    for line in file:
                        if "[Auth]" in line:  # Equivalent to grep '\[Auth\]'
                            # Apply regex transformation (equivalent to your `sed` command)
                            match = re.search(r"([0-9-]+ [0-9:]+) \[INFO\] MineBot:[0-9]+ - \[Auth\] ((?:Allowed|Open|DENIED): .*)", line)
                            if match:
                                log_lines.append(f"{match.group(1)} {match.group(2)}")

        # Send response
        if log_lines:
            response = "\n".join(log_lines[-20:])  # Send first N lines to avoid spam
        else:
            response = "No audit log entries found."

        await ctx.send(f"```{response:1990}```")  # Send output in a code block
     
