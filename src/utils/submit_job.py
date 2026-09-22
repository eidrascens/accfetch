from subprocess import run
from pathlib import Path

from src.utils.log.logger import Logger


def submit_array_job(log: Logger, script_path: Path):
    """Submit the SLURM job."""
    try:
        result = run(
                ["sbatch", script_path],
                capture_output=True,
                text=True,
                check=False
            )
        if result.returncode == 0:
            log.info(f"Array job submitted: {result.stdout.strip()}")
        log.err(f"Submission failed: {result.stderr.strip()}")
    except Exception as err:
        log.err(f"Error submitting: {err}")
    else:
        return True

    return False
