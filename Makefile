
all: sdist wheels

sdist:
	python3 -m build --sdist

wheels:
	python3 -m build --wheel -C=--build-option=--plat-name -C=--build-option=manylinux_2_17_x86_64
	python3 -m build --wheel -C=--build-option=--plat-name -C=--build-option=macosx_10_9_x86_64

.PHONY: all sdist wheels
