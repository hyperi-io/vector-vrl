#!/usr/bin/env python3
"""
Integration test for auto-stop functionality with regex2vrl.
Tests that Vector automatically stops when no data is processed for specified time.
"""

import json
import sys
import time
from pathlib import Path

# Add paths for new src structure
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'vector-bindings' / '.venv' / 'lib' / 'python3.13' / 'site-packages'))
sys.path.insert(0, str(project_root / 'vectordotdev' / 'src'))

try:
    import vector_bindings
    import vectordotdev
    from vectordotdev.regex2vrl.core import RegexToVRL
    HAS_BINDINGS = True
except ImportError as e:
    print(f"❌ Bindings not available: {e}")
    HAS_BINDINGS = False
    sys.exit(1)


def test_native_vector_auto_stop():
    """Test auto-stop with native Vector API"""
    
    print("🧪 Testing Native Vector Auto-Stop")
    print("=" * 40)
    
    # Create simple config
    config = '''[sources.python]
type = "python"

[sinks.file]
type = "file"
inputs = ["python"]
path = "/tmp/auto_stop_native_test.txt"
encoding.codec = "json"
'''
    
    try:
        # Test 1: Basic auto-stop functionality
        print("\n📋 Test 1: Basic Auto-Stop (2 second timeout)")
        
        v = vector_bindings.Vector(config)
        v.start()
        v.enable_auto_stop(2.0)  # 2 second timeout
        
        # Send some data
        print("Sending data...")
        data = json.dumps({"message": "auto-stop test", "test": 1}).encode()
        v.send("python", data)
        
        print("Waiting for auto-stop...")
        start_time = time.time()
        
        # Use wait_until_complete which will auto-stop
        v.wait_until_complete(0.1)  # Check every 100ms
        
        elapsed = time.time() - start_time
        print(f"✅ Auto-stopped after {elapsed:.1f} seconds")
        
        # Verify output was written
        import os
        if os.path.exists("/tmp/auto_stop_native_test.txt"):
            with open("/tmp/auto_stop_native_test.txt") as f:
                content = f.read()
                if content.strip():
                    print(f"✅ Data processed: {content.strip()}")
                else:
                    print("⚠️ File created but empty")
        else:
            print("❌ No output file created")
        
        return elapsed >= 1.8 and elapsed <= 2.5  # Should be ~2 seconds
        
    except Exception as e:
        print(f"❌ Auto-stop test error: {e}")
        return False


def test_cli_vector_auto_stop():
    """Test auto-stop with CLI emulation"""
    
    print("\n🧪 Testing CLI Vector Auto-Stop")
    print("=" * 35)
    
    # Create config file for CLI mode (TOML format)
    toml_config = '''[sources.file_input]
type = "file"
include = ["/tmp/cli_auto_stop_input.log"]
read_from = "beginning"

[sinks.file_output]  
type = "file"
inputs = ["file_input"]
path = "/tmp/cli_auto_stop_output.txt"
encoding.codec = "json"
'''
    
    # Create input file
    with open("/tmp/cli_auto_stop_input.log", 'w') as f:
        f.write("CLI auto-stop test line 1\n")
        f.write("CLI auto-stop test line 2\n")
    
    # Write config to file
    config_file = "/tmp/cli_auto_stop_config.toml"
    with open(config_file, 'w') as f:
        f.write(toml_config)
    
    try:
        print(f"\n📋 Test 2: CLI Auto-Stop (3 second timeout)")
        
        cli_args = ["--config", config_file, "--quiet"]
        cli_v = vector_bindings.VectorCliPy(cli_args)
        cli_v.start_from_file(config_file)
        cli_v.enable_auto_stop(3.0)  # 3 second timeout
        
        print("Waiting for CLI auto-stop...")
        start_time = time.time()
        
        # Wait for CLI to auto-stop
        cli_v.wait_until_complete(0.2)  # Check every 200ms
        
        elapsed = time.time() - start_time
        print(f"✅ CLI auto-stopped after {elapsed:.1f} seconds")
        
        return elapsed >= 2.5 and elapsed <= 3.5  # Should be ~3 seconds
        
    except Exception as e:
        print(f"❌ CLI auto-stop test error: {e}")
        return False


def test_regex2vrl_with_auto_stop():
    """Test regex2vrl VRL generation with auto-stop"""
    
    print("\n🧪 Testing regex2vrl + Auto-Stop Integration")
    print("=" * 45)
    
    try:
        # Generate VRL using regex2vrl
        converter = RegexToVRL()
        pattern = r'(?P<word>\w+)'
        vrl_code = converter.convert(pattern)
        
        print(f"📝 Generated VRL: {len(vrl_code)} chars")
        
        # Create config with VRL transform
        config = f'''[sources.python]
type = "python"

[transforms.regex2vrl_transform]
type = "remap"
inputs = ["python"]
source = """
{vrl_code}
"""

[sinks.file]
type = "file" 
inputs = ["regex2vrl_transform"]
path = "/tmp/regex2vrl_auto_stop.txt"
encoding.codec = "json"
'''
        
        print("\n📋 Test 3: regex2vrl + Auto-Stop (1.5 second timeout)")
        
        v = vector_bindings.Vector(config)
        v.start()
        v.enable_auto_stop(1.5)  # 1.5 second timeout
        
        # Send data
        data = json.dumps({"message": "regex2vrl auto-stop test"}).encode()
        v.send("python", data)
        
        print("Sending data and waiting for auto-stop...")
        start_time = time.time()
        
        v.wait_until_complete(0.05)  # Check every 50ms
        
        elapsed = time.time() - start_time
        print(f"✅ regex2vrl auto-stopped after {elapsed:.1f} seconds")
        
        return elapsed >= 1.2 and elapsed <= 2.0  # Should be ~1.5 seconds
        
    except Exception as e:
        print(f"❌ regex2vrl auto-stop error: {e}")
        return False


def main():
    if not HAS_BINDINGS:
        print("❌ vector-bindings required for auto-stop tests")
        return 1
    
    print("🚀 Auto-Stop Functionality Integration Tests")
    print("=" * 50)
    print("Testing automatic Vector shutdown when no data for <timeout> seconds")
    
    # Run all tests
    test1 = test_native_vector_auto_stop()
    test2 = test_cli_vector_auto_stop()  
    test3 = test_regex2vrl_with_auto_stop()
    
    # Results summary
    print(f"\n📊 Auto-Stop Test Results:")
    print(f"Native Vector auto-stop: {'✅' if test1 else '❌'}")
    print(f"CLI Vector auto-stop: {'✅' if test2 else '❌'}")
    print(f"regex2vrl + auto-stop: {'✅' if test3 else '❌'}")
    
    all_passed = test1 and test2 and test3
    print(f"\nOverall: {'🎉 ALL TESTS PASSED' if all_passed else '⚠️ SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())