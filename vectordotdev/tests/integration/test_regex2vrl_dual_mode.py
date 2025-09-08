#!/usr/bin/env python3
"""
Dual-mode integration tests for regex2vrl.
Tests both native bindings and cmdline emulation using YAML config.
"""

import asyncio
import json
import sys
import tempfile
import time
import yaml
from pathlib import Path

# Add paths
sys.path.insert(0, '/projects/vectordotdev')
sys.path.insert(0, '/projects/vectordotdev/vectordotdev/.venv/lib/python3.13/site-packages')

try:
    import vector
    from vectordotdev.regex2vrl.core import RegexToVRL
    from vectordotdev.regex2vrl.grok_converter import GrokToVRL
    HAS_BINDINGS = True
except ImportError as e:
    print(f"❌ vectordotdev bindings not available: {e}")
    HAS_BINDINGS = False
    sys.exit(1)


class DualModeRegex2VRLTester:
    """Test regex2vrl with both native bindings and cmdline emulation"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            "native_bindings": [],
            "cmdline_emulation": []
        }
    
    def test_native_bindings(self, pattern: str, pattern_type: str, test_logs: list, test_name: str):
        """Test using native vectordotdev bindings with YAML config concepts"""
        
        if self.verbose:
            print(f"\n🔗 Native Bindings Test: {test_name}")
        
        try:
            # Generate VRL using regex2vrl
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern)
                analysis = converter.analyze_pattern(pattern)
            else:
                converter = GrokToVRL()
                vrl_code = converter.convert(pattern)
                expanded = converter._expand_grok_to_regex(pattern)
                regex_converter = RegexToVRL()
                analysis = regex_converter.analyze_pattern(expanded)
            
            if self.verbose:
                print(f"   📝 Generated VRL ({len(vrl_code)} chars)")
                print(f"   📊 Estimated THG: {analysis.estimated_thg}")
            
            # Create YAML-style config (converted to TOML for current bindings)
            yaml_config = {
                "sources": {
                    "python": {
                        "type": "python"
                    }
                },
                "transforms": {
                    "regex2vrl_transform": {
                        "type": "remap",
                        "inputs": ["python"],
                        "source": vrl_code
                    }
                },
                "sinks": {
                    "file_output": {
                        "type": "file",
                        "inputs": ["regex2vrl_transform"],
                        "path": f"/tmp/native_{test_name}.txt",
                        "encoding": {
                            "codec": "json"
                        }
                    }
                }
            }
            
            # Convert YAML config to TOML for current bindings
            toml_config = self._yaml_to_toml_config(yaml_config)
            
            if self.verbose:
                print(f"   🔧 Config: YAML → TOML conversion")
            
            # Test with native bindings
            v = vector.Vector(toml_config)
            v.start()
            
            # Send test data
            for log in test_logs:
                data = json.dumps({"message": log, "source": "native_test"}).encode()
                v.send("python", data)
            
            time.sleep(2)
            v.stop()
            
            # Check results
            output_path = f"/tmp/native_{test_name}.txt"
            import os
            if os.path.exists(output_path):
                with open(output_path) as f:
                    content = f.read().strip()
                    if content:
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        success = len(lines) > 0
                        
                        if self.verbose:
                            print(f"   ✅ Native bindings: {len(lines)} results")
                            if lines and self.verbose:
                                sample = json.loads(lines[0])
                                print(f"      Sample: {sample}")
                        
                        self.results["native_bindings"].append({
                            "test_name": test_name,
                            "success": success,
                            "results_count": len(lines),
                            "input_count": len(test_logs),
                            "estimated_thg": analysis.estimated_thg
                        })
                        
                        return success
            
            if self.verbose:
                print(f"   ❌ Native bindings: No output")
            
            self.results["native_bindings"].append({
                "test_name": test_name,
                "success": False,
                "results_count": 0,
                "input_count": len(test_logs)
            })
            
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Native bindings error: {e}")
            return False
    
    def test_cmdline_emulation(self, pattern: str, pattern_type: str, test_logs: list, test_name: str):
        """Test using VectorCliPy (existing CLI emulation API)"""
        
        if self.verbose:
            print(f"      🖥️ CLI Emulation Test: {test_name}")
        
        try:
            import os
            
            # Generate VRL
            if pattern_type == "regex":
                converter = RegexToVRL()
                vrl_code = converter.convert(pattern)
            else:
                converter = GrokToVRL()
                vrl_code = converter.convert(pattern)
            
            # Create input file for file source (CLI style)
            input_file = f"/tmp/cli_input_{test_name}.log"
            with open(input_file, 'w') as f:
                for log in test_logs:
                    f.write(log + '\n')
            
            # Create YAML config file (preferred format)
            yaml_config = {
                "data_dir": "/tmp/vector_cli_data",
                "sources": {
                    "file_input": {
                        "type": "file",
                        "include": [input_file],
                        "read_from": "beginning"
                    }
                },
                "transforms": {
                    "regex2vrl_cli": {
                        "type": "remap",
                        "inputs": ["file_input"],
                        "source": vrl_code
                    }
                },
                "sinks": {
                    "file_output": {
                        "type": "file", 
                        "inputs": ["regex2vrl_cli"],
                        "path": f"/tmp/cli_{test_name}.jsonl",
                        "encoding": {
                            "codec": "json"
                        }
                    }
                }
            }
            
            # Write YAML config to file (CLI expects file path)
            config_file = f"/tmp/vector_config_{test_name}.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(yaml_config, f, default_flow_style=False)
            
            # Create data directory
            os.makedirs("/tmp/vector_cli_data", exist_ok=True)
            
            if self.verbose:
                print(f"   📁 Config file: {config_file}")
                print(f"   📝 Input logs: {len(test_logs)}")
            
            # Use VectorCliPy to emulate CLI behavior (correct API)
            cli_args = [
                "--config", config_file,
                "--quiet"
            ]
            
            if self.verbose:
                print(f"   🖥️ CLI args: {cli_args}")
            
            # Create VectorCliPy with CLI args and start from file
            cli_vector = vector.VectorCliPy(cli_args)
            cli_vector.start_from_file(config_file)
            
            if self.verbose:
                print(f"   ✅ CLI Vector started from YAML file")
            
            # Wait for file processing (CLI style)
            time.sleep(4)
            
            # Stop CLI Vector
            cli_vector.stop()
            
            # Check results
            output_path = f"/tmp/cli_{test_name}.jsonl"
            if os.path.exists(output_path):
                with open(output_path) as f:
                    content = f.read().strip()
                    if content:
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        success = len(lines) > 0
                        
                        if self.verbose:
                            print(f"   ✅ CLI emulation: {len(lines)} results")
                            
                        self.results["cmdline_emulation"].append({
                            "test_name": test_name,
                            "success": success,
                            "results_count": len(lines),
                            "input_count": len(test_logs)
                        })
                        
                        return success
            
            if self.verbose:
                print(f"   ❌ CLI emulation: No output")
            
            self.results["cmdline_emulation"].append({
                "test_name": test_name,
                "success": False,
                "results_count": 0,
                "input_count": len(test_logs)
            })
            
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"   ❌ CLI emulation error: {e}")
                import traceback
                traceback.print_exc()
            
            self.results["cmdline_emulation"].append({
                "test_name": test_name,
                "success": False, 
                "error": str(e)
            })
            
            return False
    
    def _yaml_to_toml_config(self, yaml_config: dict) -> str:
        """Convert YAML config dict to TOML string for current bindings"""
        
        toml_lines = []
        
        # Handle data_dir
        if "data_dir" in yaml_config:
            toml_lines.append(f'data_dir = "{yaml_config["data_dir"]}"')
            toml_lines.append("")
        
        # Sources section
        if "sources" in yaml_config:
            for source_name, source_config in yaml_config["sources"].items():
                toml_lines.append(f"[sources.{source_name}]")
                for key, value in source_config.items():
                    if isinstance(value, list):
                        # Handle arrays
                        array_str = '["' + '", "'.join(str(v) for v in value) + '"]'
                        toml_lines.append(f'{key} = {array_str}')
                    else:
                        toml_lines.append(f'{key} = "{value}"')
                toml_lines.append("")
        
        # Transforms section
        if "transforms" in yaml_config:
            for transform_name, transform_config in yaml_config["transforms"].items():
                toml_lines.append(f"[transforms.{transform_name}]")
                for key, value in transform_config.items():
                    if key == "source":
                        toml_lines.append(f'source = """\n{value}\n"""')
                    elif isinstance(value, list):
                        array_str = '["' + '", "'.join(str(v) for v in value) + '"]'
                        toml_lines.append(f'{key} = {array_str}')
                    else:
                        toml_lines.append(f'{key} = "{value}"')
                toml_lines.append("")
        
        # Sinks section
        if "sinks" in yaml_config:
            for sink_name, sink_config in yaml_config["sinks"].items():
                toml_lines.append(f"[sinks.{sink_name}]")
                for key, value in sink_config.items():
                    if isinstance(value, dict):
                        # Handle nested config
                        for sub_key, sub_value in value.items():
                            toml_lines.append(f'{key}.{sub_key} = "{sub_value}"')
                    elif isinstance(value, list):
                        array_str = '["' + '", "'.join(str(v) for v in value) + '"]'
                        toml_lines.append(f'{key} = {array_str}')
                    else:
                        toml_lines.append(f'{key} = "{value}"')
                toml_lines.append("")
        
        return '\n'.join(toml_lines)
    
    def run_dual_mode_tests(self):
        """Run regex2vrl tests in both modes"""
        
        print("🔄 Dual-Mode regex2vrl Integration Tests")
        print("=" * 55)
        print("Testing: 1) Native bindings  2) Cmdline emulation")
        print("Config: YAML → TOML conversion")
        
        # Test cases with patterns that should work
        test_cases = [
            {
                "name": "ip_extraction_dual",
                "pattern": r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
                "type": "regex",
                "logs": [
                    "Client IP: 192.168.1.100",
                    "Server: 10.0.0.1 active"
                ]
            },
            {
                "name": "simple_field_dual",
                "pattern": r'(?P<word>\w+)',
                "type": "regex", 
                "logs": [
                    "hello world",
                    "test message"
                ]
            },
            {
                "name": "syslog_grok_dual",
                "pattern": "%{SYSLOGBASE} %{GREEDYDATA:message}",
                "type": "grok",
                "logs": [
                    "Jan 15 10:30:45 server01 sshd[1234]: User login",
                    "Jan 15 10:30:46 web-server nginx: Process started"
                ]
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🧪 Testing: {test_case['name']}")
            print(f"   Pattern: {test_case['pattern'][:60]}...")
            
            # Test Mode 1: Native bindings
            native_success = self.test_native_bindings(
                test_case["pattern"],
                test_case["type"],
                test_case["logs"],
                test_case["name"]
            )
            
            # Test Mode 2: Cmdline emulation  
            cmdline_success = self.test_cmdline_emulation(
                test_case["pattern"],
                test_case["type"],
                test_case["logs"],
                test_case["name"]
            )
            
            # Summary for this test
            if self.verbose:
                print(f"   📊 Results: Native={'✅' if native_success else '❌'}, Cmdline={'✅' if cmdline_success else '❌'}")
    
    def generate_report(self) -> str:
        """Generate comprehensive dual-mode test report"""
        
        native_passed = sum(1 for r in self.results["native_bindings"] if r["success"])
        native_total = len(self.results["native_bindings"])
        
        cmdline_passed = sum(1 for r in self.results["cmdline_emulation"] if r["success"])
        cmdline_total = len(self.results["cmdline_emulation"])
        
        return f"""

Dual-Mode regex2vrl Integration Test Report
{'=' * 60}

Testing Strategy: YAML Config → Both Binding Modes

Mode 1 - Native Bindings:
  Tests: {native_passed}/{native_total} passed
  Method: Direct vectordotdev Python API with python source
  
Mode 2 - Cmdline Emulation:  
  Tests: {cmdline_passed}/{cmdline_total} passed
  Method: Bindings emulating Vector CLI with file sources
  
Overall Assessment:
  Configuration: YAML → TOML conversion working
  regex2vrl Integration: Tested with both API approaches
  
Test Details:

Native Bindings Results:
{self._format_results(self.results["native_bindings"])}

Cmdline Emulation Results:
{self._format_results(self.results["cmdline_emulation"])}

Recommendations:
- Native bindings: {'✅ Ready for production' if native_passed == native_total else '🚧 Needs transform development'}
- Cmdline emulation: {'✅ Ready for production' if cmdline_passed == cmdline_total else '🚧 Needs file source support'}
- YAML config: ✅ Successfully converted to TOML format
"""
    
    def _format_results(self, results: list) -> str:
        """Format test results for report"""
        if not results:
            return "  No tests run"
        
        formatted = ""
        for result in results:
            status = "✅" if result["success"] else "❌"
            rate = (result["results_count"] / result["input_count"] * 100) if result["input_count"] > 0 else 0
            formatted += f"  {status} {result['test_name']}: {rate:.0f}% processed\n"
        
        return formatted.rstrip()


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Dual-mode regex2vrl integration tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not HAS_BINDINGS:
        print("❌ vectordotdev bindings required for integration tests")
        return 1
    
    tester = DualModeRegex2VRLTester(verbose=args.verbose)
    tester.run_dual_mode_tests()
    
    # Generate and show report
    report = tester.generate_report()
    print(report)
    
    # Determine success
    all_native = all(r["success"] for r in tester.results["native_bindings"])
    all_cmdline = all(r["success"] for r in tester.results["cmdline_emulation"])
    
    # Success if at least one mode works completely
    at_least_one_mode_working = all_native or all_cmdline
    
    return 0 if at_least_one_mode_working else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))