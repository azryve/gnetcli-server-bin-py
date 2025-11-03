from .download_release import ensure_binary
from setuptools.build_meta import build_wheel as _build_wheel, build_sdist as _build_sdist

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    ensure_binary()
    return _build_wheel(wheel_directory, config_settings, metadata_directory)

def build_sdist(sdist_directory, config_settings=None):
    ensure_binary()
    return _build_sdist(sdist_directory, config_settings)
