import os
import sys
import tarfile
import urllib.request
import tempfile
import shutil
import platform
from pathlib import Path

OWNER = "ORIGINAL_OWNER"
REPO = "ORIGINAL_REPO"
UPSTREAM_VERSION = "v1.1.2"

def detect_target():
    p = sys.platform
    m = platform.machine().lower()
    if p.startswith("linux") and m == "x86_64":
        return "linux", "amd64"
    if p == "darwin" and m == "x86_64":
        return "darwin", "amd64"
    raise SystemExit("unsupported build platform")

def asset_name(version, os_name, arch):
    return f"gnetcli_server-{version}-{os_name}-{arch}.tar.gz"

def download(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "gnetcli-server-bin-py"})
    with urllib.request.urlopen(req) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)

def extract_binary(tar_path, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if m.isfile():
                tf.extract(m, dest_dir)
    return dest_dir / "gnetcli_server"

def ensure_binary():
    pkg_bin = Path("gnetcli_server_bin") / "_bin"
    binary_path = pkg_bin / "gnetcli_server"
    if binary_path.exists():
        return
    os_name, arch = detect_target()
    asset = asset_name(UPSTREAM_VERSION, os_name, arch)
    url = f"https://github.com/{OWNER}/{REPO}/releases/download/{UPSTREAM_VERSION}/{asset}"
    tmpdir = Path(tempfile.mkdtemp())
    tar_path = tmpdir / asset
    download(url, tar_path)
    extracted = extract_binary(tar_path, tmpdir)
    pkg_bin.mkdir(parents=True, exist_ok=True)
    shutil.move(str(extracted), str(binary_path))
    if os.name != "nt":
        binary_path.chmod(0o755)
    shutil.rmtree(tmpdir)
