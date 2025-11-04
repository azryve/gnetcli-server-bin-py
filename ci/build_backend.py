from setuptools.build_meta import build_wheel as _build_wheel, build_sdist as _build_sdist
from .download_release import download_binary

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    download_binary(config_settings or {})
    return _build_wheel(wheel_directory, config_settings, metadata_directory)

def build_sdist(sdist_directory, config_settings=None):
    download_binary(config_settings or {})
    return _build_sdist(sdist_directory, config_settings)
