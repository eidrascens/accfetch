from pathlib import Path
from os.path import exists, isdir
from os import remove, mkdir
from subprocess import run

from src.utils.log.logger import Logger


def is_downloaded(srr: str, OUT_DIR: Path) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    return exists(
            OUT_DIR / f"{srr}.sra"
        ) or isdir(
            OUT_DIR / srr
        ) or (
            exists(
                OUT_DIR / f"{srr}_1.fastq.gz"
            ) and exists(
                OUT_DIR / f"{srr}_2.fastq.gz"
            )
        ) or exists(
            OUT_DIR / f"{srr}.fastq.gz"
        )


def remove_file(log: Logger, FILE_PATH: Path) -> None:
    try:
        remove(FILE_PATH)
    except FileNotFoundError as _:
        log.info("%s does not exist." % ( FILE_PATH ))
    except (
        OSError,
        PermissionError,
        SystemError
    ) as err_:
        log.err_(
            "Cannot remove %s" % ( FILE_PATH ), err_
        )


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


def check_dir(log_: Logger, PATH_ARR: list[Path]) -> list[Path]:
    """_summary_

    Args:
        PATH_ARR (list[Path]): String list of DIR to check.
        log_ (Logger): Logger() instance.

    Returns:
        list[Path] | None: String list of missing dir.
    """

    MISSING_PATHS: list[Path] = []
    for dir_ in PATH_ARR:
        if isdir(dir_):
            log_.info(
                "Skipping: %s, path exists ..." % ( dir_ )
            )
            continue
        log_.info(
            "%s is missing, include to the list ..." % ( dir_ )
        )
        MISSING_PATHS.append(Path(dir_))

    return MISSING_PATHS


def fix_dir(log_: Logger, PATH_ARR: list[Path]) -> None:
    """Create the missing directories returned by check_dir().

    Args:
        PATH_ARR (list[str]): String list of DIR to create.
        log_ (Logger): Logger() instance.
    """

    MISSING_PATHS: list[Path] = check_dir(log_, PATH_ARR)
    if not MISSING_PATHS:
        return None

    created_dir_: list[Path] = []
    for dir_ in MISSING_PATHS:
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
            created_dir_.append(Path(dir_))

    failed_dir_: list[Path] = list(
            set(MISSING_PATHS) ^ set(created_dir_)
        )
    if failed_dir_:
        log_.info(
            "Unable to create the ff. DIR: %s." % (
                failed_dir_
            )
        )
