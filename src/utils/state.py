from pathlib import Path
from typing import Self, Any
from json import dump, load

from os.path import exists

from src.utils.log.logger import Logger


class State:
    def __init__(
            self: Self,
            log: Logger,
            state_file: Path,
            state: dict[str, Any]
        ) -> None:
        self.log: Logger = log
        self.state_file: Path = state_file
        self.state: dict[str, Any] = state

    def load_state(self: Self) -> Dict[str, Any]:
        """Load state from JSON file."""

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError) as _:
            self.log.warn(
                "Error reading %s, starting fresh." % (
                    self.state_file
                )
            )

    def save_state(self: Self) -> None:
        """Save state to JSON file atomically."""
        tmp_file = f"{self.state_file}.tmp"
        with open(tmp_file, "w") as f:
            dump(self.state, f, indent=2)
        os.replace(tmp_file, state_file)


    def update_state(
        self: Self,
        srr: str,
        key: str,
        value: bool = True,
    ) -> None:
        """Update state for a given SRR."""
        if srr not in state:
            state[srr] = {}
        state[srr][key] = value


    def get_state(self: Self, , srr: str, key: str, default: bool = False) -> bool:
        """Get state value for SRR and key."""
        return state.get(srr, {}).get(key, default)
