from json import dump, load, loads
import os
from os.path import exists
from pathlib import Path
from typing import Self

from src.utils.log.custom_logger import Logger
from src.utils.misc.get_dates import vsdate


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
            OUT_DIR: Path,
            state_file_name: str
        ) -> None:
        self.log_: Logger = log_

        try:
            self.STATE_FILE: Path = OUT_DIR / state_file_name
            if not exists(self.STATE_FILE):
                self.log_.info("%s does not exists" % ( self.STATE_FILE ))
                raise TypeError
        except TypeError as _:
            self.STATE_FILE: Path = OUT_DIR / (
                    ".state_file-%s" % (
                        vsdate(no_spaces=True)
                    )
                )
            self.log_.info("New state file: %s" % ( self.STATE_FILE ))

        self.state: dict[str, dict[str, str | Path]] = {}

    def create_state_file(self: Self) -> None:
        self.log_.info(
            "Creating new state file: %s" % ( self.STATE_FILE )
        )
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
            if not exists(self.STATE_FILE):
                self.create_state_file()

            self.log_.info(
                "Reading state file %s" % ( self.STATE_FILE )
            )
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
            self.state = loads(f"{self.state}")

        return self.state

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
        self.log_.info(
            "Updating state of %s with values %s, %s" % (
                srr, status, SRR_PATH
            )
        )
        self.state[srr] = {
            "status": status,
            "path": str(SRR_PATH)
        }
        self._save_state()

    def get_state(
            self: Self, srr: str, state_property: str
        ) -> str | Path:
        """Get state value for SRR and key."""
        self.log_.info(
            "Retrieving the state property %s of %s" % (
                state_property, srr
            )
        )
        return self.state.get(srr, {}).get(state_property, "")

