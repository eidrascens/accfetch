from os.path import exists, join
from pathlib import Path
from tomllib import load
from typing import Self

from src.utils.housekeeping import fix_dir
from src.utils.log.custom_logger import Logger


class Retrieve:
    def __init__(self: Self, log_: Logger, toml_conf: Path) -> None:
        self.log_: Logger = log_

        with open(toml_conf, "rb", encoding="utf-8") as conf:
            conf = load(conf)

        self.prog = conf["program"]
        self.compression_lvl: int = 6
        self.dir = conf["dir"]

    def retrieve(self: Self) -> None:

        # Set state file path if not provided
        if self.prog["ST_FILE"] is None:
            state_file: Path = self.prog["OUT_DIR"] / ".sra_state.json"


        # Create output directory
        DIR: list[Path] = [
                self.prog["OUT_DIR"],
                self.prog["OUT_DIR"] / "logs"
            ]
        fix_dir(self.log_, DIR)
        os.makedirs(self.dir["tmp_dir"], exist_ok=True)

        # Fetch SRR list
        try:
            srr_list = fetch_srr_list(accession)
        except RuntimeError as e:
            self.log_.err(str(e))
            raise SystemExit

        if not srr_list:
            self.log_.info("No SRRs to process.")
            return

        # If skip_existing and not scheduler, pre-filter
        if skip_existing and not scheduler:
            original_count = len(srr_list)
            filtered = []
            for srr in srr_list:
                fastq_base = join(OUT_DIR, srr)
                if exists(f"{fastq_base}.fastq") or \
                exists(f"{fastq_base}_1.fastq") or \
                exists(f"{fastq_base}.fastq.gz") or \
                exists(f"{fastq_base}_1.fastq.gz"):
                    continue
                filtered.append(srr)
            srr_list = filtered
            skipped = original_count - len(srr_list)
            if skipped:
                self.log_.info(f"Skipped {skipped} SRRs with existing FASTQ.")
            if not srr_list:
                self.log_.info("All SRRs already have FASTQ output. Nothing to do.")
                return

        # Decide execution mode
        if scheduler:
            if scheduler != "slurm":
                self.log_.err("Only SLURM scheduler is currently supported for array job submission.")
                raise SystemExit
            if array_size < 1:
                self.log_.err("--array-size must be >= 1.")
                raise SystemExit
            script_path = create_manifest_and_script(args, srr_list, array_size)
            submit_array_job(script_path)
        else:
            state = load_state(state_file)
            try:
                success, fail = process_srr_list(srr_list, args, state, state_file)
                self.log_.info(f"Finished processing. Success={success}, Failed={fail}")
                if fail > 0:
                    raise SystemExit
            except KeyboardInterrupt:
                log_.warn("Interrupted by user. State saved for resume.")
                save_state(STATE_FILE, state)
                raise SystemExit

