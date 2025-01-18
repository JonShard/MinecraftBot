import asyncio
import discord
import re
import subprocess
from mcrcon import MCRcon

intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)

# Minecraft server configuration
SERVER_IP = "192.168.50.213"
RCON_PORT = 25575
RCON_PASSWORD = "srep"  # Replace with your RCON password
LOG_FILE_PATH = '/mnt/SSD120GB/phonix/PhoenixDenPack2025/logs/latest.log'

player_count = 0
ext_chunk_count = 0


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message):
    global ext_chunk_count

    if message.content == "!status" or message.content == "stat":
        print("!status")
        try:
            # Gather system and server information
            ps_output = subprocess.check_output(['ps', '-eo', 'pid,comm,etime']).decode()
            java_process_line = [line for line in ps_output.split('\n') if 'java' in line][0]
            uptime = java_process_line.split()[-1]

            disk_space = subprocess.check_output(['df', '/dev/sda2', '/dev/sdb', '-h']).decode()
            backup_size = subprocess.check_output(['du', '/var/mcbackup/', '-sch']).decode()
            machine_uptime = subprocess.check_output(['uptime']).decode()
            memory_usage = subprocess.check_output(['free', '-h']).decode()
            latest_logs = subprocess.check_output(['tail', '-n 4', LOG_FILE_PATH]).decode()

            players_today = subprocess.check_output(
                ["(zcat /mnt/SSD120GB/phonix/PhoenixDenPack2025/logs/$(date +'%Y-%m'-%d)*.log.gz && cat /mnt/SSD120GB/phonix/PhoenixDenPack2025/logs/latest.log) | grep joined | awk '{print $6}' | sort -u"],
                shell=True
            ).decode()
            players_today_count = players_today.count("\n")

            crashes_times = subprocess.check_output(
                ["head -n 4 /mnt/SSD120GB/phonix/PhoenixDenPack2025/crash-reports/* | grep -E \"Time: \" | awk '{print $2 \" \" $3}' | tail -n 5"],
                shell=True
            ).decode()
            crashes_times = crashes_times if crashes_times else "No crashes yet! <3"

            with open(LOG_FILE_PATH, 'r') as log_file:
                log_contents = log_file.read()
            lag_occurrences = len(re.findall(r'Running \d+ms or \d+ ticks behind', log_contents))
            ms_values = [int(match) for match in re.findall(r'Running (\d+)ms or \d+ ticks behind', log_contents)]
            average_ms = sum(ms_values) / len(ms_values) if ms_values else 0
            total_missed_ticks = sum([int(match) for match in re.findall(r'Running \d+ms or (\d+) ticks behind', log_contents)])

            output = (
                f"MC Uptime: `{uptime}`\n"
                f"Player Count: `{player_count}`\n"
                f"Players Today: `{players_today_count}` ```\n{players_today} ```"
                f"Last 5 crashes: ```\n{crashes_times}\n```"
                f"Disk space:```\n{disk_space}```"
                f"Backup size:```\n{backup_size}```"
                f"Machine uptime:```\n{machine_uptime}```"
                f"Memory usage:```\n{memory_usage}```"
                f"Latest logs:```\n{latest_logs}```"
                f"Running behind count: `{lag_occurrences}`\n"
                f"Average ms: `{average_ms:.0f}` ms\n"
                f"Total missed seconds: `{total_missed_ticks * 50 / 1000}`\n"
                f"Saving external chunk log count: `{ext_chunk_count}`"
            )
        except Exception as e:
            output = f"An error occurred: {str(e)}"

        await message.channel.send(output)
        print("Done")


async def update_server_status():
    global player_count
    global ext_chunk_count
    try:
        # Use mcrcon to get player count
        with MCRcon(SERVER_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command("list")
            match = re.search(r"There are (\d+) of a max of \d+ players online", response)
            if match:
                player_count = int(match.group(1))

        # Check for external chunk saving
        with open(LOG_FILE_PATH, 'r') as log_file:
            log_contents = log_file.read()
        ext_chunk_count = len(re.findall(r'Saving oversized chunk', log_contents))

        if ext_chunk_count:
            status_message = f"External chunks! ({ext_chunk_count})"
        else:
            latest_log = log_contents.splitlines()[-1]
            lag_ms_match = re.search(r'Running (\d+)ms or \d+ ticks behind', latest_log)
            status_message = f"{player_count} players online" if not lag_ms_match else f"{player_count} players online ({int(lag_ms_match.group(1)) / 1000:.1f} sec behind)"
    except Exception as e:
        print(f"Error updating status: {e}")
        status_message = "Server is offline"
    await client.change_presence(activity=discord.Game(status_message))


async def main():
    asyncio.create_task(client.start("MTA4MTg1Nzc5OTc5NDk4NzA0OQ.GY1gHU.Zr8kWU4WXIN_Yx2JAjr3M3J2NBjVw8XkO4noC8"))
    await asyncio.sleep(10)
    while True:
        asyncio.create_task(update_server_status())
        await asyncio.sleep(3)

asyncio.run(main())
