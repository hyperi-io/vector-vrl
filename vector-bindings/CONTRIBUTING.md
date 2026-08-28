# Contributing to vector-bindings

Two audiences, two paths.

## External contributors - the short path

**You do NOT need to install `hyperi-ci` or activate any
repo-local git hooks.** Standard tooling is enough.

1. Fork the repository, clone your fork, create a topic branch.
2. Make your change. Run the project's tests with whatever the
   language ecosystem provides (`pytest`, `cargo test`,
   `npm test`, `go test ./...`). Lint via the standard tools
   the project declares in its manifest (`ruff`, `clippy`,
   `eslint`, `golangci-lint`, etc.). The project's pyproject /
   Cargo.toml / package.json carries the lint config; your IDE
   picks it up without further setup.
3. Commit with whatever message format your workflow uses.
   Open a PR against `main`.

**What happens to your PR's CI checks:**

PRs from forks intentionally do not auto-trigger this repo's
full CI pipeline. You will see green checks because all jobs
are skipped, not because they ran and passed. A maintainer
will pull your PR locally to validate it against the full
pipeline. This avoids exposing internal CI credentials and
self-hosted runners to fork-originated workflows, which is the
standard GitHub-side security recommendation.

If a maintainer requests changes, push to the same branch on
your fork. They will re-validate.

## Maintainers - the strict path

Maintainers opt in to the project's stricter tooling:

```bash
# install the CLI
uv tool install hyperi-ci          # or: pipx install hyperi-ci

# activate the repo-local git hooks (commit-msg validation +
# pre-push enforcement of `hyperi-ci push` over bare `git push`)
git config core.hooksPath .githooks

# verify
hyperi-ci --version
hyperi-ci check                    # quality + test, pre-push gate
```

Maintainer workflow:

1. Land changes on `main` via PR or direct push (your call).
2. `hyperi-ci push` instead of `git push`. The pre-push hook
   enforces this; bypass with `HYPERCI_PUSH=1 git push` if you
   know what you are doing.
3. `hyperi-ci push --publish` when you want to ship a release.
   Amends a `Publish: true` trailer to HEAD; the CI pipeline
   picks that up, predicts the next version, stamps it, and
   publishes.

## What happens when you push commits to your fork

Nothing on this repo's side. Your fork has its own GitHub
Actions context; this repo's workflows are not triggered until
you open a PR. Your fork's own CI (if you enabled it) runs in
your namespace.

## Commit message conventions

Maintainers follow Conventional Commits and the hooks enforce
it. External contributors do not need to follow this format --
the maintainer who merges your PR rewrites the merge commit
as needed.

## Security disclosures

Do NOT open a public issue or PR for security vulnerabilities.
See the repository's `SECURITY.md` (if present) or the
organisation's security contact for the disclosure process.
