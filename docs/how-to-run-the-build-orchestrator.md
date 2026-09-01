# How to run the build orchestrator

`build/` is a standalone CLI that drives a three-stage build: Vector core,
then the Rust bindings, then the Python layer. Nothing imports it and it is
not a dependency of the other two components - it is a tool you run, with
its own `pyproject.toml` and `uv.lock`.

You do not need it for ordinary work. `make check` and `maturin develop`
cover day-to-day iteration. Reach for the orchestrator when you want Vector
itself downloaded and compiled from source as part of the chain.

## Running it

```bash
./build/build
```

The launcher creates `build/.venv` and runs `uv sync` on first use, then
executes `build_system.py`. Run it directly if you prefer to manage the
environment yourself:

```bash
uv run --directory build python build_system.py
```

## The flags

There are four, and that is all there are:

```
--clean          Clean artifacts
--verbose, -v    Verbose output
--test-flow      Test build flow without heavy compilation
--skip-vector    Skip Vector build (test stages 2-3 only)
```

`--test-flow` exercises the auto-detection, version discovery and dependency
sync without compiling anything. It is the cheap way to check the
orchestrator is wired up correctly.

`--skip-vector` runs stages 2 and 3 against an already-built Vector. It
exits 1 with `No Vector build found` if there is nothing to skip to.

`--verbose` sets `VECTOR_VRL_VERBOSE=true` in the environment. You can set
that yourself and get the same result.

## --clean deletes your vector/ checkout

`--clean` removes three paths from the REPO ROOT, not from `build/`:
`target`, `.tmp`, and `vector`.

That last one is the upstream Vector clone this orchestrator compiles Vector
from source against. It is gitignored, so nothing warns you and nothing
restores it - after a `--clean` you have to re-clone it before the next run
that needs it. `vector-bindings` itself needs no such checkout; see
[how-to-build-and-test.md](how-to-build-and-test.md).

## What it does when you just run it

`robust_build()` tries the two most recent Vector versions in turn:

1. Checks for an existing Vector build and reuses it unless a rebuild is
   needed. Otherwise downloads and builds Vector core.
2. Syncs dependency versions from Vector's workspace into the bindings
   crate.
3. Builds `vector-bindings`.
4. Builds the Python layer.

The version fallback only applies to upstream compile failures. If a stage
fails for any other reason it stops rather than retrying against an older
Vector, on the grounds that the problem is this repo's code, not upstream's.

Exit code is 0 on success, 1 on failure.

## Its own checks

`build/` is a component like the others, so it gets linted and tested by the
root Makefile:

```bash
make quality-python    # covers vector-vrl and build
make test-python
```
