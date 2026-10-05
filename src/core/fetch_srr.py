from typing import Any

from requests import exceptions, get

from src.utils.log.custom_logger import Logger


def fetch_srr_list(
        log_: Logger,
        conf: dict[str, Any],
        accession: str
    ) -> list[str]:
    """Fetch all SRR run accessions for a given BioProject or SRA Study accession."""
    log_.info(
        "Fetching SRR list for accession: %s" % ( accession )
    )

    ESEARCH_URL = conf["SYSTEM"]["ESEARCH_URL"]
    ESEARCH_PARAMS = conf["SYSTEM"]["ESEARCH_PARAMS"]
    ESEARCH_PARAMS["term"] = f"{accession}[Accession]"

    try:
        response = get(
                ESEARCH_URL,
                params=ESEARCH_PARAMS,
                timeout=30
            )
        response.raise_for_status()
        esearch_data = response.json()
        uid_list = esearch_data.get(
                "esearchresult", {}
            ).get(
                "idlist", []
            )
        if not uid_list:
            log_.warn(
                "No SRA records found for %s" % ( accession )
            )
        log_.info("Found %d SRA UIDs." % ( len(uid_list) ))
    except exceptions.RequestException as err_:
        log_.warn(
            "ESearch request failed for %s" % (
                accession
            ), err_
        )

    EFETCH_URL = conf["SYSTEM"]["EFETCH_URL"]
    EFETCH_PARAMS = conf["SYSTEM"]["EFETCH_PARAMS"]
    EFETCH_PARAMS["id"] = ",".join(uid_list)

    try:
        response = get(
                EFETCH_URL,
                params=EFETCH_PARAMS,
                timeout=60
            )
        response.raise_for_status()
        csv_text = response.text
    except exceptions.RequestException as err_:
        log_.warn(
            "EFetch request failed for %s" % (
                accession
            ), err_
        )
    lines = csv_text.strip().splitlines()
    if len(lines) < 2:
        log_.warn("Runinfo CSV is empty or malformed.")
        return []

    header = lines[0].split(",")
    run_col_index = None
    for alt in ["Run", "run_accession", "RunAccession"]:
        if alt in header:
            run_col_index = header.index(alt)
            break
    if run_col_index is None:
        log_.warn(
            "Could not find 'Run' column in %s" % ( header )
        )
        return []

    srr_list = []
    for line in lines[1:]:
        if line.strip():
            fields = line.split(",")
            if run_col_index < len(fields):
                run_acc = fields[run_col_index].strip()
                if run_acc.startswith("SRR"):
                    srr_list.append(run_acc)

    srr_list = list(dict.fromkeys(srr_list))
    if not srr_list:
        log_.warn(
            "No SRR runs found for %s" % ( accession )
        )
        return []

    log_.info(
        "SRR to process: %s %d" % ( srr_list, len(srr_list) )
    )
    return srr_list

# def fetch_srr_list(accession):
#     """
#     Fetch list of runs accessions for a given study or project.
#     Supports NCBI SRA (PRJNA/SRP/SRR), DDBJ (PRJDB/DRP/DRR),
#     and ENA (PRJEB/ERP/ERR) accessions.
#     """
#
#     if accession.startswith("PRJ"):
#         # Covers PRJNA (NCBI), PRJDB (DDBJ), PRJEB (ENA)
#         query = f"{accession}[BioProject]"
#     elif accession.startswith(("SRP", "DRP", "ERP")):
#         # SRA Study / DDBJ Study / ENA Study
#         query = f"{accession}[SRA Study]"
#     elif accession.startswith(("SRR", "DRR", "ERR")):
#         # Direct run accession — bypass list fetching entirely
#         return [accession]
#     else:
#         query = accession
#
#     try:
#         cmd: list[str] = [
#                 "esearch",
#                 "-db sra",
#                 f"-query '{query}'",
#                 "|",
#                 "efetch",
#                 "-format runinfo",
#                 "|",
#                 "cut",
#                 "-d ','",
#                 "-f1",
#                 "|",
#                 "tail",
#                 "-n",
#                 "+2"
#             ]
#         result = run(
#                 cmd,
#                 shell=True,
#                 capture_output=True,
#                 text=True
#             )
#
#         if result.returncode != 0:
#             raise RuntimeError(
#                 f"Failed to fetch SRR list for {accession}"
#             )
#
#         # Accept NCBI (SRR), DDBJ (DRR), and ENA (ERR) run prefixes
#         srr_list = [
#                 line.strip()
#                 for line in result.stdout.splitlines()
#                 if line.strip().startswith(
#                     ("SRR", "DRR", "ERR")
#                 )
#             ]
#         return srr_list
#
#     except (CalledProcessError, RuntimeError) as err_:
#         raise RuntimeError from err_
