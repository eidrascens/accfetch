import gzip as gzip_module
from multiprocessing import cpu_count
from os.path import dirname, exists, realpath
from pathlib import Path
from shutil import copyfileobj
from subprocess import CalledProcessError, run

from src.utils.housekeeping import remove_file
from src.utils.log.custom_logger import Logger


def fallback_compression(
        log_: Logger,
        FASTQ_FILE: Path,
        COMP_FASTQ_FILE: Path,
        COMP_LVL: int = 6,
    ) -> tuple[Path, bool]:
    """Compress a single FASTQ file using gzip with specified COMP_LVL."""

    try:
        with open(
                FASTQ_FILE, "rb"
            ) as f_in, open(
                COMP_FASTQ_FILE, "wb"
            ) as f_out:
            with gzip_module.GzipFile(
                filename="",
                mode="wb",
                compresslevel=COMP_LVL,
                fileobj=f_out
            ) as gz_out:
                copyfileobj(f_in, gz_out)
        remove_file(log_, FASTQ_FILE)
    except Exception as err_:
        log_.err(
            "Cannot compress %s" % ( FASTQ_FILE ), err_
        )
    else:
        return COMP_FASTQ_FILE, True

    return FASTQ_FILE, False


def compression(
        log_: Logger,
        FASTQ_FILE: Path,
        COMP_LVL: int = 6
    ) -> tuple[Path, bool]:
    """
    Compress a single FASTQ file.
    Prefers `pigz` (parallel) if available; falls back to Python's gzip.
    """

    COMP_FASTQ_FILE = FASTQ_FILE.with_suffix(FASTQ_FILE.suffix + ".gz")

    try:
        # pigz: -N = COMP_LVL, -p = threads, -k = keep original, -f = force overwrite
        if not exists(PIGZ_PATH):
            raise RuntimeError(f"{PIGZ_PATH} does not exists.")
        cmd = [
                "pigz",
                f"-{COMP_LVL}",
                "-p",
                f"{cpu_count()}",
                "-f",
                f"{FASTQ_FILE}"
            ]
        run(cmd, check=True)
    except (RuntimeError, CalledProcessError) as err_:
        log_.warn(
            "Runtime error: falling back to Python Gzip", err_
        )
        fallback_compression(
            log_, FASTQ_FILE, COMP_FASTQ_FILE, COMP_LVL
        )
    else:
        return COMP_FASTQ_FILE, True

    return FASTQ_FILE, False

