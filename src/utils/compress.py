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

