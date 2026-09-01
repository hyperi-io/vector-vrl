"""The hand-written stub matches the compiled extension it describes.

`_bindings/vector_bindings.pyi` cannot be generated from pyo3, so this parses
it and compares it with the loaded `.so`: the same `__all__`, the same public
names, the same members on each class, and for every function and method the
same parameter names in the same order with defaults in the same places. A
signature change in lib.rs that is not mirrored in the stub fails here.

Out of scope, because pyo3 exposes none of it at runtime: argument
annotations, return types, property types and TypedDict fields.
"""

import ast
import inspect
from pathlib import Path

import pytest

bindings = pytest.importorskip("vector_vrl._bindings.vector_bindings")

STUB = Path(bindings.__file__).with_name("vector_bindings.pyi")


def _public(names) -> list[str]:
    return sorted(n for n in names if not n.startswith("_"))


def _stub_module() -> ast.Module:
    return ast.parse(STUB.read_text(encoding="utf-8"), filename=str(STUB))


def _stub_top_level(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.ClassDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
    }


def _stub_all(tree: ast.Module) -> list[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            return sorted(ast.literal_eval(node.value))
    raise AssertionError("the stub declares no __all__")


def _stub_params(fn: ast.FunctionDef, *, drop_self: bool) -> list[tuple[str, bool]]:
    """Parameter names paired with whether each carries a default."""
    positional = list(fn.args.posonlyargs) + list(fn.args.args)
    if drop_self and positional and positional[0].arg == "self":
        positional = positional[1:]
    padding: list[ast.expr | None] = [None] * (len(positional) - len(fn.args.defaults))
    defaults = padding + list(fn.args.defaults)
    return [
        (arg.arg, default is not None)
        for arg, default in zip(positional, defaults, strict=True)
    ]


def _runtime_params(obj) -> list[tuple[str, bool]]:
    return [
        (param.name, param.default is not inspect.Parameter.empty)
        for param in inspect.signature(obj).parameters.values()
        if param.name != "self"
    ]


def _is_property(fn: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Name) and decorator.id == "property"
        for decorator in fn.decorator_list
    )


def test_stub_all_matches_the_modules_all():
    """`import *` obeys `__all__`, so the two lists must agree exactly."""
    assert _stub_all(_stub_module()) == sorted(bindings.__all__)


def test_stub_defines_exactly_the_modules_public_names():
    assert _public(_stub_top_level(_stub_module())) == _public(dir(bindings))


@pytest.mark.parametrize("name", _public(dir(bindings)))
def test_each_export_matches_its_stub(name):
    node = _stub_top_level(_stub_module())[name]
    runtime = getattr(bindings, name)

    if inspect.isroutine(runtime):
        assert isinstance(node, ast.FunctionDef), f"{name} is a function at runtime"
        assert _stub_params(node, drop_self=False) == _runtime_params(runtime)
        return

    assert inspect.isclass(runtime), f"{name} is neither a function nor a class"
    assert isinstance(node, ast.ClassDef), f"{name} is a class at runtime"
    members = {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}
    assert _public(members) == _public(dir(runtime))

    init = members.get("__init__")
    if init is not None:
        assert _stub_params(init, drop_self=True) == _runtime_params(runtime)

    for member_name in _public(members):
        stub_member = members[member_name]
        runtime_member = getattr(runtime, member_name)
        if _is_property(stub_member):
            assert inspect.isgetsetdescriptor(runtime_member), (
                f"{name}.{member_name} is not a read-only attribute at runtime"
            )
            continue
        assert inspect.isroutine(runtime_member), (
            f"{name}.{member_name} is not a method"
        )
        assert _stub_params(stub_member, drop_self=True) == _runtime_params(
            runtime_member
        )
