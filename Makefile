# Local pre-push checks and .github/workflows/ci.yml both call these targets.
# Each wraps `hyperi-ci run <stage> -C <dir>` per component - hyperi-ci has no
# multi-component repo model, so only this cross-component orchestration is
# bespoke; the quality/test/build checks themselves are hyperi-ci's own.
HYPERCI := uvx hyperi-ci

.PHONY: check quality test build quality-rust quality-python test-rust test-python

check: quality test

quality: quality-rust quality-python

quality-rust:
	$(HYPERCI) run quality -C vector-bindings

quality-python:
	$(HYPERCI) run quality -C vectordotdev
	$(HYPERCI) run quality -C build

test: test-rust test-python

test-rust:
	$(HYPERCI) run test -C vector-bindings

test-python:
	$(HYPERCI) run test -C vectordotdev
	$(HYPERCI) run test -C build

build:
	$(HYPERCI) run build -C vectordotdev
