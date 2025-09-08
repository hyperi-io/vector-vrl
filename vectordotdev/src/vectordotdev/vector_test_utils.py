"""
Vector testing utilities with proper shell escaping and configuration management.
Provides a centralized way to test VRL code with Vector CLI without shell escaping issues.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class VectorTestRunner:
    """
    Centralized Vector test runner that handles shell escaping and configuration properly.
    NO shell escaping issues - uses file-based communication only.
    """
    
    def __init__(self, vector_binary: str = "/usr/bin/vector", verbose: bool = False):
        self.vector_binary = vector_binary
        self.verbose = verbose
        
        # Validate Vector binary exists
        if not Path(vector_binary).exists():
            raise RuntimeError(f"Vector binary not found: {vector_binary}")
    
    def test_vrl_with_vector(self, vrl_code: str, input_logs: List[str], 
                           test_name: str = "test") -> Tuple[bool, List[Dict], str]:
        """
        Test VRL code with Vector CLI using file-based communication (NO shell escaping).
        
        Returns:
            (success: bool, results: List[Dict], error_message: str)
        """
        
        # Create isolated test environment
        test_dir = Path(".tmp") / f"vector_test_{test_name}_{int(time.time())}"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create input file
            input_file = test_dir / "input.log"
            with open(input_file, 'w') as f:
                for log in input_logs:
                    f.write(log + '\n')
            
            # Create output file and data directory
            output_file = test_dir / "output.jsonl"
            data_dir = test_dir / "vector_data"
            data_dir.mkdir(exist_ok=True)
            
            # Create Vector YAML configuration (NO shell escaping needed)
            config_content = self._create_vector_yaml_config(
                input_file, output_file, data_dir, vrl_code
            )
            
            config_file = test_dir / "config.yaml"
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            if self.verbose:
                print(f"   📁 Test: {test_name}")
                print(f"   📂 Dir: {test_dir}")
                print(f"   📄 Logs: {len(input_logs)}")
                print(f"   🔧 VRL: {len(vrl_code)} chars")
            
            # Run Vector with file-based config (NO command line VRL)
            error_msg = ""
            try:
                process = subprocess.Popen([
                    self.vector_binary,
                    "--config", str(config_file)
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Let Vector process the logs
                time.sleep(3)
                
                # Stop Vector gracefully
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
                
                if stderr and ("error" in stderr.lower() or "failed" in stderr.lower()):
                    error_msg = stderr[:500]  # Capture error details
                
            except subprocess.TimeoutExpired:
                process.kill()
                error_msg = "Vector process timeout"
            except Exception as e:
                error_msg = f"Vector execution error: {e}"
            
            # Parse output results
            results = []
            success = False
            
            if output_file.exists():
                try:
                    with open(output_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    results.append(json.loads(line.strip()))
                                except json.JSONDecodeError:
                                    continue
                    
                    success = len(results) > 0
                    
                except Exception as e:
                    error_msg += f" | Output read error: {e}"
            
            if self.verbose:
                if success:
                    print(f"   ✅ SUCCESS: {len(results)}/{len(input_logs)} processed")
                else:
                    print(f"   ❌ FAILED: {error_msg[:100]}...")
            
            return success, results, error_msg
            
        finally:
            # Cleanup temp directory
            import shutil
            if test_dir.exists():
                try:
                    shutil.rmtree(test_dir)
                except Exception as e:
                    if self.verbose:
                        print(f"   ⚠️ Cleanup: {e}")
    
    def _create_vector_yaml_config(self, input_file: Path, output_file: Path, 
                                 data_dir: Path, vrl_code: str) -> str:
        """
        Create Vector YAML configuration with proper VRL code formatting.
        NO shell escaping issues - pure YAML with literal block.
        """
        
        # Properly indent VRL code for YAML literal block (6 spaces)
        indented_vrl = '\n'.join(f'      {line}' for line in vrl_code.split('\n'))
        
        return f'''# Vector configuration for VRL testing
# Generated by VectorTestRunner - no shell escaping issues
data_dir: "{data_dir}"

sources:
  file_input:
    type: file
    include:
      - "{input_file}"
    read_from: beginning
    max_read_bytes: 10485760
    ignore_older_secs: 300

transforms:
  vrl_test:
    type: remap
    inputs:
      - file_input
    source: |
{indented_vrl}

sinks:
  file_output:
    type: file
    inputs:
      - vrl_test
    path: "{output_file}"
    encoding:
      codec: json
    # Memory-only buffering for testing
    buffer:
      type: memory
      max_events: 1000
      when_full: block

api:
  enabled: false

# Disable excessive logging for testing
log:
  level: ERROR
'''
    
    def validate_field_extraction(self, results: List[Dict], expected_fields: List[str]) -> Dict[str, Any]:
        """
        Validate that expected fields were extracted from results.
        
        Returns validation report with field-by-field analysis.
        """
        
        if not results:
            return {
                "success": False,
                "extracted_fields": [],
                "missing_fields": expected_fields,
                "field_count": 0,
                "extraction_rate": 0.0
            }
        
        # Check which expected fields were found
        extracted_fields = []
        missing_fields = []
        
        # Combine all result keys to see what was extracted
        all_fields = set()
        for result in results:
            all_fields.update(result.keys())
        
        for field in expected_fields:
            if any(field in result for result in results):
                extracted_fields.append(field)
            else:
                missing_fields.append(field)
        
        extraction_rate = (len(extracted_fields) / len(expected_fields) * 100) if expected_fields else 0
        
        return {
            "success": len(missing_fields) == 0,
            "extracted_fields": extracted_fields,
            "missing_fields": missing_fields,
            "field_count": len(extracted_fields),
            "extraction_rate": extraction_rate,
            "total_result_fields": list(all_fields),
            "sample_result": results[0] if results else {}
        }


def test_vrl_simple(vrl_code: str, input_logs: List[str], 
                   expected_fields: List[str] = None, 
                   test_name: str = "simple_test") -> Dict[str, Any]:
    """
    Simple function to test VRL code with Vector CLI.
    Returns comprehensive test results with field validation.
    """
    
    runner = VectorTestRunner(verbose=True)
    success, results, error = runner.test_vrl_with_vector(vrl_code, input_logs, test_name)
    
    # Validate field extraction if expected fields provided
    field_validation = {}
    if expected_fields:
        field_validation = runner.validate_field_extraction(results, expected_fields)
    
    return {
        "success": success,
        "input_count": len(input_logs),
        "output_count": len(results),
        "results": results,
        "error": error,
        "field_validation": field_validation,
        "vrl_code": vrl_code
    }


# Example usage and testing
if __name__ == '__main__':
    print("🧪 Testing VectorTestRunner utility")
    
    # Test 1: Simple VRL
    simple_result = test_vrl_simple(
        'message_str = to_string(.message) ?? ""; .test = "working"; .processed = true',
        ['Test log message'],
        ['test', 'processed'],
        'utility_test'
    )
    
    print(f"✅ Simple test: {'PASS' if simple_result['success'] else 'FAIL'}")
    if simple_result['field_validation']:
        print(f"   Fields: {simple_result['field_validation']['field_count']}/{len(simple_result['field_validation']['extracted_fields'] + simple_result['field_validation']['missing_fields'])}")