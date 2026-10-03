from json import dump, load
import os
from pathlib import Path
from typing import Any, Dict, Self

from src.utils.log.custom_logger import Logger


class State:
    # state file new format
    #  str: dict[str, str | Path]
    # {
    #     SRR: {
    #       str: hashmap
    #         STATUS: PF, FD, or GZ
    #           str: str
    #         PATH: relevant path / Path
    #           str: Path
    #     }
    # }
    def __init__(
            self: Self,
            log_: Logger,
            STATE_FILE: Path,
            state: dict[str, Any]
        ) -> None:
        self.log_: Logger = log_
        self.STATE_FILE: Path = OUT_DIR / (
                ".state_file-%s" % (
                    vsdate(no_spaces=True)
                )
            )
        self.state: dict[str, dict[str, str | Path]] = {}

    def create_state_file(self: Self) -> None:
        if exists(self.STATE_FILE):
            raise FileExistsError

        try:
            with open(
                    self.STATE_FILE,
                    "w",
                    encoding="utf-8"
                ) as state_file_:
                dump({}, state_file_)
        except FileExistsError as _:
            self.log_.warn(
                "%s already exists!" % ( self.STATE_FILE )
            )
        except OSError as err_:
            self.log_.err(
                "Cannot create state file %s" % (
                    self.STATE_FILE
                ), err_
            )

    def load_state_file(self: Self) -> dict:
        """Load state from JSON file."""

        try:
            self.create_state_file()
            with open(
                    self.STATE_FILE,
                    "r",
                    encoding="utf-8"
                ) as state_file_:
                self.state = load(state_file_)
        except (FileNotFoundError, OSError) as err_:
            self.log_.warn(
                "Error reading %s, starting fresh." % (
                    self.STATE_FILE
                ), err_
            )

        return loads(f"{self.state}")

    def _save_state(self: Self) -> None:
        """Save state to JSON file atomically."""
        TMP_STATE_FILE: Path = Path(f"{self.STATE_FILE}.tmp")
        with open(
                TMP_STATE_FILE,
                "w",
                encoding="utf-8"
            ) as temp_state_file_:
            dump(self.state, temp_state_file_, indent=4)
        os.replace(TMP_STATE_FILE, self.STATE_FILE)


    def update_state(
            self: Self,
            srr: str,
            status: str,
            SRR_PATH: Path
        ) -> None:
        """Update state for a given SRR."""
        self.state[srr] = {
            "status": status,
            "path": SRR_PATH
        }
        self._save_state()

    def get_state(
            self: Self, srr: str
        ) -> dict[str, str | Path]:
        """Get state value for SRR and key."""
        return self.state.get(srr, {})
