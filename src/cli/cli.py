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
