#!/usr/bin/env python3
"""
Minimal Vector test to confirm basic functionality
"""

import subprocess
import tempfile
import time
from pathlib import Path


def test_minimal():
    """Test minimal Vector functionality"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir()
        
        input_file = temp_path / "input.log"
        output_file = temp_path / "output.jsonl"
        
        # Create input
        with open(input_file, 'w') as f:
            f.write("test message\n")
        
        # Minimal config
        config_content = f'''
data_dir = "{vector_data_dir}"

[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[sinks.file_output]
type = "file"
inputs = ["file_input"]
path = "{output_file}"
encoding.codec = "json"
'''
        
        config_file = temp_path / "config.toml"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print("🧪 Minimal Vector Test (no transforms)")
        
        try:
            # Start Vector process
            process = subprocess.Popen([
                "/usr/bin/vector",
                "--config", str(config_file),
                "--quiet"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Wait for processing
            time.sleep(3)
            
            # Check if Vector is still running
            if process.poll() is None:
                print("Vector still running, terminating...")
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            
            stdout, stderr = process.communicate() if process.poll() is not None else ("", "")
            
            print(f"Exit code: {process.returncode}")
            
            if output_file.exists():
                with open(output_file) as f:
                    content = f.read()
                    if content.strip():
                        print("✅ Vector processed data successfully!")
                        print(f"Output: {content.strip()}")
                        return True
                    else:
                        print("❌ Output file empty")
            else:
                print("❌ No output file created")
                
            if stderr:
                print(f"STDERR: {stderr}")
                
            return False
            
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False


if __name__ == '__main__':
    success = test_minimal()
    print(f"\nResult: {'✅ SUCCESS' if success else '❌ FAILED'}")