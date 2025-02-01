import os
import config.config as cfg
import subprocess

def reload_systemd():
    """ Reloads systemd to recognize changes in service files. """
    try:
        print("Reloading systemd daemon...")
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        print("Systemd daemon reload complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error reloading systemd daemon: {e}")

async def ensure_service_file():
    """
    Creates the Minecraft systemd service file if it does not exist.
    The service file is generated using a template and values from the configuration.
    If 'service_name' is missing or empty in the config, it defaults to the server directory name.
    """
    
    await cfg.load_config()
    # Determine service name: Use config value if present, otherwise use the directory name of the server path
    service_file_path = os.path.join(cfg.config.minecraft.service_path, cfg.config.minecraft.service_name)

    # Check if service file already exists
    if os.path.exists(service_file_path):
        print(f"Service file already exists: {service_file_path}")
        return

    # Read the service template
    template_path = "templates/service_template.txt"
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Service template file missing: {template_path}")

    with open(template_path, "r") as template_file:
        template_content = template_file.read()

    # Replace placeholders with values from the config
    service_content = template_content.replace("<server_path>", cfg.config.minecraft.server_path)

    # Write the service file
    try:
        with open(service_file_path, "w") as service_file:
            service_file.write(service_content)
        print(f"Created service file: {service_file_path}")

        # Reload systemd to recognize the new service
        reload_systemd()

    except Exception as e:
        print(f"Failed to create service file: {e}")