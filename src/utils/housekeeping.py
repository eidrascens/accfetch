from pathlib import Path
from os.path import exists, isdir

from os import remove

from src.utils.log.logger import Logger


def is_downloaded(srr: str, output_dir: Path) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    return exists(
            output_dir / f"{srr}.sra"
        ) or isdir(
            output_dir / srr
        )


def remove_file(log: Logger, file_path: Path) -> None:
    if not exists(file_path):
        log.info(
            "%s does not exist." % ( file_path )
        )
        return

    try:
        remove(file_path)
    except (
        FileNotFoundError,
        OSError,
        PermissionError,
        SystemError
    ) as err:
        log.err(
            err, "Cannot remove %s" % ( file_path )
        )


