import argparse
import atexit
import os
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import certifi
import packaging.version
import tomllib
from setuptools import build_meta as build_meta_orig
from setuptools.build_meta import *

GITHUB_REPO = "annetutil/gnetcli"
SOURCE_TARBALL_NAME = "gnetcli.tar.gz"
OUTPUT_BINARY_NAME = "gnetcli_server"
OUTPUT_BINARY_PATH = Path("gnetcli_server_bin/_bin") / OUTPUT_BINARY_NAME

PYTHON_PLATFORM_TO_GOSYSTEM = {
    "manylinux_2_17_x86_64": ("linux", "amd64"),
    "manylinux_2_17_aarch64": ("linux", "arm64"),
    "macosx_11_0_x86_64": ("darwin", "amd64"),
    "macosx_11_0_arm64": ("darwin", "arm64"),
}


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    build_binary(config_settings or {})
    return build_meta_orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    download_tarball(SOURCE_TARBALL_NAME)
    atexit.register(Path(SOURCE_TARBALL_NAME).unlink, missing_ok=True)
    return build_meta_orig.build_sdist(sdist_directory, config_settings)


def get_version() -> str:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        raise SystemExit("pyproject.toml not found")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    try:
        v = data["project"]["version"]
    except KeyError:
        raise SystemExit("project.version not found in pyproject.toml")
    return packaging.version.parse(v).base_version


def http_download(url: str, dst: str) -> None:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError:
        print(f"failed to download from: {url}", file=sys.stderr)
        raise


def download_tarball(dst: str) -> None:
    version = get_version()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/tarball/v{version}"
    http_download(url, dst)
    print(f"downloaded source: {url}", file=sys.stderr)


def extract_tarball(tar_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            # allow only dirs and regular files
            if not (m.isreg() or m.isdir()):
                continue
            # strip one level of directory
            parts = m.name.split("/", 1)
            if len(parts) < 2:
                continue
            m.name = parts[1]
            tf.extract(m, dest_dir)
    return dest_dir


def get_plat_name(config_settings: dict[str, list[str]] | None) -> str | None:
    opts: list[str] = []
    if config_settings:
        opts = config_settings.get("--build-option", [])
    try:
        idx = opts.index("--plat-name")
    except ValueError:
        return None
    return opts[idx + 1]


def build_binary(config_settings: dict) -> None:
    tarball = Path(SOURCE_TARBALL_NAME)
    plat = get_plat_name(config_settings)
    if plat is None:
        raise SystemExit("wheel build requires --build-option --plat-name <tag>")
    if plat not in PYTHON_PLATFORM_TO_GOSYSTEM:
        raise SystemExit(f"unsupported platform tag: {plat}")
    if not tarball.exists():
        raise SystemExit(f"missing tarball")

    goos, goarch = PYTHON_PLATFORM_TO_GOSYSTEM[plat]
    env = os.environ.copy()
    env["GOOS"] = goos
    env["GOARCH"] = goarch
    retcode = subprocess.call(["go", "help"], stdout=subprocess.DEVNULL)
    if retcode != 0:
        raise SystemExit(f"failed to call go compiler")

    tmpdir = Path(tempfile.mkdtemp())
    src_root = extract_tarball(SOURCE_TARBALL_NAME, tmpdir)

    out_path = tmpdir / OUTPUT_BINARY_NAME
    cmd = ["go", "build", "-o", str(out_path), f"./cmd/{OUTPUT_BINARY_NAME}"]
    print(f"building: {' '.join(cmd)} (GOOS={goos} GOARCH={goarch}) cwd={src_root}", file=sys.stderr)
    subprocess.run(cmd, cwd=str(src_root), env=env, check=True)

    OUTPUT_BINARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(out_path), str(OUTPUT_BINARY_PATH))
    if os.name != "nt":
        OUTPUT_BINARY_PATH.chmod(0o755)

    shutil.rmtree(tmpdir)
    print(f"built: {OUTPUT_BINARY_PATH}", file=sys.stderr)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("plat_name", choices=PYTHON_PLATFORM_TO_GOSYSTEM.keys())
    args = p.parse_args()
    download_tarball(SOURCE_TARBALL_NAME)
    build_binary({"--build-option": ["--plat-name", args.plat_name]})
