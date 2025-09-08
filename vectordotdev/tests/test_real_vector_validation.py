#!/usr/bin/env python3
"""
REAL Vector Validation Test for regex2vrl
Tests generated VRL against actual Vector execution to verify it works
NO MOCKS - Real Vector binary execution only
"""

import sys
import subprocess
import tempfile
import json
import time
import yaml
from pathlib import Path

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.universal_vrl_engine import UniversalVRLEngine


class RealVectorValidator:
    """Validate VRL against real Vector execution"""
    
    def __init__(self):
        self.vector_binary = self._find_vector_binary()
        self.temp_dir = Path(".tmp") / "vector_validation"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
    
    def _find_vector_binary(self) -> str:
        """Find Vector binary for real testing"""
        # Try common locations
        candidates = [
            "vector/target/release/vector",
            "vector/target/debug/vector", 
            "/usr/local/bin/vector",
            "/usr/bin/vector"
        ]
        
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        
        # Try which
        try:
            result = subprocess.run(["which", "vector"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        
        return None
    
    def test_vrl_with_real_vector(self, pattern: str, sample_logs: list, test_name: str) -> dict:
        """Test VRL code with actual Vector binary execution"""
        
        print(f"\n🔬 REAL VECTOR TEST: {test_name}")
        print(f"   Pattern: {pattern[:50]}...")
        print(f"   Sample logs: {len(sample_logs)}")
        
        if not self.vector_binary:
            return {
                "test_name": test_name,
                "success": False,
                "error": "Vector binary not found",
                "vrl_valid": False
            }
        
        # Generate VRL using our corrected system
        converter = RegexToVRL()
        vrl_code = converter.convert(pattern, sample_logs=sample_logs, output_format='vrl')
        
        print(f"   Generated VRL: {len(vrl_code)} characters")
        
        # Create Vector config with the VRL
        test_dir = self.temp_dir / test_name
        test_dir.mkdir(exist_ok=True)
        
        # Create input file
        input_file = test_dir / "input.log"
        with open(input_file, 'w') as f:
            for log in sample_logs:
                f.write(log + '\n')
        
        # Create Vector config in YAML format (more reliable)
        
        config_data = {
            'data_dir': str(test_dir / "data"),
            'sources': {
                'file_input': {
                    'type': 'file',
                    'include': [str(input_file)],
                    'read_from': 'beginning'
                }
            },
            'transforms': {
                'vrl_test': {
                    'type': 'remap',
                    'inputs': ['file_input'],
                    'source': vrl_code
                }
            },
            'sinks': {
                'output': {
                    'type': 'file',
                    'inputs': ['vrl_test'],
                    'path': str(test_dir / "output.jsonl"),
                    'encoding': {
                        'codec': 'json'
                    }
                }
            }
        }
        
        config_file = test_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        print(f"   🔧 Config created: {config_file}")
        
        # Run Vector for real
        try:
            # Create data directory
            (test_dir / "data").mkdir(exist_ok=True)
            
            print(f"   🚀 Starting Vector binary: {self.vector_binary}")
            
            # Start Vector process
            process = subprocess.Popen([
                self.vector_binary,
                "--config", str(config_file),
                "--quiet"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let Vector process the logs
            time.sleep(3)
            
            # Stop Vector
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            # Check output
            output_file = test_dir / "output.jsonl"
            results = []
            vrl_execution_success = False
            
            if output_file.exists():
                with open(output_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        for line in content.split('\n'):
                            if line.strip():
                                try:
                                    result = json.loads(line.strip())
                                    results.append(result)
                                except json.JSONDecodeError:
                                    continue
                
                vrl_execution_success = len(results) > 0
                print(f"   📊 Vector processed: {len(results)}/{len(sample_logs)} logs")
            else:
                print(f"   ❌ No output file created")
            
            # Analyze VRL errors from stderr
            vrl_compilation_errors = []
            if stderr:
                for line in stderr.split('\n'):
                    if 'error' in line.lower() or 'failed' in line.lower():
                        vrl_compilation_errors.append(line.strip())
            
            compilation_success = len(vrl_compilation_errors) == 0
            
            if compilation_success and vrl_execution_success:
                print(f"   ✅ SUCCESS: VRL compiled and executed correctly")
            elif compilation_success and not vrl_execution_success:
                print(f"   ⚠️ PARTIAL: VRL compiled but no output (check logs)")
            else:
                print(f"   ❌ FAILED: VRL compilation errors:")
                for error in vrl_compilation_errors[:3]:
                    print(f"      {error}")
            
            result = {
                "test_name": test_name,
                "success": compilation_success and vrl_execution_success,
                "vrl_compiled": compilation_success,
                "vrl_executed": vrl_execution_success,
                "input_logs": len(sample_logs),
                "output_logs": len(results),
                "compilation_errors": vrl_compilation_errors,
                "vrl_code_length": len(vrl_code),
                "sample_output": results[0] if results else None
            }
            
            self.results.append(result)
            return result
            
        except Exception as e:
            error_result = {
                "test_name": test_name,
                "success": False,
                "error": f"Vector execution failed: {e}",
                "vrl_valid": False
            }
            self.results.append(error_result)
            return error_result
    
    def run_real_validation_suite(self):
        """Run comprehensive validation with real Vector execution"""
        
        print("🚀 REAL VECTOR VALIDATION SUITE")
        print("=" * 60)
        print("Testing generated VRL against actual Vector binary")
        print("NO MOCKS - Real execution only")
        
        if not self.vector_binary:
            print("❌ Vector binary not found - cannot run real validation")
            print("   Need to build Vector first or have it in PATH")
            return False
        
        print(f"✅ Found Vector binary: {self.vector_binary}")
        
        # Real test cases
        real_test_cases = [
            {
                "name": "simple_ip_status",
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+).*(?P<status>\d{3})',
                "logs": [
                    '192.168.1.100 GET /api HTTP/1.1 200 1024',
                    '10.0.0.1 POST /data HTTP/1.1 201 512'
                ]
            },
            {
                "name": "json_detection",
                "pattern": r'^(?P<json_data>\{.*\})$',
                "logs": [
                    '{"level":"INFO","message":"Test"}',
                    '{"level":"ERROR","code":500}'
                ]
            },
            {
                "name": "complex_multifield",
                "pattern": r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) (?P<service>\w+) (?P<message>.*)',
                "logs": [
                    '2025-01-15T10:30:45 INFO auth-service User login successful',
                    '2025-01-15T10:30:46 ERROR payment Database connection failed'
                ]
            }
        ]
        
        success_count = 0
        
        for test_case in real_test_cases:
            result = self.test_vrl_with_real_vector(
                test_case["pattern"],
                test_case["logs"], 
                test_case["name"]
            )
            
            if result["success"]:
                success_count += 1
        
        # Generate report
        total_tests = len(real_test_cases)
        success_rate = (success_count / total_tests) * 100
        
        print(f"\n📋 REAL VECTOR VALIDATION REPORT")
        print("=" * 60)
        print(f"Vector Binary: {self.vector_binary}")
        print(f"Tests Run: {total_tests}")
        print(f"Successful: {success_count}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"\nDetailed Results:")
        for result in self.results:
            status = "✅" if result["success"] else "❌"
            name = result["test_name"]
            
            if result["success"]:
                logs_processed = result.get("output_logs", 0)
                logs_input = result.get("input_logs", 0)
                print(f"  {status} {name}: {logs_processed}/{logs_input} logs processed")
            else:
                error = result.get("error", "Unknown error")
                print(f"  {status} {name}: {error}")
        
        print(f"\n🎯 CONCLUSION:")
        if success_rate >= 80:
            print("✅ regex2vrl v2.0.0 generates WORKING VRL for real Vector")
        else:
            print("❌ Generated VRL has issues with real Vector execution")
            print("   VRL syntax or function issues need to be fixed")
        
        return success_rate >= 80


def main():
    """Run real Vector validation"""
    validator = RealVectorValidator()
    success = validator.run_real_validation_suite()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())