from multiprocessing import cpu_count
from pathlib import Path
from typing import Self

from src.utils.log.custom_logger import Logger


class BuildCMD:
    def __init__(
            self: Self, log_: Logger, OUT_DIR: Path, conda_env: str
        ) -> None:
        self.log_: Logger = log_
        self.OUT_DIR: Path = OUT_DIR
        self.conda_env: str = conda_env

    def build_prefetch_cmd(self: Self, srr: str) -> list[str | Path]:
        """Build the command list for running prefetch."""
        return [
                "conda",
                "run",
                "-n",
                self.conda_env,
                "prefetch",
                srr,
                "-O",
                self.OUT_DIR
            ]

    def build_fasterq_dump_cmd(
            self: Self, SRA_FILE: Path
        ) -> list[str | Path]:
        """Build the command for fasterq-dump."""


        return [
                "fasterq-dump",
                SRA_FILE,
                "-O",
                self.OUT_DIR,
                "--threads",
                f"{cpu_count()}"
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


# def process_srr_list(
#         log_: Logger,
#         OUT_DIR: Path,
#         skip_existing: bool,
#         srr_list,
#         state,
#         STATE_FILE
#     ):
#     """
#     Process a list of SRRs: download, convert, clean up.
#     Returns (success_count, fail_count).
#     """
#
#     success = 0
#     fail = 0
#
#     for srr in srr_list:
#         # Check if SRR already processed
#         if skip_existing and is_downloaded(srr, OUT_DIR):
#             log_.info("[%s] already exists" % ( srr ))
#             continue
#
#         log_.info("[%s] Processing ..." % ( srr ))
#
#         SRA_FILE = OUT_DIR / f"{srr}.sra"
#
#         # 1. Prefetch (download .sra)
#         if args.prefetch:
#             # Build command using the helper function
#             prefetch_cmd: list[str | Path] = build_prefetch_cmd(
#                     prefetch_path=args.prefetch_path,
#                     srr=srr,
#                     OUT_DIR=OUT_DIR,
#                     max_size=getattr(args, 'max_size', None),
#                     extra_args=getattr(args, 'prefetch_extra', None),
#                     conda_env=getattr(args, 'conda_env', None)
#                 )
#             # Do NOT add --no-subdirs (not supported by older prefetch)
#             log_.info(
#                 "[%s] Running: %s" % (
#                     srr, " ".join(
#                         f"{c}" for c in prefetch_cmd
#                     )
#                 )
#             )
#             result = run(prefetch_cmd)
#             if result.returncode != 0:
#                 log_.info("[%s] prefetch failed." % ( srr ))
#                 fail += 1
#                 continue
#
#             # Move .sra from subdirectory if it was created
#             sra_subdir: Path = OUT_DIR / srr
#             if sra_subdir.is_dir():
#                 sra_file_sub: Path = sra_subdir / f"{srr}.sra"
#                 if not sra_file_sub.exists():
#                     sra_file_sub.rename(SRA_FILE)
#                     print(f"[{srr}] Moved .sra from subdirectory to main output")
#                 else:
#                     print(f"[{srr}] [WARN] .sra file not found in subdirectory")
#
#                 # Clean up the empty subdirectory after moving .sra out
#                 try:
#                     sra_subdir.rmdir()   # only works if empty
#                     print(f"[{srr}] Removed empty subdirectory")
#                 except OSError:
#                     # Directory is not empty (has dependency files, cache, etc.)
#                     pass
#             else:
#                 # If subdirectory doesn't exist, maybe .sra is already in OUT_DIR
#                 if not SRA_FILE.exists():
#                     print(f"[{srr}] [WARN] .sra file not found in expected location")
#
#         # 2. fasterq-dump (convert to FASTQ)
#         if args.fasterq_dump:
#             if not SRA_FILE.exists():
#                 print(f"[{srr}] [WARN] .sra file not found, skipping conversion")
#                 fail += 1
#                 continue
#
#             fq_cmd = build_fasterq_dump_cmd(
#                 SRA_FILE=str(SRA_FILE),
#                 OUT_DIR=str(OUT_DIR),
#                 threads=args.threads,
#                 fasterq_dump_path=args.fasterq_dump_path,
#                 conda_env=getattr(args, 'conda_env', None),
#                 extra_args=getattr(args, 'fasterq_extra', None),
#                 TMP_DIR=getattr(args, 'TMP_DIR', None)
#             )
#             print(f"[{srr}] Running: {' '.join(str(c) for c in fq_cmd)}")
#             result = subprocess.run(fq_cmd)
#             if result.returncode != 0:
#                 print(f"[{srr}] [FAIL] fasterq-dump failed")
#                 fail += 1
#                 continue
#
#         # 2.5. Compress FASTQ (fasterq-dump 3.4.1 has no internal --gzip)
#         do_compress = not getattr(args, "no_gzip", False)
#         if args.fasterq_dump and do_compress:
#             compression_level = getattr(args, "compression_level", None) or 6
#             keep_fastq = getattr(args, "keep_fastq", False)
#
#             # Match both single-end (SRR.fastq) and paired-end (SRR_1.fastq, SRR_2.fastq)
#             candidates = [OUT_DIR / f"{srr}.fastq"]
#             candidates.extend(OUT_DIR.glob(f"{srr}_*.fastq"))
#             fastq_files = [f for f in candidates if f.exists()]
#
#             if not fastq_files:
#                 print(f"[{srr}] [WARN] No FASTQ files found to compress")
#             else:
#                 compression_failed = False
#                 for fq in fastq_files:
#                     try:
#                         _compress_fastq(
#                             fq,
#                             level=compression_level,
#                             keep_original=keep_fastq,
#                             threads=args.threads,
#                         )
#                         print(f"[{srr}] [COMPRESS] {fq.name} -> {fq.name}.gz")
#                     except Exception as e:
#                         print(f"[{srr}] [FAIL] Compression failed for {fq.name}: {e}")
#                         compression_failed = True
#
#                 if compression_failed:
#                     fail += 1
#                     continue
#
#         # 3. Remove .sra if requested
#         if args.remove_sra and SRA_FILE.exists():
#             try:
#                 SRA_FILE.unlink()
#                 print(f"[{srr}] [REMOVE] {SRA_FILE}")
#             except Exception as e:
#                 print(f"[{srr}] [WARN] Failed to remove .sra: {e}")
#
#         success += 1
#         print(f"[{srr}] [OK] Done")
#
#     return success, fail
#
#
#
#
# # def worker_mode(args):
# #     """Stub: worker mode for array jobs."""
# #     # Only used with --worker flag (internal for array jobs).
# #     # Not used in our test.
# #     print("Worker mode stub called.")
# #     return
