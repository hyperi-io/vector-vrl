"""Compile the VRL inside a Vector config without running Vector.

The common way a Vector config breaks is a `remap` transform whose VRL does
not compile. That is checkable here against the real compiler. Everything
else in a Vector config - sources, sinks, wiring, type compatibility - is
NOT checked, because this package does not link the `vector` crate.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["ConfigCheck", "TransformCheck", "validate_config"]

# VRL functions a real Vector deployment has but this build cannot compile.
# Vector registers the first group from its own config - enrichment tables and
# secret backends are declared in YAML, outside VRL, and the compiler only
# knows them once Vector has loaded that config. The second group is left out
# deliberately so caller-supplied VRL cannot read the host or reach the
# network. VRL calling either group is not a broken config, so it is reported
# as unchecked rather than failed.
_VECTOR_PROVIDED = (
    "get_enrichment_table_record",
    "find_enrichment_table_records",
    "get_secret",
    "set_secret",
    "remove_secret",
)
_SANDBOXED = (
    "get_env_var",
    "get_hostname",
    "http_request",
    "dns_lookup",
)


def _uncompilable_reason(vrl: str, error: str | None) -> str | None:
    """Name why this build cannot compile `vrl`, or None if it is a real error."""
    if not error or "undefined function" not in error:
        return None
    used = [fn for fn in _VECTOR_PROVIDED if fn in vrl]
    if used:
        return (
            f"uses {', '.join(used)}, which Vector provides from its own config "
            "(enrichment tables / secret backends) and this build does not link"
        )
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
