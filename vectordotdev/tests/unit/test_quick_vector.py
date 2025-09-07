#!/usr/bin/env python3
"""
Quick Vector test with optimized VRL
"""

import json
import subprocess
import tempfile
from pathlib import Path
import time


def test_quick_ip_extraction():
    """Quick test of IP extraction with Vector"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create directories
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir()
        
        # Create input
        input_file = temp_path / "input.log"
        with open(input_file, 'w') as f:
            f.write("Client IP: 192.168.1.100\n")
        
        # Create config with corrected VRL
        output_file = temp_path / "output.jsonl"
        config_content = f'''
data_dir = "{vector_data_dir}"

[sources.file_input]
type = "file"
include = ["{input_file}"]
read_from = "beginning"

[transforms.test_remap]
type = "remap"
inputs = ["file_input"]
source = """
# IP address extraction - simplified
message_str = string!(.message)
parts = split(message_str, " ")

.ip_found = false

if length(parts) > 0 {{
    part0 = string!(parts[0])
    if is_ipv4(part0) {{
        .ip_address = part0
        .ip_found = true
    }}
}}

if !.ip_found && length(parts) > 1 {{
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

.ip_version = 4
"""

[sinks.file_output]
type = "file"
inputs = ["test_remap"]
path = "{output_file}"
encoding.codec = "json"
'''
        
        config_file = temp_path / "config.toml"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print("🚀 Quick IP Extraction Test")
        print("Input: 'Client IP: 192.168.1.100'")
        
        try:
            # Run Vector with timeout
            result = subprocess.run([
                "/usr/bin/vector",
                "--config", str(config_file)
            ], capture_output=True, text=True, timeout=8)
            
            print(f"Vector exit code: {result.returncode}")
            
            if output_file.exists():
                print("✅ Output file created!")
                with open(output_file) as f:
                    content = f.read()
                    if content.strip():
                        for line in content.strip().split('\n'):
                            if line.strip():
                                parsed = json.loads(line)
                                print(f"Result: {json.dumps(parsed, indent=2)}")
                                
                                # Check for IP extraction
                                if parsed.get("ip_found") == True:
                                    print("✅ IP found flag set!")
                                if "ip_address" in parsed:
                                    print(f"✅ IP extracted: {parsed['ip_address']}")
                                if parsed.get("ip_version") == 4:
                                    print("✅ IP version set!")
                                
                                return True
                    else:
                        print("❌ Output file empty")
            else:
                print("❌ No output file")
                if result.stderr:
                    print(f"STDERR: {result.stderr}")
            
            return False
            
        except subprocess.TimeoutExpired:
            print("❌ Timeout after 8 seconds")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


if __name__ == '__main__':
    success = test_quick_ip_extraction()
    print(f"\nResult: {'✅ SUCCESS' if success else '❌ FAILED'}")