import gzip as gzip_module
from os.path import realpath, dirname
from pathlib import Path
from shutil import copyfileobj

from src.utils.log.logger import Logger
from src.utils.housekeeping import remove_file


def compress_fastq_file(
        log_: Logger,
        FASTQ_FILE: Path,
        compression_level: int,
    ) -> bool:
    """Compress a single FASTQ file using gzip with specified level."""

    out_dir: Path = Path(
            dirname( # get the directory of fastq file
                realpath(FASTQ_FILE)
            )
        )
    COMP_FASTQ_FILE: Path = Path(out_dir / f"{FASTQ_FILE}.gz")
    log_.info(
        "Compressing %s -> %s (level: %d)" % (
            FASTQ_FILE, COMP_FASTQ_FILE, compression_level
        )
    )
    try:
        with open(
                FASTQ_FILE, "rb"
            ) as f_in, open(
                COMP_FASTQ_FILE, "wb"
            ) as f_out:
            with gzip_module.GzipFile(
                filename="",
                mode="wb",
                compresslevel=compression_level,
                fileobj=f_out
            ) as gz_out:
                copyfileobj(f_in, gz_out)
        remove_file(log_, FASTQ_FILE)
    except Exception as err_:
        log_.err(
            "Cannot compress %s" % ( FASTQ_FILE ), err_
        )
    else:
        return True

    remove_file(log_, COMP_FASTQ_FILE)
    return False



def _compress_fastq(
        log_: Logger,
        FASTQ_FILE: Path,
        pigz_path: Path,
        level: int = 6,
        keep_original: bool =False,
        threads: int = 4
    ):
    """
    Compress a single FASTQ file.
    Prefers `pigz` (parallel) if available; falls back to Python's gzip.
    """

    COMP_FASTQ_FILE = FASTQ_FILE.with_suffix(FASTQ_FILE.suffix + ".gz")

    try:
        # pigz: -N = level, -p = threads, -k = keep original, -f = force overwrite
        if not exists(pigz_path):
            raise RuntimeError("%s does not exists." % ( pigz_path ))
        cmd = [
                pigz_path,
                f"-{level}",
                "-p",
                f"{threads}",
                "-k" if keep_original else "-f",
                f"{FASTQ_FILE}"
            ]
        run(cmd, check=True)
    except RuntimeError as err_:
        log_.warn(
            "Runtime error: falling back to Python Gzip", err_
        )

        with open(
                FASTQ_FILE, "rb"
            ) as f_in, gzip.open(
                COMP_FASTQ_FILE, "wb", compresslevel=level
            ) as f_out:
            copyfileobj(f_in, f_out)

        if not keep_original:
            FASTQ_FILE.unlink()

    return COMP_FASTQ_FILE
