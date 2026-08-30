#!/usr/bin/env python3
"""
Basic VRL function tests for vector-rs.
Tests core VRL functionality without requiring full Vector build.
"""

import os
import sys

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_vrl_expressions():
    """Test basic VRL expressions."""

    # Mock VRL checker for testing purposes if vector module isn't available
    try:
        import vector

        vrl_check = vector.vrl_check
        vrl_functions = vector.vrl_functions
        has_vector = True
    except ImportError:
        print("Vector module not available, using mock VRL checker")
        has_vector = False

        def vrl_check(expr):
            """Mock VRL checker for basic syntax validation."""
            # Basic syntax checks
            if not expr.strip():
                return False
            if expr.count("(") != expr.count(")"):
                return False
            if expr.count("{") != expr.count("}"):
                return False
            if expr.count("[") != expr.count("]"):
                return False

            # Check for obvious syntax errors
            invalid_patterns = [
                "invalid syntax",
                " +$",  # Incomplete operators
                " =$",  # Incomplete assignments
                "unknown_func",
                "parse_nonexistent",
            ]

            for pattern in invalid_patterns:
                if pattern in expr:
                    return False

            return True

        def vrl_functions():
            """Mock VRL functions list."""
            return [
                "now",
                "uuid_v4",
                "del",
                "parse_json",
                "to_string",
                "to_int",
                "upcase",
                "downcase",
                "strip_whitespace",
                "replace",
                "split",
                "join",
                "push",
                "pop",
                "length",
                "get",
                "contains",
                "format_timestamp",
                "parse_timestamp",
                "parse_int",
                "is_string",
                "is_integer",
                "is_array",
                "is_object",
                "type",
            ]

    print(f"Testing VRL Expressions ({'Real Vector' if has_vector else 'Mock Mode'})")
    print("=" * 50)

    # Basic valid expressions
    valid_expressions = [
        ". = .message",
        '.level = "INFO"',
        ".timestamp = now()",
        "now()",
        "uuid_v4()",
        "del(.field)",
        "del(.password)",
        "parse_json!(.message)",
        ".parsed = parse_json(.message) ?? {}",
        'if .level == "ERROR" { .alert = true }',
        '.status = if .code == 200 { "ok" } else { "error" }',
        ".processed = true",
        ".enriched = false",
    ]

    valid_count = 0
    for expr in valid_expressions:
        try:
            result = vrl_check(expr)
            status = "" if result else ""
            print(f"{status} {expr}")
            if result:
                valid_count += 1
        except Exception as e:
            print(f"{expr} - {type(e).__name__}: {e}")

    print(f"\n{valid_count}/{len(valid_expressions)} expressions validated")
    return valid_count, len(valid_expressions)


def test_vrl_functions_availability():
    """Test VRL functions availability."""

    try:
        import vector

        functions = vector.vrl_functions()
        has_vector = True
    except ImportError:
        # Mock function list
        functions = [
            "now",
            "uuid_v4",
            "del",
            "parse_json",
            "to_string",
            "to_int",
            "upcase",
            "downcase",
            "strip_whitespace",
            "replace",
            "split",
            "join",
            "push",
            "pop",
            "length",
            "get",
            "contains",
            "format_timestamp",
            "parse_timestamp",
            "parse_int",
            "is_string",
            "is_integer",
            "is_array",
            "is_object",
            "type",
        ]
        has_vector = False

    print(f"\nVRL Functions ({'Real Vector' if has_vector else 'Mock Mode'})")
    print("=" * 50)
    print(f"Total functions available: {len(functions)}")

    # Test key function categories
    expected_functions = {
        "Core": ["now", "uuid_v4", "del", "type"],
        "Parsing": ["parse_json", "parse_timestamp", "parse_int"],
        "String": ["upcase", "downcase", "strip_whitespace", "replace"],
        "Array": ["push", "pop", "length", "get", "contains"],
        "Type Conversion": ["to_string", "to_int", "to_float"],
        "Validation": ["is_string", "is_integer", "is_array", "is_object"],
    }

    total_found = 0
    total_expected = 0

    for category, expected in expected_functions.items():
        found = [f for f in expected if f in functions]
        total_found += len(found)
        total_expected += len(expected)
        print(f"{category}: {len(found)}/{len(expected)} - {found}")

    print(f"\nOverall: {total_found}/{total_expected} expected functions found")
    return len(functions), total_found, total_expected


def test_invalid_vrl_detection():
    """Test that invalid VRL expressions are properly detected."""

    try:
        import vector

        vrl_check = vector.vrl_check
        has_vector = True
    except ImportError:
        has_vector = False

        def vrl_check(expr):
            """Mock VRL checker."""
            invalid_patterns = [
                "invalid syntax",
                " +$",
                " =$",
                "unknown_func",
                "parse_nonexistent",
            ]

            for pattern in invalid_patterns:
                if pattern in expr:
                    return False

            # Check bracket matching
            if (
                expr.count("(") != expr.count(")")
                or expr.count("{") != expr.count("}")
                or expr.count("[") != expr.count("]")
            ):
                return False

            return True

    print(
        f"\nTesting Invalid VRL Detection ({'Real Vector' if has_vector else 'Mock Mode'})"
    )
    print("=" * 50)

    invalid_expressions = [
        "invalid syntax",
        ". = .field +",
        "parse_nonexistent(.field)",
        ".bad = unknown_func(.data)",
        "if .condition {",
        ".field =",
    ]

    detected_invalid = 0
    for expr in invalid_expressions:
        try:
            result = vrl_check(expr)
            if result:
                print(f"{expr} - Unexpectedly valid")
            else:
                print(f"{expr} - Correctly detected as invalid")
                detected_invalid += 1
        except Exception as e:
            print(f"{expr} - Correctly rejected: {type(e).__name__}")
            detected_invalid += 1

    print(
        f"\n{detected_invalid}/{len(invalid_expressions)} invalid expressions detected"
    )
    return detected_invalid, len(invalid_expressions)


def run_all_tests():
    """Run all VRL tests and return summary."""

    print("VRL Function Testing Suite")
    print("=" * 50)

    # Run tests
    valid_count, total_expressions = test_vrl_expressions()
    func_count, found_funcs, expected_funcs = test_vrl_functions_availability()
    invalid_detected, total_invalid = test_invalid_vrl_detection()

    # Summary
    print("\nTest Summary")
    print("=" * 30)
    print(f"Valid expressions: {valid_count}/{total_expressions}")
    print(f"Expected functions: {found_funcs}/{expected_funcs}")
    print(f"Invalid detection: {invalid_detected}/{total_invalid}")
    print(f"Total VRL functions: {func_count}")

    return {
        "valid_expressions": (valid_count, total_expressions),
        "functions_found": (found_funcs, expected_funcs),
        "invalid_detected": (invalid_detected, total_invalid),
        "total_functions": func_count,
    }


if __name__ == "__main__":
    results = run_all_tests()
    print("\nVRL testing complete!")
