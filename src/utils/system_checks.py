from pathlib import Path
import shutil
from typing import Self

from src.utils.log.custom_logger import Logger
from src.utils.misc.housekeeping import remove_file
from src.utils.misc.id_gen import id_gen


class SystemChecks:
    def __init__(self: Self, log_: Logger, OUT_DIR: Path) -> None:
        self.log_: Logger = log_
        self.OUT_DIR: Path = OUT_DIR

    def check_disk_space(self: Self, min_disk_space: float) -> bool:
        """Check available disk space in OUT_DIR."""

        try:
            _, _, free = shutil.disk_usage(self.OUT_DIR)
            free_gb: float = free / (1024 ** 3) # convert to Gb

            self.log_.info(
                "Available %0.2f GB. Required %0.2f GB" % (
                    free_gb, min_disk_space
                )
            )

            if free_gb < min_disk_space:
                raise OSError
        except OSError as _:
            self.log_.err(
                "Insufficient disk space in %s." % (
                    self.OUT_DIR
                )
            )
        except Exception as err_:
            self.log_.warn(
                "Could not check disk space: %s" % ( err_ )
            )
        else:
            return True

        return False

    def check_permissions(self: Self) -> bool:
        test_file_path: Path = self.OUT_DIR / f"{id_gen()}.txt"
        try:
            with open(
                    test_file_path,
                    "w",
                    encoding="utf-8"
                ) as test_file_:
                test_file_.write("HELLO WORLD!")

            with open(
                    test_file_path,
                    "r",
                    encoding="utf-8"
                ) as test_file_:
                test_file_.read()
        except PermissionError as err_:
            self.log_.err(
                "No sufficient permission for %s!" % (
                    self.OUT_DIR
                ), err_
            )
        else:
            remove_file(self.log_, test_file_path)
            return True

        return False

    def pre_op_checks(self: Self, min_disk_space: float) -> bool:
        return (
            self.check_disk_space(min_disk_space) and
            self.check_permissions()
        )
