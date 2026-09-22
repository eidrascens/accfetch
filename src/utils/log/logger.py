import logging
import random
from string import ascii_letters, digits
from pathlib import Path
from typing import Any, Optional

from rich.logging import RichHandler

from src.utils.get_dates import cdate, sdate


class Logger:
    """ Custom logger. """

    def __init__(self, log_filepath: Path, filename: str) -> None:
        logging.basicConfig(
            format="%(message)s",
            level=logging.INFO,
            datefmt="[%X]",
            handlers=[
                    RichHandler(
                        show_time=False,
                        show_path=False
                    )
                ]
        )
        self.log: logging.Logger = logging.getLogger("rich")
        self.log_filepath: Path = log_filepath
        self.log_filename: str = "%s-%s-%s.log" % (
                filename,
                sdate(no_spaces=True),
                "".join(
                    random.choices(
                        ascii_letters + digits, k=7
                    )
                )
            )
        self.log_file: Path = self.log_filepath / self.log_filename

        file_log: logging.FileHandler = logging.FileHandler(
                filename=self.log_file
            )
        file_log.setLevel(logging.INFO)
        file_log.setFormatter(
            logging.Formatter("%(levelname)s %(message)s")
        )

        self.log.addHandler(file_log)
        self.info(
            "Setup of logger complete, started %s %s" % (
                self.log_file, cdate()
            )
        )

    def get_log_file_path(self) -> Path:
        return self.log_file

    def crit(self, msg_: str, exception_: Optional[Any]) -> None:
        """Critical errors.

        Args:
            exception_ -- stderr from raised exception.
            msg_ -- message to be logged.
        """

        if not exception_:
            self.log.critical("%s", msg_)

        self.log.critical("%s: %s", exception_, msg_)

    def warn(self, msg_: str, exception_: Optional[Any]) -> None:
        """Warnings.

        Args:
            exception_ -- stderr from raised exception.
            msg_ -- message to be logged.
        """

        if not exception_:
            self.log.warning("%s", msg_)

        self.log.warning("%s: %s", exception_, msg_)


    def err(self, msg_: str, exception_: Optional[Any]) -> None:
        """Minor but tolerable errors.

        Args:
            exception_ -- stderr from raised exception.
            msg_ -- message to be logged.
        """

        if not exception_:
            self.log.error("%s", msg_)

        self.log.error("%s: %s", exception_, msg_)

    def info(self, msg_: str) -> None:
        """Likely important information.

        Args:
            msg_ -- message to be logged.
        """

        self.log.info("%s", msg_)
