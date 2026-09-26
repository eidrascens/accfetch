import gzip as gzip_module
from os.path import realpath, dirname
from pathlib import Path
from shutil import copyfileobj

from src.utils.log.logger import Logger
from src.utils.housekeeping import remove_file


def compress_fastq_file(
        log_: Logger,
        fastq_path: Path,
        compression_level: int,
    ) -> bool:
    """Compress a single FASTQ file using gzip with specified level."""

    out_dir: Path = Path(
            dirname( # get the directory of fastq file
                realpath(fastq_path)
            )
        )
    gz_path: Path = Path(out_dir / f"{fastq_path}.gz")
    log_.info(
        "Compressing %s -> %s (level: %d)" % (
            fastq_path, gz_path, compression_level
        )
    )
    try:
        with open(
                fastq_path, "rb"
            ) as f_in, open(
                gz_path, "wb"
            ) as f_out:
            with gzip_module.GzipFile(
                filename="",
                mode="wb",
                compresslevel=compression_level,
                fileobj=f_out
            ) as gz_out:
                copyfileobj(f_in, gz_out)
        remove_file(log_, fastq_path)
    except Exception as err_:
        log_.err(
            "Cannot compress %s" % ( fastq_path ), err_
        )
    else:
        return True

    remove_file(log_, gz_path)
    return False



def _compress_fastq(
        log_: Logger,
        fastq_path: Path,
        pigz_path: Path,
        level: int = 6,
        keep_original: bool =False,
        threads: int = 4
    ):
    """
    Compress a single FASTQ file.
    Prefers `pigz` (parallel) if available; falls back to Python's gzip.
    """

    gz_path = fastq_path.with_suffix(fastq_path.suffix + ".gz")

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
                f"{fastq_path}"
            ]
        run(cmd, check=True)
    except RuntimeError as err_:
        log_.warn(
            "Runtime error: falling back to Python Gzip", err_
        )

        with open(
                fastq_path, "rb"
            ) as f_in, gzip.open(
                gz_path, "wb", compresslevel=level
            ) as f_out:
            copyfileobj(f_in, f_out)

        if not keep_original:
            fastq_path.unlink()

    return gz_path
