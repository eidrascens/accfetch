from pathlib import Path
from subprocess import run, STDOUT

from src.utils.log.logger import Logger
from src.utils.commands import build_fasterq_dump_cmd

def run_fasterq_dump(
    log_: Logger,
    srr: str,
    sra_path: Path,
    out_dir: str,
    threads: int,
    run_log_file: Path,
) -> bool:
    """Run fasterq-dump on the .sra file, logging to a file. Returns True on success."""
    cmd = build_fasterq_dump_cmd(
            sra_path,
            out_dir,
            threads,
        )
    log_.info(f"Running fasterq-dump: {' '.join(cmd)}")
    try:
        with open(run_log_file, "a", encoding="utf-8") as log_f:
            result = run(
                    cmd,
                    stdout=log_f,
                    stderr=STDOUT,
                    text=True,
                    check=False,
                )
        if result.returncode != 0:
            raise RuntimeError

        log_.info(
            "fasterq-dump succeeded for %s" % ( srr )
        )
    except Exception as err_:
        log_.err(
            "fasterq-dump failed for %s (log: %s)" % (
                srr, run_log_file
            ), err_
        )
    else:
        return True

    return False
