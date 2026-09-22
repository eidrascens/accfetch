def run_fasterq_dump(
    srr: str,
    sra_path: str,
    output_dir: str,
    threads: int,
    fasterq_dump_path: Optional[str],
    conda_env: Optional[str],
    gzip: bool,
    extra_args: Optional[List[str]],
    log_file: str,
) -> bool:
    """Run fasterq-dump on the .sra file, logging to a file. Returns True on success."""
    cmd = build_fasterq_dump_cmd(
        sra_path, output_dir, threads, fasterq_dump_path, conda_env, gzip, extra_args)
    logger.info(f"Running fasterq-dump: {' '.join(cmd)}")
    try:
        with open(log_file, "a") as log_f:
            result = subprocess.run(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if result.returncode == 0:
            logger.info(f"fasterq-dump succeeded for {srr}")
            return True
        else:
            logger.error(f"fasterq-dump failed for {srr}: see {log_file}")
            return False
    except Exception as e:
        logger.error(f"Exception during fasterq-dump for {srr}: {e}")
        return False
