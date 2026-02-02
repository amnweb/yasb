import logging
import traceback
from typing import Any


def log_error(msg: str, error: BaseException | Exception | str | Any = ""):
    if error:
        if isinstance(error, BaseException):
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            tb_str = ""

        if tb_str:
            added_traceback = "\n #\n # " + str(tb_str).replace("\n", "\n # ")
        else:
            added_traceback = ""
        logging.error(msg + ": \n # " + str(error).replace("\n", "\n # ") + added_traceback)
    else:
        logging.error(msg)
