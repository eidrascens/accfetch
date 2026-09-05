import gzip as gzip_module
from os import remove
from os.path import exists
from shutil import copyfileobj

from src.utils.log.logger import Logger


def compress_fastq_file(
        log: Logger,
        fastq_path: str,
        compression_level: int,
    ) -> bool:
    """Compress a single FASTQ file using gzip with specified level."""

    gz_path = f"{fastq_path}.gz"
    log.info(
        "Compressing %s -> %s (level: %d)" % (
            fastq_path, gz_path, compression_level
        )
    )
    start = time.time()
    try:
        with open(fastq_path, "rb") as f_in, open(gz_path, "wb") as f_out:
            with gzip_module.GzipFile(
                filename="",
                mode="wb",
                compresslevel=compression_level,
                fileobj=f_out
            ) as gz_out:
                copyfileobj(f_in, gz_out)
        duration = time.time() - start
        remove(fastq_path)
    except Exception as e:
        log.err(f"Compression failed for {fastq_path}: {e}")
        if exists(gz_path):
            try:
                remove(gz_path)
            except:
                pass
        return False

    return True
