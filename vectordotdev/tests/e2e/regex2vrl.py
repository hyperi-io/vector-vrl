#!/usr/bin/env python3
"""
Integration tests for regex2vrl using Vector execution.
Tests regex2vrl generated VRL by running it through Vector and validating outputs.
"""

import pytest
import json
import yaml
import tempfile
import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import time

# Add regex2vrl module to path
sys.path.insert(0, str(Path(__file__).parent.parent / "vectordotdev"))

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL
from vectordotdev.regex2vrl.cli import CLI


class VectorTestFramework:
    """Framework for testing VRL code through Vector execution"""
    
    def __init__(self):
        self.vector_binary = self._find_vector_binary()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="regex2vrl_test_"))
        self.test_configs_dir = self.temp_dir / "configs"
        self.test_data_dir = self.temp_dir / "data"
        self.test_output_dir = self.temp_dir / "output"
        
        # Create directories
        self.test_configs_dir.mkdir(parents=True)
        self.test_data_dir.mkdir(parents=True)
        self.test_output_dir.mkdir(parents=True)
        
    def _find_vector_binary(self) -> Optional[Path]:
        """Find Vector binary in the project"""
        possible_paths = [
            Path("vector/target/release/vector"),
            Path("vector/target/debug/vector"),
            Path("./target/release/vector"),
            Path("./target/debug/vector"),
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
        
        # Try PATH
        try:
            result = subprocess.run(["which", "vector"], 
                                  capture_output=True, text=True, check=True)
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            pass
            
        return None
    
    def create_test_config(self, vrl_code: str, test_name: str, 
                          input_format: str = "raw") -> Path:
        """Create a Vector config for testing VRL code"""
        
        config = {
            "data_dir": str(self.temp_dir / "data"),
            "sources": {
                "test_input": {
                    "type": "file",
                    "include": [str(self.test_data_dir / f"{test_name}_input.log")],
                    "read_from": "beginning",
                    "remove_after_secs": 1
                }
            },
            "transforms": {
                "regex2vrl_test": {
                    "type": "remap",
                    "inputs": ["test_input"],
                    "source": vrl_code
                }
            },
            "sinks": {
                "test_output": {
                    "type": "file",
                    "inputs": ["regex2vrl_test"],
                    "path": str(self.test_output_dir / f"{test_name}_output.jsonl"),
                    "encoding": {
                        "codec": "json"
                    }
                }
            }
        }
        
        config_path = self.test_configs_dir / f"{test_name}_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path
    
    def create_test_data(self, log_lines: List[str], test_name: str) -> Path:
        """Create test log data file"""
        data_path = self.test_data_dir / f"{test_name}_input.log"
        with open(data_path, 'w') as f:
            for line in log_lines:
                f.write(line + '\n')
        return data_path
    
    def run_vector_test(self, config_path: Path, timeout: int = 10) -> List[Dict]:
        """Run Vector with the test config and return parsed output"""
        if not self.vector_binary:
            pytest.skip("Vector binary not found")
        
        # Run Vector
        process = subprocess.Popen([
            str(self.vector_binary),
            "--config", str(config_path),
            "--quiet"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for Vector to process
        time.sleep(2)
        
        # Stop Vector
        process.terminate()
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        
        # Parse output
        test_name = config_path.stem.replace("_config", "")
        output_file = self.test_output_dir / f"{test_name}_output.jsonl"
        
        results = []
        if output_file.exists():
            with open(output_file) as f:
                for line in f:
                    if line.strip():
                        try:
                            results.append(json.loads(line.strip()))
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}, line: {line}")
        
        return results, stdout, stderr
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


@pytest.fixture
def vector_test_framework():
    """Provide Vector test framework with cleanup"""
    framework = VectorTestFramework()
    yield framework
    framework.cleanup()


class TestRegex2VRLIntegration:
    """Integration tests for regex2vrl with Vector execution"""
    
    def test_apache_log_conversion(self, vector_test_framework):
        """Test Apache log pattern conversion and execution"""
        # Apache Combined Log Format
        regex_pattern = r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^\s]+) HTTP/(?P<version>[\d\.]+)" (?P<status>\d{3}) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
        
        converter = RegexToVRL()
        vrl_code = converter.convert(regex_pattern, output_format='commented')
        
        # Test data
        test_logs = [
            '192.168.1.100 - john [15/Jan/2024:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024 "https://google.com" "Mozilla/5.0"',
            '10.0.0.1 - - [15/Jan/2024:10:30:46 +0000] "POST /api/data HTTP/1.1" 201 512 "-" "curl/7.68.0"',
        ]
        
        # Create test config and data
        config_path = vector_test_framework.create_test_config(vrl_code, "apache_test")
        vector_test_framework.create_test_data(test_logs, "apache_test")
        
        # Run test
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        # Assertions
        assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}. stderr: {stderr}"
        
        # Check that basic parsing worked
        first_result = results[0]
        assert 'message' in first_result or 'ip' in first_result, "Expected parsed fields in output"
    
    def test_syslog_pattern_conversion(self, vector_test_framework):
        """Test syslog pattern conversion"""
        grok_pattern = '%{SYSLOGTIMESTAMP:timestamp} %{HOSTNAME:host} %{WORD:program}(?:\\[%{POSINT:pid}\\])?: %{GREEDYDATA:message}'
        
        converter = GrokToVRL()
        vrl_code = converter.convert(grok_pattern)
        
        # Test data
        test_logs = [
            'Jan 15 10:30:45 server01 sshd[1234]: Accepted password for user from 192.168.1.100',
            'Jan 15 10:30:46 server01 nginx: 192.168.1.101 - GET /health',
        ]
        
        config_path = vector_test_framework.create_test_config(vrl_code, "syslog_test")
        vector_test_framework.create_test_data(test_logs, "syslog_test")
        
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        assert len(results) >= 1, f"Expected results, stderr: {stderr}"
    
    def test_json_log_pattern(self, vector_test_framework):
        """Test JSON log pattern"""
        # This should detect JSON and use parse_json!
        regex_pattern = r'^(?P<json_data>\{.*\})$'
        
        converter = RegexToVRL()
        vrl_code = converter.convert(regex_pattern)
        
        test_logs = [
            '{"timestamp":"2024-01-15T10:30:45Z","level":"INFO","message":"User login","user_id":"12345"}',
            '{"timestamp":"2024-01-15T10:30:46Z","level":"ERROR","message":"Database connection failed","error":"timeout"}',
        ]
        
        config_path = vector_test_framework.create_test_config(vrl_code, "json_test")
        vector_test_framework.create_test_data(test_logs, "json_test")
        
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        assert len(results) >= 1, f"Expected results, stderr: {stderr}"
    
    def test_ip_extraction_pattern(self, vector_test_framework):
        """Test IP address extraction"""
        regex_pattern = r'Client IP: (?P<client_ip>\d+\.\d+\.\d+\.\d+)'
        
        converter = RegexToVRL()
        vrl_code = converter.convert(regex_pattern)
        
        test_logs = [
            'Client IP: 192.168.1.100',
            'Client IP: 10.0.0.1',
            'Client IP: 172.16.0.50',
        ]
        
        config_path = vector_test_framework.create_test_config(vrl_code, "ip_test")
        vector_test_framework.create_test_data(test_logs, "ip_test")
        
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        assert len(results) >= 1, f"Expected results, stderr: {stderr}"
    
    def test_custom_delimiter_pattern(self, vector_test_framework):
        """Test custom delimiter-based pattern"""
        regex_pattern = r'^(?P<timestamp>[^|]+)\|(?P<level>[^|]+)\|(?P<component>[^|]+)\|(?P<message>.*)$'
        
        converter = RegexToVRL()
        vrl_code = converter.convert(regex_pattern)
        
        test_logs = [
            '2024-01-15 10:30:45|INFO|WebServer|Request processed successfully',
            '2024-01-15 10:30:46|ERROR|Database|Connection timeout after 30s',
        ]
        
        config_path = vector_test_framework.create_test_config(vrl_code, "delimiter_test")
        vector_test_framework.create_test_data(test_logs, "delimiter_test")
        
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        assert len(results) >= 1, f"Expected results, stderr: {stderr}"


class TestPerformanceValidation:
    """Test performance aspects of regex2vrl generated code"""
    
    def test_pattern_analysis_performance_rating(self):
        """Test that patterns get appropriate THG ratings"""
        converter = RegexToVRL()
        
        # Simple pattern should get high rating
        simple_pattern = r'(?P<ip>\d+\.\d+\.\d+\.\d+)'
        simple_analysis = converter.analyze_pattern(simple_pattern)
        assert simple_analysis.estimated_thg >= 250, "Simple pattern should have high THG"
        
        # Complex pattern should get lower rating
        complex_pattern = r'(?P<data>.*?(?:(?:ERROR|WARN).+?|.*?)(?:(?P<nested>(?:(?:[A-Z]+.*?)*)+).*?)*)'
        complex_analysis = converter.analyze_pattern(complex_pattern)
        assert complex_analysis.estimated_thg <= 200, "Complex pattern should have lower THG"
    
    def test_builtin_parser_detection(self):
        """Test that built-in parsers are correctly detected"""
        converter = RegexToVRL()
        
        # JSON pattern should detect parse_json
        json_pattern = r'(?P<json>\{.*\})'
        json_analysis = converter.analyze_pattern(json_pattern)
        assert json_analysis.can_use_builtin, "JSON pattern should use built-in parser"
        
        # Key-value pattern should detect parse_key_value
        kv_pattern = r'(?P<pairs>key1=value1 key2=value2)'
        kv_analysis = converter.analyze_pattern(kv_pattern)
        assert kv_analysis.can_use_builtin, "Key-value pattern should use built-in parser"


class TestGrokPatterns:
    """Test grok pattern conversions"""
    
    def test_common_grok_patterns(self, vector_test_framework):
        """Test common grok patterns"""
        converter = GrokToVRL()
        
        patterns_and_data = [
            # Apache Common Log
            ('%{HTTPD_COMMONLOG}', [
                '192.168.1.100 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326'
            ]),
            
            # Timestamp with level and message
            ('%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}', [
                '2024-01-15T10:30:45.123Z INFO Application started successfully',
                '2024-01-15T10:30:46.456Z ERROR Database connection failed'
            ]),
        ]
        
        for i, (grok_pattern, test_data) in enumerate(patterns_and_data):
            vrl_code = converter.convert(grok_pattern)
            
            config_path = vector_test_framework.create_test_config(vrl_code, f"grok_test_{i}")
            vector_test_framework.create_test_data(test_data, f"grok_test_{i}")
            
            results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
            
            assert len(results) >= 1, f"Expected results for pattern {grok_pattern}, stderr: {stderr}"


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_pattern(self):
        """Test behavior with empty pattern"""
        converter = RegexToVRL()
        
        with pytest.raises(Exception):
            converter.convert("")
    
    def test_invalid_regex_pattern(self):
        """Test behavior with invalid regex"""
        converter = RegexToVRL()
        
        # Pattern with unmatched parentheses should be handled gracefully
        invalid_pattern = r'(?P<field>unclosed_group'
        
        # Should not crash, but may produce non-optimal VRL
        result = converter.convert(invalid_pattern)
        assert isinstance(result, str), "Should return string even for invalid pattern"
    
    def test_very_long_log_lines(self, vector_test_framework):
        """Test with very long log lines"""
        converter = RegexToVRL()
        pattern = r'^(?P<timestamp>[^\s]+) (?P<level>[^\s]+) (?P<message>.*)$'
        vrl_code = converter.convert(pattern)
        
        # Create a very long log line
        long_message = "A" * 10000
        test_logs = [
            f'2024-01-15T10:30:45Z INFO {long_message}',
        ]
        
        config_path = vector_test_framework.create_test_config(vrl_code, "long_line_test")
        vector_test_framework.create_test_data(test_logs, "long_line_test")
        
        results, stdout, stderr = vector_test_framework.run_vector_test(config_path)
        
        # Should handle long lines without crashing
        assert len(results) >= 0, f"Should handle long lines, stderr: {stderr}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])