#!/usr/bin/env python3
"""
Test working IP extraction VRL
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path


def test_working_ip_vrl():
    """Test working IP extraction VRL"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir()
        
        input_file = temp_path / "input.log"
        output_file = temp_path / "output.jsonl"
        
        # Create input with IP
        with open(input_file, 'w') as f:
            f.write("Client IP: 192.168.1.100\n")
        
        # Working VRL config
        config_content = f'''
data_dir = "{vector_data_dir}"

[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[transforms.ip_extract]
type = "remap"
inputs = ["file_input"]
source = """
# Simple working IP extraction
message_str = string!(.message)
parts = split(message_str, " ")

.ip_found = false

if length(parts) > 1 {{
    part1 = string!(parts[1])
    if is_ipv4(part1) {{
        .ip_address = part1
        .ip_found = true
    }}
}}

if !.ip_found && length(parts) > 2 {{
    part2 = string!(parts[2])
    if is_ipv4(part2) {{
        .ip_address = part2
        .ip_found = true
    }}
}}
"""

[sinks.file_output]
type = "file"
inputs = ["ip_extract"]
path = "{output_file}"
encoding.codec = "json"
'''
        
        config_file = temp_path / "config.toml"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print("🧪 Working IP VRL Test")
        print("Input: 'Client IP: 192.168.1.100'")
        
        try:
            process = subprocess.Popen([
                "/usr/bin/vector",
                "--config", str(config_file),
                "--quiet"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            time.sleep(2)
            
            process.terminate()
            process.wait(timeout=3)
            
            if output_file.exists():
                with open(output_file) as f:
                    content = f.read()
                    if content.strip():
                        for line in content.strip().split('\n'):
                            if line.strip():
                                result = json.loads(line)
                                print(f"✅ Result: {json.dumps(result, indent=2)}")
                                
                                # Check IP extraction
                                if result.get("ip_found"):
                                    print(f"✅ IP found: {result.get('ip_address')}")
                                    return True
                                else:
                                    print("❌ IP not found")
                                    
                        return False
            
            print("❌ No output")
            return False
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


if __name__ == '__main__':
    success = test_working_ip_vrl()
    print(f"\nResult: {'✅ SUCCESS' if success else '❌ FAILED'}")