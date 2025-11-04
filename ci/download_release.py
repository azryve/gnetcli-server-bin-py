import sys
import argparse
import os
import tarfile
import urllib.request
import urllib.error
import tempfile
import ssl
import shutil
import certifi
from pathlib import Path

# set this to your upstream
OWNER = "annetutil"
REPO = "gnetcli"


def read_project_version() -> str:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        raise SystemExit("pyproject.toml not found, cannot determine version")
    # Python 3.11+ has tomllib
    try:
        import tomllib  # type: ignore
    except ModuleNotFoundError:
        raise SystemExit("tomllib not available, need Python 3.11+ to read package version")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    try:
        return data["project"]["version"]
    except KeyError:
        raise SystemExit("project.version not found in pyproject.toml")


def get_target(config: dict):
    plat = config.get("platform-name") if config else None
    if not plat:
        raise SystemExit("missing required build option: -C platform-name=<os>/<arch>")
    parts = plat.split("/", 1)
    if len(parts) != 2:
        raise SystemExit(f"invalid platform-name {plat!r}, expected <os>/<arch>")
    os_name, arch = parts
    return os_name, arch

def download(url: str, dst: Path) -> None:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ssl_context) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError:
        print(f"failed to download from: {url}", file=sys.stderr)
        raise

def extract_binary(tar_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if m.isfile():
                tf.extract(m, dest_dir)
    return dest_dir / "gnetcli_server"


def download_binary(config_settings: dict) -> None:
    pkg_bin = Path("gnetcli_server_bin") / "_bin"
    binary_path = pkg_bin / "gnetcli_server"

    os_name, arch = get_target(config_settings)
    version = read_project_version()
    asset = f"gnetcli_server-v{version}-{os_name}-{arch}.tar.gz"
    url = f"https://github.com/{OWNER}/{REPO}/releases/download/v{version}/{asset}"

    tmpdir = Path(tempfile.mkdtemp())
    tar_path = tmpdir / asset

    download(url, tar_path)
    print(f"downloaded: {url}", file=sys.stderr)
    extracted = extract_binary(tar_path, tmpdir)

    pkg_bin.mkdir(parents=True, exist_ok=True)
    shutil.move(str(extracted), str(binary_path))
    if os.name != "nt":
        binary_path.chmod(0o755)

    shutil.rmtree(tmpdir)
    print(f"extracted: {binary_path}", file=sys.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("platform_name", help="Platform in <os>/<arch> format: darwin/amd64, linux/amd64")
    args = p.parse_args()
    download_binary({"platform-name": args.platform_name})
