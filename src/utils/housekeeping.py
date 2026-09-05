def is_downloaded(srr: str, output_dir: str) -> bool:
    """Check if a .sra file or directory for the given SRR exists."""
    sra_file = os.path.join(output_dir, f"{srr}.sra")
    sra_dir = os.path.join(output_dir, srr)
    return os.path.exists(sra_file) or os.path.isdir(sra_dir)
