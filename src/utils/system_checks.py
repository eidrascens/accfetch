import shutil
from typing import Self

from src.utils.log.custom_logger import Logger


class SystemChecks:
    def __init__(self: Self, log_: Logger) -> None:
        self.log_: Logger = log_

    def check_disk_space(
            self: Self, output_dir: str, min_gb: float
        ) -> bool:
        """Check available disk space in output_dir."""

        try:
            _, _, free = shutil.disk_usage(output_dir)
            free_gb: float = free / (1024 ** 3) # convert to Gb
            if free_gb < min_gb:
                raise OSError
        except OSError as _:
            self.log_.err(
                "Insufficient disk space in %s.\n"
                "Available %0.2f GB, required %0.2f GB"
                % ( output_dir, free_gb, min_gb )
            )
        except Exception as err:
            self.log_.warn(
                "Could not check disk space: %s" % ( err )
            )
        else:
            self.log_.info("%0.2f GB available" % ( free_gb ))
            return True

        return False
