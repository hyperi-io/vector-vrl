#!/usr/bin/env python3
"""
Main test runner for vectordotdev - organized by test type.

Test Structure:
- Unit Tests: Isolated component testing (subprocess Vector calls, VRL functions)
- Integration Tests: Component interaction testing (vectordotdev bindings)  
- E2E Tests: End-to-end production scenarios
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path


def run_unit_tests(verbose: bool = False, vector_binary: str = None):
    """Run unit tests"""
    print("🔧 Running Unit Tests")
    print("=" * 30)
    
    # VRL function unit tests
    print("\n📋 VRL Function Tests:")
    try:
        from unit.test_vrl_basic import test_vrl_expressions, test_vrl_functions_availability
        
        # Run VRL tests
        valid_count, total_count = test_vrl_expressions()
        functions_result = test_vrl_functions_availability()
        
        print(f"VRL Expressions: {valid_count}/{total_count} passed")
        print(f"VRL Functions: {'✅ Available' if functions_result else '❌ Not available'}")
        
    except ImportError as e:
        print(f"⏭️ VRL tests skipped: {e}")
    
    # Subprocess Vector unit tests  
    print("\n🔄 Vector Subprocess Unit Tests:")
    try:
        subprocess_args = ["python", str(Path(__file__).parent / "unit" / "test_vector_subprocess.py")]
        if verbose:
            subprocess_args.append("--verbose")
        if vector_binary:
            subprocess_args.extend(["--vector-binary", vector_binary])
            
        result = subprocess.run(subprocess_args, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Subprocess unit tests passed")
            if verbose:
                print(result.stdout)
        else:
            print("❌ Subprocess unit tests failed")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Subprocess tests error: {e}")
        return False
    
    return True


async def run_integration_tests(verbose: bool = False):
    """Run integration tests"""
    print("\n🔗 Running Integration Tests")
    print("=" * 35)
    
    try:
        # Import and run vectordotdev bindings integration tests
        integration_args = ["python", str(Path(__file__).parent / "integration" / "bindings.py")]
        if verbose:
            integration_args.append("--verbose")
        
        result = subprocess.run(integration_args, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Integration tests passed")
            if verbose:
                print(result.stdout)
            return True
        else:
            print("❌ Integration tests failed")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Integration tests error: {e}")
        return False


def run_e2e_tests(verbose: bool = False, vector_binary: str = None, test_filter: str = None):
    """Run end-to-end tests"""
    print("\n🚀 Running End-to-End Tests")
    print("=" * 32)
    
    try:
        # Run production patterns e2e test
        e2e_args = ["python", str(Path(__file__).parent / "e2e" / "production_patterns.py")]
        if verbose:
            e2e_args.append("--verbose")
        if vector_binary:
            e2e_args.extend(["--vector-binary", vector_binary])
        if test_filter:
            e2e_args.extend(["--filter", test_filter])
        
        result = subprocess.run(e2e_args, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ E2E tests passed")
            if verbose:
                print(result.stdout)
            return True
        else:
            print("❌ E2E tests failed") 
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ E2E tests error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description='Run vectordotdev tests by category',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Categories:
  unit        - Unit tests (subprocess Vector, VRL functions)
  integration - Integration tests (vectordotdev bindings)  
  e2e         - End-to-end tests (production patterns)
  all         - Run all test categories (default)

Examples:
  # Run all tests
  python run_tests.py
  
  # Run only unit tests
  python run_tests.py --category unit --verbose
  
  # Run with custom Vector binary
  python run_tests.py --vector-binary /path/to/vector
  
  # Run filtered e2e tests
  python run_tests.py --category e2e --filter apache
        """
    )
    
    parser.add_argument('--category', '-c', 
                       choices=['unit', 'integration', 'e2e', 'all'], 
                       default='all',
                       help='Test category to run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--vector-binary', help='Path to Vector binary')
    parser.add_argument('--filter', help='Filter tests by name (for e2e tests)')
    
    args = parser.parse_args()
    
    print("🧪 vectordotdev Test Suite")
    print("=" * 40)
    
    results = []
    
    # Run tests based on category
    if args.category in ['unit', 'all']:
        unit_result = run_unit_tests(args.verbose, args.vector_binary)
        results.append(('Unit', unit_result))
    
    if args.category in ['integration', 'all']:
        integration_result = await run_integration_tests(args.verbose)
        results.append(('Integration', integration_result))
    
    if args.category in ['e2e', 'all']:
        e2e_result = run_e2e_tests(args.verbose, args.vector_binary, args.filter)
        results.append(('E2E', e2e_result))
    
    # Summary
    print(f"\n📊 Test Summary")
    print("=" * 20)
    
    passed = 0
    failed = 0
    
    for test_type, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_type}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    total = passed + failed
    if total > 0:
        pass_rate = (passed / total) * 100
        print(f"\nOverall: {passed}/{total} categories passed ({pass_rate:.0f}%)")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))