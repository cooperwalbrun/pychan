from importlib_metadata import PackageNotFoundError, version

from pychan import api, logger

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

FourChan = api.FourChan
PychanLogger = logger.PychanLogger
LogLevel = logger.LogLevel
