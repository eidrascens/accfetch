#!/bin/bash
#SBATCH --job-name=sra_all_studies
#SBATCH --time=24:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=8
#SBATCH --output=sra_all_%j.log
#SBATCH --partition=batch
#SBATCH --qos=batch_default

set -euo pipefail

# ---------- ENVIRONMENT ----------
source /home/gerryjr.ramos/miniforge3/etc/profile.d/conda.sh
conda activate sra_tools

echo "Python:       $(which python)"
echo "prefetch:     $(which prefetch)"
echo "fasterq-dump: $(which fasterq-dump)"
echo "pigz:         $(which pigz)"

cd /scratch1/gerryjr.ramos/rice_rnaSeq_meta_analysis

export PYTHONPATH="/scratch1/gerryjr.ramos/rice_rnaSeq_meta_analysis/src${PYTHONPATH:+:$PYTHONPATH}"
export TMPDIR="${SLURM_TMPDIR:-/scratch1/gerryjr.ramos/sra_temp_cache}"
mkdir -p "$TMPDIR"
echo "TMPDIR: $TMPDIR"

# ---------- STUDY SOURCE (priority: args > file > error) ----------
STUDIES=()

if [[ $# -gt 0 ]]; then
    # 1. Command-line arguments
    STUDIES=("$@")
    echo "Loaded ${#STUDIES[@]} studies from command line"
elif [[ -f "studies.txt" ]]; then
    # 2. Portable read from studies.txt (works on bash 3.0+)
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Strip leading/trailing whitespace
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        # Skip empty lines and comments
        [[ -z "$line" ]] && continue
        [[ "$line" == \#* ]] && continue
        STUDIES+=("$line")
    done < studies.txt
    echo "Loaded ${#STUDIES[@]} studies from studies.txt"
else
    echo "ERROR: No studies provided and studies.txt not found"
    exit 1
fi

# Validate we have at least one study
if [[ ${#STUDIES[@]} -eq 0 ]]; then
    echo "ERROR: No studies to process (empty study list)"
    exit 1
fi

# ---------- OUTPUT LAYOUT ----------
BASE_OUT=/scratch1/gerryjr.ramos/sra_by_project
mkdir -p "$BASE_OUT"

# ---------- MAIN LOOP ----------
FAILED_STUDIES=()

for ENTRY in "${STUDIES[@]}"; do
    STUDY="${ENTRY%%:*}"
    BIOPROJECT="${ENTRY##*:}"
    OUTDIR="$BASE_OUT/$BIOPROJECT"
    mkdir -p "$OUTDIR"

    echo ""
    echo "=================================================================="
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing $STUDY ($BIOPROJECT)"
    echo "  Output: $OUTDIR"
    echo "=================================================================="

    if python src/cli/cli.py "$STUDY" \
        --prefetch \
        --fasterq-dump \
        --sra-toolkit-bin /home/gerryjr.ramos/miniforge3/envs/sra_tools/bin \
        --output-dir "$OUTDIR" \
        --temp-dir "$TMPDIR" \
        --threads 8 \
        --parallel-jobs 2 \
        --remove-sra \
        --skip-existing
    then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [OK] $STUDY completed"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FAIL] $STUDY failed"
        FAILED_STUDIES+=("$STUDY")
    fi
done

# ---------- SUMMARY ----------
echo ""
echo "=================================================================="
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch complete."
TOTAL=${#STUDIES[@]}
FAILED=${#FAILED_STUDIES[@]}
SUCCEEDED=$((TOTAL - FAILED))
echo "Successful: $SUCCEEDED/$TOTAL"
if [[ $FAILED -gt 0 ]]; then
    echo "Failed studies:"
    for s in "${FAILED_STUDIES[@]}"; do
        echo "  - $s"
    done
fi
echo "=================================================================="
