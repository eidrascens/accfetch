import shutil
from typing import Self
from pathlib import Path

from src.utils.log.custom_logger import Logger


class SystemChecks:
    def __init__(self: Self, log_: Logger, OUT_DIR: Path) -> None:
        self.log_: Logger = log_
        self.OUT_DIR: Path = OUT_DIR

    def check_disk_space(self: Self, min_gb: float) -> bool:
        """Check available disk space in OUT_DIR."""

        try:
            _, _, free = shutil.disk_usage(self.OUT_DIR)
            free_gb: float = free / (1024 ** 3) # convert to Gb
            if free_gb < min_gb:
                raise OSError
        except OSError as _:
            self.log_.err(
                "Insufficient disk space in %s.\n"
                "Available %0.2f GB, required %0.2f GB"
                % ( self.OUT_DIR, free_gb, min_gb )
            )
        except Exception as err:
            self.log_.warn(
                "Could not check disk space: %s" % ( err )
            )
        else:
            self.log_.info("%0.2f GB available" % ( free_gb ))
            return True

        return False
