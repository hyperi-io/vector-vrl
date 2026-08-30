# Local pre-push checks and .github/workflows/ci.yml both call these targets.
# Each wraps `hyperi-ci run <stage> -C <dir>` per component - hyperi-ci has no
# multi-component repo model, so only this cross-component orchestration is
# bespoke; the quality/test/build checks themselves are hyperi-ci's own.
#
# `uv run --directory <dir> --with hyperi-ci hyperi-ci run <stage> -C .`, not
# a bare `uvx hyperi-ci`: the bare form resolves pytest/coverage against
# whatever's on PATH rather than the target component's own venv and test
# dependencies, and fails outright ("unrecognized arguments: --cov=...", or
# silently measures 0% coverage from the wrong working directory). `uv run`'s
# `--directory` MUST come before `--with hyperi-ci hyperi-ci` on the command
# line (it is a `uv run` flag, not a `hyperi-ci` one) and relocates the
# process there first, so `-C` becomes `.` - a second `-C <dir>` on top of
# `--directory <dir>` looks for a nested `<dir>/<dir>` that does not exist
# and hyperi-ci reports "could not detect project language" instead of
# running anything.

.PHONY: check quality test build quality-rust quality-python test-rust test-python

check: quality test

quality: quality-rust quality-python

quality-rust:
	uv run --directory vector-bindings --with hyperi-ci hyperi-ci run quality -C .

quality-python:
	uv run --directory vector-vrl --with hyperi-ci hyperi-ci run quality -C .
	uv run --directory build --with hyperi-ci hyperi-ci run quality -C .

test: test-rust test-python

test-rust:
	uv run --directory vector-bindings --with hyperi-ci hyperi-ci run test -C .

test-python:
	uv run --directory vector-vrl --with hyperi-ci hyperi-ci run test -C .
	uv run --directory build --with hyperi-ci hyperi-ci run test -C .

build:
	uv run --directory vector-vrl --with hyperi-ci hyperi-ci run build -C .
