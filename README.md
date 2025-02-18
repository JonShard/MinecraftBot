# Minecraft Discord Bot

A Discord bot designed to interact with a Minecraft server, providing RCON commands, automated restarts, backups, and more.

## Features
Manage the Minecraft server from Discord
- Execute RCON commands with authorization
- Chat with in-game players from Discord
- Bar chart with player count over time
- Provide a modpack download link and setup instruction for new players
- Automate server restarts and backups easily and quickly  
- Retrieve server logs and statistics about lag, resource use and more
- MC Bot rolling logfile at `_logs/mc_bot.log` which also includes command calling history

## Installation
### Requirements
- Linux distribution with Systemd
- Running as root to allow access to MC files and manage services.
- Python 3.8+, discord.py and other dependencies
- An active Minecraft server with RCON enabled on the same machine

## Setup
1. Clone the repository:   
`git clone https://github.com/JonShard/MinecraftBot`  
`cd MinecraftBot`
1. Install dependencies:  
`pip install -r requirements.txt`
1. Configure the bot:  
Edit config.json with your bot token, RCON credentials, and other settings.

Run the bot:  
`sudo python bot.py`

## Minecraft Bot /help Command
```
Minecraft Bot Commands

Commands with a 🔒 can only be used by whitelisted admins
Modpack Commands
📥  /modpack: Provides the modpack download link and server's public IP.

🧑‍🤝‍🧑 Player & Chat Commands
👥  /rcon players: Show who is online, who has joined today, and how many joined yesterday.
💬  /rcon chat: Show a single chat window for the last 10 lines.
🗣️  /rcon say: Send a chat message to the server from Discord.

🖥️ Minecraft Server Admin
🌤️  /rcon weather: Set the weather in the Minecraft world.
🔪  /rcon kill 🔒: Kill specific types of entities in the Minecraft world.
⚙️  /rcon command 🔒: Execute an RCON command on the server.

🕘 Automatic Restarts
🖊️  /restart add 🔒: Add a new restart time. Ex: 05:00 or 23:00.
📜  /restart list 🔒: Manage all restart times. Remove a time.

💾 Backups & Restores
📁  /backup list: List all backups.
⬇️  /backup now: Create a new backup.
🔄  /backup restore 🔒: Restore a backup.

🛠️ Utility Commands
📊  /status: Show the Minecraft server status.
📰  /logs: Show recent MC server log
🎛️  /server: Control or check the MC server instance (stop, start, restart, status).
🔌  /reboot 🔒: Reboot the physical machine.
🗑️  /wipe 🔒: Delete the world. (Confirm Yes/No)
```

## Admin Permissions  

The `admin_users` and `admin_roles` fields in the configuration file define who has access to restricted 🔒 bot commands.  

```yaml
admin_users: # List of Discord user IDs with admin permissions
    - 123123123123123123  # Ola Nordmann
admin_roles:  # List of Discord role IDs with admin permissions
    - 123456789045678907 # "Minecraft Admin" role
```
The `admin_users` list contains specific Discord user IDs, granting admin privileges to those users individually. The `admin_roles` list contains Discord role IDs, allowing all members with those roles to use admin commands. To find a user or role ID, enable Discord's **Developer Mode**, then right-click the user or role and select **Copy ID**.


## Logfile
A logfile for the bot is created at `_logs/mc_bot.log`. There is also a `debug.log` file with DEBUG log level for trouble shooting.
These are rolled over at midnight and are reused accross bot restarts.
```log
2025-02-18 10:58:47 [INFO] MineBot:68 - [Auth] Open:    jonshard - /help
2025-02-18 11:01:01 [INFO] MineBot:50 - Created world backup: /var/mcbackup/backup_2025-02-18T10-59.tar.gz
2025-02-18 11:31:01 [INFO] MineBot:50 - Created world backup: /var/mcbackup/backup_2025-02-18T11-29.tar.gz
2025-02-18 11:35:10 [INFO] MineBot:68 - [Auth] Open:    jonshard - /rcon players
2025-02-18 11:35:12 [INFO] MineBot:205 - Saved bar chart to _data/stat_players.png.
2025-02-18 11:43:40 [INFO] MineBot:68 - [Auth] Open:    jonshard - /status
```

## License

This project is licensed under the GNU GLP3 License.