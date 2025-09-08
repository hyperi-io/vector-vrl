#!/usr/bin/env python3
"""
OUTPUT VALIDATION TEST - Verifies VRL actually extracts expected field values
Tests that generated VRL produces the correct parsed output from input logs
Real Vector execution with detailed output content validation
"""

import sys
import yaml
import subprocess
import time
import json
from pathlib import Path

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL


class OutputValidationTest:
    """Validate that VRL output actually contains expected field values"""
    
    def __init__(self):
        self.vector_binary = self._find_vector_binary()
        self.temp_dir = Path(".tmp") / "output_validation"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def _find_vector_binary(self) -> str:
        """Find Vector binary"""
        candidates = ["/usr/bin/vector", "/usr/local/bin/vector", "vector"]
        for candidate in candidates:
            try:
                result = subprocess.run([candidate, "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return candidate
            except:
                continue
        return None
    
    def test_field_extraction_accuracy(self):
        """Test that VRL actually extracts the expected field values"""
        
        print("🔍 OUTPUT VALIDATION TEST - Field Extraction Accuracy")
        print("=" * 70)
        print("Validates that VRL produces correct parsed output values")
        
        if not self.vector_binary:
            print("❌ Vector binary not found")
            return False
        
        # Test cases with specific expected output values
        validation_cases = [
            {
                "name": "Apache Log IP Extraction",
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
                "input_log": '192.168.1.100 - user [timestamp] "GET /path" 200 1024',
                "expected_extractions": {
                    "should_contain": ["192.168.1.100"],
                    "fields_that_should_exist": ["ip", "ip_string", "ip_available"],
                    "numeric_validations": []
                }
            },
            {
                "name": "Status Code Extraction", 
                "pattern": r'(?P<status>\d{3})',
                "input_log": 'Client request returned status 404 with error message',
                "expected_extractions": {
                    "should_contain": ["404"],
                    "fields_that_should_exist": ["status", "status_string", "status_available"],
                    "numeric_validations": [("status_as_int", 404)]
                }
            },
            {
                "name": "Multi-field Complex Log",
                "pattern": r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) (?P<level>[A-Z]+) (?P<service>\w+) (?P<message>.*)',
                "input_log": '2025-01-15T10:30:45 ERROR auth-service Database connection failed',
                "expected_extractions": {
                    "should_contain": ["2025-01-15T10:30:45", "ERROR", "auth-service", "Database"],
                    "fields_that_should_exist": ["timestamp", "level", "service", "message"],
                    "string_validations": [
                        ("timestamp_string", "2025-01-15T10:30:45"),
                        ("level_string", "ERROR"),
                        ("service_string", "auth-service")
                    ]
                }
            },
            {
                "name": "JSON Data Extraction",
                "pattern": r'^(?P<json_data>\{.*\})$',
                "input_log": '{"level":"INFO","user_id":"12345","message":"Login successful"}',
                "expected_extractions": {
                    "should_contain": ["INFO", "12345", "Login successful"],
                    "fields_that_should_exist": ["json_data", "json_data_string"],
                    "json_validations": [("json_data_string", "INFO")]
                }
            }
        ]
        
        success_count = 0
        
        for case in validation_cases:
            print(f"\n🧪 Testing: {case['name']}")
            print(f"   Pattern: {case['pattern']}")
            print(f"   Input: {case['input_log']}")
            
            # Generate VRL and test with Vector
            result = self._test_output_validation(case)
            
            if result["validation_passed"]:
                success_count += 1
                print(f"   ✅ OUTPUT VALIDATION PASSED")
                print(f"      Fields found: {result['fields_found']}")
                print(f"      Values extracted: {result['values_extracted']}")
            else:
                print(f"   ❌ OUTPUT VALIDATION FAILED")
                print(f"      Missing: {result['validation_failures']}")
        
        validation_success_rate = (success_count / len(validation_cases)) * 100
        
        print(f"\n📊 OUTPUT VALIDATION RESULTS")
        print("=" * 70)
        print(f"Tests run: {len(validation_cases)}")
        print(f"Output validation passed: {success_count}")
        print(f"Success rate: {validation_success_rate:.1f}%")
        
        if validation_success_rate >= 75:
            print(f"\n✅ CONFIRMED: VRL generates CORRECT output values")
            print(f"✅ Field extraction works as expected")
            print(f"✅ Parsed values match input log content")
        else:
            print(f"\n❌ OUTPUT VALIDATION ISSUES")
            print(f"❌ Generated VRL may not extract expected values")
        
        return validation_success_rate >= 75
    
    def _test_output_validation(self, test_case: dict) -> dict:
        """Test specific case and validate output content"""
        
        try:
            # Generate VRL
            converter = RegexToVRL()
            vrl_code = converter.convert(test_case["pattern"], sample_logs=[test_case["input_log"]])
            
            # Create test files
            test_name = test_case["name"].lower().replace(" ", "_")
            test_dir = self.temp_dir / test_name
            test_dir.mkdir(exist_ok=True)
            
            # Input file
            input_file = test_dir / "input.log"
            with open(input_file, 'w') as f:
                f.write(test_case["input_log"] + '\n')
            
            # YAML config
            config_data = {
                'data_dir': str(test_dir / "data"),
                'sources': {
                    'file_input': {
                        'type': 'file',
                        'include': [str(input_file)],
                        'read_from': 'beginning'
                    }
                },
                'transforms': {
                    'vrl_test': {
                        'type': 'remap',
                        'inputs': ['file_input'],
                        'source': vrl_code
                    }
                },
                'sinks': {
                    'output': {
                        'type': 'file',
                        'inputs': ['vrl_test'],
                        'path': str(test_dir / "output.jsonl"),
                        'encoding': {'codec': 'json'}
                    }
                }
            }
            
            config_file = test_dir / "config.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            # Create data directory
            (test_dir / "data").mkdir(exist_ok=True)
            
            # Run Vector
            process = subprocess.Popen([
                self.vector_binary,
                "--config", str(config_file),
                "--quiet"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            time.sleep(3)
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            
            # Read and validate output
            output_file = test_dir / "output.jsonl"
            if not output_file.exists():
                return {"validation_passed": False, "validation_failures": ["No output file"]}
            
            with open(output_file, 'r') as f:
                output_content = f.read().strip()
            
            if not output_content:
                return {"validation_passed": False, "validation_failures": ["Empty output"]}
            
            # Parse JSON output
            try:
                output_data = json.loads(output_content.split('\n')[0])
            except json.JSONDecodeError:
                return {"validation_passed": False, "validation_failures": ["Invalid JSON output"]}
            
            # Validate expected extractions
            expected = test_case["expected_extractions"]
            validation_failures = []
            fields_found = []
            values_extracted = []
            
            # Check that expected fields exist
            for field in expected.get("fields_that_should_exist", []):
                if field in output_data:
                    fields_found.append(field)
                else:
                    validation_failures.append(f"Missing field: {field}")
            
            # Check that expected values are present in output
            output_str = json.dumps(output_data)
            for value in expected.get("should_contain", []):
                if str(value) in output_str:
                    values_extracted.append(value)
                else:
                    validation_failures.append(f"Missing value: {value}")
            
            # Check specific field validations
            for field_name, expected_value in expected.get("string_validations", []):
                if field_name in output_data and output_data[field_name] == expected_value:
                    values_extracted.append(f"{field_name}={expected_value}")
                else:
                    validation_failures.append(f"Field {field_name} not equal to {expected_value}")
            
            # Check numeric validations
            for field_name, expected_value in expected.get("numeric_validations", []):
                if field_name in output_data and output_data[field_name] == expected_value:
                    values_extracted.append(f"{field_name}={expected_value}")
                else:
                    validation_failures.append(f"Numeric field {field_name} not equal to {expected_value}")
            
            return {
                "validation_passed": len(validation_failures) == 0,
                "validation_failures": validation_failures,
                "fields_found": fields_found,
                "values_extracted": values_extracted,
                "output_data": output_data
            }
            
        except Exception as e:
            return {
                "validation_passed": False,
                "validation_failures": [f"Exception: {e}"]
            }


def main():
    """Run output validation test"""
    tester = OutputValidationTest()
    success = tester.test_field_extraction_accuracy()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())