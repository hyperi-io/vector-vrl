#!/usr/bin/env python3
"""
Unit tests for regex2vrl using subprocess Vector calls.
Tests regex2vrl by running actual Vector binary as subprocess - NO MOCKS.
These are isolated unit tests that test the complete pipeline independently.

Requirements:
- Vector binary must be built or available in PATH
- Tests use real Vector process execution as isolated units
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from vectordotdev.regex2vrl.core import RegexToVRL
    from vectordotdev.regex2vrl.grok_converter import GrokToVRL
    HAS_REGEX2VRL = True
except ImportError as e:
    print(f"ERROR: regex2vrl not available: {e}")
    HAS_REGEX2VRL = False


class VectorSubprocessUnitTester:
    """Unit tester using real Vector subprocess calls"""
    
    def __init__(self, vector_binary: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.vector_binary = self._find_vector_binary(vector_binary)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vector_subprocess_test_"))
        self.results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}
        
        # Create subdirectories
        self.config_dir = self.temp_dir / "configs"
        self.data_dir = self.temp_dir / "data"
        self.output_dir = self.temp_dir / "output"
        
        for d in [self.config_dir, self.data_dir, self.output_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        if self.verbose:
            print(f"Vector binary: {self.vector_binary}")
            print(f"regex2vrl available: {HAS_REGEX2VRL}")
            print(f"Test workspace: {self.temp_dir}")
    
    def _find_vector_binary(self, custom_path: Optional[str]) -> Optional[Path]:
        """Find Vector binary"""
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)
        
        # Search project locations
        search_paths = [
            "vector/target/release/vector",
            "vector/target/debug/vector", 
            "../vector/target/release/vector",
            "../vector/target/debug/vector",
        ]
        
        for path_str in search_paths:
            path = Path(path_str)
            if path.exists() and path.is_file():
                return path.resolve()
        
        # Try system PATH
        try:
            result = subprocess.run(["which", "vector"], 
                                  capture_output=True, text=True, check=True)
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            pass
        
        return None
    
    def create_vector_config(self, vrl_code: str, test_name: str, 
                           input_logs: List[str]) -> Path:
        """Create Vector config file"""
        input_file = self.data_dir / f"{test_name}_input.log"
        output_file = self.output_dir / f"{test_name}_output.jsonl"
        
        # Write input logs
        with open(input_file, 'w') as f:
            for log in input_logs:
                f.write(log + '\n')
        
        # Create Vector config
        config = {
            "data_dir": str(self.temp_dir / "vector_data"),
            "sources": {
                "file_input": {
                    "type": "file",
                    "include": [str(input_file)],
                    "read_from": "beginning",
                    "remove_after_secs": 3
                }
            },
            "transforms": {
                "regex2vrl_transform": {
                    "type": "remap",
                    "inputs": ["file_input"],
                    "source": vrl_code
                }
            },
            "sinks": {
                "file_output": {
                    "type": "file", 
                    "inputs": ["regex2vrl_transform"],
                    "path": str(output_file),
                    "encoding": {"codec": "json"}
                }
            }
        }
        
        config_file = self.config_dir / f"{test_name}_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_file
    
    def run_vector_subprocess(self, config_path: Path, timeout: int = 30) -> Tuple[bool, List[Dict], str]:
        """Run Vector as subprocess and return results"""
        if not self.vector_binary:
            return False, [], "Vector binary not found"
        
        try:
            if self.verbose:
                print(f"Running: {self.vector_binary} --config {config_path}")
            
            # Start Vector process
            process = subprocess.Popen([
                str(self.vector_binary),
                "--config", str(config_path),
                "--quiet"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let Vector process the files
            time.sleep(5)
            
            # Stop Vector 
            process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            
            # Parse output
            test_name = config_path.stem.replace("_config", "")
            output_file = self.output_dir / f"{test_name}_output.jsonl"
            
            results = []
            if output_file.exists():
                with open(output_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                results.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            
            success = len(results) > 0
            error_msg = stderr if stderr and not success else ""
            
            return success, results, error_msg
            
        except subprocess.TimeoutExpired:
            process.kill()
            return False, [], f"Vector timed out after {timeout}s"
        except Exception as e:
            return False, [], f"Vector execution error: {e}"
    
    def test_pattern_unit(self, pattern: str, pattern_type: str, 
                               test_logs: List[str], test_name: str,
                               expected_fields: List[str] = None) -> Dict[str, Any]:
        """Test pattern with subprocess Vector as unit test"""
        
        if self.verbose:
            print(f"\n=== Unit Test: {test_name} ===")
            print(f"Pattern: {pattern[:80]}...")
            print(f"Type: {pattern_type}, Logs: {len(test_logs)}")
        
        result = {
            "test_name": test_name,
            "pattern": pattern,
            "pattern_type": pattern_type,
            "success": False
        }
        
        try:
            # Check prerequisites
            if not HAS_REGEX2VRL:
                result.update({"skipped": True, "error": "regex2vrl not available"})
                self.results["skipped"] += 1
                return result
                
            if not self.vector_binary:
                result.update({"skipped": True, "error": "Vector binary not found"})
                self.results["skipped"] += 1
                return result
            
            # Convert pattern to VRL
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern, output_format='commented')
                analysis = converter.analyze_pattern(pattern)
            else:  # grok
                converter = GrokToVRL() 
                vrl_code = converter.convert(pattern)
                expanded = converter._expand_grok_to_regex(pattern)
                regex_converter = RegexToVRL()
                analysis = regex_converter.analyze_pattern(expanded)
            
            if self.verbose:
                print(f"Generated VRL: {len(vrl_code)} chars")
                print(f"Estimated THG: {analysis.estimated_thg}")
            
            # Create Vector config and run
            config_path = self.create_vector_config(vrl_code, test_name, test_logs)
            success, results, error = self.run_vector_subprocess(config_path)
            
            # Analyze results
            parsing_rate = (len(results) / len(test_logs) * 100) if test_logs else 0
            
            # Field validation
            field_validation = {}
            if expected_fields and results:
                for field in expected_fields:
                    field_found = any(field in res for res in results)
                    field_validation[field] = field_found
            
            # Update result
            result.update({
                "success": success,
                "input_count": len(test_logs),
                "output_count": len(results), 
                "parsing_rate": parsing_rate,
                "estimated_thg": analysis.estimated_thg,
                "can_use_builtin": analysis.can_use_builtin,
                "suggested_parser": analysis.suggested_parser,
                "expected_fields": expected_fields or [],
                "field_validation": field_validation,
                "sample_results": results[:2] if results else [],
                "error": error
            })
            
            if success:
                self.results["passed"] += 1
                if self.verbose:
                    print(f"✅ PASSED - {len(results)}/{len(test_logs)} logs processed")
                    for field, found in field_validation.items():
                        print(f"   Field '{field}': {'✅' if found else '❌'}")
            else:
                self.results["failed"] += 1
                if self.verbose:
                    print(f"❌ FAILED - {error or 'No output generated'}")
            
            self.results["tests"].append(result)
            return result
            
        except Exception as e:
            result.update({"error": str(e)})
            self.results["failed"] += 1
            if self.verbose:
                print(f"❌ EXCEPTION - {e}")
            
            self.results["tests"].append(result)
            return result
    
    def run_unit_test_suite(self):
        """Run comprehensive unit test suite"""
        print("🚀 Vector Subprocess Unit Tests")
        print("=" * 50)
        print("Tests regex2vrl → VRL → Vector subprocess → JSON validation")
        print()
        
        # Define test cases with real patterns and data
        test_cases = [
            {
                "name": "apache_combined_integration",
                "pattern": r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^\s"]+) HTTP/(?P<version>[\d\.]+)" (?P<status>\d{3}) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"',
                "type": "regex",
                "logs": [
                    '192.168.1.100 - john [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024 "https://google.com" "Mozilla/5.0"',
                    '10.0.0.1 - - [15/Jan/2025:10:30:46 +0000] "POST /api/data HTTP/1.1" 201 512 "-" "curl/7.68.0"'
                ],
                "expected_fields": ["ip", "method", "status", "path"]
            },
            
            {
                "name": "json_app_integration",
                "pattern": r'^(?P<json_data>\{.*\})$',
                "type": "regex",
                "logs": [
                    '{"timestamp":"2025-01-15T10:30:45Z","level":"INFO","message":"User login","user_id":"12345"}',
                    '{"timestamp":"2025-01-15T10:30:46Z","level":"ERROR","message":"Database error","error_code":500}'
                ],
                "expected_fields": ["json_data"]
            },
            
            {
                "name": "syslog_integration",
                "pattern": r'^(?P<month>\w{3}) (?P<day>\d{1,2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<hostname>\S+) (?P<program>\w+)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)$',
                "type": "regex",
                "logs": [
                    'Jan 15 10:30:45 server01 sshd[1234]: Accepted password for john from 192.168.1.100',
                    'Jan 15 10:30:46 web-server nginx: worker process started'
                ],
                "expected_fields": ["hostname", "program", "message"]
            },
            
            {
                "name": "ip_extraction_integration",
                "pattern": r'IP:\s*(?P<ip_address>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
                "type": "regex", 
                "logs": [
                    'Client IP: 192.168.1.100',
                    'Server IP: 10.0.0.1',
                    'Gateway IP: 172.16.0.1'
                ],
                "expected_fields": ["ip_address"]
            },
            
            {
                "name": "grok_apache_integration",
                "pattern": "%{COMBINEDAPACHELOG}",
                "type": "grok",
                "logs": [
                    '192.168.1.100 - frank [10/Oct/2025:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/start.html" "Mozilla/4.08 [en]"'
                ],
                "expected_fields": ["clientip", "verb", "response"]
            },
            
            {
                "name": "timestamp_extraction_integration",
                "pattern": r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?) (?P<level>\w+) (?P<message>.*)$',
                "type": "regex",
                "logs": [
                    '2025-01-15T10:30:45.123Z INFO Application started successfully',
                    '2025-01-15T10:30:46Z ERROR Database connection failed'
                ],
                "expected_fields": ["timestamp", "level", "message"]
            }
        ]
        
        # Run all test cases
        for test_case in test_cases:
            self.test_pattern_unit(
                test_case["pattern"],
                test_case["type"],
                test_case["logs"],
                test_case["name"],
                test_case["expected_fields"]
            )
    
    def generate_report(self) -> str:
        """Generate integration test report"""
        total = self.results["passed"] + self.results["failed"] + self.results["skipped"]
        pass_rate = (self.results["passed"] / total * 100) if total > 0 else 0
        
        report = f"""
Vector Subprocess Integration Test Report
{'=' * 55}

Test Method: Real Vector binary subprocess execution
Vector Binary: {self.vector_binary or 'NOT FOUND'}
regex2vrl Library: {'Available' if HAS_REGEX2VRL else 'NOT AVAILABLE'}

Summary:
  Total Tests: {total}
  Passed: {self.results["passed"]} ✅
  Failed: {self.results["failed"]} ❌
  Skipped: {self.results["skipped"]} ⏭️
  Pass Rate: {pass_rate:.1f}%

Test Results:
"""
        
        for test in self.results["tests"]:
            if test.get("skipped"):
                report += f"⏭️ {test['test_name']} - SKIPPED: {test.get('error', 'Unknown')}\n"
            elif test["success"]:
                rate = test.get("parsing_rate", 0)
                thg = test.get("estimated_thg", 0)
                report += f"✅ {test['test_name']} - {rate:.0f}% parsed (THG: {thg})\n"
                
                # Field validation details
                field_val = test.get("field_validation", {})
                if field_val:
                    found_count = sum(1 for found in field_val.values() if found)
                    total_fields = len(field_val)
                    report += f"   Fields: {found_count}/{total_fields} extracted\n"
            else:
                error = test.get("error", "Unknown error")
                report += f"❌ {test['test_name']} - FAILED: {error}\n"
        
        if self.results["skipped"] > 0:
            report += f"\nNote: {self.results['skipped']} tests skipped due to missing dependencies\n"
        
        return report
    
    def cleanup(self):
        """Clean up temp files"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Vector subprocess integration tests')
    parser.add_argument('--vector-binary', help='Path to Vector binary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--output', '-o', help='Save report to file')
    parser.add_argument('--keep-workspace', action='store_true', help='Keep temp files')
    
    args = parser.parse_args()
    
    tester = VectorSubprocessUnitTester(
        vector_binary=args.vector_binary,
        verbose=args.verbose
    )
    
    try:
        tester.run_unit_test_suite()
        
        # Generate report
        report = tester.generate_report()
        print(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report saved to: {args.output}")
        
        if args.keep_workspace:
            print(f"Workspace preserved: {tester.temp_dir}")
        
        return 0 if tester.results["failed"] == 0 else 1
        
    finally:
        if not args.keep_workspace:
            tester.cleanup()


if __name__ == '__main__':
    sys.exit(main())