from importlib_metadata import PackageNotFoundError, version

try:
    __version__ = version(dist_name)
except PackageNotFoundError:
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
