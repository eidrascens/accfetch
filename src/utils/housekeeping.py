from pathlib import Path
from os.path import exists, isdir

from src.utils.log.logger import Logger
def is_downloaded(log: Logger, srr: str, output_dir: Path) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    return exists(
            output_dir / f"{srr}.sra"
        ) or isdir(
            output_dir / srr
        )
    )
