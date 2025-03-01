import discord
from discord.embeds import Embed
from discord import ui, ButtonStyle
import utility.helper_functions as helpers

import state.state as st

OPTION_JOINS = "Players Joining"
OPTION_ERRORS = "Server Errors"
OPTION_ADVANCEMENTS = "Player Advancements"

def is_user_join_subed(user_id):
    return any(str(user_id) == str(sub).split('.')[0] for sub in st.state.join_subed_users)

class SettingsView(ui.View):
    def __init__(self, user_id, message = None):
        super().__init__(timeout=60)
        self.message = message # to self delete later
        self.user_id = user_id
        # Create a button for each setting
        self.add_item(SettingsButton(user_id, OPTION_JOINS, is_user_join_subed(user_id)))
        self.add_item(SettingsButton(user_id, OPTION_ADVANCEMENTS,  user_id in st.state.advancements_subed_users))
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
        # Fetch the original message (the one sent with send_message)
        if self.state: # User subscribing
            if self.option == OPTION_JOINS and not is_user_join_subed(self.user_id):
                st.state.join_subed_users.append(self.user_id)
                # Send dropdown with list of minecraft user
                options = [
                    discord.SelectOption(label=username, value=username)
                    for username in st.state.mc_players_ever
                ]
                await interaction.response.send_message(
                        "Please select your MC username so you won't get notifications about yourself:\n*(If you're not in the list please join the MC server and try again)*", 
                        view = UsernameSelectView(interaction.user.id, options)
                     )
                await interaction.message.edit(view=SettingsView(interaction.user.id))
            elif self.option == OPTION_ERRORS:
                st.state.error_subed_users.append(self.user_id)
                await interaction.response.edit_message(view=SettingsView(interaction.user.id))
            elif self.option == OPTION_ADVANCEMENTS and not self.user_id in st.state.advancements_subed_users:
                st.state.advancements_subed_users.append(self.user_id)
                await interaction.response.edit_message(view=SettingsView(interaction.user.id))
       
        else:     # Unsubscribing    
            if self.option == OPTION_JOINS and is_user_join_subed(self.user_id):
                st.state.join_subed_users = [
                    sub for sub in st.state.join_subed_users
                    if str(self.user_id) != str(sub).split('.')[0]
                ]
            elif self.option == OPTION_ERRORS and self.user_id in st.state.error_subed_users:
                st.state.error_subed_users.remove(self.user_id)
            elif self.option == OPTION_ADVANCEMENTS and self.user_id in st.state.advancements_subed_users:
                st.state.advancements_subed_users.remove(self.user_id)

            await interaction.response.edit_message(view=SettingsView(interaction.user.id))
        st.save_state()

class UsernameDropdown(discord.ui.Select):
            def __init__(self, user_id, options):
                super().__init__(placeholder="Select your minecraft username", options=options)
                self.user_id = user_id
            async def callback(self, interaction: discord.Interaction):
                selected_username = self.values[0]
                st.state.join_subed_users = [
                    f"{user_id}.{selected_username}" if user_id == self.user_id else user_id 
                    for user_id in st.state.join_subed_users
                ]
                await interaction.response.send_message("✅ You will not be notified about yourself joining") 
                
class UsernameSelectView(discord.ui.View):
    def __init__(self, user_id, options):
        super().__init__(timeout=60)
        self.add_item(UsernameDropdown(user_id, options))
    



def register_commands(bot):
    
    @bot.tree.command(name="notifications", description="Show a menu where you can opt-in and out of different kinds of notifications")
    async def slash_notifications(interaction: discord.Interaction):
        await helpers.log_interaction(interaction)
        if interaction.guild:
            await interaction.response.send_message("Check your DMs! 📩", ephemeral=True)
            message = await interaction.user.send(
                "Please select which events you would like notifications about 🔔", 
                view=SettingsView(interaction.user.id)
            )
        else:
            await interaction.response.send_message(
                "Please select which events you would like notifications about 🔔",
                view=SettingsView(interaction.user.id)
            )
            message = await interaction.original_response()

        # Attach the message to the view so it can be deleted later
        view = SettingsView(interaction.user.id, message)
        await message.edit(view=view)