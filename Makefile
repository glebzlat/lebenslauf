.PHONY: install-python install-node install vendor-pagedjs vendor compile

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
NPM ?= npm

install-python:
	$(PIP) install -r requirements.txt

install-node:
	$(NPM) install

install: install-python install-node

vendor-pagedjs:
	$(NPM) run vendor:pagedjs

vendor: vendor-pagedjs

compile:
	$(PYTHON) -m compileall lebenslauf scripts
