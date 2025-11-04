import sys
import argparse
import os
import tarfile
import urllib.request
import urllib.error
import tempfile
import ssl
import shutil
import tomllib
from pathlib import Path

import certifi

from setuptools import build_meta as build_meta_orig
from setuptools.build_meta import *

# set this to your upstream
REPO = "https://github.com/annetutil/gnetcli"

# Converts PEP 425 platform tag into a golang GOOS/GOARCH pair
# https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/
# https://go.dev/src/internal/syslist/syslist.go
PYTHON_PLATFORM_TO_GOSYSTEM = {
    "manylinux_2_17_x86_64":   ("linux", "amd64"),
    "macosx_11_0_x86_64":      ("darwin", "amd64"),
    "macosx_11_0_arm64":       ("darwin", "arm64"), # upstream does not build those
    "macosx_11_0_universal2":  ("darwin", "amd64"), # this is false, its a amd64 binary, go combiler cant build universal executable
    # "macosx_11_0_arm64":     ("darwin",  "arm64"),
    # "win_amd64":             ("windows", "amd64"),
}


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    download_binary(config_settings or {})
    return build_meta_orig.build_wheel(
        wheel_directory, config_settings, metadata_directory
    )


def read_project_version() -> str:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        raise SystemExit("pyproject.toml not found, cannot determine version")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    try:
        return data["project"]["version"]
    except KeyError:
        raise SystemExit("project.version not found in pyproject.toml")


def download(url: str, dst: Path) -> None:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with (
            urllib.request.urlopen(req, context=ssl_context) as r,
            open(dst, "wb") as f,
        ):
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


def get_plat_name(config_settings: dict[str, list[str]] | None) -> str | None:
    build_options: list[str] = []
    if config_settings:
        build_options = config_settings.get("--build-option", [])
    try:
        plat_name_idx = build_options.index("--plat-name")
    except ValueError:
        return None
    return build_options[plat_name_idx + 1]


def download_binary(config_settings: dict) -> None:
    pkg_bin = Path("gnetcli_server_bin") / "_bin"
    binary_path = pkg_bin / "gnetcli_server"
    version = read_project_version()

    plat_pname = get_plat_name(config_settings)
    os_name, arch = PYTHON_PLATFORM_TO_GOSYSTEM[plat_pname]

    asset = f"gnetcli_server-v{version}-{os_name}-{arch}.tar.gz"
    url = f"{REPO}/releases/download/v{version}/{asset}"

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
    p.add_argument(
        "plat_name", help="Platform in <os>/<arch>", choices=PYTHON_PLATFORM_TO_GOSYSTEM.keys(),
    )
    args = p.parse_args()
    download_binary({"--build-option": ["--plat-name", args.plat_name]})
