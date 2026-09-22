from pathlib import Path
from typing import Any, Dict, Optional, List
from json import dump, load
from os import replace

from src.utils.log.logger import Logger


class State:
    def __init__(
            self,
            log: Logger,
            state_file: Path,
            state: dict[str, Any]
        ) -> None:
        self.log: Logger = log
        self.state_file: Path = state_file
        self.state: dict[str, Any] = state

    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file."""

        try:
            with open(self.state_file, "r", encoding="utf-8") as file:
                return load(file)
        except (FileNotFoundError) as _:
            self.log.warn(
                "Error reading %s, starting fresh." % (
                    self.state_file
                )
            )

    def save_state(self) -> None:
        """Save state to JSON file atomically."""
        tmp_file = f"{self.state_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as file:
            dump(self.state, file, indent=4)
        replace(tmp_file, self.state_file)


    def update_state(
            self,
            srr: str,
            key: str,
            value: bool = True
        ) -> None:
        """Update state for a given SRR."""
        if srr not in self.state:
            self.state[srr] = {}
        self.state[srr][key] = value


    def get_state(
            self,
            srr: str,
            key: str,
            default: bool = False
        ) -> bool:
        """Get state value for SRR and key."""
        return self.state.get(srr, {}).get(key, default)


import json
from pathlib import Path
from typing import Any, Dict

