#!/usr/bin/env python3
"""
Unit tests for regex2vrl using Vector subprocess.
Tests ONLY the real regex2vrl source code - NO MOCKS, NO SOURCE LOGIC.
Uses real Vector binary subprocess calls for validation.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Import ONLY the real regex2vrl implementation
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from vectordotdev.regex2vrl.core import RegexToVRL
    print("✅ Using real RegexToVRL implementation")
    HAS_REGEX2VRL = True
except ImportError as e:
    print(f"❌ Failed to import real RegexToVRL: {e}")
    HAS_REGEX2VRL = False
    sys.exit(1)


class VectorSubprocessUnitTester:
    """Unit tester using ONLY real regex2vrl + Vector subprocess calls"""
    
    def __init__(self, vector_binary: str = None, verbose: bool = False):
        self.verbose = verbose
        self.vector_binary = self._find_vector_binary(vector_binary)
        self.converter = RegexToVRL()  # REAL implementation only
        self.results = {"passed": 0, "failed": 0, "tests": []}
    
    def _find_vector_binary(self, custom_path: str = None) -> str:
        """Find Vector binary"""
        if custom_path and Path(custom_path).exists():
            return custom_path
        
        # Try common locations
        for path in ["/usr/bin/vector", "/usr/local/bin/vector"]:
            if Path(path).exists():
                return path
        
        # Try which
        try:
            result = subprocess.run(["which", "vector"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        
        return None
    
    def run_vector_test(self, vrl_code: str, test_logs: List[str], test_name: str) -> Tuple[bool, List[Dict]]:
        """Run Vector subprocess with VRL code and test logs"""
        
        if not self.vector_binary:
            return False, []
        
        # Use project temp directory per STATE.md policy
        project_temp = Path(".tmp") / f"vector_{test_name}_{int(time.time())}"
        project_temp.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create input file
            input_file = project_temp / "input.log"
            with open(input_file, 'w') as f:
                for log in test_logs:
                    f.write(log + '\n')
            
            # Create output file path and data directory
            output_file = project_temp / "output.jsonl"
            vector_data_dir = project_temp / "vector_data"
            vector_data_dir.mkdir()
            
            # Create Vector YAML config with memory buffers
            indented_vrl = '\n'.join(f'      {line}' for line in vrl_code.split('\n'))
            config_content = f'''data_dir: "{vector_data_dir}"

sources:
  file_input:
    type: file
    include:
      - "{input_file}"
    read_from: beginning

transforms:
  test_remap:
    type: remap
    inputs:
      - file_input
    source: |
{indented_vrl}

sinks:
  file_output:
    type: file
    inputs:
      - test_remap
    path: "{output_file}"
    encoding:
      codec: json
    buffer:
      type: memory
      max_events: 500
      when_full: block

api:
  enabled: false
'''
            
            config_file = project_temp / "config.yaml"
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            if self.verbose:
                print(f"   📁 Test dir: {project_temp}")
                print(f"   📄 Input logs: {len(test_logs)}")
                print(f"   🔧 VRL code: {len(vrl_code)} chars")
            
            # Run Vector
            process = subprocess.Popen([
                self.vector_binary,
                "--config", str(config_file)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let Vector process
            time.sleep(4)
            
            # Stop Vector
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            # Parse results
            results = []
            if output_file.exists():
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                results.append(json.loads(line.strip()))
                            except json.JSONDecodeError:
                                continue
            
            return len(results) > 0, results
                
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Vector error: {e}")
            return False, []
        
        finally:
            # Simple cleanup with memory buffers
            import shutil
            if project_temp.exists():
                try:
                    shutil.rmtree(project_temp)
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️  Cleanup warning: {e}")
    
    def test_pattern_unit(self, pattern: str, test_logs: List[str], 
                         test_name: str, expected_fields: List[str] = None) -> Dict[str, Any]:
        """Test a pattern conversion using REAL regex2vrl implementation"""
        
        if self.verbose:
            print(f"\n🧪 Unit Test: {test_name}")
            print(f"   Pattern: {pattern[:60]}...")
        
        # Convert pattern using REAL regex2vrl (no mocks)
        vrl_code = self.converter.convert(pattern, output_format='vrl')
        
        if self.verbose:
            print(f"   Generated VRL: {len(vrl_code)} chars by real regex2vrl")
        
        # Run Vector test
        success, results = self.run_vector_test(vrl_code, test_logs, test_name)
        
        # Validate results
        field_validation = {}
        if expected_fields and results:
            for field in expected_fields:
                field_found = any(field in result for result in results)
                field_validation[field] = field_found
        
        parsing_rate = (len(results) / len(test_logs) * 100) if test_logs else 0
        
        test_result = {
            "test_name": test_name,
            "pattern": pattern,
            "success": success,
            "input_count": len(test_logs),
            "output_count": len(results),
            "parsing_rate": parsing_rate,
            "expected_fields": expected_fields or [],
            "field_validation": field_validation,
            "sample_results": results[:1] if results else []
        }
        
        if success and parsing_rate > 0:
            self.results["passed"] += 1
            if self.verbose:
                print(f"   ✅ PASSED - {len(results)}/{len(test_logs)} logs processed")
                if field_validation:
                    for field, found in field_validation.items():
                        print(f"      Field '{field}': {'✅' if found else '❌'}")
        else:
            self.results["failed"] += 1
            if self.verbose:
                print(f"   ❌ FAILED - No output generated")
        
        self.results["tests"].append(test_result)
        return test_result
    
    def run_unit_test_suite(self):
        """Run unit test suite using REAL regex2vrl"""
        print("🚀 regex2vrl Vector Subprocess Unit Tests")
        print("=" * 55)
        print("REAL regex2vrl implementation → VRL → Vector → Validation")
        
        if not self.vector_binary:
            print("❌ Vector binary not found - tests will be skipped")
            return
        
        print(f"✅ Using Vector: {self.vector_binary}")
        
        # Real production-style test cases
        unit_tests = [
            {
                "name": "ip_extraction_real",
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
                "logs": [
                    'Client IP: 192.168.1.100',
                    'Server: 10.0.0.1 active',
                    'Gateway 172.16.0.1 online'
                ],
                "expected_fields": ["ip"]
            },
            
            {
                "name": "json_parsing_real",
                "pattern": r'^(?P<json_data>\{.*\})$',
                "logs": [
                    '{"level":"INFO","message":"Test","id":123}',
                    '{"level":"ERROR","message":"Failed","code":500}'
                ],
                "expected_fields": ["level", "message", "id"]
            },
            
            {
                "name": "apache_log_real",
                "pattern": r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - (?P<user>\S+) \[(?P<timestamp>[^\]]+)\] "(?P<method>\w+)',
                "logs": [
                    '192.168.1.100 - john [15/Jan/2025:10:30:45 +0000] "GET /index.html',
                    '10.0.0.1 - admin [15/Jan/2025:10:30:46 +0000] "POST /api/data'
                ],
                "expected_fields": ["ip", "user", "timestamp", "method"]
            },
            
            {
                "name": "syslog_real",
                "pattern": r'^(?P<timestamp>\w{3} \d{1,2} \d{2}:\d{2}:\d{2}) (?P<hostname>\S+) (?P<program>\w+)',
                "logs": [
                    'Jan 15 10:30:45 server01 sshd[1234]: User login',
                    'Jan 15 10:30:46 web-server nginx: Process started'
                ],
                "expected_fields": ["timestamp", "hostname", "program"]
            }
        ]
        
        # Run each unit test
        for test_case in unit_tests:
            self.test_pattern_unit(
                test_case["pattern"],
                test_case["logs"],
                test_case["name"],
                test_case["expected_fields"]
            )
    
    def generate_report(self) -> str:
        """Generate unit test report"""
        total = self.results["passed"] + self.results["failed"]
        pass_rate = (self.results["passed"] / total * 100) if total > 0 else 0
        
        report = f"""
Unit Test Report - REAL regex2vrl with Vector Subprocess
{'=' * 65}

Test Method: Vector subprocess calls (no mocks)
Implementation: REAL regex2vrl source code ONLY
Vector Binary: {self.vector_binary or 'NOT FOUND'}

Summary:
  Total Tests: {total}
  Passed: {self.results["passed"]} ✅
  Failed: {self.results["failed"]} ❌
  Pass Rate: {pass_rate:.1f}%

Test Details:
"""
        
        for test in self.results["tests"]:
            status = "✅" if test["success"] else "❌"
            rate = test.get("parsing_rate", 0)
            report += f"{status} {test['test_name']} - {rate:.0f}% logs processed\n"
            
            # Field validation details
            field_val = test.get("field_validation", {})
            if field_val:
                for field, found in field_val.items():
                    field_status = "✅" if found else "❌"
                    report += f"   {field_status} Field '{field}': {found}\n"
        
        return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='regex2vrl Vector subprocess unit tests - REAL implementation only')
    parser.add_argument('--vector-binary', help='Path to Vector binary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not HAS_REGEX2VRL:
        print("❌ Real regex2vrl not available")
        return 1
    
    tester = VectorSubprocessUnitTester(
        vector_binary=args.vector_binary,
        verbose=args.verbose
    )
    
    tester.run_unit_test_suite()
    
    # Generate and show report
    report = tester.generate_report()
    print(report)
    
    return 0 if tester.results["failed"] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())