# ----------------------------------------------------------------------
# Worker mode for array jobs
# ----------------------------------------------------------------------
def worker_mode(args):
    """Read manifest file and process only the SRRs assigned to this task."""
    manifest_path = args.manifest
    task_id = None
    if "SLURM_ARRAY_TASK_ID" in os.environ:
        task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])
    elif "PBS_ARRAYID" in os.environ:
        task_id = int(os.environ["PBS_ARRAYID"]) - 1
    else:
        logger.error(
            "Worker mode requires SLURM_ARRAY_TASK_ID or PBS_ARRAYID environment variable.")
        sys.exit(1)

    logger.info(f"Worker mode: processing task ID {task_id}")

    srr_list = []
    with open(manifest_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            tid, srr = parts
            if int(tid) == task_id:
                srr_list.append(srr)

    if not srr_list:
        logger.info("No SRRs assigned to this task.")
        return

    # Use per-task state file to avoid cross-task race
    state_file = args.state_file if args.state_file else os.path.join(
        args.output_dir, f".state_{task_id}.json")
    state = load_state(state_file)
    logger.info(f"Assigned {len(srr_list)} SRRs: {', '.join(srr_list)}")
    success, fail = process_srr_list(srr_list, args, state, state_file)
    logger.info(
        f"Worker task {task_id} finished. Success={success}, Failed={fail}")
    if fail > 0:
        sys.exit(1)


# ----------------------------------------------------------------------
# Array job submission
# ----------------------------------------------------------------------
def create_manifest_and_script(args, srr_list, array_size):
    """Create manifest file and SLURM submission script for array job."""
    chunk_size = (len(srr_list) + array_size - 1) // array_size
    chunks = [srr_list[i:i+chunk_size]
              for i in range(0, len(srr_list), chunk_size)]

    manifest_path = os.path.join(args.output_dir, "srr_manifest.txt")
    with open(manifest_path, "w") as f:
        for idx, chunk in enumerate(chunks):
            for srr in chunk:
                f.write(f"{idx}\t{srr}\n")
    logger.info(f"Manifest written: {manifest_path}")

    script_path = os.path.join(args.output_dir, "submit_array_job.sh")
    with open(script_path, "w") as f:
        ...
    os.chmod(script_path, 0o755)
    logger.info(f"Submission script written: {script_path}")

    return script_path
