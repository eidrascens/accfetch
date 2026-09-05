from src.utils.log.logger import Logger


def check_disk_space(
        log: Logger, output_dir: str, min_gb: float
    ) -> bool:
    """Check available disk space in output_dir."""
    if min_gb <= 0:
        return True

    try:
        _, _, free = shutil.disk_usage(output_dir)
        free_gb = free / (1024 ** 3) # convert to Gb
        if free_gb < min_gb:
            raise OSError
    except OSError as _:
        log.error(
            "Insufficient disk space in %s: "
            "available %0.2f GB, required %0.2f GB"
            % ( output_dir, free_gb, min_gb )
        )
        return False
    except Exception as err:
        log.warning(
            "Could not check disk space: %s" % ( err )
        )
    else:
        log.info("%0.2f GB available" % ( free_gb ))

    return True
