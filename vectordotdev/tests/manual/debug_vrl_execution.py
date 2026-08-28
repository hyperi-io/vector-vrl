#!/usr/bin/env python3
"""
Debug VRL execution with Vector bindings
"""

import sys
import json
import time

# Add paths
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')
sys.path.insert(0, '/projects/vectordotdev')

import vector
from vectordotdev.regex2vrl.core import RegexToVRL


def debug_vrl_execution():
    """Debug VRL execution"""
    
    print("🔍 Debugging VRL Execution")
    print("=" * 35)
    
    # Generate VRL for status pattern
    converter = RegexToVRL()
    pattern = r'(?P<status>\d{3})'
    vrl_code = converter.convert(pattern)
    
    print("Generated VRL:")
    print(vrl_code)
    
    # Test with Vector bindings
    config = f'''[sources.python]
type = "python"

[transforms.debug_test]
type = "remap"
inputs = ["python"]
source = """
{vrl_code}
"""

[sinks.file]
type = "file" 
inputs = ["debug_test"]
path = "/tmp/vrl_debug_output.txt"
encoding.codec = "json"
'''
    
    print("\nVector config:")
    print(config)
    
    try:
        print("\n🚀 Testing VRL execution...")
        v = vector.Vector(config)
        v.start()
        
        # Send test data with HTTP status
        test_message = "HTTP 200 OK response received"
        data = json.dumps({"message": test_message}).encode()
        print(f"Sending: {test_message}")
        
        v.send("python", data)
        time.sleep(2)
        v.stop()
        
        # Check result
        import os
        if os.path.exists("/tmp/vrl_debug_output.txt"):
            with open("/tmp/vrl_debug_output.txt") as f:
                content = f.read()
                print(f"\n✅ VRL executed successfully!")
                print(f"Raw output: {content}")
                
                # Parse result
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if lines:
                    result = json.loads(lines[0])
                    print(f"Parsed result: {json.dumps(result, indent=2)}")
                    
                    # Check for extracted fields
                    if "status" in result:
                        print(f"✅ Status extracted: {result['status']}")
                    if result.get("status_found"):
                        print("✅ Status found flag set!")
                        
                    return True
        else:
            print("\n❌ No output file - VRL may have failed")
            
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = debug_vrl_execution()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")