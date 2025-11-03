#!/usr/bin/env bash
set -euo pipefail

# dirs
mkdir -p gnetcli_server_bin/_bin
mkdir -p ci
mkdir -p .github/workflows
: > README.md

# pyproject.toml
cat > pyproject.toml <<'EOF'
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "ci.build_backend"

[project]
name = "gnetcli-server-bin-py"
version = "0.1.0"
description = "Python shim for a prepackaged gnetcli_server binary."
readme = "README.md"
requires-python = ">=3.9"
authors = [{ name = "Your Name" }]

[tool.setuptools.packages.find]
where = ["."]
include = ["gnetcli_server_bin*"]
EOF

# setup.py to force platform wheel
cat > setup.py <<'EOF'
from setuptools import setup
from setuptools.dist import Distribution

class BinaryDist(Distribution):
    def has_ext_modules(self):
        return True
    def is_pure(self):
        return False

setup(distclass=BinaryDist)
EOF

# runtime package
cat > gnetcli_server_bin/__init__.py <<'EOF'
from ._binary import get_binary_path

__all__ = ["get_binary_path"]

try:
    from importlib.metadata import version
    __version__ = version("gnetcli-server-bin-py")
except Exception:
    __version__ = "0.0.0"
EOF

cat > gnetcli_server_bin/_binary.py <<'EOF'
import os
from importlib.resources import files

def get_binary_path() -> str:
    name = "gnetcli_server.exe" if os.name == "nt" else "gnetcli_server"
    return str(files("gnetcli_server_bin").joinpath("_bin", name))
EOF

# build backend
cat > ci/build_backend.py <<'EOF'
from .download_release import ensure_binary
from setuptools.build_meta import build_wheel as _build_wheel, build_sdist as _build_sdist

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    ensure_binary()
    return _build_wheel(wheel_directory, config_settings, metadata_directory)

def build_sdist(sdist_directory, config_settings=None):
    ensure_binary()
    return _build_sdist(sdist_directory, config_settings)
EOF

# download helper
cat > ci/download_release.py <<'EOF'
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
EOF

# optional workflow
cat > .github/workflows/build.yml <<'EOF'
name: build
on:
  workflow_dispatch: {}

jobs:
  linux-amd64:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install --upgrade pip build
      - run: python -m build
      - run: ls -R gnetcli_server_bin/_bin
EOF

echo "Scaffold created. Now edit ci/download_release.py to set OWNER/REPO."
