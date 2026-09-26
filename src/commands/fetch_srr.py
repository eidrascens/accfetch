from requests import get, exceptions

from src.utils.log.logger import Logger


def fetch_srr_list(log_: Logger, conf, accession: str) -> list[str]:
    """Fetch all SRR run accessions for a given BioProject or SRA Study accession."""
    log_.info(
        "Fetching SRR list for accession: %s" % ( accession )
    )

    ESEARCH_URL = conf["programs"]["ESEARCH_URL"]
    EFETCH_URL = conf["programs"]["EFETCH_URL"]
    ESEARCH_PARAMS = conf["programs"]["ESEARCH_PARAMS"]
    EFETCH_PARAMS = conf["programs"]["EFETCH_PARAMS"]

    try:
        response = get(
                ESEARCH_URL,
                params=ESEARCH_PARAMS,
                timeout=30
            )
        response.raise_for_status()
        esearch_data = response.json()
        uid_list = esearch_data.get(
                "esearchresult", {}).get("idlist", []
            )
        if not uid_list:
            raise RuntimeError(
        log_.info("Found %s SRA UIDs." % ( len(uid_list) ))
    except exceptions.RequestException as err_:
        raise RuntimeError(
                f"ESearch request failed: {err_}"
            ) from err_

    uid_string = ",".join(uid_list)

    try:
        response = get(
                EFETCH_URL,
                params=EFETCH_PARAMS,
                timeout=60
            )
        response.raise_for_status()
        csv_text = response.text
    except exceptions.RequestException as err_:
        raise RuntimeError(
                f"EFetch request failed: {e}"
            ) from err_

    lines = csv_text.strip().splitlines()
    if len(lines) < 2:
        raise RuntimeError("Runinfo CSV is empty or malformed.")

    header = lines[0].split(",")
    run_col_index = None
    for alt in ["Run", "run_accession", "RunAccession"]:
        if alt in header:
            run_col_index = header.index(alt)
            break
    if run_col_index is None:
        raise RuntimeError(
            f"Could not find 'Run' column in CSV header: {header}")

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
        raise RuntimeError(f"No SRR runs found for accession: {accession}")

    log_.info(f"Total SRR runs to process: {len(srr_list)}")
    return srr_list
