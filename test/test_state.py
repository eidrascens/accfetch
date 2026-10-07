from os.path import dirname, realpath
from pathlib import Path

from src.utils.state import State
from src.utils.log.custom_logger import Logger


CWD: Path = Path(dirname(realpath(__file__))) / ".."
log = Logger(CWD / "logs", "state-test")
state = State(log, CWD, ".state_file-06.10.26_23-49")

print(state.load_state_file())
print(state.get_state("TEST1", "status"))
state.update_state("TEST2", "FD", Path("/test/path/for/test2"))
