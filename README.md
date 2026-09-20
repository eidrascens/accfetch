# SRA Retrieval Pipeline

A Python pipeline for downloading sequencing runs from NCBI SRA, DDBJ, and ENA, converting them to compressed FASTQ for downstream meta-analysis of genomic and transcriptomic data. Designed for batch processing of multiple studies on HPC clusters.

---

## Features

- Fetches runs from a Study or BioProject accession
- Downloads `.sra` via `prefetch`
- Converts to FASTQ via `fasterq-dump`
- Compresses via `pigz`
- Cleans up `.sra` and empty subdirectories
- Supports NCBI SRA, DDBJ, and ENA accessions

| Source | Project | Study | Run |
| :--- | :--- | :--- | :--- |
| NCBI SRA | `PRJNA...` | `SRP...` | `SRR...` |
| DDBJ | `PRJDB...` | `DRP...` | `DRR...` |
| ENA | `PRJEB...` | `ERP...` | `ERR...` |

---

## Design Choices

A few deliberate choices shape how this pipeline behaves:

- **Per-project output layout.** FASTQ files are organized under a
  folder named after each BioProject. This keeps runs from different
  studies separated, which is helpful when assembling a
  multi-project meta-analysis.

- **Batch-driven configuration.** A single `studies.txt` file lists
  the studies to process. Adding or removing a study requires no code
  changes.

- **Resume-safe.** Interrupted jobs can be resubmitted safely.
  Completed runs are detected and skipped, so no work is repeated.

- **HPC-native scratch handling.** Temporary files produced during
  FASTQ conversion are directed to a scratch directory rather than
  the project folder or `$HOME`, keeping quota usage low.

- **Lightweight dependencies.** The pipeline relies only on standard
  Python, SRA Toolkit, `pigz`, and `entrez-direct`. There is no
  workflow engine or container runtime to install or maintain.

- **External compression.** Compression is performed as a separate
  post-conversion step, which also allows alternative compressors
  to be swapped in if needed.

- **Graceful failure.** If one study fails during a batch, the loop
  logs the failure and continues to the next study, so a single
  problematic accession does not halt the whole run.

---

## Requirements

- Python 3.9+
- SRA Toolkit 3.x (`prefetch`, `fasterq-dump`)
- `pigz`
- `entrez-direct` (`esearch`, `efetch`)
- `rich`

### Install

```bash
mamba create -n sra_tools python=3.9 -y
conda activate sra_tools
mamba install -c bioconda sra-tools entrez-direct -y
mamba install -c conda-forge pigz -y
pip install rich
```

---

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

---

## Usage

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

---

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

---

## CLI Options

| Flag | Description |
| :--- | :--- |
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

---

## Environment Variables

**Note:** The SLURM scripts set `PYTHONPATH` and `TMPDIR` automatically.
When running interactively, export them first:

```bash
export PYTHONPATH="$PWD/src:$PYTHONPATH"
export TMPDIR=/scratch1/$USER/sra_temp_cache
```

---

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

---

## Cleanup After Cancelled Job

```bash
# Remove temp files from fasterq-dump after a mid-conversion kill
rm -rf fasterq.tmp.*

# Clear fasterq-dump scratch (only when no jobs are running)
rm -rf /scratch1/$USER/sra_temp_cache/*

# Remove empty subdirs left behind by a cancelled job
find /scratch1/$USER/sra_by_project -mindepth 2 -maxdepth 2 -type d -empty -delete
```

---

## References

- [SRA Toolkit Wiki](https://github.com/ncbi/sra-tools/wiki)
- [fasterq-dump Guide](https://github.com/ncbi/sra-tools/wiki/HowTo:-fasterq-dump)
- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [SLURM Documentation](https://slurm.schedmd.com/documentation.html)

---

## Contributors

Developed and maintained jointly by `eidrascens` and `gerryjr.ramos`.

---

## Acknowledgments

Testing and validation were performed on the **saliksik HPC cluster**
operated by the **Advanced Science and Technology Institute (ASTI)**,
Department of Science and Technology (DOST), Philippines.