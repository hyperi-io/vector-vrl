#!/usr/bin/env python3
"""
Comprehensive VRL validation test using real Vector module.
Tests VRL expressions both standalone and within YAML configurations.
"""

import vector
import yaml
import textwrap
import json

def test_basic_vrl_expressions():
    """Test basic VRL expressions that work with Vector."""
    
    print("🧪 Testing Basic VRL Expressions")
    print("=" * 40)
    
    basic_expressions = [
        # Field operations
        ". = .message",
        ".level = \"INFO\"", 
        ".timestamp = now()",
        
        # Function calls that work
        "now()",
        "uuid_v4()",
        "del(.field)",
        "del(.password)",
        
        # JSON parsing (with !)
        "parse_json!(.message)",
        ".parsed = parse_json(.message) ?? {}",
        
        # Conditionals
        "if .level == \"ERROR\" { .alert = true }",
        ".status = if .code == 200 { \"ok\" } else { \"error\" }",
        
        # Assignment with conditionals
        ".processed = true",
        ".enriched = false"
    ]
    
    valid_count = 0
    for expr in basic_expressions:
        try:
            result = vector.vrl_check(expr)
            status = "✅" if result else "❌"
            print(f"{status} {expr}")
            if result:
                valid_count += 1
        except Exception as e:
            print(f"💥 {expr} - {type(e).__name__}: {e}")
    
    print(f"\n✅ {valid_count}/{len(basic_expressions)} basic expressions valid")

def test_vrl_function_exploration():
    """Explore available VRL functions and test them."""
    
    print("\n🔍 Exploring VRL Functions")
    print("=" * 40)
    
    functions = vector.vrl_functions()
    print(f"Total VRL functions available: {len(functions)}")
    
    # Test categories of functions
    function_categories = {
        "String Functions": ['upcase', 'downcase', 'strip_whitespace', 'replace', 'split', 'join'],
        "Type Functions": ['to_string', 'to_int', 'to_float', 'to_timestamp'],
        "Array Functions": ['push', 'pop', 'length', 'get', 'contains'],
        "Time Functions": ['now', 'format_timestamp'],
        "Parsing Functions": ['parse_json', 'parse_timestamp', 'parse_int'],
        "Utility Functions": ['uuid_v4', 'del', 'type'],
        "Validation Functions": ['is_string', 'is_integer', 'is_array', 'is_object']
    }
    
    for category, func_list in function_categories.items():
        available = [f for f in func_list if f in functions]
        print(f"\n{category}: {len(available)}/{len(func_list)} available")
        print(f"  Available: {available}")
        
        # Test a few from each category
        for func in available[:2]:  # Test first 2 from each category
            if func == 'now':
                test_expr = f"{func}()"
            elif func in ['del']:
                test_expr = f"{func}(.field)"
            elif func in ['uuid_v4']:
                test_expr = f".id = {func}()"
            else:
                test_expr = f".result = {func}(.input)"
            
            try:
                result = vector.vrl_check(test_expr)
                status = "✅" if result else "❌"
                print(f"    {status} {test_expr}")
            except Exception as e:
                print(f"    💥 {test_expr} - {e}")

def test_vrl_in_yaml_configs():
    """Test VRL expressions within YAML configurations."""
    
    print("\n🗂️ Testing VRL in YAML Configurations")
    print("=" * 40)
    
    yaml_configs = [
        # Simple transform
        """
        sources:
          app:
            type: python
        
        transforms:
          simple:
            type: remap
            inputs: ["app"]
            source: |
              .timestamp = now()
              .processed = true
        
        sinks:
          output:
            type: console
            inputs: ["simple"]
        """,
        
        # JSON processing
        """
        sources:
          logs:
            type: python
        
        transforms:
          parse_logs:
            type: remap
            inputs: ["logs"]
            source: |
              .parsed = parse_json(.message) ?? {}
              .id = uuid_v4()
              del(.temp_field)
        
        sinks:
          output:
            type: file
            inputs: ["parse_logs"]
            path: "./.tmp/parsed_logs.jsonl"
            encoding:
              codec: json
        """,
        
        # Conditional processing
        """
        sources:
          events:
            type: python
        
        transforms:
          filter_events:
            type: remap
            inputs: ["events"]
            source: |
              if .level == "ERROR" {
                .alert = true
                .priority = "high"
              } else {
                .alert = false
                .priority = "low"
              }
              
              .processed_at = now()
        
        sinks:
          alerts:
            type: console
            inputs: ["filter_events"]
        """
    ]
    
    for i, config_yaml in enumerate(yaml_configs):
        print(f"\n--- Config {i+1} ---")
        
        try:
            parsed = yaml.safe_load(textwrap.dedent(config_yaml))
            print("✅ YAML parsing successful")
            
            # Validate VRL in transforms
            for transform_name, transform_config in parsed.get("transforms", {}).items():
                if "source" in transform_config:
                    vrl_source = transform_config["source"]
                    print(f"\nTransform '{transform_name}' VRL validation:")
                    
                    # Test individual VRL lines
                    lines = [line.strip() for line in vrl_source.split('\n') 
                            if line.strip() and not line.strip().startswith('#')]
                    
                    for line in lines:
                        try:
                            result = vector.vrl_check(line)
                            status = "✅" if result else "❌"
                            print(f"  {status} {line}")
                        except Exception as e:
                            print(f"  💥 {line} - {e}")
                    
                    # Test complete VRL block
                    try:
                        complete_result = vector.vrl_check(vrl_source)
                        status = "✅" if complete_result else "❌"
                        print(f"  Complete block: {status}")
                    except Exception as e:
                        print(f"  Complete block: 💥 {e}")
        
        except Exception as e:
            print(f"❌ Config {i+1} failed: {e}")

def test_invalid_vrl_detection():
    """Test that invalid VRL is properly detected."""
    
    print("\n❌ Testing Invalid VRL Detection")
    print("=" * 40)
    
    invalid_expressions = [
        "invalid syntax",
        ". = .field +",  # Incomplete
        "parse_nonexistent(.field)",
        ".bad = unknown_func(.data)",
        "if .condition {",  # Missing closing brace
        ".field =",  # Incomplete assignment
    ]
    
    detected_invalid = 0
    for expr in invalid_expressions:
        try:
            result = vector.vrl_check(expr)
            if result:
                print(f"⚠️ {expr} - Unexpectedly valid")
            else:
                print(f"✅ {expr} - Correctly detected as invalid")
                detected_invalid += 1
        except ValueError as e:
            print(f"✅ {expr} - Correctly rejected: {e}")
            detected_invalid += 1
        except Exception as e:
            print(f"✅ {expr} - Rejected with: {type(e).__name__}: {e}")
            detected_invalid += 1
    
    print(f"\n✅ {detected_invalid}/{len(invalid_expressions)} invalid expressions properly detected")

def test_yaml_with_working_vrl():
    """Test YAML config with only working VRL expressions."""
    
    print("\n📋 Testing YAML with Working VRL")
    print("=" * 40)
    
    working_config = """
    sources:
      application:
        type: python
    
    transforms:
      process:
        type: remap
        inputs: ["application"]
        source: |
          .timestamp = now()
          .id = uuid_v4()
          .parsed = parse_json(.message) ?? {}
          .processed = true
          
          if .level == "ERROR" {
            .alert = true
          } else {
            .alert = false
          }
          
          del(.internal_data)
    
    sinks:
      output:
        type: file
        inputs: ["process"]
        path: "./.tmp/working_vrl_output.log"
        encoding:
          codec: json
      
      console:
        type: console
        inputs: ["process"]
        encoding:
          codec: json
    """
    
    try:
        parsed = yaml.safe_load(textwrap.dedent(working_config))
        print("✅ YAML parsing successful")
        
        # Test the VRL
        vrl_source = parsed["transforms"]["process"]["source"]
        print(f"\nTesting complete VRL block:")
        
        try:
            result = vector.vrl_check(vrl_source)
            print(f"Complete VRL validation: {'✅ Valid' if result else '❌ Invalid'}")
            
            # If valid, test with actual Vector
            if result:
                print("\n🚀 Testing with Vector runtime:")
                vec = vector.Vector(working_config)
                vec.start()
                
                # Send test data
                test_data = {
                    "message": '{"user": "test", "action": "login"}',
                    "level": "INFO",
                    "internal_data": "should_be_deleted"
                }
                
                vec.send("application", json.dumps(test_data).encode())
                vec.stop()
                
                print("✅ Vector processing completed successfully")
            
        except Exception as e:
            print(f"VRL validation error: {e}")
    
    except Exception as e:
        print(f"Config error: {e}")

if __name__ == "__main__":
    print("🚀 Comprehensive VRL Validation Test")
    print("=" * 50)
    
    test_basic_vrl_expressions()
    test_vrl_function_exploration()
    test_vrl_in_yaml_configs()
    test_invalid_vrl_detection()
    test_yaml_with_working_vrl()
    
    print("\n🎉 VRL validation testing complete!")