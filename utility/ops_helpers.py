import asyncio
import os
import tarfile
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

import utility.server_properties_helper as props_helper

import config.config as cfg

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
    print("Starting world backup...")
    # Fetch the world folder name from server.properties
    try:
        world_name = props_helper.get_server_property(props_helper.ServerProperties.LEVEL_NAME, cfg.config.minecraft.server_path)
    except FileNotFoundError as e:
        raise RuntimeError("Failed to find server.properties.") from e
    
    if not world_name:
        raise ValueError("World name not found in server.properties.")
    
    world_path = os.path.join(cfg.config.minecraft.server_path, world_name)
    if not os.path.exists(world_path):
        raise FileNotFoundError(f"World folder '{world_name}' does not exist at {world_path}.")

    # Create a timestamped backup name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M")
    backup_name = f"{prefix}_{timestamp}.tar.gz"
    backup_path = os.path.join(cfg.config.minecraft.backup.path, backup_name)

    # Archive the world folder
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(world_path, arcname=os.path.basename(world_path))

    print(f"Created world backup: {backup_path}")
    return backup_path



# Function to run the backup in a separate thread
async def async_create_backup(prefix: str) -> str:
    """
    Runs the create_backup function asynchronously using a thread pool.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, create_world_backup_helper, prefix)





async def async_service_control(action: str, service_name: str) -> str:
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

    process = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", action, service_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Systemctl error: {stderr.decode(errors='ignore').strip()}")

    return f"Server action **{action}** completed successfully on `{service_name}`."


async def async_service_status(service_name: str) -> str:
    """
    Gets the status of a systemd service asynchronously.
    Args:
        service_name (str): The name of the service to check.
    Returns:
        str: A trimmed status message, or a meaningful message if the service is inactive/stopped.
    """
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
