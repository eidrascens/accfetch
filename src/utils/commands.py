from pathlib import Path
from typing import Optional


def build_prefetch_cmd(
        prefetch_path: str,
        srr: str,
        output_dir: Path,
        max_size: Optional[str],
        extra_args: Optional[list[str]],
        conda_env: Optional[str],
    ) -> list[str]:
    """Build the command list for running prefetch."""
    BASE_PREFETCH_CMD: list[str | Path] = [
            prefetch_path,
            srr,
            "-O",
            output_dir
        ]
    cmd: list[str] = BASE_PREFETCH_CMD
    if conda_env:
        cmd: list[str | Path]  = [
                "conda",
                "run",
                "-n",
                conda_env,
            ].extend(BASE_PREFETCH_CMD)

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
        extra_args: Optional[list[str]],
    ) -> list[str]:
    """Build the command for fasterq-dump."""
    BASE_FD_CMD: list[str | Path] = [
            fasterq_dump_path,
            sra_file,
            "-O",
            output_dir,
            "--threads",
            f"{threads}",
            "--gzip"
        ]
    cmd: list[str | Path] = BASE_FD_CMD
    elif conda_env:
        cmd: list[str | Path] = [
                "conda",
                "run",
                "-n",
                conda_env,
            ].extend(BASE_FD_CMD)

    if extra_args:
        cmd.extend(extra_args)
    return cmd
