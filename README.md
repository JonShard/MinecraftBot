# Minecraft Discord Bot

A Discord bot designed to interact with a Minecraft server, providing RCON commands, automated restarts, backups, and more.  
The bot is meant to be deployed to the same machine as a Minecraft server,  
and by providing the MC server path in the bot's config, let it manage the MC server through discord slash commands. One bot instance manages one MC server.

## Features
Manage the Minecraft server from Discord
- Execute RCON commands with authorization (Discord roles or user whitelist)
- Chat with in-game players from Discord
- Bar chart with player count over time
- Provide a modpack download link and setup instructions for new players
- Automate server restarts and backups easily and quickly  
- Preview and retrieve server log files and statistics about lag, resource use and more
- MC Bot rolling logfile at `_logs/mc_bot.log` which also includes command calling history
- Warnings about server not keeping up, or external chunks causing lag

### Backup
The bot can do frequent backups of the Minecraft world, and then delete most of them after a configured amount of time. For example backup every 15min and delete most of those, the frequent backups after 24 hours, keeping one per day. These can also eventually be deleted after for example 6 months.  
Backups can then be restored easily with the `/backup restore` command. If the desired backup is too old to fit in the dropdown, a optional timestamp can be added to look at backups before that timestamp, ex: `/backup restore 15-01-2025`  
![](https://github.com/JonShard/MinecraftBot/blob/master/docs/backup.gif?raw=true)

### Chat
Discord users can spawn a chat window, and see the player's chat messages from the game. They can then talk to the players using say to warn about a restart, ask about a problem or just say hi.  
![](https://github.com/JonShard/MinecraftBot/blob/master/docs/chat.gif?raw=true)


### Players Graph
Show who is online, who has joined today, and how many joined yesterday.
Gives you an overview of how active the server is at a glance.
![](https://github.com/JonShard/MinecraftBot/blob/master/docs/stat_players.png?raw=true)


### Minecraft Bot /help Command
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

### Admin Permissions  

The `admin_users` and `admin_roles` fields in the configuration file define who has access to restricted 🔒 bot commands.  

```yaml
admin_users: # List of Discord user IDs with admin permissions
    - 123123123123123123  # Ola Nordmann
    - 123123123123123124  # John Doe
admin_roles:  # List of Discord role IDs with admin permissions
    - 123456789045678907 # "Minecraft Admin" role
```
The `admin_users` list contains specific Discord user IDs, granting admin privileges to those users individually. The `admin_roles` list contains Discord role IDs, allowing all members with those roles to use admin commands. To find a user or role ID, enable Discord's **Developer Mode**, then right-click the user or role and select **Copy ID**.


### Logfile
A logfile for the bot is created at `_logs/mc_bot.log`. There is also a `debug.log` file with DEBUG log level for trouble shooting.
These are rolled over at midnight and are reused across bot restarts.
```log
2025-02-18 10:58:47 [INFO] MineBot:68 - [Auth] Open:    jonshard - /help
2025-02-18 11:01:01 [INFO] MineBot:50 - Created world backup: /var/mcbackup/backup_2025-02-18T10-59.tar.gz
2025-02-18 11:31:01 [INFO] MineBot:50 - Created world backup: /var/mcbackup/backup_2025-02-18T11-29.tar.gz
2025-02-18 11:35:10 [INFO] MineBot:68 - [Auth] Open:    jonshard - /rcon players
2025-02-18 11:35:12 [INFO] MineBot:205 - Saved bar chart to _data/stat_players.png.
2025-02-18 11:43:40 [INFO] MineBot:68 - [Auth] Open:    jonshard - /status
```

## Installation
### Requirements
- Linux distribution with Systemd
- Running as root to allow access to MC files and manage services.
- Python 3.8+, discord.py and other dependencies, see `requirements.txt`
- An active Minecraft server with RCON enabled on the same machine

## Setup
1. Clone the repository:   
`git clone https://github.com/JonShard/MinecraftBot`  
`cd MinecraftBot`
1. Install dependencies:  
`pip install -r requirements.txt`
1. Configure the bot:  
Edit config.json with your bot token and path to the Minecraft server

Run the bot:  
`sudo python bot.py`


## License

This project is licensed under the GNU GLP3 License.