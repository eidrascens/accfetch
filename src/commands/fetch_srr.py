def fetch_srr_list(accession: str) -> List[str]:
    """Fetch all SRR run accessions for a given BioProject or SRA Study accession."""
    logger.info(f"Fetching SRR list for accession: {accession}")

    esearch_params = {
        "db": "sra",
        "term": f"{accession}[Accession]",
        "retmax": 100000,
        "retmode": "json",
    }
    try:
        response = requests.get(ESEARCH_URL, params=esearch_params, timeout=30)
        response.raise_for_status()
        esearch_data = response.json()
        uid_list = esearch_data.get("esearchresult", {}).get("idlist", [])
        if not uid_list:
            raise RuntimeError(
                f"No SRA records found for accession: {accession}")
        logger.info(f"Found {len(uid_list)} SRA UIDs.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"ESearch request failed: {e}")

    uid_string = ",".join(uid_list)
    efetch_params = {
        "db": "sra",
        "id": uid_string,
        "rettype": "runinfo",
        "retmode": "text",
    }
    try:
        response = requests.get(EFETCH_URL, params=efetch_params, timeout=60)
        response.raise_for_status()
        csv_text = response.text
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"EFetch request failed: {e}")

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

    logger.info(f"Total SRR runs to process: {len(srr_list)}")
    return srr_list
