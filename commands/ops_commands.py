import os
import shutil
import re
import time
import subprocess

import discord

from discord import app_commands
from discord import ui
from utility.globals import *
import config.config as cfg
from utility.logger import get_logger
log = get_logger()
import utility.helper_functions as helpers
import utility.ops_helpers as ops_helpers
import utility.server_properties_helper as props_helper

# ──────────────────────────
# Slash Commands
# ──────────────────────────
def register_commands(bot):

    @bot.tree.command(name="status", description="Show the Minecraft server status")
    async def slash_status(interaction: discord.Interaction):
        """
        Slash command that responds with the server status, logs, memory, etc.
        Replicates the old !status command.
        """
        global ext_chunk_count
        await helpers.log_interaction(interaction)

        try:
            # Gather system/server information
            ps_output = subprocess.check_output(['ps', '-eo', 'pid,comm,etime']).decode()
            java_process_line = [line for line in ps_output.split('\n') if 'java' in line][0]

            # Extract the Minecraft server uptime from the `ps` output
            try:
                java_process_line = next((line for line in ps_output.splitlines() if 'java' in line), None)

                if java_process_line:
                    raw_uptime = java_process_line.split()[-1]  # Get the raw uptime, e.g., "03:29:42"
                    uptime_parts = list(map(int, raw_uptime.split(":")))  # Split into hours, minutes, seconds

                    # Ensure the format aligns with "HH Hours MM Minutes SS Seconds"
                    formatted_mc_uptime = (
                        f"{uptime_parts[0]} hours " if len(uptime_parts) == 3 and uptime_parts[0] > 0 else ""
                    ) + (
                        f"{uptime_parts[-2]} minutes " if len(uptime_parts) >= 2 else ""
                    )
                else:
                    formatted_mc_uptime = "Unknown"

            except Exception as e:
                log.error(f"Error parsing Minecraft server uptime: {e}")
                formatted_mc_uptime = "Unknown"



            # Extract machine uptime
            machine_uptime_cmd = subprocess.check_output(['uptime', '-p']).decode().strip()  # "up 1 month, 1 week, 14 hours, 8 minutes"

            # Regex to capture months, weeks, days, hours, and minutes
            uptime_match = re.search(
                r'up\s*(?:(\d+)\s*months?)?,?\s*'
                r'(?:(\d+)\s*weeks?)?,?\s*'
                r'(?:(\d+)\s*days?)?,?\s*'
                r'(?:(\d+)\s*hours?)?,?\s*'
                r'(?:(\d+)\s*minutes?)?', 
                machine_uptime_cmd
            )

            # Extract values, default to 0 if missing
            months = uptime_match.group(1) if uptime_match and uptime_match.group(1) else ""
            weeks = uptime_match.group(2) if uptime_match and uptime_match.group(2) else ""
            days = uptime_match.group(3) if uptime_match and uptime_match.group(3) else ""
            hours = uptime_match.group(4) if uptime_match and uptime_match.group(4) else ""
            minutes = uptime_match.group(5) if uptime_match and uptime_match.group(5) else ""

            # Combine parts into a human-readable format
            formatted_uptime = " ".join(filter(None, [
                f"{months} months" if months else "",
                f"{weeks} weeks" if weeks else "",
                f"{days} days" if days else "",
                f"{hours} hours" if hours else "",
                f"{minutes} minutes" if minutes else ""
            ]))


            # Extract total backup size
            backup_size_cmd = subprocess.check_output(['du', cfg.config.minecraft.backup.path, '-sch']).decode()
            backup_size_match = re.search(r'(\d+G)\s+total', backup_size_cmd)
            backup_size = backup_size_match.group(1) if backup_size_match else "Unknown"

            # Extract available disk space for the backup path
            disk_space_cmd = subprocess.check_output(['df', cfg.config.minecraft.backup.path, '-h']).decode()
            disk_space_match = re.search(r'(\d+G)\s+\d+G\s+(\d+G)\s+\d+%', disk_space_cmd)
            available_space = disk_space_match.group(2) if disk_space_match else "Unknown"

            # Get total memory from `lsmem` using a more robust method
            try:
                lsmem_output = subprocess.check_output(['lsmem'], stderr=subprocess.DEVNULL).decode()

                # Extract the total online memory line
                total_memory_match = re.search(r'Total online memory:\s+([\d,]+)G', lsmem_output)
                total_memory = f"{total_memory_match.group(1).replace(',', '.')}GB" if total_memory_match else "Unknown"
            except Exception as e:
                log.error(f"Error fetching total memory: {e}")
                total_memory = "Unknown"

            # Get memory details from `free`
            free_output = subprocess.check_output(['free', '-h']).decode().splitlines()

            # Locate the line with memory information
            mem_line = next((line for line in free_output if line.startswith('Mem:')), None)

            if mem_line:
                # Split the memory line into parts, ensuring no assumption about the number of columns
                mem_parts = mem_line.split()

                # Extract relevant data based on known column positions
                total_used = mem_parts[1]  # Total memory
                used = mem_parts[2]        # Used memory
                available = mem_parts[-1]  # Available memory (typically the last column)

                # Remove the "i" suffix for readability
                total_used = total_used.replace("Gi", "GB")
                used = used.replace("Gi", "GB")
                available = available.replace("Gi", "GB")
            else:
                total_used = "Unknown"
                used = "Unknown"
                available = "Unknown"

            # Crash reports
            crashes_cmd = (
                f"head -n 4 {cfg.config.minecraft.crash_reports_dir}/* | grep -E 'Time: ' | awk '{{print $2 \" \" $3}}' | tail -n 10"
            )
            crashes_times = subprocess.check_output([crashes_cmd], shell=True).decode() or "No crashes yet! <3"

            latest_logs = subprocess.check_output(['tail', '-n', str(5), cfg.config.minecraft.log_file_path]).decode()

            # Detect lag occurrences
            with open(cfg.config.minecraft.log_file_path, 'r') as log_file:
                log_contents = log_file.read()
            lag_occurrences = len(re.findall(r'Running \d+ms or \d+ ticks behind', log_contents))

            # Average ms behind
            ms_values = [int(match) for match in re.findall(r'Running (\d+)ms or \d+ ticks behind', log_contents)]
            average_ms = sum(ms_values) / len(ms_values) if ms_values else 0

            # Total missed ticks
            total_missed_ticks = sum(
                int(match) for match in re.findall(r'Running \d+ms or (\d+) ticks behind', log_contents)
            )

            output = (
                f"Player Count: `{player_count}`\n"
                f"Minecraft uptime: `{formatted_mc_uptime.strip()}`\n"
                f"Machine uptime: `{formatted_uptime}`\n"
                f"Total backup size: `{backup_size} ({available_space} available)`\n"
                f"Memory usage: `{used} ({available} available, total {total_memory})`\n"
                f"Recent crashes: ```\n{crashes_times}\n```"
                f"*'Running behind'* log occurrences: `{lag_occurrences}`\n"
                f"Average ms of *'Running behind'* logs: `{average_ms:.0f}` ms\n"
                f"Total missed seconds from *'Running behind'* logs: `{total_missed_ticks * 50 / 1000}`\n"
                f"*'Saving external chunk'* log occurrences: `{ext_chunk_count}`\n"
                f"Latest logs:```\n{latest_logs}```"
            )

            # Trim output if it exceeds 2000 characters
            if len(output) > cfg.config.bot.discord_char_limit:
                trimmed_length = len(output) - cfg.config.bot.discord_char_limit
                # Ensure the message ends properly with the closing backticks for the code block
                truncation_message = "... (truncated)\n```"
                output = output[:cfg.config.bot.discord_char_limit - len(truncation_message)] + truncation_message
                log.debug(f"Trimmed {trimmed_length} characters from the status message.")
            # If the message doesn't exceed the limit but still needs to end with a code block
            elif not output.endswith("```"):
                output += "```"
        except Exception as e:
            output = f"An error occurred: {str(e)}"

        # Respond to the slash command so everyone can see
        await interaction.response.send_message(output, ephemeral=False)




    @bot.tree.command(name="server", description="🔒 Control or check the MC server instance (stop, start, restart, status).")
    @app_commands.describe(action="Choose an action for the server service.")
    @app_commands.choices(action=[
        discord.app_commands.Choice(name="status", value="status"),
        discord.app_commands.Choice(name="start", value="start"),
        discord.app_commands.Choice(name="stop", value="stop"),
        discord.app_commands.Choice(name="restart", value="restart")
    ])
    async def slash_server(interaction: discord.Interaction, action: str):
        """
        Executes 'sudo systemctl <action> SERVICE_NAME' asynchronously.
        - For 'status', only show the top portion before the logs (stopping at the first blank line).
        - For stop/start/restart, confirm success or failure.
        """
        try:
            await interaction.response.defer(ephemeral=False, thinking=True)

            if action == "status":
                # Fetch and display service status
                await helpers.log_interaction(interaction)
                status_message = await ops_helpers.async_service_status()
                await interaction.followup.send(status_message, ephemeral=False)
            else:
                if not await helpers.authorize_interaction(interaction):
                    return  # Stop execution if the user is not authorized


                # Perform stop, start, or restart
                success_message = await ops_helpers.async_service_control(action)
                await interaction.followup.send(success_message, ephemeral=False)
        except Exception as ex:
            await interaction.followup.send(
                f"Error running **{action}** on `{cfg.config.minecraft.service_name}`: {ex}",
                ephemeral=True
            )



    @bot.tree.command(name="reboot", description="🔒 Reboot the physical machine.")
    async def slash_reboot(interaction: discord.Interaction):
        """
        Reboots the server by running 'sudo reboot'. Admin-only command.
        The bot logs out before executing the reboot to indicate downtime.
        """
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized


        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            # Notify about the reboot
            await interaction.followup.send(
                "Rebooting the server in soon, this may take a while. 🖥️",
                ephemeral=False
            )

            # Stop the Minecraft service
            try:
                subprocess.check_output(
                    ["sudo", "systemctl", "stop", cfg.config.minecraft.service_name],
                    stderr=subprocess.STDOUT
                )
            except subprocess.CalledProcessError as e:
                error_message = e.output.decode(errors="ignore") if e.output else "No error output"
                await interaction.followup.send(
                    f"Failed to stop the Minecraft service:\n```\n{error_message}\n```",
                    ephemeral=True
                )
                return

            # Wait for 30 seconds
            time.sleep(30)

            # Logout the bot
            await bot.close()

            # Execute the reboot command
            subprocess.check_output(["sudo", "reboot"], stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            error_message = e.output.decode(errors="ignore") if e.output else "No error output"
            try:
                await interaction.followup.send(
                    f"Failed to reboot the server:\n```\n{error_message}\n```",
                    ephemeral=True
                )
            except discord.errors.ClientException:
                log.error(f"Failed to send error message: {error_message}")
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"An unexpected error occurred while attempting to reboot the server: {e}",
                    ephemeral=True
                )
            except discord.errors.ClientException:
                log.error(f"Failed to send unexpected error message: {e}")



    class WipeConfirmationModal(ui.Modal, title="Confirm World Wipe"):
        def __init__(self):
            super().__init__()

        # Confirmation field (to type "YES" for confirmation)
        confirmation = ui.TextInput(
            label="Type 'YES' to confirm",
            placeholder="Type 'YES' to confirm wiping the world",
            style=discord.TextStyle.short,
            required=True,
            max_length=3
        )

        async def on_submit(self, interaction: discord.Interaction):
            # Check if the confirmation input matches "YES"
            if self.confirmation.value.strip().upper() == "YES":
                await interaction.response.defer(thinking=True)

                # Get the world name from server.properties
                world_name = props_helper.get_server_property(
                    props_helper.ServerProperties.LEVEL_NAME, cfg.config.minecraft.server_path
                )
                world_path = os.path.join(cfg.config.minecraft.server_path, world_name)

                was_running = await ops_helpers.is_service_running()
    
                # Check if the server is running
                if was_running:
                    # Stop the server
                    await interaction.followup.send("Stopping the server...", ephemeral=True)
                    await ops_helpers.async_service_control("stop")

                # Delete the world directory
                if os.path.exists(world_path):
                    try:
                        shutil.rmtree(world_path)
                        await interaction.followup.send(f"World `{world_name}` has been wiped successfully.", ephemeral=False)
                    except Exception as e:
                        await interaction.followup.send(f"Failed to wipe the world: {e}", ephemeral=True)
                        return

                # Restart the server if it was running
                if was_running:
                    await interaction.followup.send("Restarting the server...", ephemeral=True)
                    await ops_helpers.async_service_control("start")

            else:
                await interaction.response.send_message("Wipe canceled. Incorrect confirmation input.", ephemeral=True)


    @bot.tree.command(name="wipe", description="🔒 Delete the world. (Confirm Yes/No)")
    async def slash_wipe(interaction: discord.Interaction):
        """
        Slash command to wipe the Minecraft world.
        """
        # Check if the user is an admin
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized


        # Show the confirmation modal
        await interaction.response.send_modal(WipeConfirmationModal())
        
            
            

    @bot.tree.command(name="logs", description="Show recent MC server log (or debug log)")
    async def slash_logs(interaction: discord.Interaction, line_count: app_commands.Range[int, 1, 500] = 10, debug_log: bool = False):
        """Fetches the last N lines from the Minecraft log and sends them in chunks."""
        await helpers.log_interaction(interaction)
        
        if not debug_log:
            log_file_path = cfg.config.minecraft.log_file_path
        else:
            log_file_path = cfg.config.minecraft.debug_log_file_path

        try:
            with open(log_file_path, "r") as log_file:
                log_lines = log_file.readlines()[-line_count:]  # Read only the last N lines

            log_text = "".join(log_lines)  # Convert to a single string
            messages = [log_text[i:i + cfg.config.bot.discord_char_limit] for i in range(0, len(log_text), cfg.config.bot.discord_char_limit)]  # Split into chunks

            # Send the first message using interaction.response
            first_message = messages.pop(0)
            await interaction.response.send_message(f"{first_message}", ephemeral=True)

            # Send the remaining messages using followup
            for message in messages:
                await interaction.followup.send(f"{message}", ephemeral=True)

            # Attach the full log file
            file = discord.File(log_file_path, os.path.basename(log_file_path))
            await interaction.followup.send(file=file, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error reading log file: {str(e)}", ephemeral=True)



    class CrashDropdown(discord.ui.Select):
        def __init__(self, interaction: discord.Interaction, crash_files: list[str]):
            options = [
                discord.SelectOption(label=file, value=file) for file in crash_files
            ]
            super().__init__(placeholder="Select a crash report to view", options=options[:cfg.config.bot.discord_dropdown_limit])
            self.interaction = interaction

        async def callback(self, interaction: discord.Interaction):
            selected_file = self.values[0]
            file_path = os.path.join(cfg.config.minecraft.crash_reports_dir, selected_file)

            try:
                # Send full file as attachment
                file = discord.File(file_path, filename=selected_file)
                await interaction.response.send_message(file=file, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(
                    f"Error reading crash report: {str(e)}", ephemeral=True
                )

    class CrashView(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, crash_files: list[str]):
            super().__init__(timeout=60)
            self.add_item(CrashDropdown(interaction, crash_files))
            
    @bot.tree.command(name="crashes", description="Show and download recent crash reports")
    async def slash_crashes(interaction: discord.Interaction):
        try:
            crash_files = sorted(
                [f for f in os.listdir(cfg.config.minecraft.crash_reports_dir) if f.startswith("crash-")],
                reverse=True
            )[:cfg.config.bot.discord_dropdown_limit]  # Get the last configured number of crash files

            if not crash_files:
                await interaction.response.send_message("No crash reports found.", ephemeral=True)
                return

            view = CrashView(interaction, crash_files)
            await interaction.response.send_message("Please select one of the last {discord_dropdown_limit} crash reports:", view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"Error retrieving crash reports: {str(e)}", ephemeral=True
            )