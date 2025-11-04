from ._binary import get_binary_path

__all__ = ["get_binary_path"]

try:
    from importlib.metadata import version
    __version__ = version("gnetcli-server-bin")
except Exception:
    __version__ = "0.0.0"
