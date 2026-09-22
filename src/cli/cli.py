"""
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

import sys
import os
import argparse
from pathlib import Path

# Add ALL of these missing imports - all from utils
from src.utils.system_req import check_disk_space
from src.utils.log.logger import Logger
from src.utils.housekeeping import check_tool_available, fetch_srr_list
from src.utils.state import load_state, save_state
from src.utils.commands import (
    create_manifest_and_script,
    submit_array_job,
    process_srr_list,
    worker_mode   # <-- ADD THIS LINE
)

log: Logger = Logger(Path().home(), "sra_retrieval.log")

# Define missing constants
PARTITION_QOS_MAP = {
    "batch": "batch",
    "debug": "debug",
    "serial": "serial",
    "gpu": "gpu",
    "gpu_a100": "gpu_a100"
}
DEFAULT_MIN_DISK_GB = 10.0   # default free disk space check threshold

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
        log.err(f"--sra-toolkit-bin directory does not exist: {args.sra_toolkit_bin}")
        raise SystemExit
    if not args.prefetch_path:
        args.prefetch_path = os.path.join(args.sra_toolkit_bin, "prefetch")
    if args.fasterq_dump and not args.fasterq_dump_path:
        args.fasterq_dump_path = os.path.join(args.sra_toolkit_bin, "fasterq-dump")

if args.fasterq_dump and not args.fasterq_dump_path and args.prefetch_path:
    dir_name = os.path.dirname(args.prefetch_path)
    args.fasterq_dump_path = os.path.join(dir_name, "fasterq-dump")
    if not os.path.exists(args.fasterq_dump_path):
        log.warn(f"Inferred fasterq-dump path {args.fasterq_dump_path} does not exist. Please check.")
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
    log.err("Provide either --prefetch-path or --conda-env, not both.")
    raise SystemExit
if args.fasterq_dump and not (args.prefetch_path or args.conda_env or args.fasterq_dump_path):
    log.err("For --fasterq-dump, you must provide --prefetch-path, --conda-env, --sra-toolkit-bin, or --fasterq-dump-path.")
    raise SystemExit
if args.keep_fastq and args.compression_level is None:
    log.err("--keep-fastq requires --compression-level.")
    raise SystemExit
if args.compression_level is not None and not args.fasterq_dump:
    log.err("--compression-level requires --fasterq-dump to be enabled.")
    raise SystemExit

# Create output directory
os.makedirs(args.output_dir, exist_ok=True)
os.makedirs(os.path.join(args.output_dir, "logs"), exist_ok=True)  # for log files
if args.temp_dir:
    os.makedirs(args.temp_dir, exist_ok=True)

# Disk space check (if not worker, worker will check again)
if not args.worker:
    if not check_disk_space(log, args.output_dir, args.min_disk_space):
        raise SystemExit

# Worker mode: process manifest and exit
if args.worker:
    if not check_disk_space(log, args.output_dir, args.min_disk_space):
        raise SystemExit
    worker_mode(args)
    sys.exit(0)

# Check tools availability if not dry-run
if not args.dry_run:
    if args.prefetch:
        prefetch_cmd = [args.prefetch_path] if args.prefetch_path else (
            ["conda", "run", "-n", args.conda_env, "prefetch"] if args.conda_env else ["prefetch"]
        )
        if not check_tool_available(prefetch_cmd):
            log.err("prefetch not found. Use --prefetch-path, --sra-toolkit-bin, or --conda-env.")
            raise SystemExit

    if args.fasterq_dump:
        fq_cmd = [args.fasterq_dump_path] if args.fasterq_dump_path else (
            ["conda", "run", "-n", args.conda_env, "fasterq-dump"] if args.conda_env else ["fasterq-dump"]
        )
        if not check_tool_available(fq_cmd):
            log.err("fasterq-dump not found. Use --fasterq-dump-path, --sra-toolkit-bin, or --conda-env.")
            raise SystemExit

# Fetch SRR list
try:
    srr_list = fetch_srr_list(args.accession)
except RuntimeError as err:
    log.err(err)
    raise SystemExit from err

if not srr_list:
    log.info("No SRRs to process.")
    sys.exit(0)

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
        log.info(f"Skipped {skipped} SRRs with existing FASTQ.")
    if not srr_list:
        log.info("All SRRs already have FASTQ output. Nothing to do.")
        sys.exit(0)

# Decide execution mode
if args.scheduler:
    if args.scheduler != "slurm":
        log.err("Only SLURM scheduler is currently supported for array job submission.")
        raise SystemExit
    if args.array_size < 1:
        log.err("--array-size must be >= 1.")
        raise SystemExit
    script_path = create_manifest_and_script(args, srr_list, args.array_size)
    submit_array_job(script_path)
else:
    state = load_state(args.state_file)
    try:
        success, fail = process_srr_list(srr_list, args, state, args.state_file)
        log.info(f"Finished processing. Success={success}, Failed={fail}")
        if fail > 0:
            raise SystemExit
    except KeyboardInterrupt:
        log.warn("Interrupted by user. State saved for resume.")
        save_state(args.state_file, state)
        raise SystemExit
    