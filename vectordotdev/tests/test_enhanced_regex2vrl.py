#!/usr/bin/env python3
"""
Comprehensive validation tests for the enhanced regex2vrl system v2.0.0
Tests high-performance VRL generation with complex patterns and production data
"""

import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any

# Add vectordotdev to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vectordotdev.regex2vrl.core import RegexToVRL
from vectordotdev.regex2vrl.grok_converter import GrokToVRL
from vectordotdev.regex2vrl.performance_engine import HighPerformanceVRLGenerator


class EnhancedRegex2VRLValidator:
    """Comprehensive validator for the enhanced regex2vrl system"""
    
    def __init__(self):
        self.regex_converter = RegexToVRL()
        self.grok_converter = GrokToVRL()
        self.performance_engine = HighPerformanceVRLGenerator()
        self.results = {
            "complex_regex_tests": [],
            "complex_grok_tests": [], 
            "performance_validation": [],
            "vrl_syntax_validation": []
        }
        
        # Load production test data
        self._load_test_data()
    
    def _load_test_data(self):
        """Load production patterns and sample data"""
        try:
            # Load regex patterns
            regex_patterns_file = Path(__file__).parent / "fixtures/test_patterns/production_regex_patterns.yaml"
            with open(regex_patterns_file) as f:
                self.regex_patterns = yaml.safe_load(f)
            
            # Load grok patterns  
            grok_patterns_file = Path(__file__).parent / "fixtures/test_patterns/production_grok_patterns.yaml"
            with open(grok_patterns_file) as f:
                self.grok_patterns = yaml.safe_load(f)
                
            # Load sample logs
            sample_logs_file = Path(__file__).parent / "fixtures/test_data/production_log_samples.yaml"
            with open(sample_logs_file) as f:
                self.sample_logs = yaml.safe_load(f)
                
        except FileNotFoundError as e:
            print(f"Warning: Could not load test data: {e}")
            # Fallback to minimal test data
            self._create_fallback_test_data()
    
    def _create_fallback_test_data(self):
        """Create minimal test data if files not found"""
        self.regex_patterns = {
            "apache_combined_log": {
                "pattern": r'^(?P<remote_addr>\d+\.\d+\.\d+\.\d+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request_method>[A-Z]+) (?P<request_uri>[^\s"]+) HTTP/(?P<http_version>[\d\.]+)" (?P<status>\d{3}) (?P<body_bytes_sent>\d+) "(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)"',
                "expected_fields": ["remote_addr", "remote_user", "time_local", "request_method", "request_uri", "status"]
            }
        }
        
        self.grok_patterns = {
            "httpd_combinedlog": {
                "pattern": "%{COMBINEDAPACHELOG}",
                "expected_fields": ["clientip", "timestamp", "verb", "response"]
            }
        }
        
        self.sample_logs = {
            "apache_combined_log": [
                '192.168.1.100 - - [15/Jan/2025:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1024 "https://google.com" "Mozilla/5.0"'
            ]
        }

    def validate_complex_regex_patterns(self) -> bool:
        """Test complex regex patterns with the enhanced system"""
        print("🔍 Testing Complex Regex Patterns")
        print("=" * 50)
        
        success_count = 0
        total_count = 0
        
        for pattern_name, pattern_data in self.regex_patterns.items():
            total_count += 1
            pattern = pattern_data.get("pattern", "")
            expected_fields = pattern_data.get("expected_fields", [])
            
            # Get corresponding sample logs
            sample_logs = self.sample_logs.get(pattern_name, [])
            
            print(f"\n📋 Testing pattern: {pattern_name}")
            print(f"   Pattern: {pattern[:60]}...")
            print(f"   Expected fields: {len(expected_fields)}")
            print(f"   Sample logs: {len(sample_logs)}")
            
            try:
                # Test with sample logs for improved accuracy
                if sample_logs:
                    vrl_code = self.regex_converter.convert(
                        pattern, 
                        sample_logs=sample_logs,
                        output_format='commented'
                    )
                else:
                    vrl_code = self.regex_converter.convert(pattern, output_format='commented')
                
                # Validate VRL syntax
                syntax_valid = self._validate_vrl_syntax(vrl_code)
                
                # Check performance indicators
                performance_ok = self._check_performance_indicators(vrl_code)
                
                if syntax_valid and performance_ok:
                    success_count += 1
                    print(f"   ✅ SUCCESS - Generated {len(vrl_code)} chars of VRL")
                    
                    # Show sample VRL output
                    print(f"   📝 VRL preview:")
                    print("      " + "\n      ".join(vrl_code.split('\n')[:5]))
                    if len(vrl_code.split('\n')) > 5:
                        print("      ...")
                else:
                    print(f"   ❌ FAILED - Syntax: {syntax_valid}, Performance: {performance_ok}")
                    
                # Store results
                self.results["complex_regex_tests"].append({
                    "pattern_name": pattern_name,
                    "success": syntax_valid and performance_ok,
                    "vrl_length": len(vrl_code),
                    "expected_fields": len(expected_fields),
                    "sample_logs": len(sample_logs),
                    "syntax_valid": syntax_valid,
                    "performance_ok": performance_ok
                })
                
            except Exception as e:
                print(f"   ❌ EXCEPTION: {e}")
                self.results["complex_regex_tests"].append({
                    "pattern_name": pattern_name,
                    "success": False,
                    "error": str(e)
                })
        
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        print(f"\n📊 Complex Regex Results: {success_count}/{total_count} ({success_rate:.1f}%)")
        return success_rate >= 80  # 80% success threshold

    def validate_complex_grok_patterns(self) -> bool:
        """Test complex grok patterns with the enhanced system"""
        print("\n🔍 Testing Complex Grok Patterns")
        print("=" * 50)
        
        success_count = 0
        total_count = 0
        
        for pattern_name, pattern_data in self.grok_patterns.items():
            total_count += 1
            pattern = pattern_data.get("pattern", "")
            expected_fields = pattern_data.get("expected_fields", [])
            
            # Map grok pattern to sample logs
            sample_key = pattern_name.replace("_", "_").lower()
            if sample_key not in self.sample_logs:
                # Try common mappings
                if "apache" in pattern_name or "httpd" in pattern_name:
                    sample_key = "apache_combined_log"
                elif "syslog" in pattern_name:
                    sample_key = "syslog_standard"
            
            sample_logs = self.sample_logs.get(sample_key, [])
            
            print(f"\n📋 Testing grok: {pattern_name}")
            print(f"   Pattern: {pattern[:60]}...")
            print(f"   Expected fields: {len(expected_fields)}")
            print(f"   Sample logs: {len(sample_logs)}")
            
            try:
                # Convert grok pattern
                if sample_logs:
                    vrl_code = self.grok_converter.convert(pattern, sample_logs=sample_logs)
                else:
                    vrl_code = self.grok_converter.convert(pattern)
                
                # Validate VRL syntax
                syntax_valid = self._validate_vrl_syntax(vrl_code)
                
                # Check performance indicators  
                performance_ok = self._check_performance_indicators(vrl_code)
                
                if syntax_valid and performance_ok:
                    success_count += 1
                    print(f"   ✅ SUCCESS - Generated {len(vrl_code)} chars of VRL")
                    
                    # Show sample VRL output
                    print(f"   📝 VRL preview:")
                    print("      " + "\n      ".join(vrl_code.split('\n')[:5]))
                    if len(vrl_code.split('\n')) > 5:
                        print("      ...")
                else:
                    print(f"   ❌ FAILED - Syntax: {syntax_valid}, Performance: {performance_ok}")
                    
                # Store results
                self.results["complex_grok_tests"].append({
                    "pattern_name": pattern_name,
                    "success": syntax_valid and performance_ok,
                    "vrl_length": len(vrl_code),
                    "expected_fields": len(expected_fields),
                    "sample_logs": len(sample_logs),
                    "syntax_valid": syntax_valid,
                    "performance_ok": performance_ok
                })
                
            except Exception as e:
                print(f"   ❌ EXCEPTION: {e}")
                self.results["complex_grok_tests"].append({
                    "pattern_name": pattern_name,
                    "success": False,
                    "error": str(e)
                })
        
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        print(f"\n📊 Complex Grok Results: {success_count}/{total_count} ({success_rate:.1f}%)")
        return success_rate >= 80  # 80% success threshold

    def validate_performance_compliance(self) -> bool:
        """Validate that generated VRL follows performance guidelines"""
        print("\n⚡ Validating Performance Compliance")
        print("=" * 50)
        
        # Test patterns that should trigger different optimization paths
        test_cases = [
            {
                "name": "JSON Detection",
                "pattern": r'^(?P<json_data>\{.*\})$',
                "expected_builtin": "parse_json"
            },
            {
                "name": "Key-Value Pairs",
                "pattern": r'(?P<pairs>key1=value1.*key2=value2)',
                "expected_builtin": "parse_key_value"
            },
            {
                "name": "Delimited Fields",
                "pattern": r'^(?P<field1>[^|]+)\|(?P<field2>[^|]+)\|(?P<field3>.*)$',
                "expected_method": "split"
            },
            {
                "name": "Complex Pattern",
                "pattern": r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z) (?P<level>[A-Z]+) (?P<service>\w+) (?P<message>.*)$',
                "expected_method": "string_operations"
            }
        ]
        
        compliant_count = 0
        
        for test_case in test_cases:
            name = test_case["name"]
            pattern = test_case["pattern"]
            
            print(f"\n🧪 Testing: {name}")
            
            try:
                vrl_code = self.regex_converter.convert(pattern, output_format='commented')
                
                # Check for banned functions
                banned_found = self._check_banned_functions(vrl_code)
                
                # Check for performance indicators
                performance_ok = self._check_performance_indicators(vrl_code)
                
                # Check target THG mention
                thg_mentioned = "350+ THG" in vrl_code or "THG" in vrl_code
                
                if not banned_found and performance_ok and thg_mentioned:
                    compliant_count += 1
                    print(f"   ✅ COMPLIANT - No banned functions, performance optimized")
                else:
                    print(f"   ❌ NON-COMPLIANT - Banned: {banned_found}, Perf: {performance_ok}, THG: {thg_mentioned}")
                
                # Store detailed results
                self.results["performance_validation"].append({
                    "name": name,
                    "compliant": not banned_found and performance_ok and thg_mentioned,
                    "banned_functions": banned_found,
                    "performance_ok": performance_ok,
                    "thg_mentioned": thg_mentioned,
                    "vrl_length": len(vrl_code)
                })
                
            except Exception as e:
                print(f"   ❌ EXCEPTION: {e}")
                self.results["performance_validation"].append({
                    "name": name,
                    "compliant": False,
                    "error": str(e)
                })
        
        compliance_rate = (compliant_count / len(test_cases)) * 100
        print(f"\n📊 Performance Compliance: {compliant_count}/{len(test_cases)} ({compliance_rate:.1f}%)")
        return compliance_rate >= 90  # 90% compliance threshold

    def _validate_vrl_syntax(self, vrl_code: str) -> bool:
        """Basic VRL syntax validation"""
        # Check for common syntax issues
        if not vrl_code.strip():
            return False
        
        # Check for balanced braces
        open_braces = vrl_code.count('{')
        close_braces = vrl_code.count('}')
        if open_braces != close_braces:
            return False
        
        # Check for required VRL patterns
        has_message_extraction = 'string!(' in vrl_code
        has_field_assignment = '.' in vrl_code and '=' in vrl_code
        
        return has_message_extraction or has_field_assignment

    def _check_performance_indicators(self, vrl_code: str) -> bool:
        """Check for performance optimization indicators"""
        # Should use high-performance functions
        good_functions = [
            'string!(', 'split(', 'contains(', 'starts_with(', 'ends_with(',
            'parse_json!(', 'parse_key_value!(', 'parse_syslog!(',
            'to_int(', 'to_float(', 'length(', 'is_ipv4('
        ]
        
        has_good_functions = any(func in vrl_code for func in good_functions)
        
        # Should NOT use banned functions
        banned_functions = [
            'parse_regex(', 'parse_grok(', 'match(', 'to_regex('
        ]
        
        has_banned_functions = any(func in vrl_code for func in banned_functions)
        
        return has_good_functions and not has_banned_functions

    def _check_banned_functions(self, vrl_code: str) -> bool:
        """Check for banned regex-based functions"""
        banned_functions = [
            'parse_regex(', 'parse_regex_all(', 'parse_grok(', 'parse_groks(',
            'match(', 'to_regex(', 'is_regex('
        ]
        
        return any(func in vrl_code for func in banned_functions)

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation tests and return comprehensive results"""
        print("🚀 Enhanced regex2vrl v2.0.0 Comprehensive Validation")
        print("=" * 70)
        print("Testing high-performance VRL generation with complex patterns")
        print()
        
        # Run all validation tests
        regex_success = self.validate_complex_regex_patterns()
        grok_success = self.validate_complex_grok_patterns()  
        performance_success = self.validate_performance_compliance()
        
        # Generate final report
        overall_success = regex_success and grok_success and performance_success
        
        print("\n" + "=" * 70)
        print("📋 COMPREHENSIVE VALIDATION REPORT")
        print("=" * 70)
        print(f"Complex Regex Patterns:     {'✅ PASS' if regex_success else '❌ FAIL'}")
        print(f"Complex Grok Patterns:      {'✅ PASS' if grok_success else '❌ FAIL'}")
        print(f"Performance Compliance:     {'✅ PASS' if performance_success else '❌ FAIL'}")
        print(f"Overall System Status:      {'✅ READY FOR PRODUCTION' if overall_success else '❌ NEEDS IMPROVEMENT'}")
        
        # Calculate statistics
        total_regex_tests = len(self.results["complex_regex_tests"])
        successful_regex = sum(1 for r in self.results["complex_regex_tests"] if r.get("success", False))
        
        total_grok_tests = len(self.results["complex_grok_tests"])
        successful_grok = sum(1 for r in self.results["complex_grok_tests"] if r.get("success", False))
        
        total_perf_tests = len(self.results["performance_validation"])
        successful_perf = sum(1 for r in self.results["performance_validation"] if r.get("compliant", False))
        
        print(f"\nDetailed Statistics:")
        print(f"- Regex patterns processed: {total_regex_tests} ({successful_regex} successful)")
        print(f"- Grok patterns processed: {total_grok_tests} ({successful_grok} successful)")
        print(f"- Performance tests: {total_perf_tests} ({successful_perf} compliant)")
        
        return {
            "overall_success": overall_success,
            "regex_success": regex_success,
            "grok_success": grok_success,
            "performance_success": performance_success,
            "detailed_results": self.results,
            "statistics": {
                "total_tests": total_regex_tests + total_grok_tests + total_perf_tests,
                "successful_tests": successful_regex + successful_grok + successful_perf
            }
        }


def main():
    """Main validation entry point"""
    validator = EnhancedRegex2VRLValidator()
    results = validator.run_comprehensive_validation()
    
    # Return appropriate exit code
    return 0 if results["overall_success"] else 1


if __name__ == "__main__":
    sys.exit(main())