.PHONY: help test install uninstall preview clean

help:  ## Show this help
	@grep -E '^[a-z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

test:  ## Run the test suite (pytest)
	python -m pytest tests/ -v

install:  ## Install the plugin into GIMP (auto-detects location)
	./install.sh

uninstall:  ## Remove the plugin from GIMP
	./install.sh --uninstall

preview:  ## Launch the standalone preview (pass SKIN=path.png)
	python standalone_preview.py $(SKIN)

clean:  ## Delete __pycache__ and .pyc files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name '*.pyc' -delete 2>/dev/null; true
