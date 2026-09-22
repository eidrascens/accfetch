from pathlib import Path
from os.path import exists, isdir

from os import remove

from src.utils.log.logger import Logger


def is_downloaded(srr: str, output_dir: Path) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    return exists(
            output_dir / f"{srr}.sra"
        ) or isdir(
            output_dir / srr
        ) or (
            exists(
                output_dir / f"{srr}_1.fastq.gz"
            ) and exists(
                output_dir / f"{srr}_2.fastq.gz"
            )
        ) or exists(output_dir / f"{srr}.fastq.gz")

def remove_file(log: Logger, file_path: Path) -> None:
    if not exists(file_path):
        log.info(
            "%s does not exist." % ( file_path )
        )
        return

    try:
        remove(file_path)
    except (
        FileNotFoundError,
        OSError,
        PermissionError,
        SystemError
    ) as err:
        log.err(
            err, "Cannot remove %s" % ( file_path )
        )


def check_tool_available(cmd):
    """
    Check if a command is available in the system.
    Returns True if the command exists, False otherwise.
    """
    import shutil
    if isinstance(cmd, list):
        cmd = cmd[0]
    return shutil.which(cmd) is not None


def fetch_srr_list(accession):
    """
    Fetch list of runs accessions for a given study or project.
    Supports NCBI SRA (PRJNA/SRP/SRR), DDBJ (PRJDB/DRP/DRR),
    and ENA (PRJEB/ERP/ERR) accessions.
    """
    import subprocess

    if accession.startswith("PRJ"):
        # Covers PRJNA (NCBI), PRJDB (DDBJ), PRJEB (ENA)
        query = f"{accession}[BioProject]"
    elif accession.startswith(("SRP", "DRP", "ERP")):
        # SRA Study / DDBJ Study / ENA Study
        query = f"{accession}[SRA Study]"
    elif accession.startswith(("SRR", "DRR", "ERR")):
        # Direct run accession — bypass list fetching entirely
        return [accession]
    else:
        query = accession

    try:
        cmd = f"esearch -db sra -query '{query}' | efetch -format runinfo | cut -d',' -f1 | tail -n +2"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to fetch SRR list for {accession}")

        # Accept NCBI (SRR), DDBJ (DRR), and ENA (ERR) run prefixes
        srr_list = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip().startswith(("SRR", "DRR", "ERR"))
        ]
        return srr_list

    except Exception as e:
        raise RuntimeError(f"Error fetching SRR list for {accession}: {e}")
