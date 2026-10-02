from pathlib import Path
from src.utils.log.logger import Logger

from typing import Any, Optional


def process_single_srr(
    log_: Logger,
    srr: str,
    OUT_DIR: Path,
    state: dict[str, Any],
    state_file: str,
    lock: Optional[threading.Lock] = None,
) -> bool:
    """
    Full pipeline for one SRR: (optional) prefetch -> (optional) fasterq-dump ->
    (optional) compress -> cleanup. Uses state file to skip completed steps.
    """
    sra_file = os.path.join(OUT_DIR, f"{srr}.sra")
    sra_dir = os.path.join(OUT_DIR, srr)
    fastq_base = os.path.join(OUT_DIR, srr)
    log_file = os.path.join(OUT_DIR, "logs", f"{srr}.log")

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    if skip_existing and run_fastq:
        existing_fastq = (
            os.path.exists(f"{fastq_base}.fastq") or
            os.path.exists(f"{fastq_base}_1.fastq") or
            os.path.exists(f"{fastq_base}.fastq.gz") or
            os.path.exists(f"{fastq_base}_1.fastq.gz")
        )
        if existing_fastq:
            log_.info(f"Skipping {srr}: FASTQ output already exists.")
            return True

    # 1. Prefetch (only if enabled)
    prefetch_done = get_state(state, srr, 'prefetch', False)
    if not prefetch_done:
        prefetch_ok = run_prefetch(
            srr, OUT_DIR, max_size, temp_dir, log_file
        )
        if not prefetch_ok:
            log_.err(f"Prefetch failed for {srr}, skipping conversion.")
            return False
        if lock:
            with lock:
                update_state(state, srr, 'prefetch', True)
                save_state(state_file, state)
        else:
            update_state(state, srr, 'prefetch', True)
            save_state(state_file, state)
    else:
        log_.info(f"Prefetch already done for {srr} (from state).")

    # Locate actual sra path
    actual_sra_path = None
    if os.path.exists(sra_file):
        actual_sra_path = sra_file
    elif os.path.isdir(sra_dir):
        for root, dirs, files in os.walk(sra_dir):
            for f in files:
                if f.endswith(".sra"):
                    actual_sra_path = os.path.join(root, f)
                    break
        if not actual_sra_path:
            log_.err(f"Could not find .sra file in directory {sra_dir} for {srr}")
            return False
    else:
        log_.err(f"No .sra file or directory found for {srr} in {OUT_DIR}")
        return False

    conversion_done = get_state(state, srr, 'converted', False)
    if not conversion_done:
        if compression_level is None:
            conv_ok = run_fasterq_dump(
                srr, actual_sra_path, OUT_DIR,,
                fasterq_dump_path, log_file
            )
            if not conv_ok:
                log_.err(f"fasterq-dump failed for {srr}, keeping .sra file for retry.")
                return False
            if lock:
                with lock:
                    update_state(state, srr, 'converted', True)
                    if gzip:
                        update_state(state, srr, 'compressed', True)
                    save_state(state_file, state)
            else:
                update_state(state, srr, 'converted', True)
                if gzip:
                    update_state(state, srr, 'compressed', True)
                save_state(state_file, state)
        else:
            conv_ok = run_fasterq_dump(
                srr, actual_sra_path, OUT_DIR, threads,
                fasterq_dump_path, conda_env, gzip=False, extra_args=fasterq_extra, log_file=log_file
            )
            if not conv_ok:
                log_.err(f"fasterq-dump failed for {srr}, keeping .sra file for retry.")
                return False
            if lock:
                with lock:
                    update_state(state, srr, 'converted', True)
                    save_state(state_file, state)
            else:
                update_state(state, srr, 'converted', True)
                save_state(state_file, state)

            compression_done = get_state(state, srr, 'compressed', False)
            if not compression_done:
                fastq_files = []
                if os.path.exists(f"{fastq_base}.fastq"):
                    fastq_files.append(f"{fastq_base}.fastq")
                if os.path.exists(f"{fastq_base}_1.fastq"):
                    fastq_files.append(f"{fastq_base}_1.fastq")
                if os.path.exists(f"{fastq_base}_2.fastq"):
                    fastq_files.append(f"{fastq_base}_2.fastq")
                if not fastq_files:
                    for f in os.listdir(OUT_DIR):
                        if f.startswith(srr) and f.endswith(".fastq"):
                            fastq_files.append(os.path.join(OUT_DIR, f))
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
                if lock:
                    with lock:
                        update_state(state, srr, 'compressed', True)
                        save_state(state_file, state)
                else:
                    update_state(state, srr, 'compressed', True)
                    save_state(state_file, state)
    else:
        log_.info(f"Conversion already done for {srr} (from state).")

    if compression_level is None or get_state(state, srr, 'compressed', False):
        try:
            if os.path.isfile(actual_sra_path):
                os.remove(actual_sra_path)
                log_.info(f"Removed {actual_sra_path}")
            elif os.path.isdir(sra_dir):
                shutil.rmtree(sra_dir)
                log_.info(f"Removed directory {sra_dir}")
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
