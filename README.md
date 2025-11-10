# gnetcli-server-bin

Prebuilt/binary wheels for **gnetcli_server**.

This package exists as a convenience layer: instead of building the native parts of `cmd/gnetcli_server` from [source](https://github.com/annetutil/gnetcli/tree/main/cmd/gnetcli_server) on install, this shim distributes ready-made wheels for common platforms.


The upstream repo: https://github.com/annetutil/gnetcli.


## Installation

```bash
pip install gnetcli-server-bin
```

If a wheel is available for your platform, the install should be fast and should **not** require a compiler or system headers.

If installed from sdist it requires go compiler to be available in PATH.


## Usage

### Install into venv


```
$ /tmp/venv/bin/python3
>>> import gnetcli_server_bin
>>> gnetcli_server_bin.get_binary_path()
'/tmp/venv/lib/python3.12/site-packages/gnetcli_server_bin/_bin/gnetcli_server'
```

### Run from shell

```
$ /tmp/venv/bin/gnetcli-server-bin -h
Usage of /tmp/venv/lib/python3.12/site-packages/gnetcli_server_bin/_bin/gnetcli_server:
  -basic-auth string
...
```
