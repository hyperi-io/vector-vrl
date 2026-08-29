# Contributing

One repo, three components that build separately. Read
[ARCHITECTURE.md](ARCHITECTURE.md) before you start - the thing that
catches people out is that there is no single venv or `pip install -e .`
covering the tree.

Two audiences, two paths.

## External contributors - the short path

You do NOT need `hyperi-ci` or any repo-local git hooks. Standard tooling
is enough.

1. Fork, clone your fork, branch off `main`.
2. Change the component you care about, and test it from inside that
   component's directory. See
   [docs/how-to-build-and-test.md](docs/how-to-build-and-test.md) for the
   per-component commands.
3. Commit however your workflow does it. Open a PR against `main`.

Lint config lives in each component's manifest (`vectordotdev/pyproject.toml`
for ruff, `vector-bindings/clippy.toml` and `rustfmt.toml` for the Rust
side), so your editor picks it up without extra setup.

### What happens to your PR's CI checks

PRs from forks deliberately do not trigger this repo's full pipeline. You
will see green checks because every job was SKIPPED, not because it ran and
passed. A maintainer pulls your PR locally and validates it against the real
pipeline. That keeps CI credentials and self-hosted runners away from
fork-originated workflows, which is the standard GitHub-side recommendation.

If a maintainer asks for changes, push to the same branch on your fork and
they will re-validate.

## Maintainers - the strict path

Each component carries its own commit-msg/pre-push hooks
(`vectordotdev/.githooks/`, `vector-bindings/.githooks/`, `build/.githooks/`
- there is no single root `.githooks/`). Point git at the one for the
component you are working in:

```bash
git config core.hooksPath vectordotdev/.githooks   # or vector-bindings/, build/
```

Then:

1. Land changes on `main` via PR or direct push - your call. `git push`
   works as normal, nothing wraps it.
2. To publish `vectordotdev` to PyPI, push to `main` with a `Publish: true`
   trailer on the HEAD commit message (or trigger the workflow manually via
   `workflow_dispatch`). `.github/workflows/ci.yml`'s `plan` job checks for
   that trailer and gates the `publish-vectordotdev` job on it - every other
   push only runs quality + test.

## Before you push

From the repo root:

```bash
make check     # quality + test across all three components
```

`make check` is `make quality` then `make test`, and each of those fans out
to `hyperi-ci run <stage> -C <component>`. The cross-component fan-out in the
root `Makefile` is the only bespoke part - hyperi-ci has no multi-component
repo model, so the Makefile supplies one. The checks themselves are
hyperi-ci's own.

You can run a single side while iterating:

```bash
make quality-rust      # vector-bindings
make quality-python    # vectordotdev + build
make test-rust
make test-python
```

## Which component am I touching

- `vector-bindings/` - Rust. Everything the Python package can actually do
  is defined in `src/lib.rs`. Change a signature here and you have changed
  the public API, so update
  [docs/reference-python-api.md](docs/reference-python-api.md) in the same
  commit.
- `vectordotdev/` - the Python package that ships to PyPI. Building it
  compiles the Rust crate, because `pyproject.toml` points maturin at
  `../vector-bindings/Cargo.toml`.
- `build/` - a standalone orchestration CLI with its own `pyproject.toml`
  and `uv.lock`. Nothing imports it. See
  [docs/how-to-run-the-build-orchestrator.md](docs/how-to-run-the-build-orchestrator.md).

Never edit anything under `vector/`. It is an upstream checkout, read-only,
and not tracked in this repo.

## Tests

No mocks. Tests run against the compiled bindings or a real Vector
subprocess, never a stub. If you are adding coverage for the bindings, the
model to copy is `vectordotdev/tests/unit/test_vector_class.py` - it asserts
observed behaviour, and where behaviour is known-wrong it asserts the SHAPE
and says why rather than enshrining the wrong values.

A test that needs the compiled `.so` should skip cleanly without it:

```python
pytest.importorskip("vectordotdev._bindings")
```

## Commit messages

Maintainers follow Conventional Commits and the hooks enforce it. External
contributors do not need to - the maintainer merging your PR rewrites the
merge commit as needed.

## Security disclosures

Do NOT open a public issue or PR for a security vulnerability. Use the
repository's `SECURITY.md` if present, or the organisation's security
contact.

This crate compiles and runs VRL text supplied by its caller, so anything
that widens what that VRL can reach is a security change, not a feature.
The reasoning and the current restrictions are in ARCHITECTURE.md under
"VRL execution's security posture". Read it before touching the `vrl`
dependency's feature list.
