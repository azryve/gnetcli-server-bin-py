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
OUTPUT_BINARY_PATH = Path("gnetcli_server_bin/_bin")
GO_BUILD_FLAGS = ["-trimpath", "-ldflags=-s -w -extldflags '-static'"]

# currently we only need cmd/gnetcli_server
# and would like to control the size of pypi project
TARGET_BINARIES = ["cmd/gnetcli_server"]

TMP_DIR = Path(tempfile.mkdtemp())
atexit.register(shutil.rmtree, TMP_DIR, ignore_errors=True)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    config_settings = config_settings or {}
    determine_target_platform(config_settings)

    tarball = download_tarball()
    atexit.register(tarball.unlink)

    src_root = extract_tarball(tarball, strip=1)
    binaries_build(config_settings, TARGET_BINARIES, src_root, OUTPUT_BINARY_PATH)
    return build_meta_orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    config_settings = config_settings or {}
    determine_target_platform(config_settings)

    tarball = download_tarball()
    atexit.register(tarball.unlink)

    return build_meta_orig.build_sdist(sdist_directory, config_settings)


def get_tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(dir=TMP_DIR))


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


def download_tarball() -> Path:
    version = get_upstream_version()
    tar_path =  Path(f"gnetcli-v{version}.tar.gz")

    if tar_path.exists():
        print(f"tarball already exists: {tar_path}", file=sys.stderr)
        return tar_path

    url = f"https://api.github.com/repos/{GITHUB_REPO}/tarball/v{version}"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ssl_context) as r:
            with tar_path.open("wb") as f:
                shutil.copyfileobj(r, f)
    except urllib.error.HTTPError:
        print(f"failed to download from: {url}", file=sys.stderr)
        raise

    print(f"downloaded source tarball from: {url} to {tar_path}", file=sys.stderr)
    return tar_path


def extract_tarball(tar_path: Path, strip: int) -> Path:
    """
    Extracts tgz files stripping <strip> components from the top of the level.
    This is equivalent to 'tar xzf <tar_path> -C <dest_dir> --strip-components=<strip>'.
    Also ignores non-regulars (links, specials, etc.) - only extracts dirs and regular files.
    """
    src_root = get_tmp_dir()
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
            tf.extract(m, src_root)
    return src_root


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
 

def go_platform_from_tag(platform_tag: str) -> tuple[str, list[str]]:
    """
    Converts PEP 425 platform tag into a golang GOOS and list of GOARCH.
    The target GOOS is always a single one: linux/darwin/windows.
    List of GOARCH is nessesary for multi-ach binaries.
    Example "macosx_10_15_universal2" -> ("darwin", ["amd64", "arm64"]).

    https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/
    https://go.dev/src/internal/syslist/syslist.go
    """
    p = platform_tag.lower()
    if p.startswith(("manylinux", "musllinux", "linux")):
        if "x86_64" in p or "amd64" in p:
            return "linux", ["amd64"]
        if "aarch64" in p or "arm64" in p:
            return "linux", ["arm64"]
        raise SystemExit(f"unsupported linux platform tag: {platform_tag!r}")

    if p.startswith("macosx"):
        if "x86_64" in p or "intel" in p:
            return "darwin", ["amd64"]
        if "arm64" in p:
            return "darwin", ["arm64"]
        if "universal2" in p:
            return "darwin", ["amd64", "arm64"]
        raise SystemExit(f"unsupported macos platform tag: {platform_tag!r}")

    if p.startswith("win"):
        if "amd64" in p or "x86_64" in p:
            return "windows", ["amd64"]
        raise SystemExit(f"unsupported windows platform tag: {platform_tag!r}")

    raise SystemExit(f"unsupported platform tag: {platform_tag!r}")


def binary_go_build(src_root: Path, goos: str, goarch: str, target_binary: str) -> Path:
    env = os.environ.copy()
    env["GOOS"] = goos
    env["GOARCH"] = goarch

    tmp_dir = get_tmp_dir()
    out_path = tmp_dir / Path(target_binary).name
    cmd = ["go", "build"] + GO_BUILD_FLAGS + ["-o", str(out_path), f"./{target_binary}"]

    print(f"building: {' '.join(cmd)} (GOOS={goos} GOARCH={goarch}) cwd={src_root}", file=sys.stderr)
    subprocess.run(cmd, cwd=str(src_root), env=env, check=True)

    print(f"built: {out_path}", file=sys.stderr)
    return out_path


def binaries_combine_darwin(binaries: list[Path]) -> Path:
    tmp_dir = get_tmp_dir()
    out_path = tmp_dir / binaries[0].name
    cmd = ["lipo", "-create", "-o", str(out_path)] + [str(x) for x in binaries]

    print(f"combining: {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, check=True)

    print(f"combined: {out_path}", file=sys.stderr)
    return out_path


def binaries_finalize(goos: str, binaries: list[Path]) -> Path:
    if not binaries:
        raise SystemExit(f"no binaries found")

    if len(binaries) == 1:
        final_binary = binaries[0]
    elif len(binaries) > 1 and goos == "darwin":
        final_binary = binaries_combine_darwin(tmp_dir, binaries)
    else:
        raise SystemExit(f"multiple binaries not supported for os {goos}")

    if shutil.which("upx") and goos != "darwin":
        cmd = ["upx", "--ultra-brute", "--best", str(final_binary)]
        print(f"compressing: {' '.join(cmd)}", file=sys.stderr)
        subprocess.run(cmd, check=True)

    if os.name != "nt":
        final_binary.chmod(0o755)

    return final_binary


def binaries_build(config_settings: dict, target_binaries: str, src_root: Path, out_dir: Path) -> None:
    platform_tag = get_target_platform_name(config_settings)
    if not platform_tag:
        raise SystemExit("wheel build requires --build-option --plat-name <tag>")
    if not shutil.which("go"):
        raise SystemExit(f"failed to find go compiler in PATH")

    goos, goarches = go_platform_from_tag(platform_tag)
    for target_binary in target_binaries:
        binaries: list[Path] = []
        for goarch in goarches:
            binary = binary_go_build(src_root, goos, goarch, target_binary)
            binaries.append(binary)

        final_binary = binaries_finalize(goos, binaries)
        print(f"built: {final_binary}", file=sys.stderr)
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(final_binary, out_dir)

    print(f"output binaries in: {out_dir}", file=sys.stderr)
