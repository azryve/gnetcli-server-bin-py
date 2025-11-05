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

import distutils.util
from setuptools import build_meta as build_meta_orig
from setuptools.build_meta import *

GITHUB_REPO = "annetutil/gnetcli"
SOURCE_TARBALL_NAME = "gnetcli.tar.gz"
OUTPUT_BINARY_NAME = "gnetcli_server"
OUTPUT_BINARY_PATH = Path("gnetcli_server_bin/_bin") / OUTPUT_BINARY_NAME


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    config_settings = set_plat_name(config_settings)
    build_binary(config_settings)
    return build_meta_orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    config_settings = set_plat_name(config_settings)
    download_tarball(SOURCE_TARBALL_NAME)
    atexit.register(Path(SOURCE_TARBALL_NAME).unlink, missing_ok=True)
    return build_meta_orig.build_sdist(sdist_directory, config_settings)


def get_pyproject_version() -> str:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        raise SystemExit("pyproject.toml not found")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    try:
        v = data["project"]["version"]
    except KeyError:
        raise SystemExit("project.version not found in pyproject.toml")
    return packaging.version.parse(v).base_version


def download_tarball(dst: str) -> None:
    version = get_pyproject_version()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/tarball/v{version}"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ssl_context) as r:
            with open(dst, "wb") as f:
                shutil.copyfileobj(r, f)
    except urllib.error.HTTPError:
        print(f"failed to download from: {url}", file=sys.stderr)
        raise
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


def set_plat_name(config_settings: dict[str, list[str]] | None) -> dict[str, list[str]]:
    if not config_settings:
        config_settings = {}
    else:
        config_settings = config_settings.copy()

    if get_plat_name(config_settings):
        return config_settings

    platform_native = distutils.util.get_platform()
    platform_tag = platform_native.replace(".", "_").replace("-", "_")

    build_options = config_settings.get("--build-option", [])
    build_options.extend(["--plat-name", platform_tag])
    config_settings["--build-option"] = build_options
    return config_settings


def go_platform_from_tag(platform_tag: str) -> tuple[str, str]:
    p = platform_tag.lower()
    if p.startswith(("manylinux", "musllinux", "linux_")):
        if "x86_64" in p or "amd64" in p:
            return ("linux", "amd64")
        if "aarch64" in p or "arm64" in p:
            return ("linux", "arm64")
        raise SystemExit(f"unsupported linux platform tag: {platform_tag!r}")

    if p.startswith("macosx_"):
        if "universal2" in p:
            return ("darwin", "amd64")  # single-arch go build
        if "x86_64" in p or "intel" in p:
            return ("darwin", "amd64")
        if "arm64" in p:
            return ("darwin", "arm64")
        raise SystemExit(f"unsupported macos platform tag: {platform_tag!r}")

    if p.startswith("win_"):
        if "amd64" in p or "x86_64" in p:
            return ("windows", "amd64")
        raise SystemExit(f"unsupported windows platform tag: {platform_tag!r}")

    raise SystemExit(f"unsupported platform tag: {platform_tag!r}")


def build_binary(config_settings: dict) -> None:
    tarball = Path(SOURCE_TARBALL_NAME)
    platform_tag = get_plat_name(config_settings)
    if platform_tag is None:
        raise SystemExit("wheel build requires --build-option --plat-name <tag>")
    if not tarball.exists():
        raise SystemExit(f"missing tarball")

    goos, goarch = go_platform_from_tag(platform_tag)
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
