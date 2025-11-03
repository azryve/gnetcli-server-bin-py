import os
from importlib.resources import files

def get_binary_path() -> str:
    name = "gnetcli_server.exe" if os.name == "nt" else "gnetcli_server"
    return str(files("gnetcli_server_bin").joinpath("_bin", name))
