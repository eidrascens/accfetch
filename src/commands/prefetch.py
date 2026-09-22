def run_prefetch(
    srr: str,
    output_dir: str,
    max_size: Optional[str],
    extra_args: Optional[List[str]],
    prefetch_path: Optional[str],
    conda_env: Optional[str],
    temp_dir: Optional[str],
    log_file: str,
) -> bool:
    """Run prefetch for one SRR, logging to a file. Returns True on success."""
    cmd = build_prefetch_cmd(srr, output_dir, max_size,
                             extra_args, prefetch_path, conda_env)
    logger.info(f"Running prefetch: {' '.join(cmd)}")
    env = os.environ.copy()
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        env["TMPDIR"] = temp_dir
    try:
        with open(log_file, "a") as log_f:
            result = subprocess.run(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                env=env,
            )
        if result.returncode == 0:
            logger.info(f"prefetch succeeded for {srr}")
            return True
        else:
            logger.error(f"prefetch failed for {srr}: see {log_file}")
            return False
    except Exception as e:
        logger.error(f"Exception during prefetch for {srr}: {e}")
        return False
