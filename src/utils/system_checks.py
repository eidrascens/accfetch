import shutil
from typing import Self

from src.utils.log.custom_logger import Logger


class SystemChecks:
    def __init__(self: Self, log_: Logger) -> None:
        self.log_: Logger = log_

    def check_disk_space(
            self: Self, OUT_DIR: str, min_gb: float
        ) -> bool:
        """Check available disk space in OUT_DIR."""

        try:
            _, _, free = shutil.disk_usage(OUT_DIR)
            free_gb: float = free / (1024 ** 3) # convert to Gb
            if free_gb < min_gb:
                raise OSError
        except OSError as _:
            self.log_.err(
                "Insufficient disk space in %s.\n"
                "Available %0.2f GB, required %0.2f GB"
                % ( OUT_DIR, free_gb, min_gb )
            )
        except Exception as err:
            self.log_.warn(
                "Could not check disk space: %s" % ( err )
            )
        else:
            self.log_.info("%0.2f GB available" % ( free_gb ))
            return True

        return False
