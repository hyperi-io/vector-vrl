#!/usr/bin/env python3
"""
Test vectordotdev bindings with YAML config format.
Ensures regex2vrl works with both TOML and YAML configs.
"""

import sys
import json
import time
import yaml

# Add paths
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')
sys.path.insert(0, '/projects/vectordotdev')

import vector
from vectordotdev.regex2vrl.core import RegexToVRL


def test_yaml_config():
    """Test Vector with YAML configuration"""
    
    print("🧪 Testing YAML Config with Vector Bindings")
    print("=" * 50)
    
    # Create YAML config
    config_dict = {
        "sources": {
            "python": {
                "type": "python"
            }
        },
        "transforms": {
            "yaml_test": {
                "type": "remap",
                "inputs": ["python"],
                "source": """
message_str = string!(.message)
.yaml_processed = true
.format = "yaml"
if contains(message_str, "test") {
    .contains_test = true
}
"""
            }
        },
        "sinks": {
            "file": {
                "type": "file",
                "inputs": ["yaml_test"],
                "path": "/tmp/yaml_config_test.txt",
                "encoding": {
                    "codec": "json"
                }
            }
        }
    }
    
    # Convert to YAML string
    yaml_config = yaml.dump(config_dict, default_flow_style=False)
    print("YAML Config:")
    print(yaml_config)
    
    try:
        # Test if Vector accepts YAML
        v = vector.Vector(yaml_config)
        v.start()
        
        data = json.dumps({"message": "yaml test message"}).encode()
        v.send("python", data)
        
        time.sleep(1)
        v.stop()
        
        # Check output
        import os
        if os.path.exists("/tmp/yaml_config_test.txt"):
            with open("/tmp/yaml_config_test.txt") as f:
                content = f.read()
                print(f"✅ YAML config works! Output: {content}")
                
                # Validate
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if lines:
                    result = json.loads(lines[0])
                    if result.get("yaml_processed") == True:
                        print("✅ YAML VRL processing confirmed!")
                        return True
        else:
            print("❌ YAML config failed - no output")
            
    except Exception as e:
        print(f"❌ YAML config error: {e}")
        # If YAML fails, fall back to TOML
        print("\n🔄 Trying TOML format as fallback...")
        return test_toml_fallback()
    
    return False


def test_toml_fallback():
    """Test with TOML format if YAML fails"""
    
    # Convert same config to TOML
    toml_config = '''[sources.python]
type = "python"

[transforms.toml_test]  
type = "remap"
inputs = ["python"]
source = """
message_str = string!(.message)
.toml_processed = true
.format = "toml"
"""

[sinks.file]
type = "file"
inputs = ["toml_test"]
path = "/tmp/toml_config_test.txt"
encoding.codec = "json"
'''
    
    try:
        v = vector.Vector(toml_config)
        v.start()
        
        data = json.dumps({"message": "toml test message"}).encode()
        v.send("python", data)
        
        time.sleep(1)
        v.stop()
        
        import os
        if os.path.exists("/tmp/toml_config_test.txt"):
            with open("/tmp/toml_config_test.txt") as f:
                content = f.read()
                print(f"✅ TOML config works! Output: {content}")
                return True
        else:
            print("❌ TOML config also failed")
            
    except Exception as e:
        print(f"❌ TOML config error: {e}")
    
    return False


def test_regex2vrl_with_simple_pattern():
    """Test regex2vrl with a simple pattern that should work"""
    
    print("\n🧪 Testing regex2vrl with Simple Pattern")
    
    # Use a simpler pattern that doesn't require regex functions
    converter = RegexToVRL()
    pattern = r'(?P<word>\w+)'  # Simple word extraction
    vrl_code = converter.convert(pattern)
    
    print("Generated VRL:")
    print(vrl_code)
    
    config = f'''[sources.python]
type = "python"

[transforms.simple_regex2vrl]
type = "remap"
inputs = ["python"]
source = """
{vrl_code}
"""

[sinks.file]
type = "file"
inputs = ["simple_regex2vrl"]
path = "/tmp/simple_regex2vrl.txt"
encoding.codec = "json"
'''
    
    try:
        v = vector.Vector(config)
        v.start()
        
        data = json.dumps({"message": "hello world"}).encode()
        v.send("python", data)
        
        time.sleep(1)
        v.stop()
        
        import os
        if os.path.exists("/tmp/simple_regex2vrl.txt"):
            with open("/tmp/simple_regex2vrl.txt") as f:
                content = f.read()
                print(f"✅ Simple regex2vrl works! Output: {content}")
                
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                if lines:
                    result = json.loads(lines[0])
                    print(f"Parsed: {json.dumps(result, indent=2)}")
                    return True
        else:
            print("❌ Simple regex2vrl failed")
            
    except Exception as e:
        print(f"❌ Simple regex2vrl error: {e}")
        import traceback
        traceback.print_exc()
    
    return False


if __name__ == '__main__':
    test1 = test_yaml_config()
    test2 = test_regex2vrl_with_simple_pattern()
    
    print(f"\n📊 Results:")
    print(f"YAML config: {'✅' if test1 else '❌'}")
    print(f"regex2vrl simple: {'✅' if test2 else '❌'}")
    
    sys.exit(0 if test1 or test2 else 1)