
all: sdist wheels

sdist:
	python3 -m build --sdist

wheels:
	python3 -m build --wheel -C=--build-option=--plat-name -C=--build-option=manylinux_2_17_x86_64
	python3 -m build --wheel -C=--build-option=--plat-name -C=--build-option=macosx_11_0_universal2

clean:
	@rm -r build/ 2> /dev/null || true
	@rm -r dist/ 2> /dev/null  || true
	@rm gnetcli_server_bin/_bin/gnetcli_server 2> /dev/null || true

.PHONY: all sdist wheels clean
