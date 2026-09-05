def check_disk_space(output_dir: str, min_gb: float) -> bool:
    """Check available disk space in output_dir."""
    if min_gb <= 0:
        return True
    try:
        total, used, free = shutil.disk_usage(output_dir)
        free_gb = free / (1024 ** 3)
        if free_gb < min_gb:
            logger.error(
                f"Insufficient disk space in {output_dir}: "
                f"available {free_gb:.1f} GB, required {min_gb:.1f} GB"
            )
            return False
        logger.info(f"Disk space check passed: {free_gb:.1f} GB available")
        return True
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True
