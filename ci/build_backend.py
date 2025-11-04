# from setuptools.build_meta import build_wheel as _build_wheel, build_sdist as _build_sdist

# `from ... import *` is intentional and necessary, so that any PEP-517 hooks
# not overridden here are still available to build frontends.
from setuptools import build_meta as build_meta_orig
from setuptools.build_meta import *

# from .download_release import download_binary

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    # download_binary(config_settings or {})
    return build_meta_orig.build_wheel(wheel_directory, config_settings, metadata_directory)
