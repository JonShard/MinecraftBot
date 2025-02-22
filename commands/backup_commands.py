import os
import shutil
import re
import tarfile
import datetime
import discord
from discord import app_commands, TextStyle, ui

import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers
import utility.server_properties_helper as props_helper

import config.config as cfg
from utility.logger import get_logger
log = get_logger()

# Use regex to extract the name before the timestamp
def extract_name(full_name: str) -> str:
    match = re.match(r"^(.*?)(_?\d{4}-\d{2}-\d{2}T\d{2}-\d{2}).*", full_name)
    return match.group(1) if match else full_name  # Fallback to full name if no match

# Create a command group for /backup
class BackupCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="backup", description="Manage world backups.")

    @app_commands.command(name="list", description="List all backups.")
    @app_commands.describe(before_date="Optional: Show backups before this date (format 'HH:MM' or 'HH:MM DD-MM' or 'DD-MM-YYYY'). Ex: '20:30' or 05-01-2025")
    async def backup_list(self, interaction: discord.Interaction, before_date: str = None):
        await helpers.log_interaction(interaction)
        """Lists all `.tar.gz` archives in the backup folder with size, timestamp, and name."""
        if not os.path.exists(cfg.config.minecraft.backup.path):
            await interaction.response.send_message("Backup folder does not exist!", ephemeral=True)
            return

        # Validate and parse the timestamp
        try:
            timestamp = helpers.validate_timestamp(before_date)
        except ValueError as e:
            await interaction.response.send_message(f"Invalid date format. Use HH:MM, DD-MM, HH:MM DD-MM, or DD-MM-YYYY.\nError: {e}", ephemeral=True)
            return

        # Gather backups and sort by timestamp
        backups = [
            (file, os.path.getsize(os.path.join(cfg.config.minecraft.backup.path, file)), os.path.getmtime(os.path.join(cfg.config.minecraft.backup.path, file)))
            for file in os.listdir(cfg.config.minecraft.backup.path) if file.endswith(".tar.gz")
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
        if len(backup_message) > cfg.config.bot.discord_char_limit:
            max_backups = len(formatted_backups)
            while len(backup_message) > cfg.config.bot.discord_char_limit and max_backups > 0:
                max_backups -= 1
                backup_message = "```\n" + "\n".join(formatted_backups[:max_backups]) + "\n...```"
            log.debug(f"Trimmed backup list to fit within Discord's character limit. {len(formatted_backups) - max_backups} entries removed.")

        # Send the final message
        await interaction.response.send_message(content=backup_message, ephemeral=True)




            




    @app_commands.command(name="restore", description="🔒 Restore a backup.")
    @app_commands.describe(before_date="Optional: Show backups before this date (format 'HH:MM' or 'HH:MM DD-MM' or 'DD-MM-YYYY'). Ex: '20:30' or 05-01-2025")
    async def restore_backup(self, interaction: discord.Interaction, before_date: str = None):
        """Restores a backup by showing a dropdown of available backups."""
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized
         
        # Validate and parse the timestamp
        try:
            timestamp = helpers.validate_timestamp(before_date)
        except ValueError as e:
            await interaction.response.send_message(f"Invalid date format. Use HH:MM, DD-MM, HH:MM DD-MM, or DD-MM-YYYY.\nError: {e}", ephemeral=True)
            return

        # Gather backups and filter by timestamp
        backups = [
            (file, os.path.getmtime(os.path.join(cfg.config.minecraft.backup.path, file)), os.path.getsize(os.path.join(cfg.config.minecraft.backup.path, file)))
            for file in os.listdir(cfg.config.minecraft.backup.path) if file.endswith(".tar.gz")
        ]
        filtered_backups = [
            (file, mtime, size) for file, mtime, size in sorted(backups, key=lambda x: x[1], reverse=True)
            if datetime.datetime.fromtimestamp(mtime) <= timestamp
        ]

        if not filtered_backups:
            await interaction.response.send_message("No backups found before the specified date.", ephemeral=True)
            return

        # Limit the dropdown options to DISCORD_DROPDOWN_LIMIT
        limited_backups = filtered_backups[:cfg.config.bot.discord_dropdown_limit]

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

        class BackupConfirmationModal(ui.Modal, title="Confirm Backup Restore"):
            def __init__(self, selected_backup: str):
                super().__init__()
                self.selected_backup = selected_backup  
                self.backup_path = os.path.join(cfg.config.minecraft.backup.path, selected_backup)

                # Add a dynamic confirmation input with a custom label
                self.confirmation = ui.TextInput(
                    label=f"Use: {self.selected_backup[:39]}?",
                    placeholder="Type 'YES' to confirm using this restore",
                    style=TextStyle.short,
                    required=True,
                    max_length=3
                )
                self.add_item(self.confirmation)  # Dynamically add the text input

            async def on_submit(self, interaction: discord.Interaction):
                # Check if the confirmation input matches "YES"
                if self.confirmation.value.strip().upper() != "YES":
                    await interaction.response.send_message("Restore cancelled. You did not confirm.", ephemeral=True)
                    return            
                
                try:

                    # Shut down Minecraft server
                    await interaction.response.send_message(
                        f"Shutting down MC server...",
                        ephemeral=True
                    )
                    try:
                        await ops_helpers.async_service_control("stop")
                    except Exception as ex:
                        await interaction.followup.send(
                            f"Error running **stop** on `{cfg.config.minecraft.service_name}`\nCan not restore backup to a running MC server",
                            ephemeral=True
                        )
                        return
                    
                    # Step 1: Acknowledge the interaction immediately
                    await interaction.followup.send(
                        "Creating a restore point... This may take a while. Please wait. ⏳", ephemeral=True
                    )
                    
                    # Step 2: Create the restore point asynchronously
                    restore_point = await ops_helpers.async_create_backup("restore_point", True)
                    if restore_point == "":
                        await interaction.followup.send(
                            "World folder did not exist. No restore point was made.", ephemeral=True
                    )
                    else:
                        await interaction.followup.send(
                            f"Restore point created at `{restore_point}`\nRestoring selected backup...",
                            ephemeral=True
                        )
                    
                    # Step 3: Replace the Minecraft world folder within the server path
                    world_name = props_helper.get_server_property(props_helper.ServerProperties.LEVEL_NAME, cfg.config.minecraft.server_path)  # Get the world folder name
                    world_path = os.path.join(cfg.config.minecraft.server_path, world_name)  # Path to the world folder

                    # Ensure the parent directory exists
                    os.makedirs(cfg.config.minecraft.server_path, exist_ok=True)

                    # Remove the existing world folder if it exists
                    if os.path.exists(world_path):
                        shutil.rmtree(world_path)

                    # Extract the backup into the MC_SERVER_PATH, ensuring the world is placed correctly
                    with tarfile.open(self.backup_path, "r:gz") as tar:
                        # Extract the world folder to its proper location
                        tar.extractall(cfg.config.minecraft.server_path)

                    # Restart Minecraft server
                    try:
                        await ops_helpers.async_service_control("start")
                    except Exception as ex:
                        await interaction.followup.send(
                            f"Error running **start** on `{cfg.config.minecraft.service_name}`\nPlease investigate the MC server.",
                            ephemeral=True
                        )
                        return
                    
                    # Step 4: Notify the user of success
                    await interaction.followup.send(
                        f"Backup `{os.path.join(cfg.config.minecraft.backup.path, self.selected_backup)}` restored successfully!\nServer should be booting now.",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.followup.send(f"Failed to restore backup: {e}", ephemeral=True)



        class BackupDropdown(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="Select a backup to restore", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_backup = self.values[0]
                # Show the confirmation modal
                await interaction.response.send_modal(BackupConfirmationModal(selected_backup))
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
        await helpers.log_interaction(interaction)
        if not os.path.exists(cfg.config.minecraft.server_path):
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
            output_name = await ops_helpers.async_create_backup(helpers.sanitize_string(name, True, True), True)

            await interaction.followup.send(f"Backup `{output_name}` created successfully!", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Failed to create backup: {e}", ephemeral=True)




def register_commands(bot):
    bot.tree.add_command(BackupCommands())
