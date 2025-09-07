#!/usr/bin/env python3
"""
Production pattern tests for regex2vrl using real Vector execution.
Tests production-proven regex and grok patterns with actual Vector binary.
All patterns and test data are loaded from configuration files.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add vectordotdev module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    # Import the vectordotdev library for VRL functionality  
    import vectordotdev
    from vectordotdev.regex2vrl.core import RegexToVRL
    from vectordotdev.regex2vrl.grok_converter import GrokToVRL
    HAS_VECTORDOTDEV = True
except ImportError as e:
    print(f"Warning: vectordotdev library not available: {e}")
    HAS_VECTORDOTDEV = False


class ProductionPatternTestRunner:
    """Test runner for production regex/grok patterns using Vector and vectordotdev library"""
    
    def __init__(self, vector_binary: Optional[str] = None, verbose: bool = False):
        self.verbose = verbose
        self.vector_binary = self._find_vector_binary(vector_binary)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="production_pattern_test_"))
        self.test_results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}
        
        # Set up test directories
        self.config_dir = self.temp_dir / "configs"
        self.data_dir = self.temp_dir / "data"
        self.output_dir = self.temp_dir / "output"
        
        for dir_path in [self.config_dir, self.data_dir, self.output_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Load test configurations
        fixtures_dir = Path(__file__).parent.parent / "fixtures"
        self.test_config_dir = fixtures_dir / "test_configs"
        self.test_patterns_dir = fixtures_dir / "test_patterns"
        self.test_data_dir = fixtures_dir / "test_data"
        
        self._load_configurations()
        
        if self.verbose:
            print(f"Test workspace: {self.temp_dir}")
            print(f"Using vectordotdev library: {HAS_VECTORDOTDEV}")
    
    def _find_vector_binary(self, custom_path: Optional[str]) -> Optional[Path]:
        """Find Vector binary in the project"""
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return path
        
        # Search common locations in vectordotdev project
        search_paths = [
            Path("vector/target/release/vector"),
            Path("vector/target/debug/vector"),
            Path("../vector/target/release/vector"),
            Path("../vector/target/debug/vector"),
            Path("./target/release/vector"),
            Path("./target/debug/vector"),
        ]
        
        for path in search_paths:
            if path.exists() and path.is_file():
                return path.resolve()
        
        # Try system PATH
        try:
            result = subprocess.run(["which", "vector"], 
                                  capture_output=True, text=True, check=True)
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            pass
        
        return None
    
    def _load_configurations(self):
        """Load test configurations from YAML files"""
        try:
            # Load pattern test config
            config_file = self.test_config_dir / "pattern_test_config.yaml"
            with open(config_file) as f:
                self.test_config = yaml.safe_load(f)
            
            # Load regex patterns
            regex_file = self.test_patterns_dir / "production_regex_patterns.yaml"
            with open(regex_file) as f:
                self.regex_patterns = yaml.safe_load(f)
            
            # Load grok patterns
            grok_file = self.test_patterns_dir / "production_grok_patterns.yaml"
            with open(grok_file) as f:
                self.grok_patterns = yaml.safe_load(f)
                
            # Load sample data
            samples_file = self.test_data_dir / "production_log_samples.yaml"
            with open(samples_file) as f:
                self.sample_data = yaml.safe_load(f)
                
            if self.verbose:
                print(f"Loaded {len(self.test_config['test_configurations'])} test configurations")
                print(f"Loaded {len(self.regex_patterns)} regex patterns")
                print(f"Loaded {len(self.grok_patterns)} grok patterns")
                
        except Exception as e:
            raise RuntimeError(f"Failed to load test configurations: {e}")
    
    def _get_pattern_data(self, test_config: Dict[str, Any]) -> Tuple[str, str, List[str], List[str]]:
        """Extract pattern, description, sample data and expected fields from config"""
        pattern_file = test_config["pattern_file"]
        pattern_key = test_config["pattern_key"]
        sample_data_file = test_config["sample_data_file"] 
        sample_data_key = test_config["sample_data_key"]
        
        # Get pattern info
        if pattern_file == "production_regex_patterns.yaml":
            pattern_info = self.regex_patterns[pattern_key]
        else:
            pattern_info = self.grok_patterns[pattern_key]
            
        pattern = pattern_info["pattern"]
        description = pattern_info["description"]
        expected_fields = pattern_info.get("expected_fields", [])
        
        # Get sample data
        sample_logs = self.sample_data[sample_data_key]
        
        return pattern, description, sample_logs, expected_fields
    
    def create_vector_config(self, vrl_source: str, test_name: str, 
                           input_logs: List[str]) -> Path:
        """Create Vector configuration for testing VRL code"""
        
        input_file = self.data_dir / f"{test_name}_input.log"
        output_file = self.output_dir / f"{test_name}_output.jsonl"
        
        # Write input data
        with open(input_file, 'w') as f:
            for log_line in input_logs:
                f.write(log_line + '\n')
        
        # Create Vector config
        config = {
            "data_dir": str(self.temp_dir / "vector_data"),
            "sources": {
                "test_input": {
                    "type": "file",
                    "include": [str(input_file)],
                    "read_from": "beginning",
                    "remove_after_secs": 2
                }
            },
            "transforms": {
                "regex2vrl_transform": {
                    "type": "remap",
                    "inputs": ["test_input"],
                    "source": vrl_source
                }
            },
            "sinks": {
                "test_output": {
                    "type": "file",
                    "inputs": ["regex2vrl_transform"],
                    "path": str(output_file),
                    "encoding": {
                        "codec": "json"
                    }
                }
            }
        }
        
        config_file = self.config_dir / f"{test_name}.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_file
    
    def run_vector_test(self, config_path: Path, timeout: int = 20) -> Tuple[bool, List[Dict], str]:
        """Run Vector with configuration and return parsed results"""
        if not self.vector_binary:
            return False, [], "Vector binary not found"
        
        if self.verbose:
            print(f"Running Vector: {self.vector_binary} --config {config_path}")
        
        try:
            # Run Vector process
            process = subprocess.Popen([
                str(self.vector_binary),
                "--config", str(config_path),
                "--quiet" if not self.verbose else "--log-level", "info"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Let Vector process the data
            time.sleep(4)
            
            # Terminate Vector gracefully
            process.terminate()
            stdout, stderr = process.communicate(timeout=timeout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return False, [], f"Vector process timed out after {timeout}s"
        except Exception as e:
            return False, [], f"Vector execution failed: {e}"
        
        # Parse output file
        test_name = config_path.stem
        output_file = self.output_dir / f"{test_name}_output.jsonl"
        
        results = []
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            results.append(json.loads(line))
            except Exception as e:
                return False, [], f"Failed to parse Vector output: {e}"
        
        success = len(results) > 0
        if not success and stderr:
            return False, results, f"Vector stderr: {stderr}"
        
        return success, results, ""
    
    def test_pattern(self, test_name: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single pattern configuration"""
        
        if self.verbose:
            print(f"\n=== Testing {test_name} ===")
        
        try:
            # Skip if vectordotdev library is not available
            if not HAS_VECTORDOTDEV:
                result = {
                    "test_name": test_name,
                    "success": False,
                    "skipped": True,
                    "error": "vectordotdev library not available"
                }
                self.test_results["skipped"] += 1
                self.test_results["tests"].append(result)
                return result
            
            # Get pattern and sample data
            pattern, description, sample_logs, expected_fields = self._get_pattern_data(test_config)
            pattern_type = test_config["pattern_type"]
            performance_target = test_config.get("performance_target_thg", 300)
            
            if self.verbose:
                print(f"Pattern: {pattern[:100]}{'...' if len(pattern) > 100 else ''}")
                print(f"Type: {pattern_type}")
                print(f"Description: {description}")
                print(f"Sample logs: {len(sample_logs)}")
                print(f"Expected fields: {expected_fields}")
            
            # Convert pattern using vectordotdev library
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern, output_format='commented')
                analysis = converter.analyze_pattern(pattern)
            else:  # grok
                converter = GrokToVRL()
                vrl_code = converter.convert(pattern)
                # Analyze the expanded regex for performance metrics
                expanded = converter._expand_grok_to_regex(pattern)
                regex_converter = RegexToVRL()
                analysis = regex_converter.analyze_pattern(expanded)
            
            if self.verbose:
                print(f"Generated VRL code: {len(vrl_code)} chars")
                print(f"Estimated THG: {analysis.estimated_thg} (target: {performance_target})")
                print(f"Can use built-in: {analysis.can_use_builtin}")
                if analysis.suggested_parser:
                    print(f"Suggested parser: {analysis.suggested_parser}")
            
            # Create Vector config and run test
            config_path = self.create_vector_config(vrl_code, test_name, sample_logs)
            success, results, error = self.run_vector_test(config_path)
            
            # Analyze results
            parsed_count = len(results)
            expected_count = len(sample_logs)
            
            # Check field extraction
            field_validation = {}
            if expected_fields and results:
                for field in expected_fields:
                    field_found = any(field in result for result in results)
                    field_validation[field] = field_found
            
            # Build test result
            test_result = {
                "test_name": test_name,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "description": description,
                "success": success,
                "input_count": expected_count,
                "output_count": parsed_count,
                "parsing_rate": (parsed_count / expected_count * 100) if expected_count > 0 else 0,
                "estimated_thg": analysis.estimated_thg,
                "performance_target_thg": performance_target,
                "performance_met": analysis.estimated_thg >= performance_target,
                "can_use_builtin": analysis.can_use_builtin,
                "suggested_parser": analysis.suggested_parser,
                "expected_fields": expected_fields,
                "field_validation": field_validation,
                "sample_results": results[:2] if results else [],  # Include sample results
                "error": error
            }
            
            # Determine overall success
            overall_success = (success and 
                             parsed_count > 0 and 
                             analysis.estimated_thg >= performance_target)
            
            if overall_success:
                self.test_results["passed"] += 1
                if self.verbose:
                    print(f"✅ PASSED - {parsed_count}/{expected_count} logs parsed (THG: {analysis.estimated_thg})")
            else:
                self.test_results["failed"] += 1
                if self.verbose:
                    failure_reasons = []
                    if not success:
                        failure_reasons.append("Vector execution failed")
                    if parsed_count == 0:
                        failure_reasons.append("No logs parsed")
                    if analysis.estimated_thg < performance_target:
                        failure_reasons.append(f"Performance below target ({analysis.estimated_thg} < {performance_target})")
                    print(f"❌ FAILED - {'; '.join(failure_reasons)}")
                    if error:
                        print(f"   Error: {error}")
            
            test_result["success"] = overall_success
            self.test_results["tests"].append(test_result)
            return test_result
            
        except Exception as e:
            error_result = {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "pattern": pattern if 'pattern' in locals() else "unknown"
            }
            
            self.test_results["failed"] += 1
            self.test_results["tests"].append(error_result)
            
            if self.verbose:
                print(f"❌ EXCEPTION - {e}")
            
            return error_result
    
    def run_test_suite(self, test_filter: Optional[str] = None, max_workers: int = 4):
        """Run the full test suite"""
        print("🚀 Starting Production Pattern Test Suite")
        print(f"Vector binary: {self.vector_binary}")
        print(f"Vectordotdev library: {'Available' if HAS_VECTORDOTDEV else 'NOT AVAILABLE'}")
        print("=" * 70)
        
        if not self.vector_binary:
            print("❌ Vector binary not found!")
            print("Please build Vector or specify path with --vector-binary")
            return False
        
        # Filter tests if requested
        test_configurations = self.test_config["test_configurations"]
        if test_filter:
            test_configurations = {k: v for k, v in test_configurations.items() 
                                 if test_filter.lower() in k.lower()}
            print(f"Running filtered tests: {list(test_configurations.keys())}")
        
        # Run tests in parallel for better performance
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_test = {}
            
            for test_name, test_config in test_configurations.items():
                future = executor.submit(self.test_pattern, test_name, test_config)
                future_to_test[future] = test_name
            
            # Process completed tests
            for future in as_completed(future_to_test):
                test_name = future_to_test[future]
                try:
                    result = future.result()
                    if not self.verbose:
                        # Show progress for non-verbose mode
                        status = "✅" if result["success"] else "❌"
                        if result.get("skipped"):
                            status = "⏭️"
                        print(f"{status} {test_name}")
                except Exception as e:
                    print(f"❌ {test_name} - Exception: {e}")
        
        return True
    
    def run_performance_tests(self):
        """Run performance-focused test suites"""
        print("\n🔥 Performance Test Suites")
        print("=" * 40)
        
        performance_suites = self.test_config.get("performance_test_suites", {})
        
        for suite_name, suite_config in performance_suites.items():
            print(f"\n--- {suite_name.upper()} ---")
            print(f"Description: {suite_config['description']}")
            
            target_thg = suite_config["target_thg_minimum"]
            patterns_to_test = suite_config["patterns"]
            
            for pattern_name in patterns_to_test:
                if pattern_name not in self.test_config["test_configurations"]:
                    continue
                    
                test_config = self.test_config["test_configurations"][pattern_name]
                pattern, _, _, _ = self._get_pattern_data(test_config)
                
                # Analyze pattern performance using vectordotdev
                if HAS_VECTORDOTDEV:
                    if test_config["pattern_type"] == "regex":
                        converter = RegexToVRL()
                        analysis = converter.analyze_pattern(pattern)
                    else:
                        converter = GrokToVRL()
                        expanded = converter._expand_grok_to_regex(pattern)
                        regex_converter = RegexToVRL()
                        analysis = regex_converter.analyze_pattern(expanded)
                    
                    status = "✅" if analysis.estimated_thg >= target_thg else "⚠️"
                    builtin_info = f" [Built-in: {analysis.suggested_parser}]" if analysis.can_use_builtin else ""
                    print(f"{status} {pattern_name}: THG {analysis.estimated_thg} (target ≥{target_thg}){builtin_info}")
                else:
                    print(f"⏭️ {pattern_name}: Skipped (vectordotdev not available)")
    
    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        total_tests = self.test_results["passed"] + self.test_results["failed"] + self.test_results["skipped"]
        pass_rate = (self.test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
        
        report = f"""
Production Pattern Test Report - regex2vrl with Vector Integration
{"=" * 80}

Test Environment:
  Vector Binary: {self.vector_binary}
  Vectordotdev Library: {'Available' if HAS_VECTORDOTDEV else 'NOT AVAILABLE'}
  Test Workspace: {self.temp_dir}

Summary:
  Total Tests: {total_tests}
  Passed: {self.test_results["passed"]} ✅
  Failed: {self.test_results["failed"]} ❌  
  Skipped: {self.test_results["skipped"]} ⏭️
  Pass Rate: {pass_rate:.1f}%

Detailed Results:
"""
        
        # Group results by pattern type
        regex_tests = [t for t in self.test_results["tests"] if t.get("pattern_type") == "regex"]
        grok_tests = [t for t in self.test_results["tests"] if t.get("pattern_type") == "grok"]
        
        report += f"\nRegex Pattern Tests ({len(regex_tests)}):\n"
        for test in regex_tests:
            status = "✅" if test["success"] else "❌" if not test.get("skipped") else "⏭️"
            report += f"{status} {test['test_name']}"
            
            if test["success"]:
                parsing_rate = test.get("parsing_rate", 0)
                thg = test.get("estimated_thg", 0)
                report += f" - {parsing_rate:.0f}% parsed (THG: {thg})"
                if test.get("can_use_builtin"):
                    report += f" [Built-in: {test.get('suggested_parser')}]"
            elif test.get("error"):
                report += f" - ERROR: {test['error']}"
                
            report += "\n"
        
        report += f"\nGrok Pattern Tests ({len(grok_tests)}):\n"
        for test in grok_tests:
            status = "✅" if test["success"] else "❌" if not test.get("skipped") else "⏭️"
            report += f"{status} {test['test_name']}"
            
            if test["success"]:
                parsing_rate = test.get("parsing_rate", 0)
                thg = test.get("estimated_thg", 0)
                report += f" - {parsing_rate:.0f}% parsed (THG: {thg})"
                if test.get("can_use_builtin"):
                    report += f" [Built-in: {test.get('suggested_parser')}]"
            elif test.get("error"):
                report += f" - ERROR: {test['error']}"
                
            report += "\n"
        
        # Performance summary
        performance_summary = {}
        for test in self.test_results["tests"]:
            if test.get("estimated_thg"):
                thg = test["estimated_thg"]
                if thg >= 350:
                    performance_summary.setdefault("excellent", []).append(test["test_name"])
                elif thg >= 250:
                    performance_summary.setdefault("good", []).append(test["test_name"])
                elif thg >= 150:
                    performance_summary.setdefault("moderate", []).append(test["test_name"])
                else:
                    performance_summary.setdefault("poor", []).append(test["test_name"])
        
        report += "\nPerformance Summary:\n"
        for category, tests in performance_summary.items():
            emoji = {"excellent": "🚀", "good": "✅", "moderate": "⚠️", "poor": "❌"}[category]
            report += f"{emoji} {category.upper()}: {len(tests)} tests\n"
        
        return report
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def main():
    parser = argparse.ArgumentParser(
        description='Run production pattern tests for regex2vrl with Vector execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python run_production_pattern_tests.py
  
  # Run with custom Vector binary
  python run_production_pattern_tests.py --vector-binary /path/to/vector
  
  # Filter tests (regex patterns only)
  python run_production_pattern_tests.py --filter regex
  
  # Performance tests only
  python run_production_pattern_tests.py --performance-only
  
  # Save detailed report
  python run_production_pattern_tests.py --output report.txt --verbose
        """
    )
    
    parser.add_argument('--vector-binary', help='Path to Vector binary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--filter', help='Filter tests by name (substring match)')
    parser.add_argument('--performance-only', action='store_true', help='Run only performance analysis')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum parallel test workers')
    parser.add_argument('--output', '-o', help='Save report to file')
    parser.add_argument('--keep-workspace', action='store_true', help='Keep temporary files for debugging')
    
    args = parser.parse_args()
    
    runner = ProductionPatternTestRunner(
        vector_binary=args.vector_binary,
        verbose=args.verbose
    )
    
    try:
        if args.performance_only:
            runner.run_performance_tests()
        else:
            success = runner.run_test_suite(
                test_filter=args.filter,
                max_workers=args.max_workers
            )
            
            if success and not args.filter:
                runner.run_performance_tests()
        
        # Generate and display report
        report = runner.generate_report()
        print(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"\nReport saved to: {args.output}")
        
        # Show workspace location if keeping files
        if args.keep_workspace:
            print(f"\nWorkspace preserved at: {runner.temp_dir}")
        
        return 0 if runner.test_results["failed"] == 0 else 1
        
    finally:
        if not args.keep_workspace:
            runner.cleanup()


if __name__ == '__main__':
    sys.exit(main())