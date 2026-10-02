from multiprocessing import cpu_count
from subprocess import run
from pathlib import Path
from typing import Self

from src.utils.housekeeping import is_downloaded
from src.utils.log.logger import Logger


class BuildCmd:
    def __init__(self: Self, out_dir: Path, conda_env: str) -> None:
        self.out_dir: Path = out_dir
        self.conda_env: str = conda_env

    def build_prefetch_cmd(
            self: Self,
            srr: str,
            max_size: int = 20
        ) -> list[str | Path | int]:
        """Build the command list for running prefetch."""
        return [
                "conda",
                "run",
                "-n",
                self.conda_env,
                "prefetch",
                srr,
                "-O",
                self.out_dir,
                "--max-size",
                max_size
            ]

    def build_fasterq_dump_cmd(
            self: Self,
            sra_file: Path,
            tmp_dir: Path
        ) -> list[str | Path]:
        """Build the command for fasterq-dump."""
        return [
                "fasterq-dump",
                sra_file,
                "-O",
                self.out_dir,
                "--threads",
                f"{cpu_count()}",
                "-t",
                tmp_dir
            ]




# # ====== STUB FUNCTIONS (not used without --scheduler) ======
#
# def create_manifest_and_script(args, srr_list, array_size):
#     """Stub: create manifest and SLURM script for array job."""
#     # This is only used with --scheduler, which we're not using.
#     # Return a dummy script path to satisfy the import.
#     return "/tmp/dummy_script.sh"
#
#
# def submit_array_job(script_path):
#     """Stub: submit array job to SLURM."""
#     # This is only used with --scheduler, which we're not using.
#     print(f"Array job would be submitted with script: {script_path}")
#     return


def process_srr_list(
        log_: Logger,
        out_dir: Path,
        skip_existing: bool,
        srr_list,
        state,
        state_file
    ):
    """
    Process a list of SRRs: download, convert, clean up.
    Returns (success_count, fail_count).
    """

    success = 0
    fail = 0

    for srr in srr_list:
        # Check if SRR already processed
        if skip_existing and is_downloaded(srr, out_dir):
            log_.info("[%s] already exists" % ( srr ))
            continue

        log_.info("[%s] Processing ..." % ( srr ))

        sra_file = out_dir / f"{srr}.sra"

        # 1. Prefetch (download .sra)
        if args.prefetch:
            # Build command using the helper function
            prefetch_cmd: list[str | Path] = build_prefetch_cmd(
                    prefetch_path=args.prefetch_path,
                    srr=srr,
                    out_dir=out_dir,
                    max_size=getattr(args, 'max_size', None),
                    extra_args=getattr(args, 'prefetch_extra', None),
                    conda_env=getattr(args, 'conda_env', None)
                )
            # Do NOT add --no-subdirs (not supported by older prefetch)
            log_.info(
                "[%s] Running: %s" % (
                    srr, " ".join(
                        f"{c}" for c in prefetch_cmd
                    )
                )
            )
            result = run(prefetch_cmd)
            if result.returncode != 0:
                log_.info("[%s] prefetch failed." % ( srr ))
                fail += 1
                continue

            # Move .sra from subdirectory if it was created
            sra_subdir: Path = out_dir / srr
            if sra_subdir.is_dir():
                sra_file_sub: Path = sra_subdir / f"{srr}.sra"
                if not sra_file_sub.exists():
                    sra_file_sub.rename(sra_file)
                    print(f"[{srr}] Moved .sra from subdirectory to main output")
                else:
                    print(f"[{srr}] [WARN] .sra file not found in subdirectory")

                # Clean up the empty subdirectory after moving .sra out
                try:
                    sra_subdir.rmdir()   # only works if empty
                    print(f"[{srr}] Removed empty subdirectory")
                except OSError:
                    # Directory is not empty (has dependency files, cache, etc.)
                    pass
            else:
                # If subdirectory doesn't exist, maybe .sra is already in out_dir
                if not sra_file.exists():
                    print(f"[{srr}] [WARN] .sra file not found in expected location")

        # 2. fasterq-dump (convert to FASTQ)
        if args.fasterq_dump:
            if not sra_file.exists():
                print(f"[{srr}] [WARN] .sra file not found, skipping conversion")
                fail += 1
                continue

            fq_cmd = build_fasterq_dump_cmd(
                sra_file=str(sra_file),
                out_dir=str(out_dir),
                threads=args.threads,
                fasterq_dump_path=args.fasterq_dump_path,
                conda_env=getattr(args, 'conda_env', None),
                extra_args=getattr(args, 'fasterq_extra', None),
                tmp_dir=getattr(args, 'tmp_dir', None)
            )
            print(f"[{srr}] Running: {' '.join(str(c) for c in fq_cmd)}")
            result = subprocess.run(fq_cmd)
            if result.returncode != 0:
                print(f"[{srr}] [FAIL] fasterq-dump failed")
                fail += 1
                continue

        # 2.5. Compress FASTQ (fasterq-dump 3.4.1 has no internal --gzip)
        do_compress = not getattr(args, "no_gzip", False)
        if args.fasterq_dump and do_compress:
            compression_level = getattr(args, "compression_level", None) or 6
            keep_fastq = getattr(args, "keep_fastq", False)

            # Match both single-end (SRR.fastq) and paired-end (SRR_1.fastq, SRR_2.fastq)
            candidates = [out_dir / f"{srr}.fastq"]
            candidates.extend(out_dir.glob(f"{srr}_*.fastq"))
            fastq_files = [f for f in candidates if f.exists()]

            if not fastq_files:
                print(f"[{srr}] [WARN] No FASTQ files found to compress")
            else:
                compression_failed = False
                for fq in fastq_files:
                    try:
                        _compress_fastq(
                            fq,
                            level=compression_level,
                            keep_original=keep_fastq,
                            threads=args.threads,
                        )
                        print(f"[{srr}] [COMPRESS] {fq.name} -> {fq.name}.gz")
                    except Exception as e:
                        print(f"[{srr}] [FAIL] Compression failed for {fq.name}: {e}")
                        compression_failed = True

                if compression_failed:
                    fail += 1
                    continue

        # 3. Remove .sra if requested
        if args.remove_sra and sra_file.exists():
            try:
                sra_file.unlink()
                print(f"[{srr}] [REMOVE] {sra_file}")
            except Exception as e:
                print(f"[{srr}] [WARN] Failed to remove .sra: {e}")

        success += 1
        print(f"[{srr}] [OK] Done")

    return success, fail




# def worker_mode(args):
#     """Stub: worker mode for array jobs."""
#     # Only used with --worker flag (internal for array jobs).
#     # Not used in our test.
#     print("Worker mode stub called.")
#     return
