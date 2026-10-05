from pathlib import Path
from os.path import dirname, realpath
from tomllib import load

from src.utils.log.custom_logger import Logger
from src.core.fetch_srr import fetch_srr_list


CWD: Path = Path(dirname(realpath(__file__))) / ".."
with open(CWD / "config.toml", "rb") as conf_:
    conf = load(conf_)


log: Logger = Logger(CWD / "logs", "fetch_srr_list-test")


fetch_srr_list(log, conf, "DRP014210")
fetch_srr_list(log, conf, "SRP453361")
fetch_srr_list(log, conf, "SRP503661")
fetch_srr_list(log, conf, "SRP293811")
