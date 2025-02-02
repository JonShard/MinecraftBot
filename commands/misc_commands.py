
import os
import requests

import discord


import config.config as cfg
import utility.helper_functions as helpers

def register_commands(bot):
    @bot.tree.command(name="modpack", description="Provides the modpack download link and server's public IP.")
    async def slash_modpack(interaction: discord.Interaction):
        """
        Sends a message with the modpack download link, the server's public IP, and port.
        """
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
