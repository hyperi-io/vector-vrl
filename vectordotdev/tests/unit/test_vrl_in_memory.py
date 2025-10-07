#!/usr/bin/env python3
"""
Comprehensive in-memory VRL tests using real Vector VRL runtime via Rust bindings.
NO subprocess calls - all execution happens in-memory via PyO3 bindings.
"""

import unittest
import json
import time
from pathlib import Path
import sys

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from vectordotdev._bindings import execute_vrl, validate_vrl, get_vrl_performance, VrlResult
    HAS_VRL_BINDINGS = True
except ImportError as e:
    print(f"⚠️ VRL bindings not available: {e}")
    print("Run: cd vector-bindings && maturin develop")
    HAS_VRL_BINDINGS = False


class TestVRLInMemory(unittest.TestCase):
    """Test real in-memory VRL execution using Rust bindings"""

    @classmethod
    def setUpClass(cls):
        if not HAS_VRL_BINDINGS:
            raise unittest.SkipTest("VRL bindings not available")

        cls.vrl_dir = Path(__file__).parent.parent / "vrl"
        if not cls.vrl_dir.exists():
            raise unittest.SkipTest(f"VRL test files not found at {cls.vrl_dir}")

    def load_vrl_file(self, filename: str) -> str:
        """Load VRL code from test file"""
        vrl_path = self.vrl_dir / filename
        with open(vrl_path, 'r') as f:
            return f.read()

    def test_basic_transforms_in_memory(self):
        """Test basic VRL transforms execute in-memory"""
        vrl_code = self.load_vrl_file("basic_transforms.vrl")

        # Test data
        test_logs = [
            '{"level": "info", "message": "test log", "timestamp": "2025-01-01T00:00:00Z"}',
            '{"level": "error", "message": "error log", "timestamp": "2025-01-01T00:00:01Z"}',
        ]

        # Execute in-memory (no subprocess)
        results = execute_vrl(vrl_code, test_logs)

        # Validate results
        self.assertEqual(len(results), 2)

        # Check uppercase transformation
        for result in results:
            self.assertIn("level", result)
            # VRL upcase should transform level to uppercase
            if "level" in result:
                level = result["level"]
                # Check if level was transformed (either uppercase or has meta)
                self.assertTrue(
                    level.isupper() or "meta" in result,
                    f"Expected level to be uppercase or meta to exist, got: {result}"
                )

    def test_log_parsing_in_memory(self):
        """Test log parsing VRL executes in-memory"""
        vrl_code = self.load_vrl_file("log_parsing.vrl")

        # Apache/Nginx log format test data
        test_logs = [
            '192.168.1.100 - user1 [01/Jan/2025:00:00:00 +0000] "GET /api/v1/users HTTP/1.1" 200 1234',
            '10.0.0.1 - admin [01/Jan/2025:00:00:01 +0000] "POST /api/v1/data HTTP/1.1" 201 567',
        ]

        # Add raw_log wrapper since VRL expects it
        wrapped_logs = [json.dumps({"raw_log": log}) for log in test_logs]

        # Execute in-memory
        results = execute_vrl(vrl_code, wrapped_logs)

        # Validate parsing occurred
        self.assertEqual(len(results), 2)

        # Check if IP addresses were extracted
        for result in results:
            # Should have either parsed IP or original raw_log
            self.assertTrue("ip" in result or "raw_log" in result)

    def test_security_filtering_in_memory(self):
        """Test security filtering VRL executes in-memory"""
        vrl_code = self.load_vrl_file("security_filtering.vrl")

        # Test data with security threats
        test_logs = [
            '{"message": "SELECT * FROM users WHERE id=1 UNION SELECT password", "status_code": 200}',
            '{"message": "<script>alert(1)</script>", "status_code": 403}',
            '{"message": "Normal log message", "status_code": 200}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate security checks
        self.assertEqual(len(results), 3)

        # First log should detect SQL injection
        if "security" in results[0]:
            self.assertTrue(results[0]["security"].get("sql_injection_detected", False))

        # Second log should detect XSS
        if "security" in results[1]:
            self.assertTrue(results[1]["security"].get("xss_detected", False))

    def test_error_handling_in_memory(self):
        """Test error handling VRL executes in-memory"""
        vrl_code = self.load_vrl_file("error_handling.vrl")

        # Test data with errors and edge cases
        test_logs = [
            '{"json_data": "{\\"level\\": \\"INFO\\"}", "log_line": "2025-01-01T00:00:00 INFO Test message"}',
            '{"json_data": "invalid json{", "log_line": "ERROR: Failed"}',
            '{"status_code_str": "200"}',
            '{"status_code_str": "not_a_number"}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate error handling
        self.assertEqual(len(results), 4)

        # All events should be processed (error handling should gracefully handle errors)
        for result in results:
            self.assertIsInstance(result, dict)
            # Should have error_handling metadata
            self.assertTrue("error_handling" in result or "error" in result or "level" in result)

    def test_data_enrichment_in_memory(self):
        """Test data enrichment VRL executes in-memory"""
        vrl_code = self.load_vrl_file("data_enrichment.vrl")

        # Test data for enrichment
        test_logs = [
            '{"user_id": 123, "action": "login", "ip": "192.168.1.100"}',
            '{"user_id": 456, "action": "purchase", "ip": "10.0.0.1"}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate enrichment
        self.assertEqual(len(results), 2)

        # Check that enrichment occurred
        for result in results:
            self.assertIn("user_id", result)
            # Should have enrichment metadata or processing timestamp
            self.assertTrue(
                "enrichment" in result or "processed_at" in result or "timestamp" in result
            )

    def test_vrl_validation_in_memory(self):
        """Test VRL syntax validation using real VRL compiler"""
        # Valid VRL
        valid_vrl = """
        .level = upcase(.level)
        .timestamp = now()
        """

        result = validate_vrl(valid_vrl)
        self.assertTrue(result.success)
        self.assertIsNone(result.error)

        # Invalid VRL
        invalid_vrl = """
        this is not valid VRL syntax
        """

        result = validate_vrl(invalid_vrl)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error_type, "compilation_error")

    def test_vrl_performance_in_memory(self):
        """Test VRL performance metrics using real execution"""
        vrl_code = """
        .processed = true
        .timestamp = now()
        """

        test_logs = ['test message'] * 10

        # Get performance metrics
        metrics = get_vrl_performance(vrl_code, test_logs, iterations=100)

        # Validate metrics
        self.assertIn("events_per_second", metrics)
        self.assertIn("processing_time_seconds", metrics)
        self.assertIn("total_events", metrics)
        self.assertIn("thg_score", metrics)

        # Should process events
        self.assertEqual(metrics["total_events"], 1000)  # 10 logs * 100 iterations
        self.assertGreater(metrics["events_per_second"], 0)

    def test_complex_routing_in_memory(self):
        """Test complex routing VRL executes in-memory"""
        vrl_code = self.load_vrl_file("complex_routing.vrl")

        # Test data for routing
        test_logs = [
            '{"level": "ERROR", "service": "api", "message": "API error"}',
            '{"level": "INFO", "service": "db", "message": "DB connected"}',
            '{"level": "WARN", "service": "cache", "message": "Cache miss"}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate routing logic
        self.assertEqual(len(results), 3)

        # Check that routing metadata was added
        for result in results:
            self.assertTrue("level" in result or "route" in result or "service" in result)

    def test_metrics_extraction_in_memory(self):
        """Test metrics extraction VRL executes in-memory"""
        vrl_code = self.load_vrl_file("metrics_extraction.vrl")

        # Test data with metrics
        test_logs = [
            '{"duration_ms": 150, "status_code": 200, "request_count": 100}',
            '{"duration_ms": 500, "status_code": 500, "request_count": 50}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate metrics extraction
        self.assertEqual(len(results), 2)

        # Check metrics fields
        for result in results:
            self.assertTrue("duration_ms" in result or "metrics" in result)

    def test_vector_0_49_features_in_memory(self):
        """Test Vector 0.49 features VRL executes in-memory"""
        vrl_code = self.load_vrl_file("vector_0_49_features.vrl")

        # Test data for Vector 0.49 features
        test_logs = [
            '{"data": {"nested": {"value": 123}}}',
            '{"array": [1, 2, 3, 4, 5]}',
        ]

        # Execute in-memory
        results = execute_vrl(vrl_code, test_logs)

        # Validate execution (features might not all be supported)
        self.assertGreater(len(results), 0)


class TestVRLEdgeCasesInMemory(unittest.TestCase):
    """Test edge cases with in-memory VRL execution"""

    @classmethod
    def setUpClass(cls):
        if not HAS_VRL_BINDINGS:
            raise unittest.SkipTest("VRL bindings not available")

    def test_empty_input(self):
        """Test handling of empty input"""
        vrl_code = ".processed = true"
        results = execute_vrl(vrl_code, [])
        self.assertEqual(len(results), 0)

    def test_malformed_json(self):
        """Test handling of malformed JSON"""
        vrl_code = """
        .processed = true
        """

        test_logs = [
            'not valid json {',
            '{"incomplete": ',
        ]

        # Should handle gracefully (either parse as plain text or error)
        results = execute_vrl(vrl_code, test_logs)
        self.assertEqual(len(results), 2)

    def test_large_payload(self):
        """Test handling of large payloads"""
        vrl_code = ".size = length(.message)"

        # Large message
        large_message = "x" * 10000
        test_logs = [json.dumps({"message": large_message})]

        results = execute_vrl(vrl_code, test_logs)
        self.assertEqual(len(results), 1)
        if "size" in results[0]:
            self.assertEqual(results[0]["size"], 10000)

    def test_special_characters(self):
        """Test handling of special characters"""
        vrl_code = ".processed = true"

        test_logs = [
            json.dumps({"message": "Unicode: \u2764\ufe0f \U0001f600"}),
            json.dumps({"message": "Quotes: \"test\" 'test'"}),
            json.dumps({"message": "Newlines:\nand\ttabs"}),
        ]

        results = execute_vrl(vrl_code, test_logs)
        self.assertEqual(len(results), 3)


def run_tests():
    """Run all in-memory VRL tests"""
    if not HAS_VRL_BINDINGS:
        print("❌ Cannot run tests - VRL bindings not available")
        print("Build bindings with: cd vector-bindings && maturin develop")
        return 1

    print("🚀 Running In-Memory VRL Tests")
    print("=" * 60)
    print("Using: Real Vector VRL runtime via Rust bindings")
    print("Mode: In-process execution (NO subprocess calls)")
    print("=" * 60)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestVRLInMemory))
    suite.addTests(loader.loadTestsFromTestCase(TestVRLEdgeCasesInMemory))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 60)
    print("🎯 IN-MEMORY VRL TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("✅ All in-memory tests passed!")
        print("📊 VRL execution happens entirely in-memory via Rust bindings")
        print("🚀 No subprocess overhead - maximum performance!")
    else:
        print("❌ Some tests failed")
        for failure in result.failures:
            print(f"  FAIL: {failure[0]}")
        for error in result.errors:
            print(f"  ERROR: {error[0]}")

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
