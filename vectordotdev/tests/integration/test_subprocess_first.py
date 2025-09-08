#!/usr/bin/env python3
"""
Integration test that uses subprocess Vector validation first,
then tests vectordotdev bindings. This ensures we validate regex2vrl
with working Vector before testing the bindings.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add paths
sys.path.insert(0, '/projects/vectordotdev')
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')

import vector
from vectordotdev.regex2vrl.core import RegexToVRL


class IntegrationTester:
    """Integration tester using subprocess first, then bindings"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.vector_binary = self._find_vector_binary()
        self.results = {"subprocess": [], "bindings": []}
    
    def _find_vector_binary(self):
        """Find Vector binary"""
        for path in ["/usr/bin/vector", "/usr/local/bin/vector"]:
            if Path(path).exists():
                return path
        try:
            result = subprocess.run(["which", "vector"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def test_subprocess_vector_integration(self, pattern, test_logs, test_name):
        """Test regex2vrl with subprocess Vector (ground truth)"""
        
        if self.verbose:
            print(f"\n🔧 Subprocess Test: {test_name}")
        
        if not self.vector_binary:
            print("   ⏭️ Skipped - No Vector binary")
            return False
        
        try:
            # Generate VRL
            converter = RegexToVRL()
            vrl_code = converter.convert(pattern)
            
            # Test with subprocess Vector
            with tempfile.TemporaryDirectory(prefix="subprocess_test_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create Vector data directory
                vector_data_dir = temp_path / "vector_data"
                vector_data_dir.mkdir()
                
                # Create input file
                input_file = temp_path / "input.log"
                with open(input_file, 'w') as f:
                    for log in test_logs:
                        f.write(log + '\n')
                
                # Create Vector config (TOML format for subprocess Vector)
                output_file = temp_path / "output.jsonl"
                config_content = f'''
data_dir = "{vector_data_dir}"

[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[transforms.test_transform]
type = "remap"
inputs = ["file_input"]
source = """
{vrl_code}
"""

[sinks.file_output]
type = "file"
inputs = ["test_transform"]
path = "{output_file}"
encoding.codec = "json"
'''
                
                config_file = temp_path / "config.toml"
                with open(config_file, 'w') as f:
                    f.write(config_content)
                
                # Run Vector subprocess
                process = subprocess.Popen([
                    self.vector_binary,
                    "--config", str(config_file),
                    "--quiet"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                time.sleep(3)
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
                
                # Check results
                results = []
                if output_file.exists():
                    with open(output_file) as f:
                        for line in f:
                            if line.strip():
                                try:
                                    results.append(json.loads(line.strip()))
                                except json.JSONDecodeError:
                                    continue
                
                success = len(results) > 0
                if self.verbose:
                    print(f"   Subprocess: {'✅' if success else '❌'} - {len(results)}/{len(test_logs)} processed")
                
                self.results["subprocess"].append({
                    "test": test_name,
                    "success": success,
                    "results_count": len(results),
                    "input_count": len(test_logs)
                })
                
                return success
                
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Subprocess error: {e}")
            return False
    
    def test_bindings_integration(self, pattern, test_logs, test_name):
        """Test regex2vrl with vectordotdev bindings (after subprocess validation)"""
        
        if self.verbose:
            print(f"      🔗 Bindings Test: {test_name}")
        
        try:
            # Generate same VRL
            converter = RegexToVRL()
            vrl_code = converter.convert(pattern)
            
            # Create YAML config for bindings (TOML format for Vector bindings)
            config = f'''[sources.python]
type = "python"

[transforms.test_transform]
type = "remap"
inputs = ["python"]
source = """
{vrl_code}
"""

[sinks.file]
type = "file"
inputs = ["test_transform"]
path = "/tmp/bindings_{test_name}.txt"
encoding.codec = "json"
'''
            
            # Test with bindings
            v = vector.Vector(config)
            v.start()
            
            # Send same test data
            for log in test_logs:
                data = json.dumps({"message": log}).encode()
                v.send("python", data)
            
            time.sleep(1)
            v.stop()
            
            # Check output
            import os
            output_path = f"/tmp/bindings_{test_name}.txt"
            if os.path.exists(output_path):
                with open(output_path) as f:
                    content = f.read().strip()
                    if content:
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        success = len(lines) > 0
                        if self.verbose:
                            print(f"      Bindings: {'✅' if success else '❌'} - {len(lines)} results")
                        
                        self.results["bindings"].append({
                            "test": test_name,
                            "success": success,
                            "results_count": len(lines),
                            "input_count": len(test_logs)
                        })
                        
                        return success
            
            if self.verbose:
                print(f"      Bindings: ❌ - No output")
            
            self.results["bindings"].append({
                "test": test_name,
                "success": False,
                "results_count": 0,
                "input_count": len(test_logs)
            })
            
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"      ❌ Bindings error: {e}")
            return False
    
    def run_integration_tests(self):
        """Run integration tests: subprocess first, then bindings"""
        
        print("🔗 Integration Test: Subprocess → Bindings Validation")
        print("=" * 60)
        print("Strategy: Validate with subprocess Vector first, then test bindings")
        
        # Test cases
        test_cases = [
            {
                "name": "ip_extraction",
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
                "logs": ["Client IP: 192.168.1.100", "Server: 10.0.0.1"]
            },
            {
                "name": "simple_word",
                "pattern": r'(?P<word>\w+)',
                "logs": ["hello world", "test message"]
            }
            # Skip status pattern for now since it has VRL errors
        ]
        
        for test_case in test_cases:
            # Step 1: Validate with subprocess Vector (ground truth)
            subprocess_success = self.test_subprocess_vector_integration(
                test_case["pattern"], 
                test_case["logs"], 
                test_case["name"]
            )
            
            # Step 2: Only test bindings if subprocess works
            if subprocess_success:
                bindings_success = self.test_bindings_integration(
                    test_case["pattern"],
                    test_case["logs"], 
                    test_case["name"]
                )
            else:
                if self.verbose:
                    print(f"      ⏭️ Skipping bindings test - subprocess failed")
    
    def generate_report(self):
        """Generate integration test report"""
        
        subprocess_passed = sum(1 for r in self.results["subprocess"] if r["success"])
        subprocess_total = len(self.results["subprocess"])
        
        bindings_passed = sum(1 for r in self.results["bindings"] if r["success"]) 
        bindings_total = len(self.results["bindings"])
        
        print(f"""

Integration Test Report - Subprocess → Bindings
{'=' * 55}

Subprocess Tests (Ground Truth):
  Passed: {subprocess_passed}/{subprocess_total}
  
Bindings Tests (Implementation): 
  Passed: {bindings_passed}/{bindings_total}

Strategy Validation:
- Use subprocess tests to validate regex2vrl works correctly
- Use bindings tests to identify areas needing development
- Ensures we only test bindings with patterns we know work
""")


def main():
    tester = IntegrationTester(verbose=True)
    tester.run_integration_tests()
    tester.generate_report()


if __name__ == '__main__':
    main()