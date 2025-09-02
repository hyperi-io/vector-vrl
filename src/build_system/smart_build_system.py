#!/usr/bin/env python3
"""
Smart Vector Build System - Python Implementation
Intelligent build with progressive fallback and comprehensive verification
"""

import os
import re
import sys
import time
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Dict, NamedTuple
from dataclasses import dataclass
from enum import Enum

import requests
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from dynaconf import Dynaconf
from auto_fix_system import apply_smart_fixes, get_build_recommendations, AutoFixType
from lfs_cache_manager import LFSCacheManager, should_use_cache

# Load configuration following corporate policy
settings = Dynaconf(
    envvar_prefix="PYVECTOR", 
    settings_files=['src/build_system/config/*.yaml'],
    load_dotenv=True
)

console = Console()

class ErrorType(Enum):
    UPSTREAM_COMPILE = "upstream_compile"
    VECTOR_CORE_FAILURE = "vector_core_failure"
    BINDING_FAILURE = "binding_failure"
    BUILD_FAILURE = "build_failure"
    IMPORT_FAILURE = "import_failure"
    OUR_CODE_FAILURE = "our_code_failure"
    UNKNOWN_FAILURE = "unknown_failure"

@dataclass
class BuildResult:
    success: bool
    version: str
    build_time: float
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    verification_results: Optional[Dict] = None

class VectorBuildSystem:
    """Smart Vector build system with progressive fallback"""
    
    # Known upstream error patterns (multiline-aware)
    UPSTREAM_PATTERNS = [
        r"cannot find function.*proto_to_value.*module.*vrl.*protobuf",
        r"cannot find function.*get_message_descriptor.*module.*vrl.*protobuf", 
        r"cannot find function.*encode_message.*module.*vrl.*protobuf",
        r"cannot find function.*module.*vrl::",
        r"protobuf.*not found.*vrl",
        r"failed to select a version.*indexmap",
        r"krb5.*make failed",
        r"gssrpc.*error:",
        r"Unexpected type.*darling",
        r"missing lifetime specifier",
        r"conflicting implementations",
        r"error: could not compile.*codecs.*due to.*previous error",
        r"two different versions of crate.*toml.*are being used",
        r"arguments to this function are incorrect.*merge_into_table",
        r"expected.*Map.*found a different.*Map.*Value",
        r"note: two different versions of crate.*are being used",
        # More specific patterns for our current errors
        r"vrl::protobuf::proto_to_value.*not found",
        r"codecs.*lib.*due to.*previous errors",
    ]
    
    def __init__(self, max_fallbacks: Optional[int] = None):
        # Use configuration policy: CLI → ENV → config file → code default
        self.max_fallbacks = max_fallbacks or settings.get('build_system.max_fallbacks', 3)
        self.project_dir = Path(__file__).parent.parent
        self.cargo_toml = self.project_dir / "Cargo.toml"
        
        # Configurable temp directory (corporate requirement)
        temp_dir = settings.get('paths.temp_dir', '.tmp')
        self.tmp_dir = self.project_dir / temp_dir
        self.tmp_dir.mkdir(exist_ok=True)
        
        # Load configuration values
        self.build_timeout = settings.get('build_system.build_timeout_minutes', 30) * 60
        self.stall_timeout = settings.get('build_system.stall_timeout_minutes', 5) * 60
        self.enable_auto_fixes = settings.get('fixes.enable_auto_fixes', True)
        self.max_fix_attempts = settings.get('fixes.max_fix_attempts', 2)
        
        # Vector feature profile configuration (CLI/ENV override)
        env_profile = os.environ.get('PYVECTOR_VECTOR_PROFILE')
        self.vector_profile = env_profile or settings.get('vector.profile', 'safe')
        self.vector_features = self._get_vector_features_for_profile()
        
        # LFS cache manager
        self.cache_manager = LFSCacheManager(self.project_dir) if should_use_cache(self.project_dir) else None
        
    def _get_vector_features_for_profile(self) -> List[str]:
        """Get Vector features based on configured profile"""
        profile_key = f"vector.{self.vector_profile}_features"
        features = settings.get(profile_key, settings.get('vector.safe_features', []))
        console.print(f"[INFO] Using Vector profile '{self.vector_profile}' with {len(features)} features")
        return features
        
    def get_vector_versions(self, count: int = 5) -> List[str]:
        """Get latest stable Vector versions from GitHub"""
        try:
            console.print("[INFO] Discovering Vector versions from GitHub...")
            
            # Use git ls-remote for reliability
            result = subprocess.run([
                "git", "ls-remote", "--tags", "--refs", "--sort=-version:refname",
                "https://github.com/vectordotdev/vector.git"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                console.print(f"[WARN] Git command failed: {result.stderr}")
                return []
                
            versions = []
            for line in result.stdout.strip().split('\n'):
                if 'refs/tags/' in line:
                    tag = line.split('refs/tags/')[-1]
                    # Only stable versions (no pre-release markers)
                    if (tag.startswith('v') and 
                        not any(marker in tag for marker in ['-', 'rc', 'beta', 'alpha']) and
                        tag.count('.') >= 1):
                        versions.append(tag)
                        if len(versions) >= count:
                            break
                            
            console.print(f"[INFO] Found versions: {versions}")
            return versions
            
        except Exception as e:
            console.print(f"[ERROR] Failed to get Vector versions: {e}")
            return []
    
    def analyze_error_type(self, build_log: str, verification_output: str = "") -> Tuple[ErrorType, str]:
        """Analyze build failure and categorize error type"""
        
        # Check for upstream compilation errors first  
        for pattern in self.UPSTREAM_PATTERNS:
            if re.search(pattern, build_log, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                return ErrorType.UPSTREAM_COMPILE, f"Pattern: {pattern}"
        
        # Check verification-specific failures
        if "FAILURE_TYPE:CONFIG_PARSING" in verification_output:
            return ErrorType.VECTOR_CORE_FAILURE, "Vector config parsing failed"
        elif "FAILURE_TYPE:CLI_OPTIONS" in verification_output:
            return ErrorType.OUR_CODE_FAILURE, "CLI options creation failed"
        elif "FAILURE_TYPE:CONFIG_VALIDATION" in verification_output:
            return ErrorType.BINDING_FAILURE, "Config validation binding failed"
        
        # Check for build artifacts
        if "No wheel files found" in verification_output:
            return ErrorType.BUILD_FAILURE, "Wheel creation failed"
            
        # Check for import failures
        if "Module import failed" in verification_output:
            return ErrorType.IMPORT_FAILURE, "Python module import failed"
            
        return ErrorType.UNKNOWN_FAILURE, "Unclassified error"
    
    def get_failure_summary(self, error_type: ErrorType, error_message: str, version: str) -> str:
        """Generate concise one-line failure summary"""
        summaries = {
            ErrorType.UPSTREAM_COMPILE: f"Vector {version} → VRL/protobuf API incompatibility",
            ErrorType.VECTOR_CORE_FAILURE: f"Vector {version} → Core functionality broken",
            ErrorType.BINDING_FAILURE: f"Vector {version} → PyO3 binding issues", 
            ErrorType.BUILD_FAILURE: f"Vector {version} → Build system failure",
            ErrorType.IMPORT_FAILURE: f"Vector {version} → Module import failure",
            ErrorType.OUR_CODE_FAILURE: f"Vector {version} → Our code has bugs",
            ErrorType.UNKNOWN_FAILURE: f"Vector {version} → Unknown build failure"
        }
        
        # Add specific details based on error patterns
        if "proto_to_value" in error_message:
            return f"Vector {version} → VRL protobuf API missing functions (upstream)"
        elif "toml.*are being used" in error_message:
            return f"Vector {version} → TOML version conflicts (upstream)"
        elif "krb5.*make failed" in error_message:
            return f"Vector {version} → System library compilation failure (upstream)"
        elif "indexmap" in error_message:
            return f"Vector {version} → Dependency version conflicts (upstream)"
        
        return summaries.get(error_type, f"Vector {version} → Build failed")
    
    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if we should try an older Vector version"""
        return error_type != ErrorType.OUR_CODE_FAILURE
    
    def update_cargo_toml_version(self, version: str) -> bool:
        """Update Cargo.toml with specific Vector version"""
        try:
            with open(self.cargo_toml, 'r') as f:
                content = f.read()
            
            # Update all Vector git dependencies to use the specified tag
            # First remove any existing tag specifications to avoid duplicates
            temp_content = re.sub(r', tag = "v[0-9]+\.[0-9]+\.[0-9]+"', '', content)
            
            # Then add the new tag and update features based on profile
            if self.vector_profile == 'minimal':
                features = '["transforms-logs", "transforms-metrics", "sinks-logs", "sinks-metrics"]'
            elif self.vector_profile == 'full':
                features = '["default"]'
            else:  # safe profile
                features = '["api", "api-client", "enrichment-tables", "sinks", "sources", "transforms", "unix", "secrets"]'
            
            # Update Vector dependency with version and features
            pattern = r'vector = \{[^}]+\}'
            replacement = f'vector = {{ git = "https://github.com/vectordotdev/vector.git", tag = "{version}", default-features = false, features = {features} }}'
            new_content = re.sub(pattern, replacement, temp_content)
            
            with open(self.cargo_toml, 'w') as f:
                f.write(new_content)
                
            console.print(f"[INFO] Updated Cargo.toml to Vector {version}")
            return True
            
        except Exception as e:
            console.print(f"[ERROR] Failed to update Cargo.toml: {e}")
            return False
    
    def run_build_with_monitoring(self, version: str) -> BuildResult:
        """Run build with intelligent progress monitoring"""
        console.print(f"[INFO] Starting monitored build for Vector {version}")
        
        start_time = time.time()
        build_log_file = self.tmp_dir / f'build_vector_{version}_{int(time.time())}.log'
        build_log_file.touch()
        
        # Build environment
        env = os.environ.copy()
        env.update({
            'SKIP_VECTOR_UPDATE': '1',
            'RUSTFLAGS': '-C linker=gcc',
            'PYO3_USE_ABI3_FORWARD_COMPATIBILITY': '1'
        })
        
        try:
            with open(build_log_file, 'w') as log_file:
                # Start build process
                process = subprocess.Popen([
                    'uv', 'run', 'maturin', 'develop'
                ], stdout=log_file, stderr=subprocess.STDOUT, 
                   text=True, env=env, cwd=self.project_dir)
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TimeElapsedColumn(),
                    console=console
                ) as progress:
                    
                    build_task = progress.add_task(f"Building Vector {version}...", total=None)
                    last_log_size = 0
                    last_activity = time.time()
                    
                    # Monitor build progress
                    while True:
                        # Check if process finished
                        if process.poll() is not None:
                            break
                        
                        # Check log file growth
                        try:
                            current_log_size = build_log_file.stat().st_size
                            if current_log_size > last_log_size:
                                last_activity = time.time()
                                last_log_size = current_log_size
                                
                                # Update progress with recent activity
                                with open(build_log_file, 'r') as f:
                                    f.seek(max(0, current_log_size - 200))  # Read last 200 chars
                                    recent_output = f.read().strip()
                                    for line in recent_output.split('\n')[-3:]:  # Last 3 lines
                                        if any(keyword in line for keyword in ['Compiling', 'Downloading', 'Building']):
                                            desc = line.strip()[:60]
                                            progress.update(build_task, description=f"{desc}...")
                                            break
                        except Exception:
                            pass  # Ignore file read errors
                        
                        # Check for stall (configurable timeout)
                        if time.time() - last_activity > self.stall_timeout:
                            console.print(f"[WARN] Build stalled - no output for {self.stall_timeout//60} minutes")
                            process.terminate()
                            break
                        
                        # Absolute timeout (configurable)
                        if time.time() - start_time > self.build_timeout:
                            console.print(f"[WARN] Build exceeded {self.build_timeout//60} minute limit")
                            process.terminate()
                            break
                        
                        time.sleep(2)  # Check every 2 seconds
                    
                    # Get final process result
                    return_code = process.wait()
                    build_time = time.time() - start_time
                    
                    progress.update(build_task, description=f"Build completed in {build_time:.1f}s")
        
        finally:
            pass  # Log file is already closed
        
        # Analyze build result
        with open(build_log_file, 'r') as f:
            build_log = f.read()
        
        # Check for build success indicators
        build_succeeded = (return_code == 0 and 
                          not re.search(r"error: could not compile|💥 maturin failed|returned non-zero exit status", build_log))
        
        if build_succeeded:
            # Run comprehensive verification
            verification_results = self.run_verification_tests(version)
            if verification_results['success']:
                return BuildResult(
                    success=True,
                    version=version,
                    build_time=build_time,
                    verification_results=verification_results
                )
            else:
                error_type, error_msg = self.analyze_error_type(build_log, str(verification_results))
                return BuildResult(
                    success=False,
                    version=version, 
                    build_time=build_time,
                    error_type=error_type,
                    error_message=error_msg,
                    verification_results=verification_results
                )
        else:
            console.print(f"[DEBUG] Build log length: {len(build_log)} chars")
            console.print(f"[DEBUG] Log contains proto_to_value: {'proto_to_value' in build_log}")
            error_type, error_msg = self.analyze_error_type(build_log, "")
            console.print(f"[DEBUG] Error analysis result: {error_type.value} - {error_msg}")
            return BuildResult(
                success=False,
                version=version,
                build_time=build_time,
                error_type=error_type,
                error_message=error_msg
            )
    
    def run_verification_tests(self, version: str) -> Dict:
        """Run comprehensive verification tests"""
        console.print("[INFO] Running comprehensive verification tests...")
        
        results = {
            'success': True,
            'tests': {},
            'details': []
        }
        
        # Test 1: Check wheel files exist
        wheels_dir = self.project_dir / "target" / "wheels"
        if not wheels_dir.exists() or not list(wheels_dir.glob("*.whl")):
            results['tests']['wheel_creation'] = False
            results['details'].append("No wheel files found")
            results['success'] = False
        else:
            results['tests']['wheel_creation'] = True
            
        # Test 2: Module import and API availability
        import_test = self._test_module_import()
        results['tests']['module_import'] = import_test['success']
        results['details'].extend(import_test['details'])
        if not import_test['success']:
            results['success'] = False
            
        # Test 3: Vector core functionality
        if results['tests']['module_import']:
            core_test = self._test_vector_functionality()
            results['tests']['vector_core'] = core_test['success']
            results['details'].extend(core_test['details'])
            if not core_test['success']:
                results['success'] = False
        
        return results
    
    def _test_module_import(self) -> Dict:
        """Test module import and API availability"""
        test_script = '''
import pyvector
import sys

# Check main classes exist
classes = ['Vector', 'VectorCli', 'VectorCliOptions']
missing_classes = []
for cls in classes:
    if hasattr(pyvector, cls):
        print(f"[OK] {cls} class available")
    else:
        print(f"[FAIL] {cls} class missing")
        missing_classes.append(cls)

# Check functions exist  
functions = ['vector_from_cli_args', 'parse_cli_args', 'validate_config_file', 'check_config_syntax']
missing_functions = []
for func in functions:
    if hasattr(pyvector, func):
        print(f"[OK] {func} function available")
    else:
        print(f"[FAIL] {func} function missing")
        missing_functions.append(func)

if missing_classes or missing_functions:
    print("FAILURE_TYPE:API_MISSING")
    sys.exit(1)
else:
    print("SUCCESS_TYPE:API_COMPLETE")
'''
        
        return self._run_python_test(test_script, "Module Import")
    
    def _test_vector_functionality(self) -> Dict:
        """Test Vector core functionality"""
        test_script = '''
import pyvector
import sys

# Test 1: Simple config parsing
config = """
[sources.test]
type = "file"
include = ["/tmp/nonexistent.log"]

[sinks.test] 
type = "blackhole"
inputs = ["test"]
"""

try:
    vector = pyvector.Vector(config)
    print("[OK] Vector config parsing successful")
except Exception as e:
    print(f"[FAIL] Vector config parsing failed: {e}")
    print("FAILURE_TYPE:CONFIG_PARSING")
    sys.exit(1)

# Test 2: CLI options
try:
    cli_opts = pyvector.VectorCliOptions()
    print("[OK] VectorCliOptions creation successful")
except Exception as e:
    print(f"[FAIL] VectorCliOptions creation failed: {e}")
    print("FAILURE_TYPE:CLI_OPTIONS") 
    sys.exit(1)

# Test 3: Config validation
try:
    result = pyvector.validate_config_file('/dev/null')
    print("[OK] Config validation function works")
except Exception as e:
    print(f"[FAIL] Config validation failed: {e}")
    print("FAILURE_TYPE:CONFIG_VALIDATION")
    sys.exit(1)

print("SUCCESS_TYPE:FULL_FUNCTIONALITY")
'''
        
        return self._run_python_test(test_script, "Vector Functionality")
    
    def _run_python_test(self, script: str, test_name: str) -> Dict:
        """Run a Python test script and analyze results"""
        try:
            env = os.environ.copy()
            env.update({
                'RUSTFLAGS': '-C linker=gcc',
                'PYO3_USE_ABI3_FORWARD_COMPATIBILITY': '1'
            })
            
            result = subprocess.run([
                'build/.venv/bin/python', '-m', 'uv', 'run', 'python', '-c', script
            ], capture_output=True, text=True, timeout=30, env=env, cwd=self.project_dir)
            
            success = result.returncode == 0 and "SUCCESS_TYPE:" in result.stdout
            details = result.stdout.strip().split('\n') if result.stdout else []
            
            if result.stderr:
                details.extend([f"STDERR: {line}" for line in result.stderr.strip().split('\n')])
            
            return {
                'success': success,
                'details': details,
                'output': result.stdout,
                'error': result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'details': [f"{test_name} test timed out"],
                'output': '',
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'details': [f"{test_name} test failed: {e}"],
                'output': '',
                'error': str(e)
            }
    
    def backup_cargo_toml(self) -> str:
        """Backup Cargo.toml and return backup path"""
        backup_path = f"{self.cargo_toml}.backup"
        shutil.copy2(self.cargo_toml, backup_path)
        return backup_path
    
    def restore_cargo_toml(self, backup_path: str):
        """Restore Cargo.toml from backup"""
        if os.path.exists(backup_path):
            shutil.move(backup_path, self.cargo_toml)
    
    def save_build_info(self, result: BuildResult):
        """Save build information for caching"""
        build_info = {
            'vector_version': result.version,
            'build_date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'build_success': result.success,
            'build_time': result.build_time,
            'error_type': result.error_type.value if result.error_type else None,
            'error_message': result.error_message,
            'verification_results': result.verification_results
        }
        
        with open(self.project_dir / '.vector-build-info', 'w') as f:
            json.dump(build_info, f, indent=2)
    
    def smart_build(self) -> BuildResult:
        """Main smart build function with progressive fallback"""
        console.print(Panel.fit(
            "[bold blue]Smart Vector Build System[/bold blue]\n"
            "Intelligent build with progressive fallback", 
            border_style="blue"
        ))
        
        versions = self.get_vector_versions(self.max_fallbacks + 2)
        if not versions:
            return BuildResult(False, "unknown", 0, ErrorType.BUILD_FAILURE, "No versions discovered")
        
        console.print(f"[INFO] Testing versions: {versions[:self.max_fallbacks + 1]}")
        
        # Backup original Cargo.toml
        backup_path = self.backup_cargo_toml()
        
        try:
            for attempt, version in enumerate(versions):
                if attempt >= self.max_fallbacks + 1:
                    console.print(f"[WARN] Maximum fallback attempts ({self.max_fallbacks}) reached")
                    break
                
                console.print(f"\n[INFO] Attempt {attempt + 1}: Testing Vector {version}")
                
                # Update version in Cargo.toml
                if not self.update_cargo_toml_version(version):
                    continue
                
                # Try to restore cache first
                if self.cache_manager:
                    cache_key = self.cache_manager.find_compatible_cache(version)
                    if cache_key:
                        console.print(f"[INFO] Attempting to restore cache for Vector {version}")
                        if self.cache_manager.restore_cache_archive(cache_key, version):
                            console.print("[INFO] Build cache restored - faster build expected")
                
                # Clean specific build artifacts (but preserve cache)
                if (self.project_dir / "Cargo.lock").exists():
                    os.remove(self.project_dir / "Cargo.lock")
                
                # Run build with monitoring
                result = self.run_build_with_monitoring(version)
                
                if result.success:
                    console.print(f"[bold green]✓ Build successful with Vector {version}![/bold green]")
                    self.save_build_info(result)
                    
                    # Create LFS cache for successful build
                    if self.cache_manager:
                        console.print("[INFO] Creating LFS cache for successful build...")
                        cache_key = self.cache_manager.get_cargo_cache_key()
                        self.cache_manager.create_cache_archive(cache_key, version)
                    
                    return result
                else:
                    # Generate concise failure summary
                    failure_summary = self.get_failure_summary(result.error_type, result.error_message, version)
                    console.print(f"[bold red]✗ {failure_summary}[/bold red]")
                    
                    # Try to apply automatic fixes for known issues
                    console.print("[INFO] Attempting automatic fixes...")
                    
                    # Find the most recent log file for this version
                    log_files = list(self.tmp_dir.glob(f'build_vector_{version}_*.log'))
                    if log_files:
                        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                        with open(latest_log, 'r') as f:
                            build_log_for_fixes = f.read()
                    else:
                        build_log_for_fixes = ""
                    
                    fixes_applied = apply_smart_fixes(self.project_dir, build_log_for_fixes, version)
                    
                    if fixes_applied:
                        console.print(f"[INFO] Applied fixes: {[fix.value for fix in fixes_applied]}")
                        console.print("[INFO] Retrying build with fixes...")
                        
                        # Retry build once with fixes
                        retry_result = self.run_build_with_monitoring(f"{version}-fixed")
                        if retry_result.success:
                            console.print(f"[bold green]✓ Build successful after auto-fixes![/bold green]")
                            self.save_build_info(retry_result)
                            return retry_result
                        else:
                            console.print("[WARN] Auto-fixes didn't resolve the issue")
                    
                    if not self.should_retry(result.error_type):
                        console.print("[CRIT] Our code has issues - stopping fallback")
                        return result
                    else:
                        next_version = versions[attempt + 1] if attempt + 1 < len(versions) else "none"
                        console.print(f"[INFO] Upstream issue → Falling back to Vector {next_version}")
        
        finally:
            self.restore_cargo_toml(backup_path)
        
        # All versions failed
        return BuildResult(False, "all_failed", 0, ErrorType.BUILD_FAILURE, 
                          f"All {self.max_fallbacks + 1} versions failed")

@click.command()
@click.option('--max-fallbacks', default=None, type=int, help='Maximum number of fallback versions to try')
@click.option('--force-update', is_flag=True, help='Force version update even if cached')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--profile', help='Vector feature profile (minimal/safe/full)')
def main(max_fallbacks: Optional[int], force_update: bool, verbose: bool, profile: Optional[str]):
    """Smart Vector build system with progressive fallback"""
    
    if verbose:
        console.print("[DEBUG] Verbose mode enabled")
    
    # Check for cached build info
    build_info_file = Path(__file__).parent.parent / '.vector-build-info'
    if build_info_file.exists() and not force_update:
        try:
            with open(build_info_file, 'r') as f:
                cached_info = json.load(f)
            
            if cached_info.get('build_success'):
                console.print(f"[INFO] Using cached Vector version: {cached_info['vector_version']}")
                console.print("[INFO] Use --force-update to check for newer versions")
                return
        except Exception:
            pass  # Ignore cache read errors
    
    # Set profile override if provided via CLI
    if profile:
        os.environ['PYVECTOR_VECTOR_PROFILE'] = profile
    
    # Run smart build
    build_system = VectorBuildSystem(max_fallbacks)
    result = build_system.smart_build()
    
    # Display results
    if result.success:
        console.print(Panel.fit(
            f"[bold green]✓ Build Successful![/bold green]\n"
            f"Vector Version: {result.version}\n"
            f"Build Time: {result.build_time:.1f}s",
            border_style="green"
        ))
        sys.exit(0)
    else:
        console.print(Panel.fit(
            f"[bold red]✗ Build Failed[/bold red]\n"
            f"Error Type: {result.error_type.value if result.error_type else 'unknown'}\n"
            f"Error: {result.error_message}",
            border_style="red"  
        ))
        sys.exit(1)

if __name__ == "__main__":
    main()