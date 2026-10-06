import concurrent.futures
from os import listdir, makedirs, remove
from os.path import dirname, exists, isdir, isfile, join
from pathlib import Path
from shutil import rmtree
import threading
from typing import Any

from src.commands.run_cmd import RunCMD
from src.utils.compress import compression
from src.utils.log.custom_logger import Logger
from src.utils.state import State
from src.utils.misc.housekeeping import is_downloaded, remove_file


def process_single_srr(
    log_: Logger,
    srr: str,
    OUT_DIR: Path,
    conda_env: str,
    max_size: int,
    state: State,
    CMD_LOG: Path
    # state_file: str,
    # lock: Optional[threading.Lock] = None,
) -> bool:
    """
    Full pipeline for one SRR: (optional) prefetch -> (optional) fasterq-dump ->
    (optional) compress -> cleanup. Uses state file to skip completed steps.
    """
    run_cmd: RunCMD = RunCMD(log_, OUT_DIR, conda_env, CMD_LOG)

    SRA_FILE: Path = OUT_DIR / f"{srr}.sra"
    SRA_DIR: Path = OUT_DIR / srr
    FASTQ_BASE: Path = OUT_DIR / srr

    if (
            exists(f"{FASTQ_BASE}.fastq") or
            exists(f"{FASTQ_BASE}_1.fastq") or
            exists(f"{FASTQ_BASE}.fastq.gz") or
            exists(f"{FASTQ_BASE}_1.fastq.gz")
        ):
        log_.info(
            "%s: Skipping, FASTQ output already exists." % ( srr )
        )
        return True


        prefetch_ok = run_cmd.run_prefetch(srr)
        if not prefetch_ok:
            log_.err(
                "%s: Prefetch failed, skipping conversion." % ( srr )
            )
            return False
    else:
        log_.info(
            "%s: Prefetch already done (from state)." % ( srr )
        )

    # Locate actual sra path
    if not exists(SRA_FILE):
        log_.err(
            "Downloaded SRA (%s) file missing in %s." % (
                srr, SRA_FILE
            )
        )
        return False

    if state.get_state(srr):
        log_.info(
            "%s: Conversion already done (from state)." % ( srr )
        )

    if not run_cmd.run_fasterq_dump(srr, SRA_FILE):
        log_.err(
            "%s: fasterq-dump failed, keeping .sra for retry." % (
                srr
            )
        )

        return False

    compression_done = state.get_state(srr)
    if not compression_done:
        fastq_files = []
        for file_ in listdir(OUT_DIR):
            if file_.startswith(srr) and file_.endswith(".fastq"):
                fastq_files.append(join(OUT_DIR, file_))

        if not fastq_files:
            log_.err(
                "No %s FASTQ file(s) for compression" % ( srr )
            )
            return False

        compressed_files: list[Path] = []
        for fastq_fie_ in fastq_files:
            comp_file, comp_stat = compression(log_, fastq_fie_)
            if comp_stat:
                compressed_files.append(comp_file)

        if not compressed_files:
            log_.err(
                "Compression failed for %s" % ( compressed_files )
            )
            return False

    if not remove_file(log_, SRA_FILE) or not remove_file(log_, SRA_DIR):
        log_.warn("%s: Failed to remove .sra" % ( srr ),)

    return True


def process_srr_list(
    log_: Logger,
    srr_list: list[str],
    OUT_DIR: Path,
    parallel_jobs: int,
    state: dict[str, Any],
    state_file: str,
) -> tuple[int, int]:
    """Process a list of SRRs using parallel jobs as specified."""
    success = 0
    fail = 0
    parallel_jobs = max(1, parallel_jobs)

    # Create a lock only if we are going to use multiple threads
    lock = threading.Lock() if parallel_jobs > 1 else None

    if parallel_jobs > 1:
        log_.info(
            "Processing %d SRRs with %s parallel jobs." % (
                len(srr_list), parallel_jobs
            )
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {
                executor.submit(
                    process_single_srr,
                    log_,
                    srr,
                    OUT_DIR,
                    state,
                    state_file,
                    lock,                   # pass the lock
                ): srr
                for srr in srr_list
            }
            for future in concurrent.futures.as_completed(futures):
                srr = futures[future]
                if future.result():
                    success += 1
                else:
                    fail += 1
                log_.info(
                    "Progress: %d done (success=%d, failed=%d)" % (
                        (success + fail/len(srr_list)), success, fail
                    )
                )
    else:
        # sequential mode, no lock needed
        for srr in srr_list:
            if process_single_srr(
                log_,
                srr,
                OUT_DIR,
                state,
                state_file,
                lock,  # lock is None here
            ):
                success += 1
            else:
                fail += 1
            log_.info(
                    "Progress: %d done (success=%d, failed=%d)" % (
                        (success + fail/len(srr_list)), success, fail
                    )
                )

    return success, fail
