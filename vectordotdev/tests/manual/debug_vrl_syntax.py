#!/usr/bin/env python3
"""
Debug VRL syntax errors in generated code
"""

import subprocess
import tempfile
from pathlib import Path


def test_vrl_syntax():
    """Test VRL syntax by running Vector with detailed error output"""
    
    # Test the corrected IP extraction VRL
    vrl_code = '''
# IP address extraction - VRL compatible syntax
message_str = string!(.message)
parts = split(message_str, " ")

.ip_found = false

# Check each part for IPv4 with proper type handling
if length(parts) > 0 {
    part0 = string!(parts[0])
    if is_ipv4(part0) {
        .ip_address = part0
        .ip_found = true
    }
}

if !.ip_found && length(parts) > 1 {
    part1 = string!(parts[1])
    if is_ipv4(part1) {
        .ip_address = part1
        .ip_found = true
    }
}

if !.ip_found && length(parts) > 2 {
    part2 = string!(parts[2])
    if is_ipv4(part2) {
        .ip_address = part2
        .ip_found = true
    }
}

# Clean up common prefixes and try again
if !.ip_found {
    # Chain replace calls for proper VRL syntax
    clean_msg = replace(message_str, "IP:", "")
    clean_msg = replace(clean_msg, "Address:", "")
    clean_msg = replace(clean_msg, "Client:", "")
    clean_msg = replace(clean_msg, "Server:", "")
    clean_msg = replace(clean_msg, "Gateway:", "")
    
    clean_parts = split(strip_whitespace(clean_msg), " ")
    
    if length(clean_parts) > 0 {
        clean0 = string!(clean_parts[0])
        if is_ipv4(clean0) {
            .ip_address = clean0
            .ip_found = true
            .extraction_method = "cleaned_prefix"
        }
    }
    
    if !.ip_found && length(clean_parts) > 1 {
        clean1 = string!(clean_parts[1])
        if is_ipv4(clean1) {
            .ip_address = clean1
            .ip_found = true
            .extraction_method = "cleaned_prefix"
        }
    }
}

# Set additional fields if IP found
if .ip_found {
    .ip_version = 4
}
'''
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create directories
        vector_data_dir = temp_path / "vector_data"
        vector_data_dir.mkdir()
        
        # Create input file
        input_file = temp_path / "input.log"
        with open(input_file, 'w') as f:
            f.write("Client IP: 192.168.1.100\n")
        
        # Create config
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
{vrl_code}
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
        
        print("🧪 Testing VRL Syntax")
        print("=" * 30)
        print("VRL Code:")
        print(vrl_code)
        print("\nConfig:")
        print(config_content)
        
        # Run Vector with verbose error output
        print("\n🚀 Running Vector...")
        
        try:
            result = subprocess.run([
                "/usr/bin/vector",
                "--config", str(config_file),
                "--verbose"
            ], capture_output=True, text=True, timeout=10)
            
            print(f"Exit code: {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            
            if output_file.exists():
                print(f"\n✅ Output file exists")
                with open(output_file) as f:
                    content = f.read()
                    print(f"Content: {content}")
            else:
                print(f"\n❌ No output file created")
                
        except subprocess.TimeoutExpired:
            print("❌ Timeout")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == '__main__':
    test_vrl_syntax()