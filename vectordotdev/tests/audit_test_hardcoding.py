#!/usr/bin/env python3
"""
Audit script to find hardcoded VRL and test data in test files
Ensures compliance with external data file architecture
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


def audit_test_file(file_path: Path) -> Dict[str, List[str]]:
    """
    Audit a test file for hardcoded content
    Returns dict with violation types and line numbers
    """
    violations = {
        "hardcoded_vrl": [],
        "hardcoded_json": [],
        "hardcoded_logs": [],
        "hardcoded_configs": []
    }
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        return {"error": [str(e)]}
    
    for i, line in enumerate(lines, 1):
        line_content = line.strip()
        
        # Check for hardcoded VRL (multi-line strings with VRL functions)
        if re.search(r'("""|\'\'\').*?(parse_json|parse_syslog|parse_regex|to_int|split|contains)', line_content):
            violations["hardcoded_vrl"].append(f"Line {i}: {line_content[:80]}...")
        
        # Check for hardcoded JSON in strings
        if re.search(r'["\'][^"\']*\{[^}]*"level"[^}]*\}[^"\']*["\']', line_content):
            violations["hardcoded_json"].append(f"Line {i}: {line_content[:80]}...")
        
        # Check for hardcoded log samples
        if re.search(r'(apache_logs|nginx_logs|k8s_logs|json_logs|syslog_logs)\s*=\s*\[', line_content):
            violations["hardcoded_logs"].append(f"Line {i}: {line_content[:80]}...")
        
        # Check for hardcoded configurations
        if re.search(r'(config|pattern)\s*=\s*\{.*"type".*"remap"', line_content):
            violations["hardcoded_configs"].append(f"Line {i}: {line_content[:80]}...")
    
    # Remove empty violation categories
    return {k: v for k, v in violations.items() if v}


def audit_all_tests(tests_dir: Path) -> Dict[str, Dict[str, List[str]]]:
    """Audit all test files in directory tree"""
    results = {}
    
    for test_file in tests_dir.rglob("test_*.py"):
        violations = audit_test_file(test_file)
        if violations:
            relative_path = test_file.relative_to(tests_dir)
            results[str(relative_path)] = violations
    
    return results


def generate_audit_report(audit_results: Dict[str, Dict[str, List[str]]]) -> str:
    """Generate comprehensive audit report"""
    report = []
    report.append("🔍 TEST HARDCODING AUDIT REPORT")
    report.append("=" * 60)
    
    total_files = len(audit_results)
    total_violations = sum(len(violations) for file_violations in audit_results.values() 
                          for violations in file_violations.values())
    
    report.append(f"📊 SUMMARY:")
    report.append(f"   Files with violations: {total_files}")
    report.append(f"   Total violations: {total_violations}")
    
    if total_files == 0:
        report.append("✅ All test files are clean - no hardcoded content found!")
        return "\n".join(report)
    
    report.append(f"\n❌ VIOLATIONS FOUND:")
    report.append("=" * 60)
    
    for file_path, file_violations in audit_results.items():
        report.append(f"\n📁 {file_path}")
        report.append("-" * 40)
        
        for violation_type, violations in file_violations.items():
            report.append(f"  🚨 {violation_type.upper().replace('_', ' ')}: {len(violations)} violations")
            for violation in violations[:3]:  # Show first 3 violations
                report.append(f"     {violation}")
            if len(violations) > 3:
                report.append(f"     ... and {len(violations) - 3} more")
    
    report.append(f"\n💡 RECOMMENDATIONS:")
    report.append("=" * 60)
    report.append("1. Move hardcoded VRL to separate .vrl files")
    report.append("2. Move test data to separate .ndjson files")
    report.append("3. Move parameters to .yaml config files")
    report.append("4. Use TestDataLoader pattern for file loading")
    report.append("5. Follow test_native_vrl_executor_clean.py example")
    
    return "\n".join(report)


def fix_test_file(file_path: Path, dry_run: bool = True) -> List[str]:
    """
    Suggest fixes for a test file (or apply if not dry_run)
    Returns list of suggested fixes
    """
    fixes = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        return [f"Error reading file: {e}"]
    
    # Detect hardcoded VRL blocks
    vrl_blocks = re.findall(r'(vrl.*?=.*?["\'\"\'\"])(.*?)([\"\'\"\'\"])', content, re.DOTALL)
    for i, (prefix, vrl_content, suffix) in enumerate(vrl_blocks):
        if any(func in vrl_content for func in ['parse_json', 'parse_syslog', 'parse_regex']):
            vrl_file_name = f"{file_path.stem}_{i}.vrl"
            fixes.append(f"Extract VRL block {i} to: {vrl_file_name}")
            
            if not dry_run:
                # Create VRL file
                vrl_path = file_path.parent / "test_data" / file_path.stem / vrl_file_name
                vrl_path.parent.mkdir(parents=True, exist_ok=True)
                with open(vrl_path, 'w') as vrl_file:
                    vrl_file.write(vrl_content.strip())
    
    # Detect hardcoded test data
    data_assignments = re.findall(r'(\w+_(?:logs|data))\s*=\s*\[(.*?)\]', content, re.DOTALL)
    for var_name, data_content in data_assignments:
        if len(data_content.strip()) > 100:  # Substantial hardcoded data
            ndjson_file_name = f"{file_path.stem}_{var_name}.ndjson"
            fixes.append(f"Extract {var_name} to: {ndjson_file_name}")
    
    return fixes


def main():
    """Run comprehensive test audit"""
    tests_dir = Path(__file__).parent
    
    print("🔍 Auditing vectordotdev test suite for hardcoded content...")
    print("=" * 60)
    
    # Perform audit
    audit_results = audit_all_tests(tests_dir)
    
    # Generate and display report
    report = generate_audit_report(audit_results)
    print(report)
    
    if not audit_results:
        print("\n🎉 Audit complete: All tests follow external data architecture!")
        return 0
    
    # Generate fix suggestions
    print(f"\n🔧 SUGGESTED FIXES:")
    print("=" * 60)
    
    for file_path_str in audit_results.keys():
        file_path = tests_dir / file_path_str
        fixes = fix_test_file(file_path, dry_run=True)
        
        if fixes:
            print(f"\n📁 {file_path_str}:")
            for fix in fixes:
                print(f"   🛠️  {fix}")
    
    print(f"\n📋 CLEAN ARCHITECTURE EXAMPLE:")
    print("✅ tests/unit/test_native_vrl_executor_clean.py")
    print("✅ tests/unit/test_data/native_vrl_executor/")
    
    return len(audit_results)  # Return number of files with violations


if __name__ == "__main__":
    exit_code = main()
    sys.exit(min(exit_code, 1))  # 0 if clean, 1 if violations found