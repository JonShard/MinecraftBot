import asyncio
import os
import tarfile
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

import utility.server_properties_helper as props_helper
import utility.service_helpers as serv_helper

import config.config as cfg
from utility.logger import get_logger
log = get_logger()

# For running tar async
executor = ThreadPoolExecutor()

def create_world_backup_helper(prefix: str) -> str:
    """
    Creates a timestamped tar.gz backup of the Minecraft world folder.
    Args:
        prefix (str): The prefix for the backup file name.
    Returns:
        str: The path of the created backup.
    """
    log.debug("Starting world backup...")
    # Fetch the world folder name from server.properties
    try:
        world_name = props_helper.get_server_property(props_helper.ServerProperties.LEVEL_NAME, cfg.config.minecraft.server_path)
    except FileNotFoundError as e:
        raise RuntimeError("Failed to find server.properties.") from e
    
    if not world_name:
        raise ValueError("World name not found in server.properties.")
    
    world_path = os.path.join(cfg.config.minecraft.server_path, world_name)
    if not os.path.exists(world_path):
        log.warning(f"Backup failed: World folder '{world_name}' does not exist at {world_path}.")
        return ""
    
    # Create a timestamped backup name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M")
    backup_name = f"{prefix}_{timestamp}.tar.gz"
    backup_path = os.path.join(cfg.config.minecraft.backup.path, backup_name)

    # Archive the world folder
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(world_path, arcname=os.path.basename(world_path))

    log.info(f"Created world backup: {backup_path}")
    return backup_path



async def wait_for_pretty_timestamp():
    """
    Waits asynchronously until the next 'pretty' timestamp based on the interval.
    """
    now = datetime.datetime.now()
    current_minute = now.minute
    current_hour = now.hour

    remainder = current_minute % cfg.config.minecraft.backup.interval_min
    if remainder == 0:
        return  # No waiting needed

    # Calculate next rounded time
    next_minute = current_minute + (cfg.config.minecraft.backup.interval_min - remainder)
    if next_minute >= 60:
        next_minute -= 60
        current_hour = (current_hour + 1) % 24  # Handle hour overflow

    next_time = now.replace(hour=current_hour, minute=next_minute, second=0, microsecond=0)
    wait_time = (next_time - now).total_seconds() - 10 # magic number, start a few sec early so backup is more likely to be pretty number

    log.debug(f"Waiting {int(wait_time // 60)} min {int(wait_time % 60)} sec until {next_time.strftime('%H:%M')}...")
    await asyncio.sleep(wait_time)
    

# Function to run the backup in a separate thread
async def async_create_backup(prefix: str, skip_wait: bool = False) -> str:
    """
    Runs the create_backup function asynchronously using a thread pool.
    """
    loop = asyncio.get_running_loop()
    if not skip_wait:
        await wait_for_pretty_timestamp()
    return await loop.run_in_executor(executor, create_world_backup_helper, prefix)





def delete_old_backups_helper() -> int:
    """
    Deletes backups older than 120 days and removes backups from days older than 24 hours,
    while keeping the one closest to 05:00 AM.
    Returns:
        int: Number of deleted backups.
    """
    BACKUP_DIR = cfg.config.minecraft.backup.path
    TARGET_HOUR = 5  # 05:00 AM
    TARGET_MINUTE = 0
    deleted_count = 0

    if not os.path.exists(BACKUP_DIR):
        log.warning(f"Backup directory does not exist: {BACKUP_DIR}")
        return deleted_count

    # List all backup files
    all_backups = [
        os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".tar.gz")
    ]

    backups_by_day = {}

    for file in all_backups:
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file))
        file_age_days = (datetime.datetime.now() - file_time).days
        file_age_hours = (datetime.datetime.now() - file_time).total_seconds() / 3600

        # Step 1: Delete backups older than 120 days
        if file_age_days > cfg.config.minecraft.backup.delete_sparse_after_days:
            os.remove(file)
            deleted_count += 1
            log.debug(f"Deleted sparse backup: {file}")
            continue  # Skip processing for these files

        # Step 2: Group backups by day (ONLY IF older than 24 hours)
        if file_age_hours > cfg.config.minecraft.backup.delete_frequent_after_hours:
            day_key = file_time.date()
            if day_key not in backups_by_day:
                backups_by_day[day_key] = []
            backups_by_day[day_key].append((file, file_time))

    # Step 3: For each day, find and keep the backup closest to 05:00 AM
    for day, backups in backups_by_day.items():
        closest_backup = None
        closest_time_diff = float('inf')

        for file, file_time in backups:
            # Calculate the absolute time difference from 05:00
            target_time = datetime.datetime(file_time.year, file_time.month, file_time.day, TARGET_HOUR, TARGET_MINUTE)
            time_diff = abs((file_time - target_time).total_seconds())

            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_backup = file

        # Delete all backups from this day except the closest one
        for file, _ in backups:
            if file != closest_backup:
                os.remove(file)
                deleted_count += 1
                log.debug(f"Deleted frequent backup: {file}")

    return deleted_count






# Function to delete old backups in a separate thread. Returns number of deleted files.
async def async_delete_old_backups() -> int:
    """
    Runs the delete_old_backups_helper function asynchronously using a thread pool.
    Returns number of deleted files.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, delete_old_backups_helper)



async def async_service_control(action: str) -> str:
    """
    Controls a systemd service asynchronously (stop, start, restart).
    Args:
        action (str): Action to perform on the service (stop, start, restart).
        service_name (str): The name of the service to control.
    Returns:
        str: Success message if the action is completed successfully.
    Raises:
        Exception: If the systemctl command fails.
    """
    valid_actions = {"stop", "start", "restart"}
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Use one of {valid_actions}.")
    
    await cfg.load_config()
    
    # Ensure the service file exist for systemd. Create from template if not exist.
    await serv_helper.ensure_service_file()
    service_name = cfg.config.minecraft.service_name

    log.info(f"{action} {service_name}")
    
    process = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", action, service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Systemctl error: {stderr.decode(errors='ignore').strip()}")

    return f"Server action **{action}** completed successfully on `{service_name}`."


async def async_service_status() -> str:
    """
    Gets the status of a systemd service asynchronously.
    Args:
        service_name (str): The name of the service to check.
    Returns:
        str: A trimmed status message, or a meaningful message if the service is inactive/stopped.
    """
    # Ensure the service file exist for systemd. Create from template if not exist.
    await serv_helper.ensure_service_file()
    await cfg.load_config()

    service_name = cfg.config.minecraft.service_name
    process = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", "status", service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    raw_output = stdout.decode(errors="ignore").strip()
    error_output = stderr.decode(errors="ignore").strip()

    # Check return code for success or failure
    if process.returncode == 3:  # Systemd exit code for 'inactive/dead'
        return f"**Status for** `{service_name}`:\n```\nThe service is inactive or stopped.\n```"
    elif process.returncode != 0:
        raise Exception(f"Systemctl error: {error_output}")

    # Parse and trim the output for active services
    parts = raw_output.split("\n\n", 1)  # Split at the first blank line
    trimmed_output = parts[0] if parts else "No status information available."

    if len(trimmed_output) > 1900:
        trimmed_output = trimmed_output[:1900] + "\n... (truncated) ..."

    return f"**Status for** `{service_name}`:\n```\n{trimmed_output}\n```"



async def is_service_running(skip_service_check: bool = False) -> bool:
    """
    Checks if the Minecraft server service is currently running.
    Returns:
        bool: True if the service is running, False otherwise.
    """
    if not skip_service_check:
        # Ensure the service file exists
        await serv_helper.ensure_service_file()
    
    service_name = cfg.config.minecraft.service_name

    # Use `systemctl is-active` to check the service status
    process = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", "is-active", service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    # Decode the output
    status_output = stdout.decode(errors="ignore").strip()
    error_output = stderr.decode(errors="ignore").strip()

    if process.returncode == 0 and status_output == "active":
        return True
    elif process.returncode != 0:
        # Log or print an error message for debugging if necessary
        if error_output:
            log.error(f"Error checking service status: {error_output}")
    return False
