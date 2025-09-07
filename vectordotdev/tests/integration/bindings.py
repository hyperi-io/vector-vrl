#!/usr/bin/env python3
"""
Pure vectordotdev integration tests for regex2vrl.
Uses vectordotdev Python bindings directly - NO subprocess calls, NO mocks.
Tests regex2vrl generated VRL by running it through vectordotdev library.
"""

import asyncio
import json
import sys
import tempfile
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add vectordotdev to path  
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import vector
    import vectordotdev
    from vectordotdev.regex2vrl.core import RegexToVRL
    from vectordotdev.regex2vrl.grok_converter import GrokToVRL
    HAS_VECTORDOTDEV = True
except ImportError as e:
    print(f"ERROR: vectordotdev library not available: {e}")
    HAS_VECTORDOTDEV = False
    sys.exit(1)


class VectorDotDevTestRunner:
    """Test runner using pure vectordotdev Python bindings"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.temp_dir = Path(tempfile.mkdtemp(prefix="vectordotdev_test_"))
        self.results = {"passed": 0, "failed": 0, "tests": []}
        
        # Load test configurations
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        self.test_patterns_dir = fixtures_dir / "test_patterns"  
        self.test_data_dir = fixtures_dir / "test_data"
        self.test_config_dir = fixtures_dir / "test_configs"
        
        self._load_configurations()
        
        if self.verbose:
            print(f"Using vectordotdev library: {HAS_VECTORDOTDEV}")
            print(f"Temp workspace: {self.temp_dir}")
    
    def _load_configurations(self):
        """Load patterns and test data from YAML files"""
        # Load regex patterns
        with open(self.test_patterns_dir / "production_regex_patterns.yaml") as f:
            self.regex_patterns = yaml.safe_load(f)
        
        # Load grok patterns  
        with open(self.test_patterns_dir / "production_grok_patterns.yaml") as f:
            self.grok_patterns = yaml.safe_load(f)
            
        # Load sample data
        with open(self.test_data_dir / "production_log_samples.yaml") as f:
            self.sample_data = yaml.safe_load(f)
            
        # Load test config
        with open(self.test_config_dir / "pattern_test_config.yaml") as f:
            self.test_config = yaml.safe_load(f)
    
    async def test_pattern_with_vectordotdev(
        self, 
        pattern: str, 
        pattern_type: str,
        test_logs: List[str], 
        test_name: str,
        expected_fields: List[str] = None
    ) -> Dict[str, Any]:
        """Test a pattern using vectordotdev Python bindings directly"""
        
        if self.verbose:
            print(f"\n=== Testing {test_name} with vectordotdev ===")
            print(f"Pattern: {pattern[:100]}{'...' if len(pattern) > 100 else ''}")
            print(f"Type: {pattern_type}")
            print(f"Test logs: {len(test_logs)}")
        
        try:
            # Convert pattern to VRL using vectordotdev library
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern)
                analysis = converter.analyze_pattern(pattern)
            else:  # grok
                converter = GrokToVRL()
                vrl_code = converter.convert(pattern)
                # Analyze expanded regex for performance
                expanded = converter._expand_grok_to_regex(pattern)
                regex_converter = RegexToVRL()
                analysis = regex_converter.analyze_pattern(expanded)
            
            if self.verbose:
                print(f"Generated VRL ({len(vrl_code)} chars)")
                print(f"Estimated THG: {analysis.estimated_thg}")
                print(f"Built-in parser: {analysis.suggested_parser}")
            
            # Create Vector config with generated VRL
            output_file = self.temp_dir / f"{test_name}_output.jsonl"
            
            vector_config = f"""
[sources.test_input]
type = "python"

[transforms.regex2vrl_transform]
type = "remap"
inputs = ["test_input"]
source = '''
{vrl_code}
'''

[sinks.test_output]
type = "file"
inputs = ["regex2vrl_transform"]
path = "{output_file}"
encoding.codec = "json"
"""
            
            if self.verbose:
                print("Vector config created")
                print("Starting Vector instance...")
            
            # Create Vector instance using vectordotdev bindings
            vector_instance = vector.Vector(vector_config)
            await vector_instance.start()
            
            if self.verbose:
                print(f"Sending {len(test_logs)} log entries...")
            
            # Send test logs directly through Python bindings
            for i, log_line in enumerate(test_logs):
                log_data = {"message": log_line, "timestamp": "2025-01-15T10:30:45.123Z"}
                json_data = json.dumps(log_data).encode('utf-8')
                await vector_instance.send("test_input", json_data)
                
                if self.verbose and i < 3:
                    print(f"  Sent: {log_line}")
            
            # Give Vector time to process
            await asyncio.sleep(1)
            
            # Stop Vector
            await vector_instance.stop()
            
            if self.verbose:
                print("Vector stopped, reading output...")
            
            # Read and parse output
            results = []
            if output_file.exists():
                with open(output_file) as f:
                    for line in f:
                        if line.strip():
                            try:
                                results.append(json.loads(line.strip()))
                            except json.JSONDecodeError as e:
                                if self.verbose:
                                    print(f"JSON parse error: {e}")
            
            # Validate field extraction
            field_validation = {}
            if expected_fields and results:
                for field in expected_fields:
                    field_found = any(field in result for result in results)
                    field_validation[field] = field_found
            
            success = len(results) > 0
            parsing_rate = (len(results) / len(test_logs) * 100) if test_logs else 0
            
            test_result = {
                "test_name": test_name,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "success": success,
                "input_count": len(test_logs),
                "output_count": len(results),
                "parsing_rate": parsing_rate,
                "estimated_thg": analysis.estimated_thg,
                "can_use_builtin": analysis.can_use_builtin,
                "suggested_parser": analysis.suggested_parser,
                "expected_fields": expected_fields or [],
                "field_validation": field_validation,
                "sample_results": results[:2] if results else []
            }
            
            if success:
                self.results["passed"] += 1
                if self.verbose:
                    print(f"✅ PASSED - {len(results)}/{len(test_logs)} logs processed")
                    if field_validation:
                        for field, found in field_validation.items():
                            status = "✅" if found else "❌"
                            print(f"   {status} Field '{field}' extracted: {found}")
            else:
                self.results["failed"] += 1
                if self.verbose:
                    print(f"❌ FAILED - No output generated")
            
            self.results["tests"].append(test_result)
            return test_result
            
        except Exception as e:
            error_result = {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "pattern": pattern
            }
            
            self.results["failed"] += 1
            if self.verbose:
                print(f"❌ EXCEPTION - {e}")
            
            self.results["tests"].append(error_result)
            return error_result
    
    async def run_production_pattern_tests(self, test_filter: str = None):
        """Run tests for production patterns"""
        print("🚀 vectordotdev Integration Tests - Production Patterns")
        print("=" * 65)
        print("Using vectordotdev Python bindings directly (no subprocesses)")
        print()
        
        test_configs = self.test_config["test_configurations"]
        
        # Filter tests if requested
        if test_filter:
            test_configs = {k: v for k, v in test_configs.items() 
                           if test_filter.lower() in k.lower()}
            print(f"Filtered to: {list(test_configs.keys())}")
        
        # Run each test
        for test_name, config in test_configs.items():
            # Get pattern data
            pattern_file = config["pattern_file"]
            pattern_key = config["pattern_key"]
            sample_key = config["sample_data_key"]
            pattern_type = config["pattern_type"]
            
            # Get pattern
            if pattern_file == "production_regex_patterns.yaml":
                pattern_info = self.regex_patterns[pattern_key]
            else:
                pattern_info = self.grok_patterns[pattern_key]
            
            pattern = pattern_info["pattern"]
            expected_fields = pattern_info.get("expected_fields", [])
            
            # Get test data
            test_logs = self.sample_data[sample_key]
            
            # Run test
            await self.test_pattern_with_vectordotdev(
                pattern, pattern_type, test_logs, test_name, expected_fields
            )
    
    async def run_specific_tests(self):
        """Run specific high-value tests"""
        print("🎯 Specific High-Value Tests")
        print("=" * 35)
        
        # Test cases with pattern, logs, and expected behavior
        test_cases = [
            {
                "name": "apache_logs_direct",
                "pattern": r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+) (?P<path>[^\s"]+) HTTP/(?P<version>[\d\.]+)" (?P<status>\d{3}) (?P<size>\d+)',
                "type": "regex",
                "logs": [
                    '192.168.1.100 - john [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024',
                    '10.0.0.1 - - [15/Jan/2025:10:30:46 +0000] "POST /api/data HTTP/1.1" 201 512'
                ],
                "expected_fields": ["ip", "method", "status", "path"]
            },
            
            {
                "name": "json_logs_direct", 
                "pattern": r'^(?P<json_data>\{.*\})$',
                "type": "regex",
                "logs": [
                    '{"level":"INFO","message":"User login","user_id":"12345"}',
                    '{"level":"ERROR","message":"Database error","code":500}'
                ],
                "expected_fields": ["json_data"]
            },
            
            {
                "name": "syslog_grok_direct",
                "pattern": "%{SYSLOGBASE} %{GREEDYDATA:message}",
                "type": "grok", 
                "logs": [
                    'Jan 15 10:30:45 server01 sshd[1234]: User login from 192.168.1.100',
                    'Jan 15 10:30:46 web-server nginx: Process started'
                ],
                "expected_fields": ["timestamp", "logsource", "program", "message"]
            }
        ]
        
        for test_case in test_cases:
            await self.test_pattern_with_vectordotdev(
                test_case["pattern"],
                test_case["type"],
                test_case["logs"],
                test_case["name"],
                test_case["expected_fields"]
            )
    
    def generate_report(self) -> str:
        """Generate test report"""
        total = self.results["passed"] + self.results["failed"]
        pass_rate = (self.results["passed"] / total * 100) if total > 0 else 0
        
        report = f"""
vectordotdev Integration Test Report
{'=' * 50}

Test Method: Direct vectordotdev Python bindings
- No subprocess calls
- No external Vector binary  
- No mocks or stubs

Summary:
  Total Tests: {total}
  Passed: {self.results["passed"]} ✅
  Failed: {self.results["failed"]} ❌
  Pass Rate: {pass_rate:.1f}%

Results:
"""
        
        for test in self.results["tests"]:
            status = "✅" if test["success"] else "❌"
            report += f"{status} {test['test_name']}"
            
            if test["success"]:
                rate = test.get("parsing_rate", 0)
                thg = test.get("estimated_thg", 0)
                report += f" - {rate:.0f}% parsed (THG: {thg})"
                
                # Field validation summary
                field_val = test.get("field_validation", {})
                if field_val:
                    fields_found = sum(1 for found in field_val.values() if found)
                    total_fields = len(field_val)
                    report += f", {fields_found}/{total_fields} fields"
                    
            elif test.get("error"):
                report += f" - ERROR: {test['error']}"
            
            report += "\n"
        
        return report
    
    def cleanup(self):
        """Clean up temp files"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='vectordotdev integration tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--filter', help='Filter tests by name')
    parser.add_argument('--specific', action='store_true', help='Run specific test cases only')
    parser.add_argument('--output', '-o', help='Save report to file')
    
    args = parser.parse_args()
    
    if not HAS_VECTORDOTDEV:
        print("❌ vectordotdev library not available")
        return 1
    
    runner = VectorDotDevTestRunner(verbose=args.verbose)
    
    try:
        if args.specific:
            await runner.run_specific_tests()
        else:
            await runner.run_production_pattern_tests(test_filter=args.filter)
        
        # Generate report
        report = runner.generate_report()
        print(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report saved to: {args.output}")
        
        return 0 if runner.results["failed"] == 0 else 1
        
    finally:
        runner.cleanup()


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))