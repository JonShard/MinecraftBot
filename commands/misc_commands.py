
import os
import requests
import re
import discord
from discord.embeds import Embed


import config.config as cfg
from utility.logger import get_logger, LOG_DIR, BASE_LOG_NAME
log = get_logger()


import commands.ops_commands as ops_com
import utility.helper_functions as helpers

def register_commands(bot):
    @bot.tree.command(name="modpack", description="Provides the modpack download link and server's public IP.")
    async def slash_modpack(interaction: discord.Interaction):
        """
        Sends a message with the modpack download link, the server's public IP, and port.
        """
        await helpers.log_interaction(interaction)
        try:
            # Fetch the public IP dynamically
            response = requests.get("https://api.ipify.org?format=text")
            response.raise_for_status()
            public_ip = response.text.strip()
        except Exception as e:
            public_ip = "Unable to fetch public IP"

        # Parse the server port from server.properties
        server_properties_path = os.path.join(cfg.config.minecraft.server_path, "server.properties")
        server_port = "25565"  # Default port
        try:
            with open(server_properties_path, "r") as file:
                for line in file:
                    if line.startswith("server-port="):
                        server_port = line.split("=")[-1].strip()
                        break
        except FileNotFoundError:
            server_port = "Unknown"

        # Append the port to the IP if it's not the default
        if server_port != "25565" and public_ip != "Unable to fetch public IP":
            public_ip = f"{public_ip}:{server_port}"

    # Create the guide
        guide = (
            "## 🛠️ Setup Guide 🛠️\n"
            "1. **Install the CurseForge App**:\n"
            "   - Download and install the CurseForge app from the official website:  \n"
            "   https://download.curseforge.com\n"
            "2. **Download the modpack**:\n"
            "   - Open the CurseForge app and click on the **Minecraft** tab.\n"
            "   - Search for the modpack and click **Install**.\n"
            "   - Once installed, click **Play** to start the modpack.\n"
            "Enjoy your game! 🎮🔥"
        )

        await interaction.response.send_message(
            content=guide,
            ephemeral=False, 
            suppress_embeds=True
        )
        # Send the modpack URL and server address as separate messages for better visibility
        await interaction.channel.send(
            content=(
                f"**Server Address:** `{public_ip}`\n"
                f"**Modpack:** {cfg.config.minecraft.modpack_url}"
            )
        )

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
            "- 📥  **/modpack**: Provides the modpack download link and server's public IP.\n\n"
            
            "### 🧑‍🤝‍🧑 **Player & Chat Commands**\n"
            "- 👥  **/rcon players**: Show who is online, who has joined today, and how many joined yesterday.\n"
            "- 💬  **/rcon chat**: Show a single chat window for the last 10 lines.\n"
            "- 🗣️  **/rcon say**: Send a chat message to the server from Discord.\n\n"

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
            "- 📰  **/logs**: Show recent MC server log\n"
            "- 🎛️  **/server**: Control or check the MC server instance (stop, start, restart, status).\n"
            "- 🔌  **/reboot** 🔒: Reboot the physical machine.\n"
            "- 🗑️  **/wipe** 🔒: Delete the world. (Confirm Yes/No)\n\n"
            
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
            response = "\n".join(log_lines[:10])  # Send first 10 lines to avoid spam
        else:
            response = "No audit log entries found."

        await ctx.send(f"```{response:1990}```")  # Send output in a code block
     
