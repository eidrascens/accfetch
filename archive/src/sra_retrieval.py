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
