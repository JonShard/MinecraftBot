from discord import app_commands
import discord
import config.config as cfg
import utility.helper_functions as helpers

class DeleteButton(discord.ui.View):
    def __init__(self, time : str):
        super().__init__(timeout=None)  # No timeout, stays active
        self.time = time
        
    @discord.ui.button(label="🗑️(🔒)",  style=discord.ButtonStyle.danger, custom_id="delete_button")
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized

        error = cfg.config.minecraft.restart.remove_restart_time(self.time)
        if error == None:
            cfg.save_config()
            response = f"Time {self.time} removed successfully. Updated restart times:\n"
            for t in cfg.config.minecraft.restart.times:
                response += f"- {t}\n"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message(error, ephemeral=True)

class RestartCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="restart", description="Manage MC server restart times.")

    @app_commands.command(name="list", description="Manage all restart times. Remove a time.")
    async def restart_list(self, interaction: discord.Interaction):
        await interaction.response.send_message("The MC server will restart at these times:\n")
        
        for time in cfg.config.minecraft.restart.times:
            await interaction.channel.send(f"# {time}", view=DeleteButton(time))


    @app_commands.command(name="add", description="🔒 Add a new restart time. Ex: 05:00 or 23:00")
    async def restart_add(self, interaction: discord.Interaction, time: str):
        if not await helpers.authorize_interaction(interaction):
            return  # Stop execution if the user is not authorized


        error = cfg.config.minecraft.restart.add_restart_time(time)
        if error == None:
            cfg.save_config()
            response = f"Time {time} added successfully:\n"
            for t in cfg.config.minecraft.restart.times:
                if t == time:
                    response += f"• **{t}**\n"
                else:
                    response += f"• {t}\n"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message(error, ephemeral=True)


def register_commands(bot):
    bot.tree.add_command(RestartCommands())
