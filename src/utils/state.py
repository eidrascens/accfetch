from json import dump, load
import os
from pathlib import Path
from typing import Any, Dict, Self

from src.utils.log.custom_logger import Logger


class State:
    def __init__(
            self: Self,
            log_: Logger,
            STATE_FILE: Path,
            state: dict[str, Any]
        ) -> None:
        self.log_: Logger = log_
        self.STATE_FILE: Path = STATE_FILE
        self.state: dict[str, Any] = state

    def load_state(self: Self) -> Dict[str, Any] | None:
        """Load state from JSON file."""

        try:
            with open(
                    self.STATE_FILE,
                    "r",
                    encoding="utf-8"
                ) as file:
                return load(file)
        except (FileNotFoundError) as err_:
            self.log_.warn(
                "Error reading %s, starting fresh." % (
                    self.STATE_FILE
                ), err_
            )

        return None

    def save_state(self: Self) -> None:
        """Save state to JSON file atomically."""
        TMP_STATE_FILE: Path = Path(f"{self.STATE_FILE}.tmp")
        with open(
                TMP_STATE_FILE,
                "w",
                encoding="utf-8"
            ) as file_:
            dump(self.state, file_, indent=4)
        os.replace(TMP_STATE_FILE, self.STATE_FILE)


    def update_state(
            self: Self,
            srr: str,
            key: str,
            value: bool = True
        ) -> None:
        """Update state for a given SRR."""
        if srr not in self.state:
            self.state[srr] = {}
        self.state[srr][key] = value


    def get_state(
            self: Self,
            srr: str,
            key: str,
            default: bool = False
        ) -> bool:
        """Get state value for SRR and key."""
        return self.state.get(srr, {}).get(key, default)
