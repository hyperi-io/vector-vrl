#!/usr/bin/env python3
"""
Structured Native VRL Executor Tests
Each test saves results to <basename>.results, output to <basename>.out, errors to <basename>.error
Tests organized in individual directories for better organization
"""

import unittest
import json
import yaml
import tempfile
from pathlib import Path
import sys
import io
from datetime import datetime

# Add vectordotdev to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vectordotdev.native_vector_executor import (
    execute_vrl_remap, quick_vrl_test, NativeVectorExecutor,
    VectorExecutionResult, ExecutionMetrics, VectorError
)


class StructuredTestRunner:
    """Enhanced test runner that saves results, output, and errors to files"""
    
    def __init__(self, test_base_dir: Path):
        self.test_base_dir = test_base_dir
        
    def run_test_with_artifacts(self, test_name: str, source_data: list, vrl_code: str, **kwargs) -> VectorExecutionResult:
        """
        Run VRL test and save all artifacts to files
        
        Saves:
        - <test_name>.results: Complete metrics and execution info  
        - <test_name>.out: Output data (processed events)
        - <test_name>.error: Error details if any failures
        """
        test_dir = self.test_base_dir / test_name
        test_dir.mkdir(exist_ok=True, parents=True)
        
        # Execute VRL processing
        result = execute_vrl_remap(source_data, vrl_code, **kwargs)
        
        # Save results (metrics and execution info)
        results_file = test_dir / f"{test_name}.results"
        with open(results_file, 'w') as f:
            results_data = {
                "test_name": test_name,
                "timestamp": datetime.now().isoformat(),
                "success": result.success,
                "metrics": {
                    "events_processed": result.metrics.events_processed,
                    "events_per_second": result.metrics.events_per_second,
                    "cpu_usage_percent": result.metrics.cpu_usage_percent,
                    "memory_usage_mb": result.metrics.memory_usage_mb,
                    "execution_time_seconds": result.metrics.execution_time_seconds,
                    "errors_count": result.metrics.errors_count,
                    "dropped_events": result.metrics.dropped_events,
                    "bytes_processed": result.metrics.bytes_processed,
                    "thg_score": result.metrics.thg_score,
                    "performance_grade": result.metrics.performance_grade
                },
                "execution_log": result.execution_log,
                "source_events_count": len(source_data),
                "output_events_count": len(result.output_data),
                "vrl_code_length": len(vrl_code),
                "test_parameters": kwargs
            }
            json.dump(results_data, f, indent=2)
        
        # Save output data (processed events)
        output_file = test_dir / f"{test_name}.out"
        with open(output_file, 'w') as f:
            for event in result.output_data:
                f.write(json.dumps(event) + '\n')
        
        # Save errors if any
        if result.errors:
            error_file = test_dir / f"{test_name}.error"
            with open(error_file, 'w') as f:
                error_data = {
                    "test_name": test_name,
                    "timestamp": datetime.now().isoformat(),
                    "total_errors": len(result.errors),
                    "errors": [
                        {
                            "error_type": error.error_type,
                            "component": error.component,
                            "message": error.message,
                            "details": error.details,
                            "line_number": error.line_number,
                            "column_number": error.column_number,
                            "vrl_context": error.vrl_context
                        } for error in result.errors
                    ]
                }
                json.dump(error_data, f, indent=2)
        
        return result
    
    def load_test_files(self, test_name: str) -> tuple:
        """Load VRL and data files for a test"""
        test_dir = self.test_base_dir / test_name
        
        vrl_file = test_dir / f"{test_name}.vrl"
        data_file = test_dir / f"{test_name}.ndjson"
        
        if not vrl_file.exists():
            raise FileNotFoundError(f"VRL file not found: {vrl_file}")
        if not data_file.exists():
            raise FileNotFoundError(f"Data file not found: {data_file}")
        
        with open(vrl_file, 'r') as f:
            vrl_code = f.read().strip()
            # Remove comments
            vrl_lines = [line for line in vrl_code.split('\n') if not line.strip().startswith('#')]
            vrl_code = '\n'.join(vrl_lines)
        
        with open(data_file, 'r') as f:
            test_data = [line.strip() for line in f if line.strip()]
        
        return vrl_code, test_data


class TestJSONParsingProduction(unittest.TestCase):
    """Test JSON parsing with production data - saves artifacts"""
    
    def setUp(self):
        self.test_runner = StructuredTestRunner(Path(__file__).parent)
        self.test_name = "json_parsing_production"
    
    def test_json_parsing_with_artifacts(self):
        """Test JSON parsing and save complete artifacts"""
        vrl_code, test_data = self.test_runner.load_test_files(self.test_name)
        
        result = self.test_runner.run_test_with_artifacts(
            self.test_name, test_data, vrl_code, timeout_seconds=10
        )
        
        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, len(test_data))
        self.assertGreater(result.metrics.thg_score, 100)
        
        # Verify artifacts were created
        test_dir = Path(__file__).parent / self.test_name
        self.assertTrue((test_dir / f"{self.test_name}.results").exists())
        self.assertTrue((test_dir / f"{self.test_name}.out").exists())


class TestSyslogParsingProduction(unittest.TestCase):
    """Test syslog parsing with production data - saves artifacts"""
    
    def setUp(self):
        self.test_runner = StructuredTestRunner(Path(__file__).parent)
        self.test_name = "syslog_parsing_production"
    
    def test_syslog_parsing_with_artifacts(self):
        """Test syslog parsing and save complete artifacts"""
        vrl_code, test_data = self.test_runner.load_test_files(self.test_name)
        
        result = self.test_runner.run_test_with_artifacts(
            self.test_name, test_data, vrl_code, timeout_seconds=10
        )
        
        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, len(test_data))
        
        # Verify artifacts were created
        test_dir = Path(__file__).parent / self.test_name
        self.assertTrue((test_dir / f"{self.test_name}.results").exists())
        self.assertTrue((test_dir / f"{self.test_name}.out").exists())


class TestVRLSyntaxErrors(unittest.TestCase):
    """Test VRL syntax error handling - saves error artifacts"""
    
    def setUp(self):
        self.test_runner = StructuredTestRunner(Path(__file__).parent)
        self.test_name = "vrl_syntax_errors"
    
    def test_vrl_syntax_errors_with_artifacts(self):
        """Test VRL syntax errors and save error artifacts"""
        vrl_code, test_data = self.test_runner.load_test_files(self.test_name)
        
        result = self.test_runner.run_test_with_artifacts(
            self.test_name, test_data, vrl_code, timeout_seconds=5
        )
        
        # Should fail due to syntax errors
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)
        
        # Verify error artifacts were created
        test_dir = Path(__file__).parent / self.test_name
        self.assertTrue((test_dir / f"{self.test_name}.results").exists())
        self.assertTrue((test_dir / f"{self.test_name}.error").exists())
        
        # Validate error structure
        error_file = test_dir / f"{self.test_name}.error"
        with open(error_file, 'r') as f:
            error_data = json.load(f)
            self.assertIn("errors", error_data)
            self.assertGreater(error_data["total_errors"], 0)
            
            # Check error structure
            for error in error_data["errors"]:
                self.assertIn("error_type", error)
                self.assertIn("component", error)
                self.assertIn("message", error)


class TestPerformanceIntensive(unittest.TestCase):
    """Test performance with large dataset - saves performance artifacts"""
    
    def setUp(self):
        self.test_runner = StructuredTestRunner(Path(__file__).parent)
        self.test_name = "performance_intensive"
    
    def test_performance_intensive_with_artifacts(self):
        """Test performance with large dataset and save performance artifacts"""
        # Load VRL from performance_intensive_processing file
        vrl_file = Path(__file__).parent.parent / "test_data" / "native_vrl_executor" / "performance_intensive_processing.vrl"
        with open(vrl_file, 'r') as f:
            vrl_code = f.read().strip()
            vrl_lines = [line for line in vrl_code.split('\n') if not line.strip().startswith('#')]
            vrl_code = '\n'.join(vrl_lines)
        
        # Generate large test dataset
        test_dataset = []
        for i in range(100):
            level = ["INFO", "ERROR", "WARN", "DEBUG"][i % 4]
            duration = [45, 120, 250, 500, 1200][i % 5]
            status = [200, 201, 400, 401, 500][i % 5]
            
            log_entry = {
                "timestamp": f"2023-09-08T12:00:{i % 60:02d}Z",
                "level": level,
                "service": "api",
                "request_id": f"req_{i:03d}",
                "duration_ms": duration,
                "user_id": f"user_{i}",
                "method": "GET",
                "path": "/api/v1/users",
                "status": status
            }
            test_dataset.append(json.dumps(log_entry))
        
        result = self.test_runner.run_test_with_artifacts(
            self.test_name, test_dataset, vrl_code, timeout_seconds=30
        )
        
        # Validate performance
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, 100)
        self.assertGreater(result.metrics.events_per_second, 200)
        self.assertGreater(result.metrics.thg_score, 200)
        
        # Verify performance artifacts
        test_dir = Path(__file__).parent / self.test_name
        self.assertTrue((test_dir / f"{self.test_name}.results").exists())
        
        # Validate performance metrics in results file
        results_file = test_dir / f"{self.test_name}.results"
        with open(results_file, 'r') as f:
            results_data = json.load(f)
            self.assertGreater(results_data["metrics"]["events_per_second"], 200)
            self.assertGreater(results_data["metrics"]["thg_score"], 200)


def run_all_structured_tests():
    """Run all structured tests and create artifacts"""
    print("🧪 Running Structured Native VRL Executor Tests")
    print("💾 Saving results, output, and errors to individual files")
    print("=" * 60)
    
    # Load all test classes
    test_classes = [
        TestJSONParsingProduction,
        TestSyslogParsingProduction, 
        TestVRLSyntaxErrors,
        TestPerformanceIntensive
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 STRUCTURED TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Tests Run: {result.testsRun}")
    print(f"❌ Failures: {len(result.failures)}")
    print(f"⚠️ Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("🚀 All structured tests passed!")
        print("💾 Test artifacts saved to individual directories:")
        
        # List created artifacts
        base_dir = Path(__file__).parent
        for test_dir in base_dir.iterdir():
            if test_dir.is_dir():
                artifacts = list(test_dir.glob("*.*"))
                if artifacts:
                    print(f"   📁 {test_dir.name}/")
                    for artifact in sorted(artifacts):
                        print(f"      📄 {artifact.name}")
    else:
        print("⚠️ Some structured tests failed")
        for failure in result.failures:
            print(f"FAILURE: {failure[0]}")
        for error in result.errors:
            print(f"ERROR: {error[0]}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_structured_tests()
    sys.exit(0 if success else 1)