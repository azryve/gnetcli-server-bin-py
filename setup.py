from setuptools import setup
from setuptools.dist import Distribution

class BinaryDist(Distribution):
    def has_ext_modules(self):
        return True
    def is_pure(self):
        return False

setup(distclass=BinaryDist)
