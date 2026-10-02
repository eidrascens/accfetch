from pathlib import Path
from shutil import rmtree
from os.path import exists, join, dirname, isdir
from os import makedirs, listdir, remove, walk
from typing import Any, Optional

from src.utils.log.logger import Logger
from src.commands.run_cmd import RunCMD


def process_single_srr(
    log_: Logger,
    srr: str,
    OUT_DIR: Path,
    conda_env: Path,
    max_size: int,
    TMP_DIR: Path,
    state: dict[str, Any],
    state_file: str,
    lock: Optional[threading.Lock] = None,
) -> bool:
    """
    Full pipeline for one SRR: (optional) prefetch -> (optional) fasterq-dump ->
    (optional) compress -> cleanup. Uses state file to skip completed steps.
    """
    run_cmd: RunCMD = RunCMD(log_, OUT_DIR, conda_env)

    SRA_FILE: Path = OUT_DIR / f"{srr}.sra"
    SRA_DIR: Path = OUT_DIR / srr
    FASTQ_BASE: Path = OUT_DIR / srr
    SRA_LOG_FILE: Path = OUT_DIR / ".logs" / f"{srr}.log"

    makedirs(dirname(SRA_LOG_FILE), exist_ok=True)

    if skip_existing and run_fastq:
        existing_fastq = (
            exists(f"{FASTQ_BASE}.fastq") or
            exists(f"{FASTQ_BASE}_1.fastq") or
            exists(f"{FASTQ_BASE}.fastq.gz") or
            exists(f"{FASTQ_BASE}_1.fastq.gz")
        )
        if existing_fastq:
            log_.info(f"Skipping {srr}: FASTQ output already exists.")
            return True

    # 1. Prefetch (only if enabled)
    prefetch_done = get_state(state, srr, "prefetch", False)
    if not prefetch_done:
        prefetch_ok = run_cmd.run_prefetch(
                srr, max_size, SRA_LOG_FILE
            )
        if not prefetch_ok:
            log_.err(f"Prefetch failed for {srr}, skipping conversion.")
            return False
        # if lock:
        #     with lock:
        #         update_state(state, srr, "prefetch", True)
        #         save_state(state_file, state)
        # else:
        #     update_state(state, srr, "prefetch", True)
        #     save_state(state_file, state)
    else:
        log_.info(f"Prefetch already done for {srr} (from state).")

    # Locate actual sra path
    if not exists(SRA_FILE):
        log_.err(
            "Downloaded SRA (%s) file missing in %s." % (
                srr, SRA_FILE
            )
        )
        return False

    conversion_done = get_state(state, srr, "converted", False)
    if not conversion_done:
        conv_ok = run_cmd.run_fasterq_dump(
                srr,
                SRA_FILE,
                TMP_DIR,
                SRA_LOG_FILE
            )
        if not conv_ok:
            log_.err(f"fasterq-dump failed for {srr}, keeping .sra file for retry.")
            return False

        # if lock:
        #     with lock:
        #         update_state(state, srr, "converted", True)
        #         save_state(state_file, state)
        # else:
        #     update_state(state, srr, "converted", True)
        #     save_state(state_file, state)

        compression_done = get_state(state, srr, "compressed", False)
        if not compression_done:
            fastq_files = []
            if exists(f"{FASTQ_BASE}.fastq"):
                fastq_files.append(f"{FASTQ_BASE}.fastq")
            if exists(f"{FASTQ_BASE}_1.fastq"):
                fastq_files.append(f"{FASTQ_BASE}_1.fastq")
            if exists(f"{FASTQ_BASE}_2.fastq"):
                fastq_files.append(f"{FASTQ_BASE}_2.fastq")
            if not fastq_files:
                for f in listdir(OUT_DIR):
                    if f.startswith(srr) and f.endswith(".fastq"):
                        fastq_files.append(join(OUT_DIR, f))
            if not fastq_files:
                log_.err(f"No FASTQ files found for compression for {srr}")
                return False

            compress_ok = True
            for fq in fastq_files:
                if not compress_fastq_file(fq, compression_level, keep_fastq):
                    compress_ok = False
                    break
            if not compress_ok:
                log_.err(f"Compression failed for some files of {srr}")
                return False
            # if lock:
            #     with lock:
            #         update_state(state, srr, "compressed", True)
            #         save_state(state_file, state)
            # else:
            #     update_state(state, srr, "compressed", True)
            #     save_state(state_file, state)
    else:
        log_.info(f"Conversion already done for {srr} (from state).")

    if compression_level is None or get_state(state, srr, "compressed", False):
        try:
            if isfile(actual_sra_path):
                remove(actual_sra_path)
                log_.info(f"Removed {actual_sra_path}")
            elif isdir(SRA_DIR):
                rmtree(SRA_DIR)
                log_.info(f"Removed directory {SRA_DIR}")
        except Exception as e:
            log_.warn(f"Failed to remove .sra for {srr}: {e}")

    return True


def process_srr_list(
    log_: Logger,
    srr_list: list[str],
    OUT_DIR: Path,
    state: dict[str, Any],
    state_file: str,
) -> tuple[int, int]:
    """Process a list of SRRs using parallel jobs as specified."""
    success = 0
    fail = 0
    parallel_jobs = max(1, args.parallel_jobs)

    # Create a lock only if we are going to use multiple threads
    lock = threading.Lock() if parallel_jobs > 1 else None

    if parallel_jobs > 1:
        log_.info(f"Processing {len(srr_list)} SRRs with {parallel_jobs} parallel jobs.")
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
                log_.info(f"Progress: {success+fail}/{len(srr_list)} done (success={success}, failed={fail})")
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
            log_.info(f"Progress: {success+fail}/{len(srr_list)} done (success={success}, failed={fail})")

    return success, fail
