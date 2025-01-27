
import re
import time
import subprocess

import discord

from discord import app_commands

from config import *
import utility.ops_helpers as ops_helpers

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
                print(f"Error parsing Minecraft server uptime: {e}")
                formatted_mc_uptime = "Unknown"



            # Extract machine uptime
            machine_uptime_cmd = subprocess.check_output(['uptime', '-p']).decode().strip()  # Example: "up 1 day, 11 hours, 59 minutes"
            machine_uptime_match = re.search(r'up (\d+ days?)?,?\s?(\d+ hours?)?,?\s?(\d+ minutes?)?', machine_uptime_cmd)

            # Initialize parts to empty strings
            days = machine_uptime_match.group(1) if machine_uptime_match and machine_uptime_match.group(1) else ""
            hours = machine_uptime_match.group(2) if machine_uptime_match and machine_uptime_match.group(2) else ""
            minutes = machine_uptime_match.group(3) if machine_uptime_match and machine_uptime_match.group(3) else ""

            # Combine parts into a human-readable format
            formatted_uptime = " ".join(filter(None, [days.strip(), hours.strip(), minutes.strip()])).replace("  ", " ")



            # Extract total backup size
            backup_size_cmd = subprocess.check_output(['du', BACKUP_PATH, '-sch']).decode()
            backup_size_match = re.search(r'(\d+G)\s+total', backup_size_cmd)
            backup_size = backup_size_match.group(1) if backup_size_match else "Unknown"

            # Extract available disk space for the backup path
            disk_space_cmd = subprocess.check_output(['df', BACKUP_PATH, '-h']).decode()
            disk_space_match = re.search(r'(\d+G)\s+\d+G\s+(\d+G)\s+\d+%', disk_space_cmd)
            available_space = disk_space_match.group(2) if disk_space_match else "Unknown"

            # Get total memory from `lsmem` using a more robust method
            try:
                lsmem_output = subprocess.check_output(['lsmem'], stderr=subprocess.DEVNULL).decode()

                # Extract the total online memory line
                total_memory_match = re.search(r'Total online memory:\s+([\d,]+)G', lsmem_output)
                total_memory = f"{total_memory_match.group(1).replace(',', '.')}GB" if total_memory_match else "Unknown"
            except Exception as e:
                print(f"Error fetching total memory: {e}")
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
                f"head -n 4 {CRASH_REPORTS_DIR}/* | grep -E 'Time: ' | awk '{{print $2 \" \" $3}}' | tail -n 10"
            )
            crashes_times = subprocess.check_output([crashes_cmd], shell=True).decode() or "No crashes yet! <3"

            latest_logs = subprocess.check_output(['tail', '-n', str(LATEST_LOG_LINES), LOG_FILE_PATH]).decode()

            # Detect lag occurrences
            with open(LOG_FILE_PATH, 'r') as log_file:
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
            if len(output) > DISCORD_CHAR_LIMIT:
                trimmed_length = len(output) - DISCORD_CHAR_LIMIT
                # Ensure the message ends properly with the closing backticks for the code block
                truncation_message = "... (truncated)\n```"
                output = output[:DISCORD_CHAR_LIMIT - len(truncation_message)] + truncation_message
                print(f"Trimmed {trimmed_length} characters from the status message.")
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
                status_message = await ops_helpers.async_service_status(SERVICE_NAME)
                await interaction.followup.send(status_message, ephemeral=False)
            else:
                # Authorization (whitelist)
                if interaction.user.id not in ADMIN_USERS:
                    await interaction.followup.send("Sorry, you are not authorized to use this command.", ephemeral=True)
                    return

                # Perform stop, start, or restart
                success_message = await ops_helpers.async_service_control(action, SERVICE_NAME)
                await interaction.followup.send(success_message, ephemeral=False)
        except Exception as ex:
            await interaction.followup.send(
                f"Error running **{action}** on `{SERVICE_NAME}`: {ex}",
                ephemeral=True
            )



    @bot.tree.command(name="reboot", description="🔒 Reboot the physical machine.")
    async def slash_reboot(interaction: discord.Interaction):
        """
        Reboots the server by running 'sudo reboot'. Admin-only command.
        The bot logs out before executing the reboot to indicate downtime.
        """
        # Check if the user is an admin
        if interaction.user.id not in ADMIN_USERS:
            await interaction.response.send_message(
                "Sorry, you are not authorized to use this command.",
                ephemeral=True
            )
            return

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
                    ["sudo", "systemctl", "stop", SERVICE_NAME],
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
                print(f"Failed to send error message: {error_message}")
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"An unexpected error occurred while attempting to reboot the server: {e}",
                    ephemeral=True
                )
            except discord.errors.ClientException:
                print(f"Failed to send unexpected error message: {e}")
