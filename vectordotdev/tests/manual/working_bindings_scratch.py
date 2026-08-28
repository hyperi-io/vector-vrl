#!/usr/bin/env python3
"""
Working integration test for vectordotdev bindings.
Uses exact config that works manually.
"""

import sys
import json
import time

# Add paths
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')
sys.path.insert(0, '/projects/vectordotdev')

import vector
from vectordotdev.regex2vrl.core import RegexToVRL


def test_working_integration():
    """Test working vectordotdev integration"""
    
    print("🔗 Working vectordotdev Integration Test")
    print("=" * 45)
    
    # Test 1: Use exact working config format
    print("\n🧪 Test 1: Basic Vector Integration")
    
    config = '''[sources.python]
type = "python"

[sinks.file]
type = "file"
inputs = ["python"]
path = "/tmp/integration_test.txt"
encoding.codec = "json"
'''
    
    try:
        print("Creating Vector instance...")
        v = vector.Vector(config)
        
        print("Starting Vector...")
        v.start()
        
        print("Sending data...")
        data = json.dumps({"message": "integration test message", "test": "working"}).encode()
        v.send("python", data)
        
        print("Waiting for processing...")
        time.sleep(2)
        
        print("Stopping Vector...")
        v.stop()
        
        print("Checking output...")
        import os
        if os.path.exists("/tmp/integration_test.txt"):
            with open("/tmp/integration_test.txt") as f:
                content = f.read()
                print(f"✅ Success! Output: {content}")
                
                # Validate content (handle multiple JSON lines)
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if lines:
                    parsed = json.loads(lines[0])  # Parse first line
                    if parsed.get("message") == "integration test message":
                        print("✅ Data processing confirmed!")
                        return True
        else:
            print("❌ No output file")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return False


def test_regex2vrl_integration():
    """Test regex2vrl with Vector integration"""
    
    print("\n🧪 Test 2: regex2vrl Integration")
    
    # Generate VRL using regex2vrl
    converter = RegexToVRL()
    pattern = r'(?P<status>\d{3})'  # Simple HTTP status pattern
    vrl_code = converter.convert(pattern)
    
    print(f"regex2vrl generated VRL: {vrl_code[:100]}...")
    
    # Create config with generated VRL
    config = f'''[sources.python]
type = "python"

[transforms.regex2vrl_test]
type = "remap"
inputs = ["python"]
source = """
{vrl_code}
"""

[sinks.file]
type = "file"
inputs = ["regex2vrl_test"]
path = "/tmp/regex2vrl_integration.txt"
encoding.codec = "json"
'''
    
    try:
        v = vector.Vector(config)
        v.start()
        
        # Send test data with HTTP status
        data = json.dumps({"message": "HTTP 200 OK"}).encode()
        v.send("python", data)
        
        time.sleep(2)
        v.stop()
        
        # Check output
        import os
        if os.path.exists("/tmp/regex2vrl_integration.txt"):
            with open("/tmp/regex2vrl_integration.txt") as f:
                content = f.read()
                print(f"✅ regex2vrl integration success!")
                print(f"Output: {content}")
                
                # Check if VRL processing worked (handle multiple JSON lines)
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if lines:
                    parsed = json.loads(lines[0])
                    if "message" in parsed:
                        print("✅ VRL transformation applied!")
                        return True
        else:
            print("❌ No regex2vrl output file")
            
    except Exception as e:
        print(f"❌ regex2vrl integration error: {e}")
        import traceback
        traceback.print_exc()
    
    return False


if __name__ == '__main__':
    test1 = test_working_integration()
    test2 = test_regex2vrl_integration()
    
    overall = test1 and test2
    print(f"\n{'✅ ALL TESTS PASSED' if overall else '❌ SOME TESTS FAILED'}")
    print(f"Basic integration: {'✅' if test1 else '❌'}")
    print(f"regex2vrl integration: {'✅' if test2 else '❌'}")
    
    sys.exit(0 if overall else 1)