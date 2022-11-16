from enum import IntEnum


class LogLevel(IntEnum):
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3,
    OFF = 4


class PychanLogger:
    _RED = u"\u001b[31m"
    _GREEN = u"\u001b[32m"
    _YELLOW = u"\u001b[33m"
    _RESET = u"\u001b[0m"

    def __init__(self, level: LogLevel = LogLevel.OFF, *, colorized: bool = True):
        self._log_level = level
        self._colorized = colorized

    def _red(self, text: str) -> str:
        return self._RED + text + self._RESET if self._colorized else text

    def _green(self, text: str) -> str:
        return self._GREEN + text + self._RESET if self._colorized else text

    def _yellow(self, text: str) -> str:
        return self._YELLOW + text + self._RESET if self._colorized else text

    def debug(self, message: str) -> None:
        if self._log_level <= LogLevel.DEBUG:
            print(self._green("[pychan] " + message))

    def info(self, message: str) -> None:
        if self._log_level <= LogLevel.INFO:
            print("[pychan] " + message)

    def warn(self, message: str) -> None:
        if self._log_level <= LogLevel.WARN:
            print(self._yellow("[pychan] " + message))

    def error(self, message: str) -> None:
        if self._log_level <= LogLevel.ERROR:
            print(self._red("[pychan] " + message))
