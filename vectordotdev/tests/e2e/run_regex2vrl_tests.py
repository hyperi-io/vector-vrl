#!/usr/bin/env python3
"""
Test runner for regex2vrl integration tests with Vector execution.
This script coordinates Vector testing with regex2vrl generated configurations.
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add regex2vrl to path
sys.path.insert(0, str(Path(__file__).parent.parent / "vectordotdev"))

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL
from test_data.sample_logs import LogDataGenerator


class VectorTestRunner:
    """Runs comprehensive regex2vrl tests using Vector execution"""
    
    def __init__(self, vector_binary: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.vector_binary = self._find_vector_binary(vector_binary)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="regex2vrl_integration_"))
        self.results = {"passed": 0, "failed": 0, "tests": []}
        
        # Set up directories
        self.config_dir = self.temp_dir / "configs"
        self.data_dir = self.temp_dir / "data"
        self.output_dir = self.temp_dir / "output"
        
        for dir_path in [self.config_dir, self.data_dir, self.output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        if self.verbose:
            print(f"Test workspace: {self.temp_dir}")
    
    def _find_vector_binary(self, custom_path: Optional[str]) -> Optional[Path]:
        """Locate Vector binary"""
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return path
        
        # Search common locations
        search_paths = [
            Path("vector/target/release/vector"),
            Path("vector/target/debug/vector"),
            Path("target/release/vector"),
            Path("target/debug/vector"),
            Path("./vector"),
            Path("/usr/local/bin/vector"),
            Path("/usr/bin/vector"),
        ]
        
        for path in search_paths:
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
    
    def create_vector_config(self, vrl_source: str, test_name: str, 
                           input_data: List[str], expected_fields: Dict[str, Any] = None) -> Path:
        """Create Vector configuration for testing VRL code"""
        
        input_file = self.data_dir / f"{test_name}_input.log"
        output_file = self.output_dir / f"{test_name}_output.jsonl"
        
        # Write input data
        with open(input_file, 'w') as f:
            for line in input_data:
                f.write(line + '\n')
        
        # Create Vector config
        config = {
            "data_dir": str(self.temp_dir / "vector_data"),
            "sources": {
                "test_input": {
                    "type": "file",
                    "include": [str(input_file)],
                    "read_from": "beginning",
                    "remove_after_secs": 1
                }
            },
            "transforms": {
                "regex2vrl_transform": {
                    "type": "remap",
                    "inputs": ["test_input"],
                    "source": vrl_source
                }
            },
            "sinks": {
                "test_output": {
                    "type": "file",
                    "inputs": ["regex2vrl_transform"],
                    "path": str(output_file),
                    "encoding": {
                        "codec": "json"
                    }
                }
            }
        }
        
        config_file = self.config_dir / f"{test_name}.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_file
    
    def run_vector_test(self, config_path: Path, timeout: int = 15) -> Tuple[bool, List[Dict], str]:
        """Run Vector with configuration and return results"""
        if not self.vector_binary:
            return False, [], "Vector binary not found"
        
        if self.verbose:
            print(f"Running Vector with config: {config_path}")
        
        # Start Vector process
        try:
            process = subprocess.Popen([
                str(self.vector_binary),
                "--config", str(config_path),
                "--quiet" if not self.verbose else "--verbose"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let Vector process for a bit
            time.sleep(3)
            
            # Stop Vector gracefully
            process.terminate()
            stdout, stderr = process.communicate(timeout=timeout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return False, [], f"Vector timed out after {timeout}s"
        except Exception as e:
            return False, [], f"Vector execution failed: {e}"
        
        # Parse output
        test_name = config_path.stem
        output_file = self.output_dir / f"{test_name}_output.jsonl"
        
        results = []
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line.strip()))
            except Exception as e:
                return False, [], f"Failed to parse output: {e}"
        
        success = len(results) > 0
        error_msg = stderr if stderr and not success else ""
        
        return success, results, error_msg
    
    def test_pattern_conversion(self, pattern: str, pattern_type: str, 
                              test_data: List[str], test_name: str,
                              expected_fields: List[str] = None) -> Dict[str, Any]:
        """Test a specific pattern conversion"""
        
        if self.verbose:
            print(f"\n--- Testing {test_name} ---")
            print(f"Pattern: {pattern}")
            print(f"Type: {pattern_type}")
        
        try:
            # Convert pattern to VRL
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern, output_format='commented')
                analysis = converter.analyze_pattern(pattern)
            else:  # grok
                converter = GrokToVRL()
                vrl_code = converter.convert(pattern)
                # For grok, expand to regex first for analysis
                expanded = converter._expand_grok_to_regex(pattern)
                regex_converter = RegexToVRL()
                analysis = regex_converter.analyze_pattern(expanded)
            
            if self.verbose:
                print(f"Generated VRL ({len(vrl_code)} chars)")
                print(f"Estimated THG: {analysis.estimated_thg}")
            
            # Create and run Vector test
            config_path = self.create_vector_config(vrl_code, test_name, test_data)
            success, results, error_msg = self.run_vector_test(config_path)
            
            test_result = {
                "test_name": test_name,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "success": success,
                "input_count": len(test_data),
                "output_count": len(results),
                "estimated_thg": analysis.estimated_thg,
                "can_use_builtin": analysis.can_use_builtin,
                "suggested_parser": analysis.suggested_parser,
                "results": results[:3] if results else [],  # Sample results
                "error": error_msg
            }
            
            # Validate expected fields if provided
            if expected_fields and results:
                field_validation = {}
                for field in expected_fields:
                    field_validation[field] = any(field in result for result in results)
                test_result["field_validation"] = field_validation
            
            if success:
                self.results["passed"] += 1
                if self.verbose:
                    print(f"✅ PASSED - Processed {len(results)} records")
            else:
                self.results["failed"] += 1
                if self.verbose:
                    print(f"❌ FAILED - {error_msg}")
            
            self.results["tests"].append(test_result)
            return test_result
            
        except Exception as e:
            error_result = {
                "test_name": test_name,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "success": False,
                "error": str(e)
            }
            self.results["failed"] += 1
            self.results["tests"].append(error_result)
            
            if self.verbose:
                print(f"❌ EXCEPTION - {e}")
            
            return error_result
    
    def run_comprehensive_test_suite(self):
        """Run comprehensive test suite"""
        print("🚀 Starting regex2vrl Integration Test Suite")
        print("=" * 60)
        
        # Generate test data
        generator = LogDataGenerator()
        test_data = generator.generate_test_suite()
        
        # Define test cases
        test_cases = [
            # Apache Combined Log Format
            {
                "pattern": r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^\s]+) HTTP/(?P<version>[\d\.]+)" (?P<status>\d{3}) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"',
                "type": "regex",
                "data": test_data["apache_combined"][:10],
                "name": "apache_combined_regex",
                "expected_fields": ["ip", "method", "status"]
            },
            
            # Grok Apache Pattern
            {
                "pattern": "%{HTTPD_COMBINEDLOG}",
                "type": "grok",
                "data": test_data["apache_combined"][:10],
                "name": "apache_combined_grok",
                "expected_fields": []
            },
            
            # Syslog Pattern
            {
                "pattern": r'^(?P<month>\w{3}) (?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<hostname>\S+) (?P<program>\w+)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)$',
                "type": "regex",
                "data": test_data["syslog"][:8],
                "name": "syslog_regex",
                "expected_fields": ["hostname", "program", "message"]
            },
            
            # Grok Syslog Pattern
            {
                "pattern": "%{SYSLOGTIMESTAMP:timestamp} %{HOSTNAME:host} %{WORD:program}(?:\\[%{POSINT:pid}\\])?: %{GREEDYDATA:message}",
                "type": "grok", 
                "data": test_data["syslog"][:8],
                "name": "syslog_grok",
                "expected_fields": ["host", "program", "message"]
            },
            
            # JSON Pattern (should use parse_json!)
            {
                "pattern": r'^(?P<json_data>\{.*\})$',
                "type": "regex",
                "data": test_data["json_application"][:12],
                "name": "json_regex",
                "expected_fields": ["json_data"]
            },
            
            # Custom Delimiter Pattern
            {
                "pattern": r'^(?P<timestamp>[^|]+)\|(?P<level>[^|]+)\|(?P<component>[^|]+)\|(?P<message>.*)$',
                "type": "regex",
                "data": test_data["custom_delimited"][:6],
                "name": "custom_delimiter",
                "expected_fields": ["timestamp", "level", "component", "message"]
            },
            
            # Simple IP extraction
            {
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
                "type": "regex",
                "data": ["IP: 192.168.1.100", "Address: 10.0.0.1", "Client: 172.16.0.50"],
                "name": "ip_extraction",
                "expected_fields": ["ip"]
            },
            
            # Timestamp patterns
            {
                "pattern": r'^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*',
                "type": "regex",
                "data": ["2024-01-15 10:30:45 Application started", "2024-01-15 10:30:46 User logged in"],
                "name": "timestamp_extraction",
                "expected_fields": ["timestamp"]
            }
        ]
        
        # Run tests in parallel for speed
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for test_case in test_cases:
                future = executor.submit(
                    self.test_pattern_conversion,
                    test_case["pattern"],
                    test_case["type"], 
                    test_case["data"],
                    test_case["name"],
                    test_case.get("expected_fields", [])
                )
                futures.append(future)
            
            # Wait for completion
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Test execution error: {e}")
    
    def run_performance_tests(self):
        """Run performance-focused tests"""
        print("\n🔥 Performance Validation Tests")
        print("=" * 40)
        
        converter = RegexToVRL()
        
        # Test patterns for THG ratings
        patterns = [
            ("Simple IP", r'(?P<ip>\d+\.\d+\.\d+\.\d+)', 350),
            ("JSON detection", r'(?P<json>\{.*\})', 350),
            ("Complex nested", r'(?P<data>.*?(?:(?:ERROR|WARN).+?|.*?)(?:(?P<nested>(?:(?:[A-Z]+.*?)*)+).*?)*)', 100),
            ("Greedy quantifiers", r'(?P<match>.*?.*?.*?)', 150),
        ]
        
        for name, pattern, expected_min_thg in patterns:
            analysis = converter.analyze_pattern(pattern)
            
            status = "✅" if analysis.estimated_thg >= expected_min_thg else "⚠️"
            print(f"{status} {name}: THG {analysis.estimated_thg} (expected ≥{expected_min_thg})")
            
            if analysis.can_use_builtin:
                print(f"   Built-in parser: {analysis.suggested_parser}")
    
    def generate_report(self) -> str:
        """Generate test report"""
        total_tests = self.results["passed"] + self.results["failed"] 
        pass_rate = (self.results["passed"] / total_tests * 100) if total_tests > 0 else 0
        
        report = f"""
regex2vrl Integration Test Report
{"=" * 50}

Summary:
  Total Tests: {total_tests}
  Passed: {self.results["passed"]} ✅
  Failed: {self.results["failed"]} ❌
  Pass Rate: {pass_rate:.1f}%

Test Details:
"""
        
        for test in self.results["tests"]:
            status = "✅" if test["success"] else "❌"
            report += f"\n{status} {test['test_name']}"
            
            if test["success"]:
                report += f" - Processed {test.get('output_count', 0)} records"
                if 'estimated_thg' in test:
                    report += f" (THG: {test['estimated_thg']})"
            else:
                report += f" - ERROR: {test.get('error', 'Unknown error')}"
            
            if test.get("can_use_builtin"):
                report += f" [Built-in: {test.get('suggested_parser')}]"
        
        return report
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            if self.verbose:
                print(f"Cleaned up {self.temp_dir}")


def main():
    parser = argparse.ArgumentParser(description='Run regex2vrl integration tests with Vector')
    parser.add_argument('--vector-binary', help='Path to Vector binary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--performance-only', action='store_true', help='Run only performance tests')
    parser.add_argument('--quick', action='store_true', help='Run reduced test suite')
    parser.add_argument('--output', '-o', help='Save report to file')
    
    args = parser.parse_args()
    
    runner = VectorTestRunner(vector_binary=args.vector_binary, verbose=args.verbose)
    
    try:
        if not runner.vector_binary:
            print("❌ Vector binary not found!")
            print("Please ensure Vector is built or specify path with --vector-binary")
            return 1
        
        print(f"Using Vector binary: {runner.vector_binary}")
        
        if args.performance_only:
            runner.run_performance_tests()
        else:
            runner.run_comprehensive_test_suite()
            if not args.quick:
                runner.run_performance_tests()
        
        # Generate report
        report = runner.generate_report()
        print(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"\nReport saved to: {args.output}")
        
        # Return appropriate exit code
        return 0 if runner.results["failed"] == 0 else 1
        
    finally:
        if not args.verbose:  # Keep files for debugging if verbose
            runner.cleanup()


if __name__ == '__main__':
    sys.exit(main())