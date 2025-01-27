import os
import re
import shutil
import subprocess
import tarfile
import datetime
import discord
from discord import app_commands

import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers
import utility.server_properties_helper as props_helper

from config import *

import asyncio
from concurrent.futures import ThreadPoolExecutor

# For running tar async
executor = ThreadPoolExecutor()


def create_world_backup(prefix: str) -> str:
    """
    Creates a timestamped tar.gz backup of the Minecraft world folder.
    Args:
        prefix (str): The prefix for the backup file name.
    Returns:
        str: The path of the created backup.
    """
    # Fetch the world folder name from server.properties
    try:
        world_name = props_helper.get_server_property(props_helper.ServerProperties.LEVEL_NAME, MC_SERVER_PATH)
    except FileNotFoundError as e:
        raise RuntimeError("Failed to find server.properties.") from e
    
    if not world_name:
        raise ValueError("World name not found in server.properties.")
    
    world_path = os.path.join(MC_SERVER_PATH, world_name)
    if not os.path.exists(world_path):
        raise FileNotFoundError(f"World folder '{world_name}' does not exist at {world_path}.")

    # Create a timestamped backup name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M")
    backup_name = f"{prefix}_{timestamp}.tar.gz"
    backup_path = os.path.join(BACKUP_PATH, backup_name)

    # Archive the world folder
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(world_path, arcname=os.path.basename(world_path))

    print(f"Created world backup: {backup_path}")
    return backup_path



# Function to run the backup in a separate thread
async def async_create_backup(prefix: str) -> str:
    """
    Runs the create_backup function asynchronously using a thread pool.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, create_world_backup, prefix)


# Use regex to extract the name before the timestamp
def extract_name(full_name: str) -> str:
    match = re.match(r"^(.*?)(_?\d{4}-\d{2}-\d{2}T\d{2}-\d{2}).*", full_name)
    return match.group(1) if match else full_name  # Fallback to full name if no match


# Create a command group for /backup
class BackupCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="backup", description="Manage world backups.")

    @app_commands.command(name="list", description="List all backups.")
    @app_commands.describe(before_date="Optional: Show backups before this date (format DD-MM or DD-MM-YYYY). Ex: 23-01 or 23-01-2025")
    async def backup_list(self, interaction: discord.Interaction, before_date: str = None):
        """Lists all `.tar.gz` archives in the backup folder with size, timestamp, and name."""
        if not os.path.exists(BACKUP_PATH):
            await interaction.response.send_message("Backup folder does not exist!", ephemeral=True)
            return

        # Parse the before_date or use the current timestamp
        try:
            if before_date:
                if len(before_date.split("-")) == 2:  # DD-MM format
                    timestamp = datetime.datetime.strptime(before_date, "%d-%m").replace(year=datetime.datetime.now().year)
                else:  # DD-MM-YYYY format
                    timestamp = datetime.datetime.strptime(before_date, "%d-%m-%Y")
            else:
                timestamp = datetime.datetime.now()
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use DD-MM or DD-MM-YYYY.", ephemeral=True)
            return

        # Gather backups and sort by timestamp
        backups = [
            (file, os.path.getsize(os.path.join(BACKUP_PATH, file)), os.path.getmtime(os.path.join(BACKUP_PATH, file)))
            for file in os.listdir(BACKUP_PATH) if file.endswith(".tar.gz")
        ]
        backups.sort(key=lambda x: x[2], reverse=True)  # Sort by timestamp (descending)

        # Filter backups based on the before_date
        filtered_backups = [
            (name, size, mtime) for name, size, mtime in backups if datetime.datetime.fromtimestamp(mtime) <= timestamp
        ]

        if not filtered_backups:
            await interaction.response.send_message("No backups found before the specified date.", ephemeral=True)
            return

        # Format the backup information
        formatted_backups = [
            f"{datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')} - {size / (1024 * 1024):.2f} MB - {extract_name(name)}"
            for name, size, mtime in filtered_backups
        ]

        # Combine formatted backups into a single string
        backup_message = "```\n" + "\n".join(formatted_backups) + "\n```"

        # Trim the message if it exceeds DISCORD_CHAR_LIMIT
        if len(backup_message) > DISCORD_CHAR_LIMIT:
            max_backups = len(formatted_backups)
            while len(backup_message) > DISCORD_CHAR_LIMIT and max_backups > 0:
                max_backups -= 1
                backup_message = "```\n" + "\n".join(formatted_backups[:max_backups]) + "\n...```"
            print(f"Trimmed backup list to fit within Discord's character limit. {len(formatted_backups) - max_backups} entries removed.")

        # Send the final message
        await interaction.response.send_message(content=backup_message, ephemeral=True)








    @app_commands.command(name="restore", description="🔒 Restore a backup.")
    @app_commands.describe(before_date="Optional: Show backups before this date (format DD-MM or DD-MM-YYYY).")
    async def restore_backup(self, interaction: discord.Interaction, before_date: str = None):
        """Restores a backup by showing a dropdown of available backups."""
        # Authorization (whitelist)
        if interaction.user.id not in ADMIN_USERS:
            await interaction.response.send_message("Sorry, you are not authorized to use this command.", ephemeral=True)
            return     
        # Parse the before_date or use the current timestamp
        try:
            if before_date:
                if len(before_date.split("-")) == 2:  # DD-MM format
                    timestamp = datetime.datetime.strptime(before_date, "%d-%m").replace(year=datetime.datetime.now().year)
                else:  # DD-MM-YYYY format
                    timestamp = datetime.datetime.strptime(before_date, "%d-%m-%Y")
            else:
                timestamp = datetime.datetime.now()
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use DD-MM or DD-MM-YYYY.", ephemeral=True)
            return

        # Gather backups and filter by timestamp
        backups = [
            (file, os.path.getmtime(os.path.join(BACKUP_PATH, file)), os.path.getsize(os.path.join(BACKUP_PATH, file)))
            for file in os.listdir(BACKUP_PATH) if file.endswith(".tar.gz")
        ]
        filtered_backups = [
            (file, mtime, size) for file, mtime, size in sorted(backups, key=lambda x: x[1], reverse=True)
            if datetime.datetime.fromtimestamp(mtime) <= timestamp
        ]

        if not filtered_backups:
            await interaction.response.send_message("No backups found before the specified date.", ephemeral=True)
            return

        # Limit the dropdown options to DISCORD_DROPDOWN_LIMIT
        limited_backups = filtered_backups[:DISCORD_DROPDOWN_LIMIT]

        # Get newest and oldest backups in the set
        newest_backup = limited_backups[0]
        oldest_backup = limited_backups[-1]
        newest_label = f"{datetime.datetime.fromtimestamp(newest_backup[1]).strftime('%Y-%m-%d %H:%M')} - {newest_backup[2] / (1024 * 1024):.2f} MB - {extract_name(newest_backup[0])}"
        oldest_label = f"{datetime.datetime.fromtimestamp(oldest_backup[1]).strftime('%Y-%m-%d %H:%M')} - {oldest_backup[2] / (1024 * 1024):.2f} MB - {extract_name(oldest_backup[0])}"

        # Dropdown with limited backup files
        options = [
            discord.SelectOption(
                label=f"{datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')} - {size / (1024 * 1024):.2f} MB - {extract_name(file)}",
                value=file
            )
            for file, mtime, size in limited_backups
        ]

        class BackupDropdown(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Select a backup to restore", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_backup = self.values[0]
                backup_path = os.path.join(BACKUP_PATH, selected_backup)

                try:

                    # Shut down Minecraft server
                    await interaction.response.send_message(
                        f"Shutting down MC server...",
                        ephemeral=True
                    )
                    try:
                        await ops_helpers.async_service_control("stop", SERVICE_NAME)
                    except Exception as ex:
                        await interaction.followup.send(
                            f"Error running **stop** on `{SERVICE_NAME}`\nCan not restore backup to a running MC server",
                            ephemeral=True
                        )
                        return
                    
                    # Step 1: Acknowledge the interaction immediately
                    await interaction.followup.send(
                        "Creating a restore point... This may take a while. Please wait. ⏳", ephemeral=True
                    )
                    
                    # Step 2: Create the restore point asynchronously
                    restore_point = await async_create_backup("restore_point")

                    await interaction.followup.send(
                        f"Restore point created at `{restore_point}`\nRestoring selected backup...",
                        ephemeral=True
                    )
                    
                    # Step 3: Replace the Minecraft world folder within the server path
                    world_name = props_helper.get_server_property(props_helper.ServerProperties.LEVEL_NAME, MC_SERVER_PATH)  # Get the world folder name
                    world_path = os.path.join(MC_SERVER_PATH, world_name)  # Path to the world folder

                    # Ensure the parent directory exists
                    os.makedirs(MC_SERVER_PATH, exist_ok=True)

                    # Remove the existing world folder if it exists
                    if os.path.exists(world_path):
                        shutil.rmtree(world_path)

                    # Extract the backup into the MC_SERVER_PATH, ensuring the world is placed correctly
                    with tarfile.open(backup_path, "r:gz") as tar:
                        # Extract the world folder to its proper location
                        tar.extractall(MC_SERVER_PATH)

                    # Restart Minecraft server
                    try:
                        await ops_helpers.async_service_control("start", SERVICE_NAME)
                    except Exception as ex:
                        await interaction.followup.send(
                            f"Error running **start** on `{SERVICE_NAME}`\nPlease investigate the MC server.",
                            ephemeral=True
                        )
                        return
                    
                    # Step 4: Notify the user of success
                    await interaction.followup.send(
                        f"Backup `{os.path.join(BACKUP_PATH, selected_backup)}` restored successfully!\nServer should be booting now.",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.followup.send(f"Failed to restore backup: {e}", ephemeral=True)

        class BackupView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(BackupDropdown())

        # Respond with the dropdown and additional information
        await interaction.response.send_message(
            content=(
                f"**Select a backup to restore:**\n"
                f"Newest in set: `{newest_label}`\n"
                f"Oldest in set:  `{oldest_label}`"
            ),
            view=BackupView(),
            ephemeral=True
        )



    @app_commands.command(name="now", description="Create a new backup.")
    @app_commands.describe(name="Optional custom name for the backup",)
    async def create_backup(self, interaction: discord.Interaction, name: str = "backup"):
        """Creates a new backup of the Minecraft server folder."""
        if not os.path.exists(MC_SERVER_PATH):
            await interaction.response.send_message("Minecraft server folder not found!", ephemeral=True)
            return
        
        error = helpers.validate_string(name, 1, 20, True, False)
        if error != "":
            await interaction.response.send_message(error, ephemeral=True)
            return

        try:
            await interaction.response.send_message(
                        "Creating a backup... This may take a while. Please wait. ⏳", ephemeral=True
                    )
            output_name = await async_create_backup(helpers.sanitize_string(name, True, True))

            await interaction.followup.send(f"Backup `{output_name}` created successfully!", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Failed to create backup: {e}", ephemeral=True)




def register_commands(bot):
    bot.tree.add_command(BackupCommands())
