from pathlib import Path
from subprocess import CalledProcessError, run

from src.utils.log.custom_logger import Logger


def submit_array_job(log_: Logger, SCRIPT_PATH: Path):
    """Submit the SLURM job."""
    try:
        result = run(
                ["sbatch", SCRIPT_PATH],
                capture_output=True,
                text=True,
                check=False
            )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        log_.info(
            "Array job submitted: %s" % ( result.stdout.strip() )
        )
    except (CalledProcessError, RuntimeError) as err_:
        log_.err("Error submitting job.", err_)
    else:
        return True

    return False
