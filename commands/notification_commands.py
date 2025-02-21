
import discord
from discord.embeds import Embed
from discord import ui, ButtonStyle
import utility.helper_functions as helpers

import state.state as st

OPTION_JOINS = "Players Joining"
OPTION_ERRORS = "Server Errors"

class SettingsView(ui.View):
    def __init__(self, user_id, message = None):
        super().__init__(timeout=60)
        self.message = message # to self delete later
        self.user_id = user_id
        # Create a button for each setting
        
        self.add_item(SettingsButton(user_id, OPTION_JOINS, user_id in st.state.join_subed_users))
        self.add_item(SettingsButton(user_id, OPTION_ERRORS, user_id in st.state.error_subed_users))
    
    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass  # Message already deleted

class SettingsButton(ui.Button):
    def __init__(self, user_id, option, state):
        super().__init__(label=f"{option}: {'✅' if state else '🔲'}", style=ButtonStyle.primary)
        self.user_id = user_id
        self.option = option
        self.state = state

    async def callback(self, interaction: discord.Interaction):
        self.state = not self.state
        if self.state: # User subscribing
            if self.option == OPTION_JOINS:
                st.state.join_subed_users.append(self.user_id)
            elif self.option == OPTION_ERRORS:
                st.state.error_subed_users.append(self.user_id)
            st.save_state()
        else:   # Unsubscribing
            if self.option == OPTION_JOINS and self.user_id in st.state.join_subed_users:
                st.state.join_subed_users.remove(self.user_id)
            elif self.option == OPTION_ERRORS and self.user_id in st.state.error_subed_users:
                st.state.error_subed_users.remove(self.user_id)

        # Refresh menu
        await interaction.response.edit_message(view=SettingsView(interaction.user.id))

def register_commands(bot):
    
    @bot.tree.command(name="notifications", description="Show a menu where you can opt-in and out of different kinds of notifications")
    async def slash_notifications(interaction: discord.Interaction):
        await helpers.log_interaction(interaction)
        if interaction.guild:
            await interaction.response.send_message("Check your DMs! 📩", ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
        
        message = await interaction.user.send(
                "Please select which events you would like notifications about 🔔", 
                view=SettingsView(interaction.user.id)
            )

        # Attach the message to the view so it can be deleted later
        view = SettingsView(interaction.user.id, message)
        await message.edit(view=view)