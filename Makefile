# The targets and why they wrap uv run: CONTRIBUTING.md, Context.
# --directory is uv's flag and moves the process first, so -C is `.`, never the directory again.

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
