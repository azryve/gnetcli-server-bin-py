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
from pathlib import Path, PurePosixPath

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
    config_settings = config_settings or {}
    determine_target_platform(config_settings)
    download_tarball(SOURCE_TARBALL_NAME)
    atexit.register(Path(SOURCE_TARBALL_NAME).unlink, missing_ok=True)
    build_binary(config_settings)
    return build_meta_orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    config_settings = config_settings or {}
    determine_target_platform(config_settings)
    download_tarball(SOURCE_TARBALL_NAME)
    atexit.register(Path(SOURCE_TARBALL_NAME).unlink, missing_ok=True)
    return build_meta_orig.build_sdist(sdist_directory, config_settings)


def get_upstream_version() -> str:
    """
    Returns base version of the based on pyproject.toml version
    Strip pre/post/dev/local version segment leaving only semver:
    "1.2.3.post1" -> "1.2.3", "1.2.3rc1" -> "1.2.3"
    """
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
    path = Path(dst)
    if path.exists():
        print(f"tarball already exists: {dst}", file=sys.stderr)
        return

    version = get_upstream_version()
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


def extract_tarball(tar_path: Path, dest_dir: Path, strip: int) -> Path:
    """
    Extracts tgz files stripping <strip> components from the top of the level.
    This is equivalent to 'tar xzf <tar_path> -C <dest_dir> --strip-components=<strip>'.
    Also ignores non-regulars (links, specials, etc.) - only extracts dirs and regular files.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            # allow only dirs and regular files
            if not (m.isreg() or m.isdir()):
                print(f"extract_tarball: skipping non-regular file {m.name}", file=sys.stderr)
                continue
            # strip n levels of directory
            path = PurePosixPath(m.name)
            if len(path.parts) < strip:
                print(f"extract_tarball: ignoring file due to strip {m.name}", file=sys.stderr)
                continue
            m.name = str(PurePosixPath(*path.parts[strip:]))
            tf.extract(m, dest_dir)
    return dest_dir


def get_target_platform_name(config_settings: dict[str, list[str]] | None) -> str | None:
    opts: list[str] = []
    if config_settings:
        opts = config_settings.get("--build-option", [])
    try:
        idx = opts.index("--plat-name")
    except ValueError:
        return None
    return opts[idx + 1]


def set_target_platform_name(config_settings: dict[str, list[str]], platform_name: str) -> None:
    build_options = config_settings.get("--build-option", [])
    build_options.extend(["--plat-name", platform_name])
    config_settings["--build-option"] = build_options


def determine_target_platform(config_settings: dict[str, list[str]]) -> None:
    """
    Sets current platform as target platform for wheels if no --plat-name is provided manually.
    """
    if get_target_platform_name(config_settings):
        return

    platform_native = distutils.util.get_platform()
    platform_tag = platform_native.replace(".", "_").replace("-", "_")
    set_target_platform_name(config_settings, platform_tag)
 

def go_platform_from_tag(platform_tag: str) -> tuple[str, str]:
    """
    Converts PEP 425 platform tag into a golang GOOS/GOARCH pair.

    https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/
    https://go.dev/src/internal/syslist/syslist.go

    TODO: To support macos universal2  we need to combine amd64/arm64 binaries with lipo:
    https://dev.to/thewraven/universal-macos-binaries-with-go-1-16-3mm3
    """
    p = platform_tag.lower()
    if p.startswith(("manylinux", "musllinux", "linux")):
        if "x86_64" in p or "amd64" in p:
            return ("linux", "amd64")
        if "aarch64" in p or "arm64" in p:
            return ("linux", "arm64")
        raise SystemExit(f"unsupported linux platform tag: {platform_tag!r}")

    if p.startswith("macosx"):
        if "x86_64" in p or "intel" in p:
            return ("darwin", "amd64")
        if "arm64" in p:
            return ("darwin", "arm64")
        raise SystemExit(f"unsupported macos platform tag: {platform_tag!r}")

    if p.startswith("win"):
        if "amd64" in p or "x86_64" in p:
            return ("windows", "amd64")
        raise SystemExit(f"unsupported windows platform tag: {platform_tag!r}")

    raise SystemExit(f"unsupported platform tag: {platform_tag!r}")


def build_binary(config_settings: dict) -> None:
    tarball = Path(SOURCE_TARBALL_NAME)
    platform_tag = get_target_platform_name(config_settings)
    if not platform_tag:
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
    src_root = extract_tarball(SOURCE_TARBALL_NAME, tmpdir, 1)

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
