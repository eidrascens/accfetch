from pathlib import Path
from os.path import exists, isdir
from os import remove, mkdir
from shutil import which
from subprocess import run

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
        ) or exists(
            output_dir / f"{srr}.fastq.gz"
        )


def remove_file(log: Logger, file_path: Path) -> None:
    try:
        remove(file_path)
    except FileNotFoundError as _:
        log.info("%s does not exist." % ( file_path ))
    except (
        OSError,
        PermissionError,
        SystemError
    ) as err_:
        log.err_(
            "Cannot remove %s" % ( file_path ), err_
        )


def check_tool_available(cmd):
    """Check if a command is available in the system.

    Returns True if the command exists, False otherwise.
    """
    if isinstance(cmd, list):
        cmd = cmd[0]
    return which(cmd) is not None


def fetch_srr_list(accession):
    """
    Fetch list of runs accessions for a given study or project.
    Supports NCBI SRA (PRJNA/SRP/SRR), DDBJ (PRJDB/DRP/DRR),
    and ENA (PRJEB/ERP/ERR) accessions.
    """

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
        cmd: list[str] = [
                "esearch",
                "-db sra",
                f"-query '{query}'",
                "|",
                "efetch",
                "-format runinfo",
                "|",
                "cut",
                "-d ','",
                "-f1",
                "|",
                "tail",
                "-n",
                "+2"
            ]
        result = run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to fetch SRR list for {accession}"
            )

        # Accept NCBI (SRR), DDBJ (DRR), and ENA (ERR) run prefixes
        srr_list = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip().startswith(
                    ("SRR", "DRR", "ERR")
                )
            ]
        return srr_list

    except Exception as err_:
        raise RuntimeError from err_


def check_dir(log_: Logger, path_arr: list[Path]) -> list[Path]:
    """_summary_

    Args:
        path_arr (list[Path]): String list of DIR to check.
        log_ (Logger): Logger() instance.

    Returns:
        list[Path] | None: String list of missing dir.
    """

    missing_path: list[Path] = []
    for dir_ in path_arr:
        if isdir(dir_):
            log_.info(
                "Skipping: %s, path exists ..." % ( dir_ )
            )
            continue
        log_.info(
            "%s is missing, include to the list ..." % ( dir_ )
        )
        missing_path.append(Path(dir_))

    return missing_path


def fix_dir(log_: Logger, path_arr: list[Path]) -> None:
    """Create the missing directories returned by check_dir().

    Args:
        path_arr (list[str]): String list of DIR to create.
        log_ (Logger): Logger() instance.
    """

    missing_path: list[Path] = check_dir(log_, path_arr)
    if not missing_path:
        return None

    created_dir: list[Path] = []
    for dir_ in missing_path:
        try:
            log_.info(
                "Trying to create dir: %s" % ( dir_ )
            )
            mkdir(dir_)
        except OSError as err_:
            log_.crit(
                "Cannot create DIR: %s" % ( dir_ ), err_
            )
        else:
            created_dir.append(Path(dir_))

    failed_dir: list[Path] = list(
            set(missing_path) ^ set(created_dir)
        )
    if failed_dir:
        log_.info(
            "Unable to create the ff. DIR: %s." % (
                failed_dir
            )
        )
