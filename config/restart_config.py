from typing import List
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class RestartConfig:
    enabled: bool = True
    times: List[str] = field(default_factory=list)  # List of "HH:MM" strings

    def add_restart_time(self, time: str) -> str:
        """
        Adds a restart time to the list after validation.
        Args:
            time (str): Time in "HH:MM" format.
        Returns:
            str: Success message or error if invalid.
        """
        if not self._validate_time_format(time):
            return f"Invalid time format: {time}. Use 'HH:MM'."

        if time in self.times:
            return f"Time {time} already exists in the list."

        self.times.append(time)
        self.times.sort()  # Ensure times are ordered
        return f"Time {time} added successfully."

    def remove_restart_time(self, time: str) -> str:
        """
        Removes a restart time from the list.

        Args:
            time (str): Time in "HH:MM" format.

        Returns:
            str: Success or error message.
        """
        if time not in self.times:
            return f"Time {time} not found in the list."

        self.times.remove(time)
        return f"Time {time} removed successfully."

    def _validate_time_format(self, time: str) -> bool:
        """
        Validates that a time is in the "HH:MM" format.

        Args:
            time (str): Time string to validate.

        Returns:
            bool: True if valid, False otherwise.
        """
        try:
            datetime.strptime(time, "%H:%M")
            return True
        except ValueError:
            return False
