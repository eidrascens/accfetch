from typing import Any
from requests import get, exceptions

from src.utils.log.logger import Logger


def fetch_srr_list(
        log_: Logger,
        conf: dict[str, Any],
        accession: str
    ) -> list[str]:
    """Fetch all SRR run accessions for a given BioProject or SRA Study accession."""
    log_.info(
        "Fetching SRR list for accession: %s" % ( accession )
    )

    ESEARCH_URL = conf["SYSTEM"]["ESEARCH_URL"]
    EFETCH_URL = conf["SYSTEM"]["EFETCH_URL"]
    ESEARCH_PARAMS = conf["SYSTEM"]["ESEARCH_PARAMS"]
    EFETCH_PARAMS = conf["SYSTEM"]["EFETCH_PARAMS"]

    try:
        response = get(
                ESEARCH_URL,
                params=ESEARCH_PARAMS,
                timeout=30
            )
        response.raise_for_status()
        esearch_data = response.json()
        uid_list = esearch_data.get(
                "esearchresult", {}).get("idlist", []
            )
        if not uid_list:
            raise RuntimeError(
                f"No SRA records found for accession: {accession}"
            )
        log_.info("Found %s SRA UIDs." % ( len(uid_list) ))
    except exceptions.RequestException as err_:
        raise RuntimeError(
                f"ESearch request failed: {err_}"
            ) from err_

    uid_string = ",".join(uid_list)

    try:
        response = get(
                EFETCH_URL,
                params=EFETCH_PARAMS,
                timeout=60
            )
        response.raise_for_status()
        csv_text = response.text
    except exceptions.RequestException as err_:
        raise RuntimeError(
                f"EFetch request failed: {e}"
            ) from err_

    lines = csv_text.strip().splitlines()
    if len(lines) < 2:
        raise RuntimeError("Runinfo CSV is empty or malformed.")

    header = lines[0].split(",")
    run_col_index = None
    for alt in ["Run", "run_accession", "RunAccession"]:
        if alt in header:
            run_col_index = header.index(alt)
            break
    if run_col_index is None:
        raise RuntimeError(
            f"Could not find 'Run' column in CSV header: {header}"
        )

    srr_list = []
    for line in lines[1:]:
        if line.strip():
            fields = line.split(",")
            if run_col_index < len(fields):
                run_acc = fields[run_col_index].strip()
                if run_acc.startswith("SRR"):
                    srr_list.append(run_acc)

    srr_list = list(dict.fromkeys(srr_list))
    if not srr_list:
        raise RuntimeError(
            f"No SRR runs found for accession: {accession}"
        )

    log_.info(f"Total SRR runs to process: {len(srr_list)}")
    return srr_list

def process_single_srr(
    srr: str,
    output_dir: str,
    max_size: Optional[str],
    prefetch_extra: Optional[List[str]],
    prefetch_path: Optional[str],
    conda_env: Optional[str],
    temp_dir: Optional[str],
    run_fastq: bool,
    fasterq_dump_path: Optional[str],
    threads: int,
    gzip: bool,
    compression_level: Optional[int],
    keep_fastq: bool,
    fasterq_extra: Optional[List[str]],
    remove_sra: bool,
    skip_existing: bool,
    do_prefetch: bool,
    dry_run: bool,
    state: Dict[str, Any],
    state_file: str,
    lock: Optional[threading.Lock] = None,
) -> bool:
    """
    Full pipeline for one SRR: (optional) prefetch -> (optional) fasterq-dump ->
    (optional) compress -> cleanup. Uses state file to skip completed steps.
    """
    sra_file = os.path.join(output_dir, f"{srr}.sra")
    sra_dir = os.path.join(output_dir, srr)
    fastq_base = os.path.join(output_dir, srr)
    log_file = os.path.join(output_dir, "logs", f"{srr}.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    if skip_existing and run_fastq:
        existing_fastq = (
            os.path.exists(f"{fastq_base}.fastq") or
            os.path.exists(f"{fastq_base}_1.fastq") or
            os.path.exists(f"{fastq_base}.fastq.gz") or
            os.path.exists(f"{fastq_base}_1.fastq.gz")
        )
        if existing_fastq:
            logger.info(f"Skipping {srr}: FASTQ output already exists.")
            return True

    # 1. Prefetch (only if enabled)
    if do_prefetch:
        prefetch_done = get_state(state, srr, 'prefetch', False)
        if not prefetch_done:
            prefetch_ok = run_prefetch(
                srr, output_dir, max_size, prefetch_extra, prefetch_path, conda_env, temp_dir, log_file
            )
            if not prefetch_ok:
                logger.error(f"Prefetch failed for {srr}, skipping conversion.")
                return False
            if lock:
                with lock:
                    update_state(state, srr, 'prefetch', True)
                    save_state(state_file, state)
            else:
                update_state(state, srr, 'prefetch', True)
                save_state(state_file, state)
        else:
            logger.info(f"Prefetch already done for {srr} (from state).")
    else:
        logger.info(f"Skipping prefetch for {srr} (disabled).")

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
            logger.error(f"Could not find .sra file in directory {sra_dir} for {srr}")
            return False
    else:
        logger.error(f"No .sra file or directory found for {srr} in {output_dir}")
        return False

    # 2. Conversion
    if run_fastq:
        conversion_done = get_state(state, srr, 'converted', False)
        if not conversion_done:
            if compression_level is None:
                conv_ok = run_fasterq_dump(
                    srr, actual_sra_path, output_dir, threads,
                    fasterq_dump_path, conda_env, gzip, fasterq_extra, log_file
                )
                if not conv_ok:
                    logger.error(f"fasterq-dump failed for {srr}, keeping .sra file for retry.")
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
                    srr, actual_sra_path, output_dir, threads,
                    fasterq_dump_path, conda_env, gzip=False, extra_args=fasterq_extra, log_file=log_file
                )
                if not conv_ok:
                    logger.error(f"fasterq-dump failed for {srr}, keeping .sra file for retry.")
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
                        for f in os.listdir(output_dir):
                            if f.startswith(srr) and f.endswith(".fastq"):
                                fastq_files.append(os.path.join(output_dir, f))
                    if not fastq_files:
                        logger.error(f"No FASTQ files found for compression for {srr}")
                        return False

                    compress_ok = True
                    for fq in fastq_files:
                        if not compress_fastq_file(fq, compression_level, keep_fastq):
                            compress_ok = False
                            break
                    if not compress_ok:
                        logger.error(f"Compression failed for some files of {srr}")
                        return False
                    if lock:
                        with lock:
                            update_state(state, srr, 'compressed', True)
                            save_state(state_file, state)
                    else:
                        update_state(state, srr, 'compressed', True)
                        save_state(state_file, state)
        else:
            logger.info(f"Conversion already done for {srr} (from state).")

        if remove_sra:
            if compression_level is None or get_state(state, srr, 'compressed', False):
                try:
                    if os.path.isfile(actual_sra_path):
                        os.remove(actual_sra_path)
                        logger.info(f"Removed {actual_sra_path}")
                    elif os.path.isdir(sra_dir):
                        shutil.rmtree(sra_dir)
                        logger.info(f"Removed directory {sra_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove .sra for {srr}: {e}")

    return True


def process_srr_list(
    srr_list: List[str],
    args,
    state: Dict[str, Any],
    state_file: str,
) -> tuple[int, int]:
    """Process a list of SRRs using parallel jobs as specified."""
    success = 0
    fail = 0
    parallel_jobs = max(1, args.parallel_jobs)

    # Create a lock only if we are going to use multiple threads
    lock = threading.Lock() if parallel_jobs > 1 else None

    if parallel_jobs > 1:
        logger.info(f"Processing {len(srr_list)} SRRs with {parallel_jobs} parallel jobs.")
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = {
                executor.submit(
                    process_single_srr,
                    srr,
                    args.output_dir,
                    args.max_size,
                    args.prefetch_extra,
                    args.prefetch_path,
                    args.conda_env,
                    args.temp_dir,
                    args.fasterq_dump,
                    args.fasterq_dump_path,
                    args.threads,          # threads per conversion
                    args.gzip,
                    args.compression_level,
                    args.keep_fastq,
                    args.fasterq_extra,
                    args.remove_sra,
                    args.skip_existing,
                    args.prefetch,
                    args.dry_run,
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
                logger.info(f"Progress: {success+fail}/{len(srr_list)} done (success={success}, failed={fail})")
    else:
        # sequential mode, no lock needed
        for srr in srr_list:
            if process_single_srr(
                srr,
                args.output_dir,
                args.max_size,
                args.prefetch_extra,
                args.prefetch_path,
                args.conda_env,
                args.temp_dir,
                args.fasterq_dump,
                args.fasterq_dump_path,
                args.threads,
                args.gzip,
                args.compression_level,
                args.keep_fastq,
                args.fasterq_extra,
                args.remove_sra,
                args.skip_existing,
                args.prefetch,
                args.dry_run,
                state,
                state_file,
                lock,  # lock is None here
            ):
                success += 1
            else:
                fail += 1
            logger.info(f"Progress: {success+fail}/{len(srr_list)} done (success={success}, failed={fail})")

    return success, fail
