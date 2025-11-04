import sys
import subprocess

import gnetcli_server_bin

if __name__ == "__main__":
    binary_path = gnetcli_server_bin.get_binary_path()
    subprocess.check_call([binary_path] + sys.argv[1:])
