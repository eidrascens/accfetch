from pathlib import Path
from subprocess import run, STDOUT
from typing import Self

from src.utils.log.logger import Logger
from src.utils.command_builder import BuildCmd



class RunCMD:
    def __init__(
            self: Self, log_: Logger, OUT_DIR: Path, conda_env: Path
        ) -> None:
        self.log_: Logger = log_
        self.cmd: BuildCmd = BuildCmd(OUT_DIR, conda_env)

    def run_fasterq_dump(
        self: Self,
        srr: str,
        sra_path: Path,
        TMP_DIR: Path,
        CMD_LOG: Path,
    ) -> bool:
        """Run fasterq-dump on the .sra file, logging to a file.

        Returns True on success.
        """
        fasterq_dump_cmd = self.cmd.build_fasterq_dump_cmd(
                sra_path, TMP_DIR
            )
        self.log_.info(f"Running fasterq-dump: {' '.join(cmd)}")
        try:
            with open(CMD_LOG, "a", encoding="utf-8") as log_f_:
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
                    srr, CMD_LOG
                ), err_
            )
        except Exception as err_:
            self.log_.err(
                "Error occured while executing %s (log: %s)" % (
                    fasterq_dump_cmd, CMD_LOG
                ), err_
            )
        else:
            return True

        return False

    def run_prefetch(
        self: Self,
        srr: str,
        max_size: Path,
        CMD_LOG: Path
    ) -> bool:
        """Run prefetch for one SRR, logging to a file.

        Returns True on success.
        """
        prefetch_cmd = self.cmd.build_prefetch_cmd(srr, max_size)
        try:

            with open(CMD_LOG, "a", encoding="utf-8") as log_f_:
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
        except (RuntimeError, CalledProcessError) as err_:
            self.log_.err(
                "prefetch failed for %s (log: %s)" % (
                    srr, CMD_LOG
                ), err_
            )
        except Exception as err_:
            self.log_.err(
                "Error occured while executing %s (log: %s)" % (
                    prefetch_cmd, CMD_LOG
                ), err_
            )
        else:
            return True

        return False
