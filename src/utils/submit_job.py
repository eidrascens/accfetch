from subprocess import run
from pathlib import Path

from src.utils.log.logger import Logger


def submit_array_job(log_: Logger, script_path: Path):
    """Submit the SLURM job."""
    try:
        result = run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=False
            )
        if result.returncode == 0:
            log_.info(
                "Array job submitted: %s" % ( result.stdout.strip() )
            )
        log_.err("Submission failed: %s" % ( result.stderr.strip() ))
    except Exception as err:
        log_.err("Error submitting: %s" % ( err ), err)
    else:
        return True

    return False
