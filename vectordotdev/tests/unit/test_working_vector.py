#!/usr/bin/env python3
"""
Working Vector subprocess test - simplified approach.
"""

import subprocess
import tempfile
import time
from pathlib import Path


def test_vector_basic():
    """Test basic Vector functionality"""
    
    with tempfile.TemporaryDirectory(prefix="vector_working_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create Vector data directory
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir()
        
        # Create input file
        input_file = temp_path / "input.log"
        with open(input_file, 'w') as f:
            f.write("hello world\n")
            f.write("test message\n")
        
        # Create output file path  
        output_file = temp_path / "output.jsonl"
        
        # Create Vector config (YAML format)
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
      .processed = true
      .original_message = .message

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
'''
        
        config_file = temp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print(f"📁 Testing in: {temp_path}")
        print("🚀 Running Vector for 5 seconds...")
        
        try:
            # Start Vector process
            process = subprocess.Popen([
                "/usr/bin/vector", 
                "--config", str(config_file)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let it run briefly
            time.sleep(5)
            
            # Terminate
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            print(f"Vector exit code: {process.returncode}")
            
            # Check output
            if output_file.exists():
                print("✅ Output file created!")
                
                with open(output_file, 'r') as f:
                    content = f.read()
                    if content.strip():
                        print("✅ Output contains data:")
                        for line in content.strip().split('\n'):
                            if line.strip():
                                try:
                                    import json
                                    parsed = json.loads(line)
                                    print(f"   📄 {parsed}")
                                    
                                    # Check our fields
                                    if parsed.get("processed") == True:
                                        print("   ✅ Field 'processed' = true")
                                    if "original_message" in parsed:
                                        print(f"   ✅ Field 'original_message' = '{parsed['original_message']}'")
                                        
                                except json.JSONDecodeError:
                                    print(f"   📄 Raw: {line}")
                        
                        return True
                    else:
                        print("❌ Output file is empty")
                        return False
            else:
                print("❌ Output file was not created")
                if stderr:
                    print(f"Vector stderr: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            process.kill()
            print("❌ Vector process killed due to timeout")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


if __name__ == '__main__':
    print("🧪 Vector Subprocess Working Test")
    print("=" * 40)
    
    success = test_vector_basic()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)