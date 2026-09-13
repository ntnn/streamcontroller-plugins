GIT ?= git
UPSTREAM_URL := https://github.com/StreamController/StreamController
UPSTREAM := upstream
VENV := $(UPSTREAM)/.venv
DATA := $(UPSTREAM)/data
INSTALL_DIR := $(HOME)/.var/app/com.core447.StreamController/data/plugins
PLUGINS := $(notdir $(wildcard plugins/*))

.PHONY: setup
setup: ##@ Clone StreamController and set up its venv for local testing.
	test -d $(UPSTREAM) || $(GIT) clone $(UPSTREAM_URL) $(UPSTREAM)
	test -d $(VENV) || python -m venv $(VENV)
	$(VENV)/bin/pip install -r $(UPSTREAM)/requirements.txt pytest
	mkdir -p $(DATA)/plugins

.PHONY: build
build: ##@ Symlink plugins into the dev instance's data dir for live editing.
	mkdir -p $(DATA)/plugins
	for p in $(PLUGINS); do \
		rm -rf $(DATA)/plugins/$$p; \
		ln -s $(CURDIR)/plugins/$$p $(DATA)/plugins/$$p; \
	done

.PHONY: test
test: ##@ Run unit tests for plugin logic modules.
	$(VENV)/bin/python -m pytest plugins

.PHONY: run
run: build ##@ Run StreamController from source against the dev data dir.
	cd $(UPSTREAM) && .venv/bin/python main.py --data data

.PHONY: install
install: ##@ Copy plugins into the Flatpak install's plugin dir.
	mkdir -p $(INSTALL_DIR)
	for p in $(PLUGINS); do \
		rm -rf $(INSTALL_DIR)/$$p; \
		cp -r plugins/$$p $(INSTALL_DIR)/; \
	done

.PHONY: help
help: ##@ Print help
	@awk 'BEGIN { fs="##@ " } { FS=fs } /:.*##@/ { doc=$$2; FS=":"; $$0=$$0; printf "%s: %s\n", $$1, doc; }' $(MAKEFILE_LIST) | grep -v fs=
