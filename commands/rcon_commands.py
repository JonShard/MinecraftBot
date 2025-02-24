import os
import re
import sys
import subprocess

import discord
from discord import app_commands

import config.config as cfg
import state.state as st
from utility.logger import get_logger
log = get_logger()
import utility.helper_functions as helpers
import utility.rcon_helpers as rcon_helpers


# Create a command group for /rcon
class RconCommands(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="rcon", description="Communicate / interact with the MC server")
        self.bot = bot

    @app_commands.command(name="players", description="Show who is online, who has joined today and how many joined yesterday.")
    @app_commands.describe(last_days="Optional number of days to show in the player count graph.")
    async def slash_players(self, interaction: discord.Interaction, last_days: int = 30):
        """
        1) Counts how many players joined yesterday, how many are online now, and how many joined today.
        2) Displays that info at the top in plain text.
        3) Then shows two code blocks:
        - "■■■■ Players Joined Today (X) ■■■■"
        - "■■■■ Currently Online (Y) ■■■■"
        """
        await helpers.log_interaction(interaction)
        await interaction.response.defer(ephemeral=False, thinking=True)

        # ─── 1) PLAYERS WHO JOINED YESTERDAY ───
        try:
            # Similar approach to the "players who joined today," but for "yesterday" logs
            # For instance, date -d '1 day ago' for the day:
            # (zcat logs/2025-01-18*.log.gz && cat logs/latest.log) ...
            players_yesterday_cmd = (
                f"(zcat {cfg.config.minecraft.logs_dir}/$(date +'%Y-%m'-%d -d '1 day ago')*.log.gz 2>/dev/null || true) "
                f"| grep joined | awk '{{print $6}}' | sort -u"
            )
            players_yesterday = subprocess.check_output(
                [players_yesterday_cmd], shell=True
            ).decode(errors="ignore").strip()
            if players_yesterday:
                players_yesterday_count = players_yesterday.count("\n") + 1
            else:
                players_yesterday_count = 0
        except Exception as e:
            log.error(f"Error retrieving players who joined yesterday: {e}")
            players_yesterday_count = 0

        # ─── 2) CURRENT ONLINE PLAYERS VIA RCON ───
        await rcon_helpers.ensure_rcon_connection()
        if rcon_helpers.mcr_connection is None:
            # We'll still try to show the other info even if RCON is down
            currently_online = []
            player_count_now = 0
        else:
            currently_online = await rcon_helpers.get_players()
            player_count_now = len(currently_online)

        # ─── 4) BUILD TEXT OUTPUT ───

        # Top lines (plain text, no code blocks):
        # e.g.:
        # Players Yesterday: 3
        # Players Online Now: 2
        # Players Joined Today: 5
        top_text = (
            f"Players Yesterday: `{players_yesterday_count}`"
        )

        # Code block #1: Players Joined Today
        if len(st.state.mc_players_today) == 0:
            joined_today_lines = "no players today"
        else:
            joined_today_lines = "\n".join(st.state.mc_players_today)

        code_block_today = (
            "```text\n"
            f"■■■■ Players Joined Today ({len(st.state.mc_players_today)}) ■■■■\n"
            f"{joined_today_lines}\n"
            "```"
        )

        # Code block #2: Currently Online
        if player_count_now == 0:
            currently_online_block = "no players currently online"
        else:
            currently_online_block = "\n".join(currently_online)

        code_block_online = (
            "```text\n"
            f"■■■■ Currently Online ({player_count_now}) ■■■■\n"
            f"{currently_online_block}\n"
            "```"
        )

        # Update / generate graph PNG
        helpers.update_csv_player_count()
        helpers.generate_player_count_graph(last_days)

        # Final response
        reply = f"{top_text}\n{code_block_today}{code_block_online}"

            # Now send the final message with an attached file
        await interaction.followup.send(
            content=reply,
            ephemeral=False,
            file=discord.File(cfg.config.stats.player_count_png, filename=cfg.config.stats.player_count_png)
        )



    @app_commands.command(name="chat", description="Show a single chat window for the last 10 lines.")
    async def slash_chat(self, interaction: discord.Interaction):
        """
        Creates (or recreates) one chat window in this channel (DM or text).
        Keeps refreshing for 5 minutes.
        """
        await helpers.log_interaction(interaction)
        # Acknowledge command
        await interaction.response.defer(ephemeral=False, thinking=True)
        # Post/refresh
        await helpers.post_or_refresh_chat_window(self.bot, interaction.channel)
        # Let user know
        await interaction.followup.send("Chat window created or refreshed for this channel.", ephemeral=False)



    @app_commands.command(name="say", description="Send a chat message to the server from Discord.")
    @app_commands.describe(message="The message to send")
    async def slash_say(self, interaction: discord.Interaction, message: str):
        """
        Send /say to the server with a color-coded prefix,
        then move the chat window to the bottom if it exists in this channel.
        """
        await helpers.log_interaction(interaction)

        await rcon_helpers.ensure_rcon_connection()
        if rcon_helpers.mcr_connection is None:
            await interaction.response.send_message("Could not connect to RCON. Try again later.", ephemeral=True)
            return

        try:
            # Format text for Minecraft
            say_string = f"§7§o{interaction.user.name}: {message}§r"
            rcon_helpers.mcr_connection.command(f"say {say_string}")
            await interaction.response.send_message(
                f"Sent to server chat:\n`{interaction.user.name}: {message}`",
                ephemeral=False
            )
        except Exception as e:
            await rcon_helpers.close_rcon_connection()
            await interaction.response.send_message(f"Failed to send message: {e}", ephemeral=True)
            return

        await helpers.repost_chat_window(self.bot, interaction)




    @app_commands.command(name="weather", description="Set the weather in the Minecraft world.")
    @app_commands.describe(
        weather_type="Choose the type of weather to set.",
        duration_minutes="Optional duration in minutes for the weather to last."
    )
    @app_commands.choices(weather_type=[
        discord.app_commands.Choice(name="Clear", value="clear"),
        discord.app_commands.Choice(name="Rain", value="rain"),
        discord.app_commands.Choice(name="Thunder", value="thunder"),
    ])
    async def slash_weather(self, interaction: discord.Interaction, weather_type: str, duration_minutes: int = None):
        """
        Sets the weather in the Minecraft world with input validation for duration_minutes and weather-specific emojis.
        """
        await helpers.log_interaction(interaction)
        await interaction.response.defer(ephemeral=False, thinking=True)

        await rcon_helpers.ensure_rcon_connection()
        if rcon_helpers.mcr_connection is None:
            await interaction.followup.send("Could not connect to RCON. Try again later.", ephemeral=True)
            return

        try:
            # Emojis for each weather type
            weather_emojis = {
                "clear": "☀️",
                "rain": "🌧️",
                "thunder": "⛈️"
            }

            if duration_minutes is not None:
                # Clamp duration to a maximum safe value
                MAX_DURATION = sys.maxsize // 60  # Convert max seconds to minutes
                if duration_minutes < 0:
                    await interaction.followup.send("Duration cannot be negative. Please enter a valid value.", ephemeral=True)
                    return
                elif duration_minutes > MAX_DURATION:
                    duration_minutes = MAX_DURATION

                # Convert duration_minutes to seconds
                duration_seconds = duration_minutes * 60
                command = f"weather {weather_type} {duration_seconds}"
            else:
                command = f"weather {weather_type}"

            # Execute the command
            response = rcon_helpers.mcr_connection.command(command)

            # Format the duration into human-readable units
            if duration_minutes:
                seconds = duration_minutes * 60
                years, remainder = divmod(seconds, 60 * 60 * 24 * 365)
                days, remainder = divmod(remainder, 60 * 60 * 24)
                hours, remainder = divmod(remainder, 60 * 60)
                minutes, _ = divmod(remainder, 60)

                duration_parts = []
                if years > 0:
                    duration_parts.append(f"{years:,} Years")
                if days > 0:
                    duration_parts.append(f"{days} Days")
                if hours > 0:
                    duration_parts.append(f"{hours} Hours")
                if minutes > 0:
                    duration_parts.append(f"{minutes} Minutes")

                duration_msg = " for " + ", ".join(duration_parts)
            else:
                duration_msg = ""

            # Get emoji for the weather type
            emoji = weather_emojis.get(weather_type, "")

            # Notify the user
            await interaction.followup.send(
                content=f"`{response.strip()}`\n{emoji} Weather set to **{weather_type}**{duration_msg}.",
                ephemeral=False
            )
        except Exception as e:
            await rcon_helpers.close_rcon_connection()
            await interaction.followup.send(f"Failed to set weather: {e}", ephemeral=True)




    @app_commands.command(name="kill", description="🔒 Kill specific types of entities in the Minecraft world.")
    @app_commands.describe(target="What to kill (items, vanilla_animals, vanilla_monsters, vanilla_villagers).")
    @app_commands.choices(target=[
        discord.app_commands.Choice(name="items", value="items"),
        discord.app_commands.Choice(name="vanilla_animals", value="vanilla_animals"),
        discord.app_commands.Choice(name="vanilla_monsters", value="vanilla_monsters"),
        discord.app_commands.Choice(name="vanilla_villagers", value="vanilla_villagers"),
    ])
    async def slash_kill(self, interaction: discord.Interaction, target: str):
        """
        Kills specific types of entities in the Minecraft world based on the selected target.
        - items: Kills all dropped items.
        - vanilla_animals: Kills all passive vanilla animals and snowmen.
        - vanilla_monsters: Kills all hostile mobs.
        - vanilla_villagers: Kills villagers, wandering traders, and golems.
        """
        await interaction.response.defer(ephemeral=False, thinking=True)

        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized
  

        await rcon_helpers.ensure_rcon_connection()
        if rcon_helpers.mcr_connection is None:
            await interaction.followup.send("Could not connect to RCON. Try again later.", ephemeral=True)
            return

        try:
            response_lines = []
            if target == "items":
                response = rcon_helpers.mcr_connection.command("kill @e[type=minecraft:item]")
                response_lines.append(f"`{response.strip()}` - Cleared all dropped items.")

            elif target == "vanilla_animals":
                animal_types = [
                    "minecraft:cow", "minecraft:sheep", "minecraft:chicken", "minecraft:pig",
                    "minecraft:horse", "minecraft:donkey", "minecraft:llama", "minecraft:mooshroom",
                    "minecraft:rabbit", "minecraft:cat", "minecraft:wolf", "minecraft:parrot",
                    "minecraft:fox", "minecraft:frog", "minecraft:turtle", "minecraft:snow_golem"
                ]
                for entity in animal_types:
                    response = rcon_helpers.mcr_connection.command(f"kill @e[type={entity}]")
                    if not response.startswith("No entity was found"):
                        response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

            elif target == "vanilla_monsters":
                monster_types = [
                    "minecraft:zombie", "minecraft:skeleton", "minecraft:creeper", "minecraft:spider",
                    "minecraft:enderman", "minecraft:witch", "minecraft:slime", "minecraft:ghast",
                    "minecraft:blaze", "minecraft:phantom", "minecraft:silverfish", "minecraft:drowned",
                    "minecraft:ravager", "minecraft:vindicator", "minecraft:illusioner", "minecraft:evoker",
                    "minecraft:husk", "minecraft:warden", "minecraft:zombified_piglin", "minecraft:shulker",
                    "minecraft:magma_cube", "minecraft:hoglin", "minecraft:stray", "minecraft:pillager",
                    "minecraft:guardian", "minecraft:elder_guardian", "minecraft:piglin", "minecraft:piglin_brute"
                ]
                for entity in monster_types:
                    response = rcon_helpers.mcr_connection.command(f"kill @e[type={entity}]")
                    if not response.startswith("No entity was found"):
                        response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

            elif target == "vanilla_villagers":
                villager_types = [
                    "minecraft:villager", "minecraft:wandering_trader",
                    "minecraft:iron_golem", "minecraft:snow_golem"
                ]
                for entity in villager_types:
                    response = rcon_helpers.mcr_connection.command(f"kill @e[type={entity}]")
                    if not response.startswith("No entity was found"):
                        response_lines.append(f"{response.strip()} - Cleared all {entity.split(':')[1]}s.")

            else:
                await interaction.followup.send("Invalid target. Please choose a valid option.", ephemeral=True)
                return

            # Combine all responses into a single message
            final_response = "\n".join(response_lines) if response_lines else "No entities were found to kill."
            await interaction.followup.send(final_response, ephemeral=False)

        except Exception as e:
            await rcon_helpers.close_rcon_connection()
            await interaction.followup.send(f"Failed to execute kill command: {e}", ephemeral=True)





    @app_commands.command(name="command", description="🔒Execute an RCON command on the server")
    @app_commands.describe(rcon_command="The RCON command to run on the server.")
    async def slash_rcon_command(self, interaction: discord.Interaction, rcon_command: str):
        """Runs an RCON command if the user is on the ADMIN_USERS whitelist."""
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized


        await rcon_helpers.ensure_rcon_connection()
        if rcon_helpers.mcr_connection is None:
            await interaction.response.send_message("Could not connect to RCON. Try again later.", ephemeral=True)
            return

        try:
            response = rcon_helpers.mcr_connection.command(rcon_command)
            reply = f"Command executed: `{rcon_command}`"
            if response.strip():
                reply += f"\nResponse: ```{response}```"
            await interaction.response.send_message(reply, ephemeral=False)
        except Exception as e:
            await rcon_helpers.close_rcon_connection()
            await interaction.response.send_message(f"RCON command failed: {e}", ephemeral=True)


def register_commands(bot):
    bot.tree.add_command(RconCommands(bot))
