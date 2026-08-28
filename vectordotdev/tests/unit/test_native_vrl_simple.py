#!/usr/bin/env python3
"""
Simple test demonstrating native VRL execution via Rust bindings.
No subprocess calls - all execution happens in-memory.
"""

import sys
import json
from pathlib import Path

import pytest

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# pytest re-raises SystemExit as fatal rather than a per-module collection
# error, so a bare sys.exit() here would take down the whole session when
# the compiled bindings aren't built. importorskip skips just this module.
pytest.importorskip(
    "vectordotdev._bindings",
    reason="compiled PyO3 bindings not built - run: cd vector-bindings && .venv/bin/maturin develop --release",
)
from vectordotdev._bindings import execute_vrl, validate_vrl, get_vrl_performance
HAS_BINDINGS = True


def test_basic_execution():
    """Test basic VRL execution"""
    print("\n" + "="*60)
    print("TEST 1: Basic VRL Execution")
    print("="*60)

    vrl_code = """
    .level = upcase!(.level)
    .processed = true
    .timestamp = now()
    """

    events = [
        '{"level": "info", "message": "User login"}',
        '{"level": "error", "message": "Auth failed"}',
        '{"level": "debug", "message": "Cache hit"}',
    ]

    print(f"VRL Code:\n{vrl_code}")
    print(f"\nInput events: {len(events)}")
    for i, event in enumerate(events, 1):
        print(f"  {i}. {event}")

    # Execute natively (in-memory, no subprocess)
    results = execute_vrl(vrl_code, events)

    print(f"\nOutput events: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {json.dumps(result, indent=2)}")

    # Verify transformations
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    for result in results:
        assert result['level'].isupper(), f"Level should be uppercase: {result['level']}"
        assert result['processed'] is True, "processed should be true"
        assert 'timestamp' in result, "timestamp should be added"

    print("\n✅ Basic execution test PASSED")
    return True


def test_validation():
    """Test VRL syntax validation"""
    print("\n" + "="*60)
    print("TEST 2: VRL Syntax Validation")
    print("="*60)

    # Valid VRL
    valid_vrl = ".level = upcase!(.level)"
    print(f"\nValidating VALID VRL: {valid_vrl}")
    result = validate_vrl(valid_vrl)
    print(f"Result: success={result.success}, error={result.error}")

    assert result.success, "Valid VRL should pass validation"

    # Invalid VRL
    invalid_vrl = ".level = undefined_function(.level)"
    print(f"\nValidating INVALID VRL: {invalid_vrl}")
    result = validate_vrl(invalid_vrl)
    print(f"Result: success={result.success}, error={result.error}")

    assert not result.success, "Invalid VRL should fail validation"
    assert result.error is not None, "Invalid VRL should have error message"

    print("\n✅ Validation test PASSED")
    return True


def test_performance():
    """Test VRL performance metrics"""
    print("\n" + "="*60)
    print("TEST 3: VRL Performance Measurement")
    print("="*60)

    vrl_code = """
    .processed = true
    .level = upcase!(.level)
    """

    events = [
        '{"level": "info", "message": "test"}',
        '{"level": "error", "message": "test"}',
    ]

    print(f"Measuring performance for {len(events)} events...")
    metrics = get_vrl_performance(vrl_code, events, iterations=1000)

    print(f"\nPerformance Metrics:")
    print(f"  Events/second: {metrics['events_per_second']:,.0f}")
    print(f"  Processing time: {metrics['processing_time_seconds']:.6f}s")
    print(f"  Total events: {metrics['total_events']:,}")
    print(f"  THG score: {metrics['thg_score']:.2f}")

    assert metrics['events_per_second'] > 0, "Should process events"
    assert metrics['total_events'] == 2000, "Should process 2000 events (2 * 1000)"

    print("\n✅ Performance test PASSED")
    return True


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*60)
    print("TEST 4: Edge Cases")
    print("="*60)

    vrl_code = ".processed = true"

    # Empty input
    print("\nTest: Empty input")
    results = execute_vrl(vrl_code, [])
    assert len(results) == 0, "Empty input should return empty output"
    print("✅ Empty input handled correctly")

    # Special characters
    print("\nTest: Special characters")
    events = [
        json.dumps({"message": "Unicode: ❤️ 😀"}),
        json.dumps({"message": "Quotes: \"test\" 'test'"}),
    ]
    results = execute_vrl(vrl_code, events)
    assert len(results) == 2, "Should handle special characters"
    print("✅ Special characters handled correctly")

    # Multiple fields
    print("\nTest: Multiple fields")
    vrl_code = """
    .uppercase = upcase!(.text)
    .lowercase = downcase!(.text)
    .length = length!(.text)
    """
    events = ['{"text": "Hello World"}']
    results = execute_vrl(vrl_code, events)
    assert results[0]['uppercase'] == "HELLO WORLD"
    assert results[0]['lowercase'] == "hello world"
    assert results[0]['length'] == 11
    print("✅ Multiple fields handled correctly")

    print("\n✅ Edge cases test PASSED")
    return True


def test_error_handling():
    """Test error handling"""
    print("\n" + "="*60)
    print("TEST 5: Error Handling")
    print("="*60)

    # Fallible operations need error handling
    vrl_code = """
    .processed = true
    .level = upcase!(.level)
    """

    events = ['{"level": "info"}']

    print(f"VRL with infallible operator: {vrl_code.strip()}")
    results = execute_vrl(vrl_code, events)
    assert len(results) == 1
    print(f"✅ Infallible operations work correctly")

    print("\n✅ Error handling test PASSED")
    return True


def run_all_tests():
    """Run all tests"""
    if not HAS_BINDINGS:
        print("❌ Bindings not available")
        return False

    print("="*60)
    print("Native VRL Execution Tests")
    print("="*60)
    print("Mode: In-memory execution via Rust PyO3 bindings")
    print("No subprocess calls - direct VRL runtime access")
    print("="*60)

    tests = [
        test_basic_execution,
        test_validation,
        test_performance,
        test_edge_cases,
        test_error_handling,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n❌ Test FAILED: {test_func.__name__}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✅ ALL TESTS PASSED")
        print("\n🎯 Native VRL execution is working!")
        print("   - In-memory execution via Rust bindings")
        print("   - No subprocess overhead")
        print("   - Full VRL compiler and runtime access")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
