def build_prefetch_cmd(
    srr: str,
    output_dir: str,
    max_size: Optional[str],
    extra_args: Optional[List[str]],
    prefetch_path: Optional[str],
    conda_env: Optional[str],
) -> List[str]:
    """Build the command list for running prefetch."""
    if prefetch_path:
        cmd = [prefetch_path, srr, "-O", output_dir]
    elif conda_env:
        cmd = ["conda", "run", "-n", conda_env,
               "prefetch", srr, "-O", output_dir]
    else:
        cmd = ["prefetch", srr, "-O", output_dir]

    if max_size:
        cmd.extend(["--max-size", max_size])
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def build_fasterq_dump_cmd(
    sra_file: str,
    output_dir: str,
    threads: int,
    fasterq_dump_path: Optional[str],
    conda_env: Optional[str],
    gzip: bool,
    extra_args: Optional[List[str]],
) -> List[str]:
    """Build the command for fasterq-dump."""
    if fasterq_dump_path:
        cmd = [fasterq_dump_path, sra_file, "-O",
               output_dir, "--threads", str(threads)]
    elif conda_env:
        cmd = ["conda", "run", "-n", conda_env, "fasterq-dump",
               sra_file, "-O", output_dir, "--threads", str(threads)]
    else:
        cmd = ["fasterq-dump", sra_file, "-O",
               output_dir, "--threads", str(threads)]

    if gzip:
        cmd.append("--gzip")
    if extra_args:
        cmd.extend(extra_args)
    return cmd
