def compress_fastq_file(
    fastq_path: str,
    compression_level: int,
    keep_fastq: bool,
) -> bool:
    """Compress a single FASTQ file using gzip with specified level."""
    gz_path = fastq_path + ".gz"
    logger.info(
        f"Compressing {fastq_path} -> {gz_path} (level {compression_level})")
    start = time.time()
    try:
        with open(fastq_path, 'rb') as f_in, open(gz_path, 'wb') as f_out:
            import gzip as gzip_module
            with gzip_module.GzipFile(filename='', mode='wb', compresslevel=compression_level, fileobj=f_out) as gz_out:
                shutil.copyfileobj(f_in, gz_out)
        duration = time.time() - start
        logger.info(f"Compressed {fastq_path} in {duration:.1f}s")
        if not keep_fastq:
            os.remove(fastq_path)
            logger.info(f"Removed original {fastq_path}")
        return True
    except Exception as e:
        logger.error(f"Compression failed for {fastq_path}: {e}")
        if os.path.exists(gz_path):
            try:
                os.remove(gz_path)
            except:
                pass
        return False
