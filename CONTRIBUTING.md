# Contributing

One repo, three components that build separately. Read [docs/architecture.md](docs/architecture.md) before you start: no single venv or `pip install -e .` covers the tree, and that's what catches people out.

## External contributors

You don't need `hyperi-ci` or the repo's git hooks. Standard tooling is enough.

1. Fork, clone your fork, branch off `main`.
2. Change the component you care about, and test it from inside that component's directory. [docs/how-to-build-and-test.md](docs/how-to-build-and-test.md) has the per-component commands.
3. Open a PR against `main`. Your commit messages needn't follow Conventional Commits: the maintainer merging the PR rewrites the merge commit as needed.

Lint config sits in each component's manifest (`vector-vrl/pyproject.toml` and `build/pyproject.toml` for ruff, `vector-bindings/clippy.toml` and `rustfmt.toml` for Rust), so your editor picks it up with no extra setup.

A PR from a fork runs the commit-message check and skips every other job, so most ticks on it are skipped jobs. That keeps CI credentials and runners away from fork-originated workflows. A maintainer pulls the PR and validates it against the full pipeline. If they ask for changes, push to the same branch on your fork.

## Maintainers

Each component has commit-msg and pre-push hooks, in `vector-vrl/.githooks/`, `vector-bindings/.githooks/` and `build/.githooks/`. There's no root `.githooks/`. The hooks enforce Conventional Commits. Point git at the one for the component you're working in:

```bash
git config core.hooksPath vector-vrl/.githooks   # or vector-bindings/, build/
```

To publish `vector-vrl` to PyPI, push to `main` with a `Release: true` trailer on the HEAD commit, or run the workflow by hand through `workflow_dispatch`. The `plan` job in `.github/workflows/ci.yml` reads the trailer and gates the `tag-and-release` job on it. Every other push runs quality and test and stops there.

## Tests

No mocks. Tests run against the compiled bindings or a `vector` subprocess, never a stub. For bindings coverage, the model to copy is `vector-vrl/tests/unit/test_vector_class.py`, which asserts observed behaviour through the compiled extension. [vector-vrl/tests/README.md](vector-vrl/tests/README.md) maps the suite.

A test that needs the compiled `.so` should skip cleanly without it:

```python
pytest.importorskip("vector_vrl._bindings")
```

## Security disclosures

Don't open a public issue or PR for a vulnerability. Report it privately from the repository's Security tab, under "Report a vulnerability".

This crate compiles and runs VRL text its caller supplies, so anything that widens what that VRL can reach is a security change. Read [What caller-supplied VRL cannot reach](docs/architecture.md#what-caller-supplied-vrl-cannot-reach) before touching the `vrl` dependency's feature list.

## Context

### What this is

One PyPI wheel built from a three-component checkout. The repo and the package share a name, which misleads: `vector-vrl/` is one directory of three, and the Rust crate beside it does the compiling. It's VRL the language with no sources/transforms/sinks pipeline, and `Vector`'s `config` argument is stored, never applied. Nor is it a wrapper around a Vector checkout: `vector-bindings` pulls the `vrl` crate from git and reads no local Vector source.

### Where things live

| Path | What it holds |
|---|---|
| `vector-bindings/` | Rust crate (PyO3) that compiles and runs VRL. `src/lib.rs` is the Python API, `enrichment.rs` and `secrets.rs` add the VRL functions the `vrl` crate lacks, `nesting.rs` is the bracket guard. A signature change here changes the public API, so update [docs/reference-python-api.md](docs/reference-python-api.md) in the same commit |
| `vector-vrl/` | The package that ships to PyPI. maturin builds it, not setuptools |
| `build/` | Tooling run in place, never imported: the `./build/build` orchestrator, `vector_pin.py` for the Vector test pin, `wheel_smoke_check.py` for CI's installed-wheel check, and `vrl-examples-probe/`, which dumps VRL's upstream examples for the tests |
| `Makefile` | The one thing the root is a working directory for |
| `docs/` | Architecture, building and testing, the orchestrator, the Python API reference |

There's no manifest at the root, just the three below it ([issue #22](https://github.com/hyperi-io/vector-vrl/issues/22)). Never edit anything under `vector/`: it's an upstream checkout the orchestrator downloads, gitignored.

### Commands that prove a change

```bash
make check      # quality + test, all three components
make quality    # lint and format
make test       # tests
make build      # the vector-vrl wheel
```

The narrower targets are `quality-rust`, `quality-python`, `test-rust` and `test-python`. Each wraps `uv run --directory <component> --with hyperi-ci hyperi-ci run <stage> -C .`, since hyperi-ci has no multi-component repo model. `.github/workflows/ci.yml` calls the same targets, one job per language, rather than hyperi-ci's reusable workflow, which assumes the checkout root is the project and has no wheel matrix.

A local passing run can mislead three ways, all silent:

- The gitignored `.so` under `vector-vrl/src/vector_vrl/_bindings/` isn't rebuilt when the Rust changes, and tests needing it `importorskip` out of the run when it's missing.
- Tests using the `vector_runner` fixture fall back from a local binary to docker to a skip, and the integration tests skip with no `vector` on PATH. Under `$CI` either skip is a failure, and CI installs the version pinned in `vector-vrl/tests/conftest.py`.
- The wheel smoke check skips the cross-built macOS x86_64 leg.

Detail: [docs/how-to-build-and-test.md](docs/how-to-build-and-test.md).

### What tends to bite

| Don't | Do | Why |
|---|---|---|
| Edit `lib.rs`, then run the Python tests | `maturin develop --release` in `vector-bindings/` first | The tree's `.so` is stale and gives the old behaviour with no warning |
| `pip install .` in `vector-vrl/` | `maturin build --release` | `manifest-path` points at `../vector-bindings/Cargo.toml`, so installing compiles the crate |
| A bare `uvx hyperi-ci` at the root | The `make` targets | It resolves pytest against PATH, not the component's venv. Dies on `unrecognized arguments: --cov=...`, or reports 0% from the wrong directory |
| A Python fenced block in either README as illustration | Runnable code | `vector-vrl/tests/unit/test_readme_examples.py` executes every Python block in both READMEs, skipping `>>>` transcripts |
| Run `./build/build`, then commit everything | Read `git diff vector-bindings/Cargo.toml` first | Its dependency sync rewrites the `serde_json` line to the version in Vector's workspace |
| Trust the `# vX.Y.Z` comment on a pinned action SHA | `gh api repos/<owner>/<repo>/commits/<sha>` | Nothing checks the comment against the SHA |

### Where this sits

Inbound: hyperi-io/scalo-py, because `build/pyproject.toml` declares `scalo[http]` with a floor and no ceiling. That's the build tooling's dependency alone, since the published wheel has no runtime dependencies. With no ceiling, a scalo major lands here unopposed.

Outbound: nothing in HyperI's suite graph consumes this repo. Changes reach consumers through PyPI.

The two upstreams that matter most are not suite members. `vector-bindings/Cargo.toml` tracks vectordotdev/vrl at branch `main`, and the test binary is a vectordotdev/vector release (the release tarball in CI, the `timberio/vector` image locally when there's no binary on PATH).
