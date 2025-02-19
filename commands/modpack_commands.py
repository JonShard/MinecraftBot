import os
import re
import requests
import zipfile
import shutil
from urllib.parse import urlparse

import discord
from discord import app_commands

import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers
import utility.server_properties_helper as props_helper

import config.config as cfg
from utility.logger import get_logger

# Create a command group for /backup
class ModpackCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="modpack", description="Get info about the current modpack or install a new one")


    @app_commands.command(name="info", description="Provides the modpack download link and server's public IP.")
    async def slash_modpack(self, interaction: discord.Interaction):
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



    # # Constants
    # CURSEFORGE_API_KEY = 'your_curseforge_api_key'
    # HEADERS = {'x-api-key': CURSEFORGE_API_KEY}
    # BASE_URL = 'https://api.curseforge.com/v1'
    # MODS_ENDPOINT = f'{BASE_URL}/mods'
    # FILES_ENDPOINT = f'{BASE_URL}/mods/{{mod_id}}/files/{{file_id}}/download-url'
    # MODPACKS_DIR = '/path/to/minecraft/modpacks'
    # SERVER_MODS_DIR = '/path/to/minecraft/server/mods'

    # def extract_modpack_id(input_str):
    #     """Extracts modpack ID from a URL or returns the ID if directly provided."""
    #     # Check if input is a URL
    #     if input_str.startswith('http'):
    #         # Parse the URL to extract the modpack ID
    #         parsed_url = urlparse(input_str)
    #         match = re.search(r'/mc-mods/(\d+)', parsed_url.path)
    #         if match:
    #             return int(match.group(1))
    #         else:
    #             raise ValueError("Invalid CurseForge modpack URL.")
    #     else:
    #         # Assume the input is a direct modpack ID
    #         return int(input_str)

    # def fetch_modpack_details(modpack_id):
    #     """Fetches modpack details from CurseForge API."""
    #     response = requests.get(f'{MODS_ENDPOINT}/{modpack_id}', headers=HEADERS)
    #     if response.status_code == 200:
    #         return response.json()['data']
    #     else:
    #         raise Exception(f"Failed to fetch modpack details: {response.status_code}")

    # def download_modpack_file(download_url, dest_path):
    #     """Downloads the modpack file from the given URL."""
    #     response = requests.get(download_url, stream=True)
    #     if response.status_code == 200:
    #         with open(dest_path, 'wb') as f:
    #             for chunk in response.iter_content(chunk_size=8192):
    #                 f.write(chunk)
    #     else:
    #         raise Exception(f"Failed to download modpack file: {response.status_code}")

    # def install_modpack(modpack_id_or_url):
    #     try:
    #         # Step 1: Extract Modpack ID
    #         modpack_id = extract_modpack_id(modpack_id_or_url)

    #         # Step 2: Fetch Modpack Details
    #         modpack_details = fetch_modpack_details(modpack_id)
    #         latest_file = modpack_details['latestFiles'][0]  # Assuming the first file is the latest
    #         file_id = latest_file['id']
    #         file_name = latest_file['fileName']

    #         # Step 3: Get Download URL
    #         download_url_response = requests.get(FILES_ENDPOINT.format(mod_id=modpack_id, file_id=file_id), headers=HEADERS)
    #         if download_url_response.status_code == 200:
    #             download_url = download_url_response.json()['data']
    #         else:
    #             raise Exception(f"Failed to get download URL: {download_url_response.status_code}")

    #         # Step 4: Download the Modpack
    #         modpack_zip_path = os.path.join(MODPACKS_DIR, file_name)
    #         download_modpack_file(download_url, modpack_zip_path)

    #         # Step 5: Extract and Install the Modpack
    #         with zipfile.ZipFile(modpack_zip_path, 'r') as zip_ref:
    #             zip_ref.extractall(MODPACKS_DIR)

    #         # Move extracted files to the server's mod directory
    #         extracted_modpack_dir = os.path.join(MODPACKS_DIR, file_name.replace('.zip', ''))
    #         for item in os.listdir(extracted_modpack_dir):
    #             s = os.path.join(extracted_modpack_dir, item)
    #             d = os.path.join(SERVER_MODS_DIR, item)
    #             if os.path.isdir(s):
    #                 shutil.copytree(s, d, dirs_exist_ok=True)
    #             else:
    #                 shutil.copy2(s, d)

    #         # Clean up
    #         os.remove(modpack_zip_path)
    #         shutil.rmtree(extracted_modpack_dir)

    #         print("Modpack installed successfully. Please restart the server to apply changes.")

    #     except Exception as e:
    #         print(f"An error occurred: {e}")












def register_commands(bot):
    bot.tree.add_command(ModpackCommands())
