import shutil

from src.utils.log.logger import Logger


def check_disk_space(
        log_: Logger, output_dir: str, min_gb: float
    ) -> bool:
    """Check available disk space in output_dir."""
    if min_gb <= 0:
        return True

    try:
        _, _, free = shutil.disk_usage(output_dir)
        free_gb: float = free / (1024 ** 3) # convert to Gb
        if free_gb < min_gb:
            raise OSError
    except OSError as _:
        log_.err(
            "Insufficient disk space in %s.\n"
            "Available %0.2f GB, required %0.2f GB"
            % ( output_dir, free_gb, min_gb )
        )
    except Exception as err:
        log_.warn(
            "Could not check disk space: %s" % ( err )
        )
    else:
        log_.info("%0.2f GB available" % ( free_gb ))
        return True

    return False
