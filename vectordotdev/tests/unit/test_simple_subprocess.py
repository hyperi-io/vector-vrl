#!/usr/bin/env python3
"""
Simple Vector subprocess unit test - no external dependencies.
Tests that Vector can process basic VRL transformations via subprocess calls.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def create_test_vector_config(vrl_code: str, input_logs: list, temp_dir: Path) -> Path:
    """Create a simple Vector config for testing"""
    input_file = temp_dir / "input.log"
    output_file = temp_dir / "output.jsonl"
    
    # Write test logs
    with open(input_file, 'w') as f:
        for log in input_logs:
            f.write(log + '\n')
    
    # Create Vector config (YAML format)
    # Properly indent VRL code for YAML literal block
    indented_vrl = '\n'.join(f'      {line}' for line in vrl_code.split('\n'))
    
    config_content = f"""sources:
  file_input:
    type: file
    include:
      - "{input_file}"
    read_from: beginning

transforms:
  test_transform:
    type: remap
    inputs:
      - file_input
    source: |
{indented_vrl}

sinks:
  file_output:
    type: file
    inputs:
      - test_transform
    path: "{output_file}"
    encoding:
      codec: json
    buffer:
      type: memory
      max_events: 500
      when_full: block
"""
    
    config_file = temp_dir / "config.yaml"
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    return config_file


def run_vector_test(vector_binary: str, config_file: Path, temp_dir: Path) -> tuple:
    """Run Vector and return results"""
    try:
        # Run Vector
        process = subprocess.Popen([
            vector_binary,
            "--config", str(config_file),
            "--quiet"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Let Vector process
        time.sleep(3)
        
        # Stop Vector
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        
        # Read output
        output_file = temp_dir / "output.jsonl"
        results = []
        
        if output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            results.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        
        return True, results, ""
        
    except Exception as e:
        return False, [], str(e)


def test_basic_vrl_transformations():
    """Test basic VRL transformations with Vector subprocess"""
    
    # Find Vector binary
    vector_binary = None
    possible_paths = ["/usr/bin/vector", "/usr/local/bin/vector"]
    
    for path in possible_paths:
        if Path(path).exists():
            vector_binary = path
            break
    
    if not vector_binary:
        try:
            result = subprocess.run(["which", "vector"], capture_output=True, text=True, check=True)
            vector_binary = result.stdout.strip()
        except subprocess.CalledProcessError:
            print("❌ Vector binary not found")
            return False
    
    print(f"✅ Found Vector binary: {vector_binary}")
    
    # Test cases
    test_cases = [
        {
            "name": "simple_field_assignment",
            "vrl": ".status = \"processed\"",
            "input": ["test log message"],
            "expected_field": "status"
        },
        {
            "name": "string_split",
            "vrl": '''
            message_str = string!(.message)
            parts = split(message_str, " ")
            if length(parts) > 0 {
                .first_word = parts[0]
            }
            ''',
            "input": ["hello world test"],
            "expected_field": "first_word"
        },
        {
            "name": "timestamp_assignment", 
            "vrl": ".timestamp = now()",
            "input": ["log entry"],
            "expected_field": "timestamp"
        }
    ]
    
    results = {"passed": 0, "failed": 0}
    
    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        
        with tempfile.TemporaryDirectory(prefix="vector_test_") as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Create config
                config_file = create_test_vector_config(
                    test_case["vrl"], 
                    test_case["input"],
                    temp_path
                )
                
                # Run Vector
                success, output, error = run_vector_test(vector_binary, config_file, temp_path)
                
                if success and output:
                    # Check if expected field exists
                    field_found = any(test_case["expected_field"] in result for result in output)
                    
                    if field_found:
                        print(f"✅ PASSED - Field '{test_case['expected_field']}' found")
                        results["passed"] += 1
                    else:
                        print(f"❌ FAILED - Field '{test_case['expected_field']}' not found")
                        print(f"   Output: {output}")
                        results["failed"] += 1
                else:
                    print(f"❌ FAILED - No output or error: {error}")
                    results["failed"] += 1
                    
            except Exception as e:
                print(f"❌ EXCEPTION - {e}")
                results["failed"] += 1
    
    # Summary
    total = results["passed"] + results["failed"]
    print(f"\n📊 Test Results:")
    print(f"Passed: {results['passed']}/{total}")
    print(f"Failed: {results['failed']}/{total}")
    
    return results["failed"] == 0


if __name__ == '__main__':
    print("🚀 Simple Vector Subprocess Unit Tests")
    print("=" * 45)
    print("Testing basic VRL transformations via Vector subprocess calls")
    
    success = test_basic_vrl_transformations()
    sys.exit(0 if success else 1)