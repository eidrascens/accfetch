## Quick Start

```bash
# 1. Clone and activate
git clone git@github.com:<user>/rice_rnaSeq_meta_analysis.git
cd rice_rnaSeq_meta_analysis
git checkout devel
conda activate sra_tools

# 2. Configure paths
export PROJECT_ROOT="/scratch1/$USER/rice_rnaSeq_meta_analysis"
export OUTPUT_BASE="/scratch1/$USER/sra_by_project"
export TEMP_BASE="/scratch1/$USER/sra_temp_cache"
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
export TMPDIR="$TEMP_BASE"
mkdir -p "$OUTPUT_BASE" "$TEMP_BASE"

# 3. Define studies (one per line: STUDY:BIOPROJECT)
cat > studies.txt << 'EOF'
DRP014210:PRJDB28498
SRP453361:PRJNA1002258
SRP503661:PRJNA1103873
SRP293811:PRJNA680441
EOF

# 4. Submit the batch
sbatch run_all_studies.slurm
squeue -u $USER
tail -f sra_all_*.log
```

### Test a Single Accession

```bash
python src/cli/cli.py SRR292241 \
    --prefetch --fasterq-dump \
    --sra-toolkit-bin $(dirname $(which prefetch)) \
    --output-dir "$OUTPUT_BASE/test" \
    --temp-dir "$TMPDIR" \
    --threads 4 --remove-sra
```

### Run All Studies in `studies.txt`

```bash
sbatch run_all_studies.slurm
```

### Run a Single Study

```bash
sbatch run_all_studies.slurm SRP453361:PRJNA1002258
```

### Resume After Cancellation

Just resubmit — completed runs are skipped:

```bash
sbatch run_all_studies.slurm
```

## Output Layout

```
/scratch1/$USER/sra_by_project/
├── PRJDB28498/
│   ├── DRR730469_1.fastq.gz
│   ├── DRR730469_2.fastq.gz
│   └── ...
├── PRJNA1002258/
├── PRJNA1103873/
└── PRJNA680441/
```

Each completed run produces:

- **Paired-end:** `<SRR>_1.fastq.gz` + `<SRR>_2.fastq.gz`
- **Single-end:** `<SRR>.fastq.gz`

## CLI Options

| Flag | Description |
| | |
| `<accession>` | Study / BioProject / Run (required) |
| `--prefetch` | Download `.sra` |
| `--fasterq-dump` | Convert to FASTQ |
| `--sra-toolkit-bin <dir>` | Directory with both tools |
| `--output-dir <dir>` | Final FASTQ location |
| `--temp-dir <dir>` | Scratch for temp files |
| `--threads <n>` | Threads per conversion |
| `--parallel-jobs <n>` | Simultaneous conversions |
| `--remove-sra` | Delete `.sra` after conversion |
| `--skip-existing` | Skip runs with existing output |
| `--dry-run` | Print commands only |

## Environment Variables

**Note:** The SLURM scripts set `PYTHONPATH` and `TMPDIR` automatically.
When running interactively, export them first:

```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"
export TMPDIR=/scratch1/$USER/sra_temp_cache
```

## Monitoring

```bash
# Job status
squeue -u $USER

# Live log
tail -f sra_all_*.log

# Progress per project
cd /scratch1/$USER/sra_by_project
for d in */; do
    echo "$(basename $d): $(ls $d/*_1.fastq.gz 2>/dev/null | wc -l) runs"
done
```

## Cleanup After Cancelled Job

```bash
# Remove temp files from fasterq-dump after a mid-conversion kill
rm -rf fasterq.tmp.*

# Clear fasterq-dump scratch (only when no jobs are running)
rm -rf /scratch1/$USER/sra_temp_cache/*

# Remove empty subdirs left behind by a cancelled job
find /scratch1/$USER/sra_by_project -mindepth 2 -maxdepth 2 -type d -empty -delete
```
