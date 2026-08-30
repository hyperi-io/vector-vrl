"""Check a Vector config, at two levels.

`validate_config` compiles the VRL inside every `remap` transform in-process,
needing no `vector` binary. It cannot see sources, sinks, wiring, or the
enrichment tables and secret backends Vector registers from its own config.

`validate_config_with_vector` shells out to `vector validate`, which checks all
of that. It needs the binary, and runs it one-shot - never as a daemon.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ConfigCheck",
    "TransformCheck",
    "VectorValidation",
    "validate_config",
    "validate_config_with_vector",
]

# VRL functions this build cannot judge on its own.
#
# The enrichment functions DO compile here, but only against tables registered
# through `register_enrichment_table`. Vector declares its tables in YAML
# outside VRL, so a config naming a table this process was never given is
# unchecked rather than wrong - register the table to have it checked.
_ENRICHMENT = (
    "get_enrichment_table_record",
    "find_enrichment_table_records",
)
# Left out of the default build so caller-supplied VRL cannot read the host or
# reach the network. Present when the crate was built with its `full-stdlib`
# feature, in which case no undefined-function error names them and this list
# is simply never consulted.
_SANDBOXED = (
    "get_env_var",
    "encode_proto",
    "parse_proto",
    "parse_etld",
    "validate_json_schema",
    "get_hostname",
    "get_timezone_name",
    "http_request",
    "dns_lookup",
    "reverse_dns",
)


def _uncompilable_reason(vrl: str, error: str | None) -> str | None:
    """Name why this build cannot check `vrl`, or None if it is a real error."""
    if not error:
        return None

    if "unknown enrichment table" in error:
        used = [fn for fn in _ENRICHMENT if fn in vrl]
        if used:
            return (
                f"uses {', '.join(used)} against an enrichment table this process "
                "has not registered - Vector declares its tables in its own config; "
                "call register_enrichment_table to have this checked"
            )

    if "undefined function" not in error:
        return None
    used = [fn for fn in _SANDBOXED if fn in vrl]
    if used:
        return (
            f"uses {', '.join(used)}, which is deliberately not compiled in so "
            "caller-supplied VRL cannot reach the host or network"
        )
    return None


@dataclass(frozen=True)
class TransformCheck:
    """One `remap` transform's compile result.

    `ok` is False only for VRL this build judged genuinely wrong. VRL this
    build cannot compile at all carries `ok` True and an `unchecked_reason`.
    """

    name: str
    ok: bool
    error: str | None = None
    unchecked_reason: str | None = None


@dataclass(frozen=True)
class ConfigCheck:
    """What compiled, what did not, and what could not be checked."""

    ok: bool
    checked: tuple[TransformCheck, ...]
    skipped: tuple[str, ...]

    @property
    def failures(self) -> tuple[TransformCheck, ...]:
        """Transforms whose VRL failed to compile."""
        return tuple(c for c in self.checked if not c.ok)

    @property
    def unchecked(self) -> tuple[TransformCheck, ...]:
        """Transforms whose VRL this build cannot compile, so cannot judge."""
        return tuple(c for c in self.checked if c.unchecked_reason is not None)


def _load_yaml(text: str) -> Any:
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on the extra
        raise ModuleNotFoundError(
            "Reading a YAML Vector config needs PyYAML: pip install vector-vrl[yaml]"
        ) from exc
    return yaml.safe_load(text)


def _parse(source: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Return the config as a dict, parsing by file suffix when given a path."""
    if isinstance(source, dict):
        return source

    path = Path(source)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        parsed = _load_yaml(text)
    elif suffix == ".toml":
        parsed = tomllib.loads(text)
    elif suffix == ".json":
        parsed = json.loads(text)
    else:
        raise ValueError(
            f"unsupported Vector config format {suffix!r} - expected "
            ".yaml, .yml, .toml or .json"
        )

    if not isinstance(parsed, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return parsed


def validate_config(source: dict[str, Any] | str | Path) -> ConfigCheck:
    """Compile every `remap` transform's VRL in a Vector config.

    Args:
        source: A parsed config dict, or a path to a .yaml/.yml/.toml/.json
            Vector config.

    Returns:
        A ConfigCheck. `ok` is True when every remap transform carrying inline
        `source` VRL compiled. Transforms whose VRL lives in an external file
        (`file:`) are reported in `skipped`, not compiled.

    Raises:
        ValueError: The config format is unsupported, or does not parse to a
            mapping.
        ModuleNotFoundError: A YAML config was given without the `yaml` extra.

    """
    # Imported here, not at module scope, so this module stays importable on a
    # build with no compiled extension (`__init__` degrades to stubs there).
    from ._bindings import validate_vrl

    config = _parse(source)
    transforms = config.get("transforms") or {}
    if not isinstance(transforms, dict):
        raise ValueError("'transforms' is present but is not a mapping")

    checked: list[TransformCheck] = []
    skipped: list[str] = []

    for name, transform in transforms.items():
        if not isinstance(transform, dict) or transform.get("type") != "remap":
            continue
        vrl = transform.get("source")
        if vrl is None:
            # A remap reading its VRL from `file:` - the path is Vector's to
            # resolve, so report it rather than guessing at it.
            skipped.append(str(name))
            continue
        source_text = str(vrl)
        result = validate_vrl(source_text)
        reason = (
            None if result.success else _uncompilable_reason(source_text, result.error)
        )
        checked.append(
            TransformCheck(
                name=str(name),
                ok=result.success or reason is not None,
                error=None if result.success or reason else result.error,
                unchecked_reason=reason,
            )
        )

    return ConfigCheck(
        ok=all(c.ok for c in checked),
        checked=tuple(checked),
        skipped=tuple(skipped),
    )


@dataclass(frozen=True)
class VectorValidation:
    """The result of one `vector validate` run."""

    ok: bool
    returncode: int
    output: str


def validate_config_with_vector(
    path: str | Path,
    *,
    vector_binary: str = "vector",
    no_environment: bool = True,
    deny_warnings: bool = False,
    timeout: float = 60.0,
) -> VectorValidation:
    """Validate a whole Vector config by running `vector validate`.

    Checks everything `validate_config` cannot: sources, sinks, wiring, and the
    VRL that depends on enrichment tables or secret backends declared in the
    config. Vector exits as soon as it has answered - this never starts a
    daemon and never moves data.

    Args:
        path: The Vector config file. Vector detects the format from the name.
        vector_binary: Binary to run, resolved on PATH unless given a path.
        no_environment: Pass `--no-environment`, skipping the component and
            health checks that would open network connections. Turn it off
            only when reaching the configured sinks is the point.
        deny_warnings: Pass `--deny-warnings`, failing on warnings too.
        timeout: Seconds to wait before giving up on the binary.

    Returns:
        A VectorValidation. `output` carries Vector's own report, which names
        the offending component when it fails.

    Raises:
        FileNotFoundError: `vector_binary` is not on PATH.
        subprocess.TimeoutExpired: Vector did not finish within `timeout`.

    """
    exe = shutil.which(vector_binary) or (
        vector_binary if Path(vector_binary).is_file() else None
    )
    if exe is None:
        raise FileNotFoundError(
            f"no {vector_binary!r} binary on PATH - install Vector "
            "(https://vector.dev/docs/setup/installation/) or use "
            "validate_config() for the in-process VRL check instead"
        )

    cmd = [exe, "validate"]
    if no_environment:
        cmd.append("--no-environment")
    if deny_warnings:
        cmd.append("--deny-warnings")
    cmd.append(str(path))

    run = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return VectorValidation(
        ok=run.returncode == 0,
        returncode=run.returncode,
        output=(run.stdout + run.stderr).strip(),
    )
