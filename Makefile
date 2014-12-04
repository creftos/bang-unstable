SHELL := /bin/bash
HERE := $(shell cd $(dir $(lastword $(MAKEFILE_LIST))); /bin/pwd)/
DIST_DIR := $(HERE)dist/
BANG_PKG_DIR := $(HERE)bang/
VERSION := $(shell cut -d "'" -f 2 $(BANG_PKG_DIR)version.py)
BANG_TAR_GZ := $(DIST_DIR)bang-$(VERSION).tar.gz

ifndef V
  q := @
  out := &>/dev/null
endif

venv_run := $(q)cd $(HERE); . activate-bang;
setup_py := $(venv_run) ./setup.py

default: sdist

.PHONY: sdist upload clean

sdist: $(BANG_TAR_GZ)
$(BANG_TAR_GZ):
	$(setup_py) sdist $(o)

upload: $(BANG_TAR_GZ)
	$(setup_py) upload $(o)

clean:
	$(q)cd $(HERE); find . -name *.pyc | xargs rm -f $(o)
	$(q)rm -rf $(DIST_DIR) $(o)
