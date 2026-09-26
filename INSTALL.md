## Requirements

- Python 3.10+
- SRA Toolkit 3.x (`prefetch`, `fasterq-dump`)
- `pigz`
- `entrez-direct` (`esearch`, `efetch`)
- `rich`

### Install

```bash
mamba create -n sra_tools python=3.10 -y
conda activate sra_tools
mamba install -c bioconda sra-tools entrez-direct -y
mamba install -c conda-forge pigz -y
pip install rich
```
