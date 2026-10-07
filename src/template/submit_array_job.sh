#!/usr/bin/env bash

#SBATCH --job-name=<args.job_name>
#SBATCH --array=0-<array_size-1>
#SBATCH --partition=<args.partition>
#SBATCH --qos=<PARTITION_QOS_MAP.get(args.partition, 'normal')>
# Request enough CPUs for parallel_jobs * threads
#SBATCH --cpus-per-task=<args.parallel_jobs * args.threads>
#SBATCH --mem=<args.mem>
#SBATCH --time=<args.time>
#SBATCH --output=<args.output_dir>/slurm_%A_%a.out
#SBATCH --error=<args.output_dir>/slurm_%A_%a.err
# Use per-task state file
STATE_FILE="<args.output_dir>/.state_$SLURM_ARRAY_TASK_ID.json"
python <MODULE_PATH> --worker --manifest <manifest_path>    \
    --output-dir <args.output_dir>                          \
    --state-file "$STATE_FILE"
if args.max_size:
    --max-size <args.max_size>
if args.prefetch_path:
    --prefetch-path <args.prefetch_path>
if args.conda_env:
    --conda-env <args.conda_env>
if args.temp_dir:
    --temp-dir <args.temp_dir>
if args.fasterq_dump:
    --fasterq-dump
if args.fasterq_dump_path:
    --fasterq-dump-path <args.fasterq_dump_path>
if args.no_gzip:
    --no-gzip
if args.compression_level is not None:
    --compression-level <args.compression_level>
    if args.keep_fastq:
        --keep-fastq
if args.remove_sra:
    --remove-sra
if args.skip_existing:
    --skip-existing
if args.prefetch:
    --prefetch
if args.threads:
    --threads <args.threads>
if args.parallel_jobs:
    --parallel-jobs <args.parallel_jobs>
if args.min_disk_space:
    --min-disk-space <args.min_disk_space>
if args.dry_run:
    --dry-run
if args.prefetch_extra:
    --prefetch-extra " + " ".join(args.prefetch_extra) + "
if args.fasterq_extra:
    --fasterq-extra " + " ".join(args.fasterq_extra) + "

