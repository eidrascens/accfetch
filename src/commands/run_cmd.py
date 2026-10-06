from pathlib import Path
from subprocess import CalledProcessError, DEVNULL, STDOUT, run
from typing import Self

from src.commands.cmd_builder import BuildCMD
from src.utils.log.custom_logger import Logger


class RunCMD:
    def __init__(
            self: Self,
            log_: Logger,
            OUT_DIR: Path,
            conda_env: str,
            CMD_LOG: Path
        ) -> None:
        self.log_: Logger = log_
        self.cmd: BuildCMD = BuildCMD(log_, OUT_DIR, conda_env)
        self.CMD_LOG: Path = CMD_LOG

    def run_fasterq_dump(
        self: Self, srr: str, sra_path: Path
    ) -> bool:
        """Run fasterq-dump on the .sra file, logging to a file.

        Returns True on success.
        """
        fasterq_dump_cmd = self.cmd.build_fasterq_dump_cmd(sra_path)
        self.log_.info(
            "Running fasterq-dump for %s: %s" % (
                srr, fasterq_dump_cmd
            )
        )
        try:
            with open(self.CMD_LOG, "a", encoding="utf-8") as log_f_:
                result = run(
                        fasterq_dump_cmd,
                        stdout=log_f_,
                        stderr=STDOUT,
                        text=True,
                        check=False
                    )
            if result.returncode != 0:
                raise RuntimeError

            self.log_.info(
                "fasterq-dump succeeded for %s" % ( srr )
            )
        except (RuntimeError, CalledProcessError) as err_:
            self.log_.err(
                "fasterq-dump failed for %s (log: %s)" % (
                    srr, self.CMD_LOG
                ), err_
            )
        else:
            return True

        return False

    def run_prefetch(self: Self, srr: str) -> bool:
        """Run prefetch for one SRR, logging to a file.

        Returns True on success.
        """
        prefetch_cmd = self.cmd.build_prefetch_cmd(srr)
        self.log_.info("Running prefetch for %s: %s" % (
                srr, prefetch_cmd
            )
        )
        try:

            with open(self.CMD_LOG, "a", encoding="utf-8") as log_f_:
                result = run(
                        prefetch_cmd,
                        stdout=log_f_,
                        stderr=STDOUT,
                        stdin=DEVNULL,
                        text=True,
                        check=False
                    )
            if result.returncode != 0:
                raise RuntimeError

            self.log_.info(
                "prefetch succeeded for %s" % ( srr )
            )
        except (RuntimeError, CalledProcessError) as err_:
            self.log_.err(
                "prefetch failed for %s (log: %s)" % (
                    srr, self.CMD_LOG
                ), err_
            )
        else:
            return True

        return False
