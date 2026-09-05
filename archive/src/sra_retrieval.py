#!/usr/bin/env python3
"""
Automate SRA retrieval and conversion (prefetch -> fasterq-dump) for all runs
under a BioProject or SRA Study accession. Designed for HPC clusters, especially
the COARE "Saliksik" environment.

Features:
- Fetches all SRR accessions for a given accession using NCBI E-utilities.
- Downloads .sra files with `prefetch` (disabled by default; use --prefetch).
- Converts .sra to FASTQ with `fasterq-dump`.
- Compression: default is gzip level 6. If --compression-level is not given,
  gzip is applied on-the-fly during fasterq-dump (level 6). If you specify
  --compression-level 1-9, the workflow first produces uncompressed FASTQ,
  then compresses separately with the chosen level.
- Optional deletion of .sra after successful conversion (--remove-sra).
- Disk space pre-check with --min-disk-space (GB).
- Resume support: a state file records progress per SRR.
- HPC efficiency:
    * --parallel-jobs controls the number of concurrent SRR conversions (independent of --threads per conversion).
    * In SLURM array mode, each task uses its own state file to avoid race conditions.
    * Subprocess output is redirected to per‑SRR log files instead of held in memory.
    * --dry-run prints intended commands without executing them.
    * Thread-safe state updates in local parallel mode via threading.Lock.
- Supports SLURM array jobs (--scheduler slurm --array-size N).
- Correct QoS/partition mapping for Saliksik.

Recommended usage:
    - For small sets (< ~20 SRRs), you can run locally with --parallel-jobs > 1.
      To avoid duplicate work after an interruption, also use --skip-existing.
    - If you rely heavily on accurate resume and do not want any risk of lost state,
      set --parallel-jobs 1.
    - For larger sets, prefer array jobs (--scheduler slurm) where each task uses its
      own state file, completely eliminating race conditions.

Requirements:
- Python 3.6+
- SRA Toolkit installed (provide --prefetch-path, --sra-toolkit-bin, or --conda-env)
- 'requests' library (pip install requests)

Usage examples:
    # Only convert existing .sra files
    python sra_retrieval.py SRPXXXXXX \
        --sra-toolkit-bin /path/to/bin \
        --fasterq-dump \
        --compression-level 6 \
        --remove-sra \
        --output-dir /scratch1/user/fastq \
        --parallel-jobs 4 --threads 8

    # Enable download before conversion
    python sra_retrieval.py SRPXXXXXX \
        --sra-toolkit-bin /path/to/bin \
        --prefetch \
        --fasterq-dump \
        --compression-level 6 \
        --remove-sra \
        --output-dir /scratch1/user/fastq \
        --parallel-jobs 4 --threads 8

    # Submit as a SLURM array job
    python sra_retrieval.py SRPXXXXXX \
    --sra-toolkit-bin /path/to/bin \
    --prefetch \
    --fasterq-dump \
    --compression-level 6 \
    --remove-sra \
    --output-dir /scratch1/user/fastq \
    --scheduler slurm \
    --array-size 20 \
    --partition batch \
    --mem 16G \
    --time 24:00:00 \
    --parallel-jobs 2 \
    --threads 4

    # Dry run to see commands
    python sra_retrieval.py SRPXXXXXX \
        --sra-toolkit-bin /path/to/bin \
        --prefetch \
        --fasterq-dump \
        --dry-run
"""

import argparse
import concurrent.futures
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import threading
from typing import List, Optional, Dict, Any

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)



# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------
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
        cmd = ["conda", "run", "-n", conda_env, "prefetch", srr, "-O", output_dir]
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
        cmd = [fasterq_dump_path, sra_file, "-O", output_dir, "--threads", str(threads)]
    elif conda_env:
        cmd = ["conda", "run", "-n", conda_env, "fasterq-dump", sra_file, "-O", output_dir, "--threads", str(threads)]
    else:
        cmd = ["fasterq-dump", sra_file, "-O", output_dir, "--threads", str(threads)]

    if gzip:
        cmd.append("--gzip")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def check_tool_available(cmd: List[str]) -> bool:
    """Check if a command exists by running --version."""
    try:
        subprocess.run(cmd + ["--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def fetch_srr_list(accession: str) -> List[str]:
    """Fetch all SRR run accessions for a given BioProject or SRA Study accession."""
    logger.info(f"Fetching SRR list for accession: {accession}")

    esearch_params = {
        "db": "sra",
        "term": f"{accession}[Accession]",
        "retmax": 100000,
        "retmode": "json",
    }
    try:
        response = requests.get(ESEARCH_URL, params=esearch_params, timeout=30)
        response.raise_for_status()
        esearch_data = response.json()
        uid_list = esearch_data.get("esearchresult", {}).get("idlist", [])
        if not uid_list:
            raise RuntimeError(f"No SRA records found for accession: {accession}")
        logger.info(f"Found {len(uid_list)} SRA UIDs.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"ESearch request failed: {e}")

    uid_string = ",".join(uid_list)
    efetch_params = {
        "db": "sra",
        "id": uid_string,
        "rettype": "runinfo",
        "retmode": "text",
    }
    try:
        response = requests.get(EFETCH_URL, params=efetch_params, timeout=60)
        response.raise_for_status()
        csv_text = response.text
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"EFetch request failed: {e}")

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
        raise RuntimeError(f"Could not find 'Run' column in CSV header: {header}")

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
        raise RuntimeError(f"No SRR runs found for accession: {accession}")

    logger.info(f"Total SRR runs to process: {len(srr_list)}")
    return srr_list


def is_downloaded(srr: str, output_dir: str) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    sra_file = os.path.join(output_dir, f"{srr}.sra")
    sra_dir = os.path.join(output_dir, srr)
    return os.path.exists(sra_file) or os.path.isdir(sra_dir)


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
    cmd = build_prefetch_cmd(srr, output_dir, max_size, extra_args, prefetch_path, conda_env)
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
    cmd = build_fasterq_dump_cmd(sra_path, output_dir, threads, fasterq_dump_path, conda_env, gzip, extra_args)
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


def compress_fastq_file(
    fastq_path: str,
    compression_level: int,
    keep_fastq: bool,
) -> bool:
    """Compress a single FASTQ file using gzip with specified level."""
    gz_path = fastq_path + ".gz"
    logger.info(f"Compressing {fastq_path} -> {gz_path} (level {compression_level})")
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


# ----------------------------------------------------------------------
# State file handling
# ----------------------------------------------------------------------
def load_state(state_file: str) -> Dict[str, Any]:
    """Load state from JSON file."""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception:
            logger.warning(f"Could not read state file {state_file}, starting fresh.")
    return {}


def save_state(state_file: str, state: Dict[str, Any]) -> None:
    """Save state to JSON file atomically."""
    tmp_file = state_file + ".tmp"
    with open(tmp_file, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)


def update_state(
    state: Dict[str, Any],
    srr: str,
    key: str,
    value: bool = True,
) -> None:
    """Update state for a given SRR."""
    if srr not in state:
        state[srr] = {}
    state[srr][key] = value


def get_state(state: Dict[str, Any], srr: str, key: str, default: bool = False) -> bool:
    """Get state value for SRR and key."""
    return state.get(srr, {}).get(key, default)


# ----------------------------------------------------------------------
# Disk space check
# ----------------------------------------------------------------------
def check_disk_space(output_dir: str, min_gb: float) -> bool:
    """Check available disk space in output_dir."""
    if min_gb <= 0:
        return True
    try:
        total, used, free = shutil.disk_usage(output_dir)
        free_gb = free / (1024 ** 3)
        if free_gb < min_gb:
            logger.error(
                f"Insufficient disk space in {output_dir}: "
                f"available {free_gb:.1f} GB, required {min_gb:.1f} GB"
            )
            return False
        logger.info(f"Disk space check passed: {free_gb:.1f} GB available")
        return True
    except Exception as e:
        logger.warning(f"Could not check disk space: {e}")
        return True


# ----------------------------------------------------------------------
# Pipeline for a single SRR
# ----------------------------------------------------------------------
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

    # Dry run: print commands and return success
    if dry_run:
        logger.info(f"[DRY RUN] Processing {srr}:")
        if do_prefetch:
            cmd = build_prefetch_cmd(srr, output_dir, max_size, prefetch_extra, prefetch_path, conda_env)
            logger.info(f"  prefetch: {' '.join(cmd)}")
        if run_fastq:
            # In dry run we don't know the exact sra path; just print a placeholder
            sra_path = f"{output_dir}/{srr}.sra"
            cmd = build_fasterq_dump_cmd(sra_path, output_dir, threads, fasterq_dump_path, conda_env, gzip, fasterq_extra)
            logger.info(f"  fasterq-dump: {' '.join(cmd)}")
            if compression_level is not None:
                logger.info(f"  compress FASTQ with level {compression_level} (keep_fastq={keep_fastq})")
            if remove_sra:
                logger.info(f"  remove .sra after conversion")
        return True

    # If skip_existing and final output exists, skip entire run
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

    # Helper to safely update state and save with lock if provided
    def _save_state_with_lock():
        if lock:
            with lock:
                save_state(state_file, state)
        else:
            save_state(state_file, state)

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


# ----------------------------------------------------------------------
# Worker mode for array jobs
# ----------------------------------------------------------------------
def worker_mode(args):
    """Read manifest file and process only the SRRs assigned to this task."""
    manifest_path = args.manifest
    task_id = None
    if "SLURM_ARRAY_TASK_ID" in os.environ:
        task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])
    elif "PBS_ARRAYID" in os.environ:
        task_id = int(os.environ["PBS_ARRAYID"]) - 1
    else:
        logger.error("Worker mode requires SLURM_ARRAY_TASK_ID or PBS_ARRAYID environment variable.")
        sys.exit(1)

    logger.info(f"Worker mode: processing task ID {task_id}")

    srr_list = []
    with open(manifest_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            tid, srr = parts
            if int(tid) == task_id:
                srr_list.append(srr)

    if not srr_list:
        logger.info("No SRRs assigned to this task.")
        return

    # Use per-task state file to avoid cross-task race
    state_file = args.state_file if args.state_file else os.path.join(args.output_dir, f".state_{task_id}.json")
    state = load_state(state_file)
    logger.info(f"Assigned {len(srr_list)} SRRs: {', '.join(srr_list)}")
    success, fail = process_srr_list(srr_list, args, state, state_file)
    logger.info(f"Worker task {task_id} finished. Success={success}, Failed={fail}")
    if fail > 0:
        sys.exit(1)


# ----------------------------------------------------------------------
# Array job submission
# ----------------------------------------------------------------------
def create_manifest_and_script(args, srr_list, array_size):
    """Create manifest file and SLURM submission script for array job."""
    chunk_size = (len(srr_list) + array_size - 1) // array_size
    chunks = [srr_list[i:i+chunk_size] for i in range(0, len(srr_list), chunk_size)]

    manifest_path = os.path.join(args.output_dir, "srr_manifest.txt")
    with open(manifest_path, "w") as f:
        for idx, chunk in enumerate(chunks):
            for srr in chunk:
                f.write(f"{idx}\t{srr}\n")
    logger.info(f"Manifest written: {manifest_path}")

    script_path = os.path.join(args.output_dir, "submit_array_job.sh")
    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"#SBATCH --job-name={args.job_name}\n")
        f.write(f"#SBATCH --array=0-{array_size-1}\n")
        f.write(f"#SBATCH --partition={args.partition}\n")
        f.write(f"#SBATCH --qos={PARTITION_QOS_MAP.get(args.partition, 'normal')}\n")
        # Request enough CPUs for parallel_jobs * threads
        f.write(f"#SBATCH --cpus-per-task={args.parallel_jobs * args.threads}\n")
        f.write(f"#SBATCH --mem={args.mem}\n")
        f.write(f"#SBATCH --time={args.time}\n")
        f.write(f"#SBATCH --output={args.output_dir}/slurm_%A_%a.out\n")
        f.write(f"#SBATCH --error={args.output_dir}/slurm_%A_%a.err\n")
        f.write("\n")
        # Use per-task state file
        f.write(f"STATE_FILE=\"{args.output_dir}/.state_$SLURM_ARRAY_TASK_ID.json\"\n")
        f.write(f"python {os.path.abspath(__file__)} --worker --manifest {manifest_path} ")
        f.write(f"--output-dir {args.output_dir} ")
        f.write(f"--state-file \"$STATE_FILE\" ")
        if args.max_size:
            f.write(f"--max-size {args.max_size} ")
        if args.prefetch_path:
            f.write(f"--prefetch-path {args.prefetch_path} ")
        if args.conda_env:
            f.write(f"--conda-env {args.conda_env} ")
        if args.temp_dir:
            f.write(f"--temp-dir {args.temp_dir} ")
        if args.fasterq_dump:
            f.write("--fasterq-dump ")
        if args.fasterq_dump_path:
            f.write(f"--fasterq-dump-path {args.fasterq_dump_path} ")
        if args.no_gzip:
            f.write("--no-gzip ")
        if args.compression_level is not None:
            f.write(f"--compression-level {args.compression_level} ")
            if args.keep_fastq:
                f.write("--keep-fastq ")
        if args.remove_sra:
            f.write("--remove-sra ")
        if args.skip_existing:
            f.write("--skip-existing ")
        if args.prefetch:
            f.write("--prefetch ")
        if args.threads:
            f.write(f"--threads {args.threads} ")
        if args.parallel_jobs:
            f.write(f"--parallel-jobs {args.parallel_jobs} ")
        if args.min_disk_space:
            f.write(f"--min-disk-space {args.min_disk_space} ")
        if args.dry_run:
            f.write("--dry-run ")
        if args.prefetch_extra:
            f.write("--prefetch-extra " + " ".join(args.prefetch_extra) + " ")
        if args.fasterq_extra:
            f.write("--fasterq-extra " + " ".join(args.fasterq_extra) + " ")
        f.write("\n")
    os.chmod(script_path, 0o755)
    logger.info(f"Submission script written: {script_path}")

    return script_path


def submit_array_job(script_path):
    """Submit the SLURM job."""
    try:
        result = subprocess.run(["sbatch", script_path], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            logger.info(f"Array job submitted: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"Submission failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Error submitting: {e}")
        return False


# ----------------------------------------------------------------------
# Main argument parsing
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SRA retrieval and conversion (prefetch + fasterq-dump) for a BioProject/Study."
    )
    parser.add_argument("accession", help="BioProject (PRJ...) or SRA Study (SRP...) accession.")
    parser.add_argument("-o", "--output-dir", default=".", help="Directory for final FASTQ.")
    parser.add_argument("--temp-dir", help="Scratch directory for temporary files (sets TMPDIR).")
    parser.add_argument("--threads", type=int, default=1,
                        help="Number of threads per fasterq-dump conversion (default: 1).")
    parser.add_argument("--parallel-jobs", type=int, default=1,
                        help="Number of concurrent SRR conversions (default: 1).")
    parser.add_argument("--max-size", help="Maximum .sra file size to download (e.g., '20G').")
    parser.add_argument("--prefetch-path", help="Full path to prefetch executable.")
    parser.add_argument("--conda-env", help="Conda environment name containing SRA Toolkit.")
    parser.add_argument("--prefetch-extra", nargs=argparse.REMAINDER, help="Extra args for prefetch.")

    # Convenience option
    parser.add_argument("--sra-toolkit-bin", help="Directory containing both prefetch and fasterq-dump.")

    # Prefetch flag (disabled by default)
    parser.add_argument("--prefetch", dest="prefetch", action="store_true",
                        help="Enable prefetch download of .sra files (default: disabled).")

    # fasterq-dump options
    parser.add_argument("--fasterq-dump", action="store_true", help="Enable conversion to FASTQ with fasterq-dump.")
    parser.add_argument("--fasterq-dump-path", help="Full path to fasterq-dump executable.")
    parser.add_argument("--no-gzip", action="store_true", help="Disable gzip compression during fasterq-dump.")
    parser.add_argument("--compression-level", type=int, choices=range(1,10),
                        help="If set, produce uncompressed FASTQ then compress with this gzip level (1-9).")
    parser.add_argument("--keep-fastq", action="store_true",
                        help="Keep uncompressed FASTQ files after separate compression (only with --compression-level).")
    parser.add_argument("--fasterq-extra", nargs=argparse.REMAINDER, help="Extra args for fasterq-dump.")
    parser.add_argument("--remove-sra", action="store_true", help="Delete .sra file after successful conversion.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip SRRs that already have FASTQ output.")

    # HPC / array job options
    parser.add_argument("--scheduler", choices=["slurm", "pbs"], help="Submit as array job to the specified scheduler.")
    parser.add_argument("--array-size", type=int, default=10, help="Number of array tasks (default: 10).")
    parser.add_argument("--partition", choices=list(PARTITION_QOS_MAP.keys()), default="batch",
                        help="SLURM partition (default: batch).")
    parser.add_argument("--job-name", default="sra_retrieval", help="Job name.")
    parser.add_argument("--mem", default="16G", help="Memory per task (e.g., 16G).")
    parser.add_argument("--time", default="24:00:00", help="Wall time limit (HH:MM:SS).")

    # New options
    parser.add_argument("--min-disk-space", type=float, default=DEFAULT_MIN_DISK_GB,
                        help=f"Minimum free disk space in GB (default: {DEFAULT_MIN_DISK_GB}).")
    parser.add_argument("--state-file", help="Path to state file for resume support (default: <output_dir>/.sra_state.json).")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing.")

    # Worker mode (internal)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manifest", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve tool paths with priority: individual flags > --sra-toolkit-bin > inference
    # ------------------------------------------------------------------
    if args.sra_toolkit_bin:
        if not os.path.isdir(args.sra_toolkit_bin):
            logger.error(f"--sra-toolkit-bin directory does not exist: {args.sra_toolkit_bin}")
            sys.exit(1)
        if not args.prefetch_path:
            args.prefetch_path = os.path.join(args.sra_toolkit_bin, "prefetch")
        if args.fasterq_dump and not args.fasterq_dump_path:
            args.fasterq_dump_path = os.path.join(args.sra_toolkit_bin, "fasterq-dump")

    if args.fasterq_dump and not args.fasterq_dump_path and args.prefetch_path:
        dir_name = os.path.dirname(args.prefetch_path)
        args.fasterq_dump_path = os.path.join(dir_name, "fasterq-dump")
        if not os.path.exists(args.fasterq_dump_path):
            logger.warning(f"Inferred fasterq-dump path {args.fasterq_dump_path} does not exist. Please check.")
            args.fasterq_dump_path = None

    # Determine gzip flag
    if args.compression_level is not None:
        args.gzip = False
    else:
        args.gzip = args.fasterq_dump and not args.no_gzip

    # Set state file path if not provided
    if args.state_file is None:
        args.state_file = os.path.join(args.output_dir, ".sra_state.json")

    # Validate
    if args.prefetch_path and args.conda_env:
        logger.error("Provide either --prefetch-path or --conda-env, not both.")
        sys.exit(1)
    if args.fasterq_dump and not (args.prefetch_path or args.conda_env or args.fasterq_dump_path):
        logger.error("For --fasterq-dump, you must provide --prefetch-path, --conda-env, --sra-toolkit-bin, or --fasterq-dump-path.")
        sys.exit(1)
    if args.keep_fastq and args.compression_level is None:
        logger.error("--keep-fastq requires --compression-level.")
        sys.exit(1)
    if args.compression_level is not None and not args.fasterq_dump:
        logger.error("--compression-level requires --fasterq-dump to be enabled.")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "logs"), exist_ok=True)  # for log files
    if args.temp_dir:
        os.makedirs(args.temp_dir, exist_ok=True)

    # Disk space check (if not worker, worker will check again)
    if not args.worker:
        if not check_disk_space(args.output_dir, args.min_disk_space):
            sys.exit(1)

    # Worker mode: process manifest and exit
    if args.worker:
        if not check_disk_space(args.output_dir, args.min_disk_space):
            sys.exit(1)
        worker_mode(args)
        return

    # Check tools availability if not dry-run
    if not args.dry_run:
        if args.prefetch:
            prefetch_cmd = [args.prefetch_path] if args.prefetch_path else (
                ["conda", "run", "-n", args.conda_env, "prefetch"] if args.conda_env else ["prefetch"]
            )
            if not check_tool_available(prefetch_cmd):
                logger.error("prefetch not found. Use --prefetch-path, --sra-toolkit-bin, or --conda-env.")
                sys.exit(1)

        if args.fasterq_dump:
            fq_cmd = [args.fasterq_dump_path] if args.fasterq_dump_path else (
                ["conda", "run", "-n", args.conda_env, "fasterq-dump"] if args.conda_env else ["fasterq-dump"]
            )
            if not check_tool_available(fq_cmd):
                logger.error("fasterq-dump not found. Use --fasterq-dump-path, --sra-toolkit-bin, or --conda-env.")
                sys.exit(1)

    # Fetch SRR list
    try:
        srr_list = fetch_srr_list(args.accession)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    if not srr_list:
        logger.info("No SRRs to process.")
        return

    # If skip_existing and not scheduler, pre-filter
    if args.skip_existing and not args.scheduler:
        original_count = len(srr_list)
        filtered = []
        for srr in srr_list:
            fastq_base = os.path.join(args.output_dir, srr)
            if os.path.exists(f"{fastq_base}.fastq") or \
               os.path.exists(f"{fastq_base}_1.fastq") or \
               os.path.exists(f"{fastq_base}.fastq.gz") or \
               os.path.exists(f"{fastq_base}_1.fastq.gz"):
                continue
            filtered.append(srr)
        srr_list = filtered
        skipped = original_count - len(srr_list)
        if skipped:
            logger.info(f"Skipped {skipped} SRRs with existing FASTQ.")
        if not srr_list:
            logger.info("All SRRs already have FASTQ output. Nothing to do.")
            return

    # Decide execution mode
    if args.scheduler:
        if args.scheduler != "slurm":
            logger.error("Only SLURM scheduler is currently supported for array job submission.")
            sys.exit(1)
        if args.array_size < 1:
            logger.error("--array-size must be >= 1.")
            sys.exit(1)
        script_path = create_manifest_and_script(args, srr_list, args.array_size)
        submit_array_job(script_path)
    else:
        state = load_state(args.state_file)
        try:
            success, fail = process_srr_list(srr_list, args, state, args.state_file)
            logger.info(f"Finished processing. Success={success}, Failed={fail}")
            if fail > 0:
                sys.exit(1)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user. State saved for resume.")
            save_state(args.state_file, state)
            sys.exit(1)


if __name__ == "__main__":
    main()
