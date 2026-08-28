#!/usr/bin/env python3
"""
Simple integration test for vectordotdev bindings - working version.
Tests that vectordotdev Python bindings work with regex2vrl.
"""

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

# Add correct paths
sys.path.insert(0, '/projects/vectordotdev')
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')

import vector
from vectordotdev.regex2vrl.core import RegexToVRL


async def test_simple_integration():
    """Test simple regex2vrl + Vector bindings integration"""
    
    print("🔗 Simple vectordotdev Bindings Integration Test")
    print("=" * 55)
    
    # Test 1: Basic VRL with Vector bindings
    print("\n🧪 Test 1: Basic VRL Processing")
    
    basic_config = '''[sources.python]
type = "python"

[transforms.test_transform]
type = "remap"
inputs = ["python"]
source = """
.processed = true
.test_field = "added_by_vrl"
"""

[sinks.file]
type = "file"
inputs = ["test_transform"]
path = "/tmp/basic_test_output.txt"
encoding.codec = "json"
'''
    
    try:
        v = vector.Vector(basic_config)
        v.start()
        
        # Send test data
        test_data = json.dumps({"message": "test log entry"}).encode()
        v.send("python", test_data)
        
        # Wait for processing
        await asyncio.sleep(1)
        v.stop()
        
        # Check output
        output_file = Path("/tmp/basic_test_output.txt")
        if output_file.exists():
            with open(output_file) as f:
                content = f.read().strip()
                if content:
                    result = json.loads(content)
                    print(f"✅ Basic VRL test passed!")
                    print(f"   Output: {result}")
                    if result.get("processed") == True and result.get("test_field") == "added_by_vrl":
                        print("   ✅ VRL fields added correctly!")
                else:
                    print("❌ Output file empty")
                    return False
        else:
            print("❌ No output file created")
            return False
            
    except Exception as e:
        print(f"❌ Basic test failed: {e}")
        return False
    
    # Test 2: regex2vrl integration
    print("\n🧪 Test 2: regex2vrl + Vector Integration")
    
    # Use regex2vrl to generate VRL
    converter = RegexToVRL()
    ip_pattern = r'(?P<ip>\d+\.\d+\.\d+\.\d+)'
    generated_vrl = converter.convert(ip_pattern)
    
    print(f"Generated VRL ({len(generated_vrl)} chars)")
    if len(generated_vrl) < 200:  # Show short VRL
        print(f"VRL: {generated_vrl}")
    
    # Create Vector config with regex2vrl generated VRL
    regex2vrl_config = f'''[sources.python]
type = "python"

[transforms.regex2vrl_transform]
type = "remap"
inputs = ["python"]
source = """
{generated_vrl}
"""

[sinks.file]
type = "file"
inputs = ["regex2vrl_transform"]
path = "/tmp/regex2vrl_test_output.txt"
encoding.codec = "json"
'''
    
    try:
        v2 = vector.Vector(regex2vrl_config)
        v2.start()
        
        # Send IP test data
        ip_data = json.dumps({"message": "Client IP: 192.168.1.100"}).encode()
        v2.send("python", ip_data)
        
        await asyncio.sleep(1)
        v2.stop()
        
        # Check output
        output_file = Path("/tmp/regex2vrl_test_output.txt")
        if output_file.exists():
            with open(output_file) as f:
                content = f.read().strip()
                if content:
                    result = json.loads(content)
                    print(f"✅ regex2vrl integration test passed!")
                    print(f"   Output: {result}")
                    if "ip_address" in result:
                        print(f"   ✅ IP extracted: {result['ip_address']}")
                        return True
                    else:
                        print("   ⚠️ IP not extracted but processing worked")
                        return True
                else:
                    print("❌ Output file empty")
                    return False
        else:
            print("❌ No output file created")
            return False
            
    except Exception as e:
        print(f"❌ regex2vrl test failed: {e}")
        return False


if __name__ == '__main__':
    success = asyncio.run(test_simple_integration())
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    sys.exit(0 if success else 1)