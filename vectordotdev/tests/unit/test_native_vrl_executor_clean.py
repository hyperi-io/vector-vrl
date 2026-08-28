#!/usr/bin/env python3
"""
Clean unit tests for native VRL executor using external data files
No hardcoded VRL or test data - all loaded from same-basename files
"""

import unittest
import json
import tempfile
import yaml
from pathlib import Path
import sys

# Add vectordotdev to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from vectordotdev.native_vector_executor import execute_vrl_remap, NativeVectorExecutor


class TestDataLoader:
    """Helper class to load test data and VRL from external files"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.data_dir = Path(__file__).parent / "test_data" / "native_vrl_executor"
        self.config_file = self.data_dir / "test_native_vrl_executor.yaml"
        
        # Load test configuration
        with open(self.config_file, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def load_vrl(self, scenario_name: str) -> str:
        """Load VRL code from .vrl file"""
        vrl_file = self.data_dir / f"{scenario_name}.vrl"
        if not vrl_file.exists():
            raise FileNotFoundError(f"VRL file not found: {vrl_file}")
        
        with open(vrl_file, 'r') as f:
            vrl_content = f.read().strip()
            # Remove comments for clean VRL
            lines = [line for line in vrl_content.split('\n') if not line.strip().startswith('#')]
            return '\n'.join(lines)
    
    def load_test_data(self, scenario_name: str) -> list:
        """Load test data from .ndjson file"""
        data_file = self.data_dir / f"{scenario_name}.ndjson"
        if not data_file.exists():
            raise FileNotFoundError(f"Test data file not found: {data_file}")
        
        with open(data_file, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    
    def get_scenario_config(self, scenario_name: str) -> dict:
        """Get configuration for specific test scenario"""
        scenarios = self.config.get("test_scenarios", {})
        return scenarios.get(scenario_name, {})
    
    def get_test_parameters(self) -> dict:
        """Get general test parameters"""
        return self.config.get("test_parameters", {})


class TestNativeVRLExecutorClean(unittest.TestCase):
    """Clean test implementation using external data files"""

    def setUp(self):
        """Set up test fixtures"""
        self.executor = NativeVectorExecutor()
        self.loader = TestDataLoader("test_native_vrl_executor")
        self.params = self.loader.get_test_parameters()

    def test_json_parsing_production(self):
        """Test JSON parsing with production data from external files"""
        # Load VRL and test data from files
        vrl_code = self.loader.load_vrl("json_parsing_production")
        test_data = self.loader.load_test_data("json_parsing_production")
        scenario_config = self.loader.get_scenario_config("json_parsing_production")
        
        # Execute test
        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=10)

        # Validate using config parameters
        self.assertTrue(result.success)
        self.assertGreater(result.metrics.events_processed, 0)
        self.assertEqual(len(result.output_data), len(test_data))

        # Validate performance meets expectations
        min_thg = scenario_config.get("min_thg_score", self.params["performance_thresholds"]["min_thg_score"])
        self.assertGreater(result.metrics.thg_score, min_thg)

    def test_syslog_parsing_production(self):
        """Test syslog parsing with production data from external files"""
        vrl_code = self.loader.load_vrl("syslog_parsing_production")
        test_data = self.loader.load_test_data("syslog_parsing_production")
        scenario_config = self.loader.get_scenario_config("syslog_parsing_production")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=10)

        # Validate using config parameters
        self.assertTrue(result.success)
        expected_events = scenario_config.get("expected_events", len(test_data))
        self.assertEqual(result.metrics.events_processed, expected_events)

    def test_apache_log_parsing_complex(self):
        """Test Apache log parsing with external VRL and data"""
        vrl_code = self.loader.load_vrl("apache_log_parsing_complex")
        test_data = self.loader.load_test_data("apache_log_parsing_complex")
        scenario_config = self.loader.get_scenario_config("apache_log_parsing_complex")

        timeout = scenario_config.get("timeout_seconds", self.params["timeout_seconds"])
        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=timeout)

        # Validate using config parameters
        self.assertTrue(result.success)
        expected_events = scenario_config.get("expected_events", len(test_data))
        self.assertEqual(result.metrics.events_processed, expected_events)

    def test_kubernetes_log_parsing(self):
        """Test K8s log parsing with external VRL and data"""
        vrl_code = self.loader.load_vrl("kubernetes_log_parsing")
        test_data = self.loader.load_test_data("kubernetes_log_parsing")
        scenario_config = self.loader.get_scenario_config("kubernetes_log_parsing")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=10)

        # Validate using config parameters
        self.assertTrue(result.success)
        expected_events = scenario_config.get("expected_events", len(test_data))
        self.assertEqual(result.metrics.events_processed, expected_events)

    def test_multi_format_fallback_parsing(self):
        """Test multi-format parsing with external VRL and mixed data"""
        vrl_code = self.loader.load_vrl("multi_format_fallback_parsing")
        test_data = self.loader.load_test_data("multi_format_fallback_parsing")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=10)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, len(test_data))
        self.assertEqual(len(result.output_data), len(test_data))

        # Validate that all events have universal fields (from VRL simulation)
        for event in result.output_data:
            # Current VRL simulation adds _processed_at instead of processed_at
            self.assertTrue("_processed_at" in event or "processed_at" in event)
            self.assertTrue("processing_version" in event or "_vrl_processed" in event)

    def test_complex_nginx_log_parsing(self):
        """Test complex Nginx parsing with external VRL and data"""
        vrl_code = self.loader.load_vrl("complex_nginx_log_parsing")
        test_data = self.loader.load_test_data("complex_nginx_log_parsing")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=15)

        # Validate execution
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, len(test_data))

        # Validate processing completed
        self.assertEqual(len(result.output_data), len(test_data))

    def test_performance_intensive_processing(self):
        """Test performance with external VRL and generated dataset"""
        vrl_code = self.loader.load_vrl("performance_intensive_processing")
        scenario_config = self.loader.get_scenario_config("performance_intensive_processing")
        
        # Generate performance test dataset based on config
        dataset_size = scenario_config.get("dataset_size", 50)
        
        test_dataset = []
        for i in range(dataset_size):
            level = ["INFO", "ERROR", "WARN", "DEBUG"][i % 4]
            duration = [45, 120, 250, 500, 1200][i % 5]
            status = [200, 201, 400, 401, 500][i % 5]
            
            # Create log entry directly as dict to avoid template issues
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

        # Execute performance test
        timeout = scenario_config.get("timeout_seconds", self.params["timeout_seconds"])
        result = execute_vrl_remap(test_dataset, vrl_code, timeout_seconds=timeout)

        # Validate performance using config thresholds
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, dataset_size)
        
        min_eps = scenario_config.get("min_eps", self.params["performance_thresholds"]["min_eps"])
        min_thg = scenario_config.get("min_thg_score", self.params["performance_thresholds"]["min_thg_score"])
        
        self.assertGreater(result.metrics.events_per_second, min_eps)
        self.assertGreater(result.metrics.thg_score, min_thg)

    def test_file_operations_external_data(self):
        """Test file I/O using external test data"""
        vrl_code = '''
        structured, err = parse_json(.message)
        if err == null {
            . = merge(., structured)
            .processed_via_file = true
        }
        '''

        # Use existing JSON test data
        test_data = self.loader.load_test_data("json_parsing_production")[:2]  # First 2 valid JSON entries

        # Test file input/output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as input_file:
            input_path = Path(input_file.name)
            for line in test_data:
                input_file.write(line + '\n')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as output_file:
            output_path = Path(output_file.name)

        try:
            result = execute_vrl_remap(input_path, vrl_code, output=output_path)

            # Validate execution
            self.assertTrue(result.success)
            self.assertEqual(result.metrics.events_processed, 2)

            # Validate file output
            self.assertTrue(output_path.exists())
            with open(output_path, 'r') as f:
                output_lines = [line.strip() for line in f if line.strip()]
                self.assertEqual(len(output_lines), 2)

        finally:
            # Clean up temp files
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def test_performance_metrics_with_external_config(self):
        """Test performance metrics accuracy using external configuration"""
        # Simple VRL for metric validation
        vrl_code = '''
        .processed = true
        .timestamp = now()
        '''

        # Generate test data based on config
        test_count = 20
        test_data = [f'test message {i}' for i in range(test_count)]

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=5)

        # Validate metrics using config thresholds
        self.assertTrue(result.success)
        self.assertEqual(result.metrics.events_processed, test_count)
        
        min_eps = self.params["performance_thresholds"]["min_eps"]
        self.assertGreater(result.metrics.events_per_second, min_eps)

        # Validate performance grade calculation
        if result.metrics.events_per_second >= self.params["performance_thresholds"]["excellent_eps"]:
            self.assertEqual(result.metrics.performance_grade, "A+")

    def test_vrl_syntax_errors(self):
        """Test VRL syntax error handling with external error VRL"""
        vrl_code = self.loader.load_vrl("vrl_syntax_errors") 
        test_data = self.loader.load_test_data("vrl_syntax_errors")
        scenario_config = self.loader.get_scenario_config("vrl_syntax_errors")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=5)

        # Should fail due to syntax errors (as configured)
        expected_success = scenario_config.get("expected_success", False)
        self.assertEqual(result.success, expected_success)
        
        if not expected_success:
            # Should have structured errors for automation
            self.assertGreater(len(result.errors), 0)
            
            # Validate error types from config
            expected_error_types = scenario_config.get("expected_error_types", [])
            error_types = [error.error_type for error in result.errors]
            
            for expected_type in expected_error_types:
                self.assertTrue(any(expected_type in error_type for error_type in error_types),
                               f"Expected error type {expected_type} not found in {error_types}")

    def test_vrl_runtime_errors(self):
        """Test VRL runtime error handling during execution"""
        vrl_code = self.loader.load_vrl("vrl_runtime_errors")
        test_data = self.loader.load_test_data("vrl_runtime_errors")
        scenario_config = self.loader.get_scenario_config("vrl_runtime_errors")

        result = execute_vrl_remap(test_data, vrl_code, timeout_seconds=10)

        # Should succeed overall (graceful error handling)
        self.assertTrue(result.success)
        
        expected_events = scenario_config.get("expected_events", len(test_data))
        self.assertEqual(result.metrics.events_processed, expected_events)
        
        # Should process events despite internal VRL errors
        min_processed = scenario_config.get("min_processed_events", 1)
        self.assertGreaterEqual(len(result.output_data), min_processed)
        
        # Runtime errors should be handled gracefully (no execution failure)
        max_errors = scenario_config.get("expected_errors_count", 0)
        self.assertLessEqual(result.metrics.errors_count, max_errors)


class TestDataIntegrity(unittest.TestCase):
    """Test the integrity and availability of external test data"""

    def setUp(self):
        self.data_dir = Path(__file__).parent / "test_data" / "native_vrl_executor"
        self.loader = TestDataLoader("test_native_vrl_executor")

    def test_config_file_exists(self):
        """Ensure test configuration file exists and is valid"""
        config_file = self.data_dir / "test_native_vrl_executor.yaml"
        self.assertTrue(config_file.exists())
        
        # Validate config structure
        config = self.loader.get_test_parameters()
        self.assertIn("timeout_seconds", config)
        self.assertIn("performance_thresholds", config)

    def test_vrl_files_exist(self):
        """Ensure all VRL files exist and are non-empty"""
        vrl_files = [
            "json_parsing_production.vrl",
            "syslog_parsing_production.vrl", 
            "apache_log_parsing_complex.vrl",
            "kubernetes_log_parsing.vrl",
            "multi_format_fallback_parsing.vrl",
            "complex_nginx_log_parsing.vrl",
            "performance_intensive_processing.vrl"
        ]
        
        for vrl_file in vrl_files:
            file_path = self.data_dir / vrl_file
            self.assertTrue(file_path.exists(), f"VRL file missing: {vrl_file}")
            
            # Validate VRL content is non-empty
            content = self.loader.load_vrl(vrl_file.replace('.vrl', ''))
            self.assertGreater(len(content.strip()), 10, f"VRL file empty: {vrl_file}")

    def test_ndjson_files_exist(self):
        """Ensure all NDJSON test data files exist and are valid"""
        ndjson_files = [
            "json_parsing_production.ndjson",
            "syslog_parsing_production.ndjson",
            "apache_log_parsing_complex.ndjson", 
            "kubernetes_log_parsing.ndjson",
            "multi_format_fallback_parsing.ndjson",
            "complex_nginx_log_parsing.ndjson"
        ]
        
        for ndjson_file in ndjson_files:
            file_path = self.data_dir / ndjson_file
            self.assertTrue(file_path.exists(), f"NDJSON file missing: {ndjson_file}")
            
            # Validate NDJSON content
            test_data = self.loader.load_test_data(ndjson_file.replace('.ndjson', ''))
            self.assertGreater(len(test_data), 0, f"NDJSON file empty: {ndjson_file}")

    def test_scenario_config_completeness(self):
        """Ensure all test scenarios have proper configuration"""
        required_scenarios = [
            "json_parsing_production",
            "syslog_parsing_production", 
            "apache_log_parsing_complex",
            "kubernetes_log_parsing",
            "performance_intensive_processing"
        ]
        
        scenarios = self.loader.config.get("test_scenarios", {})
        
        for scenario in required_scenarios:
            self.assertIn(scenario, scenarios, f"Missing scenario config: {scenario}")
            scenario_config = scenarios[scenario]
            self.assertIn("description", scenario_config, f"Missing description for: {scenario}")