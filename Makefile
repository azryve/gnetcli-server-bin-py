SHELL := /bin/sh

all: sdist wheels

sdist:
	python3 -m build --sdist

wheels:
	@git clean -fxd --exclude NOTES --exclude dist/
	python3 -m build -C=--build-option=--plat-name -C=--build-option=manylinux_2_17_x86_64

	@git clean -fxd --exclude NOTES --exclude dist/
	python3 -m build -C=--build-option=--plat-name -C=--build-option=manylinux_2_17_aarch64

	@git clean -fxd --exclude NOTES --exclude dist/
	python3 -m build -C=--build-option=--plat-name -C=--build-option=macosx_11_0_x86_64

	@git clean -fxd --exclude NOTES --exclude dist/
	python3 -m build -C=--build-option=--plat-name -C=--build-option=macosx_11_0_arm64

	@git clean -fxd --exclude NOTES --exclude dist/

clean:
	@git clean -fxd --exclude NOTES

test:
	@set -eu; \
	echo Build venv; \
	tmpdir=$$(mktemp -d); \
	curdir=$(CURDIR); \
	python3 -mvenv "$$tmpdir"; \
	echo Install wheel; \
	cd "$$tmpdir/"; \
	"$$tmpdir/bin/python" -m pip install -qqq --no-index -f "$$curdir/dist" gnetcli_server_bin; \
	echo Test calling binary; \
	"$$tmpdir/bin/python" -m gnetcli_server_bin -help 2>&1 | grep -q conf-file; \
	echo OK

.PHONY: all sdist wheels clean test
