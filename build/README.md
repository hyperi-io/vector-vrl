# vector-vrl build tooling

Build system for vector-vrl.

Tooling run in place from the repo root, with a separate venv, never imported by the other two components.

| File | What it does |
|---|---|
| `build`, `build_system.py` | The build orchestrator: compile Vector, then `vector-bindings`, then the Python layer. See [docs/how-to-run-the-build-orchestrator.md](../docs/how-to-run-the-build-orchestrator.md) |
| `vector_pin.py` | Checks and updates the Vector release the tests run against (`_VECTOR_TAG` in `vector-vrl/tests/conftest.py`). The daily `vector-auto-update.yml` workflow runs it |
| `wheel_smoke_check.py` | Installs a built wheel into a throwaway venv and runs VRL through it. CI runs it on every wheel it can execute |
| `vrl-examples-probe/` | Prints every VRL stdlib function's upstream examples as JSON, the source of `vector-vrl/tests/data/vrl_examples.json` |

The daily workflow skips any Vector release under 7 days old. It tries a newer one with `make check` before touching git, then pushes a `vector-bump/<version>` branch and opens a PR, one at a time. It pushes with the default `GITHUB_TOKEN`, so the PR's CI waits until someone with write access selects "Approve workflows to run". It needs the repo setting "Allow GitHub Actions to create and approve pull requests".

```bash
./build/build --help
```
