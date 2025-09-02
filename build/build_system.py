#!/usr/bin/env python3
"""
Robust 3-Stage Build System for vectordotdev
Heartbeat-based monitoring without timeouts
"""

import os
import re
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum

try:
    from dynaconf import Dynaconf
    HAS_DYNACONF = True
except ImportError:
    HAS_DYNACONF = False

class BuildStage(Enum):
    VECTOR_CORE = "vector_core"
    VECTOR_BINDINGS = "vector_bindings" 
    PYTHON_BINDINGS = "python_bindings"

class ErrorType(Enum):
    UPSTREAM_COMPILE = "upstream_compile"
    VECTOR_CORE_FAILURE = "vector_core_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    PYTHON_FAILURE = "python_failure"
    OUR_CODE_FAILURE = "our_code_failure"

@dataclass
class StageResult:
    stage: BuildStage
    success: bool
    build_time: float
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None

@dataclass
class BuildResult:
    success: bool
    vector_version: str
    total_time: float
    stage_results: Dict[BuildStage, StageResult]

class RobustBuildSystem:
    """3-stage build with heartbeat monitoring"""
    
    UPSTREAM_PATTERNS = [
        r"cannot find function.*proto_to_value.*vrl.*protobuf",
        r"cannot find function.*get_message_descriptor.*vrl.*protobuf", 
        r"cannot find function.*encode_message.*vrl.*protobuf",
        r"error: could not compile.*codecs.*due to.*previous error",
        r"krb5.*make failed",
        r"make failed in lib",
        r"auth_none\.c.*too many arguments to function",
        r"thread 'main' panicked at.*krb5-src",
    ]
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        
        # Load configuration following policy: CLI → ENV → .env → config file → code default
        if HAS_DYNACONF:
            self.settings = Dynaconf(
                envvar_prefix="VECTORDOTDEV",
                settings_files=['build/config/default.yaml'],
                load_dotenv=True
            )
        else:
            # Fallback configuration object
            class FallbackConfig:
                def get(self, key, default):
                    return default
            self.settings = FallbackConfig()
        
        # Configure paths (configurable per policy)
        self.vector_dir = self.project_root / self.settings.get('paths.vector_dir', 'vector')
        self.vectordotdev_dir = self.project_root / self.settings.get('paths.python_dir', 'vectordotdev')
        temp_dir = self.settings.get('paths.temp_dir', '.tmp')
        self.tmp_dir = self.project_root / temp_dir
        self.tmp_dir.mkdir(exist_ok=True, parents=True)
        
        # Build configuration (ENV variables override config file)
        self.stall_timeout = self.settings.get('build_system.stall_timeout_minutes', 10) * 60
        self.max_fallbacks = self.settings.get('build_system.max_fallbacks', 2)
        self.verbose = (
            os.environ.get('VECTORDOTDEV_VERBOSE', '').lower() == 'true' or
            self.settings.get('build_system.enable_verbose', False)
        )
        
    def log(self, message: str):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")
    
    def get_vector_versions(self) -> List[str]:
        """Get Vector versions with git fallback"""
        try:
            result = subprocess.run([
                "git", "ls-remote", "--tags", "--refs", "--sort=-version:refname",
                "https://github.com/vectordotdev/vector.git"
            ], capture_output=True, text=True, timeout=30)
            
            versions = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'refs/tags/' in line:
                        tag = line.split('refs/tags/')[-1]
                        if (tag.startswith('v') and 
                            not any(m in tag for m in ['-', 'rc', 'beta']) and
                            tag.count('.') >= 1):
                            versions.append(tag)
                            if len(versions) >= 5:
                                break
            
            return versions or ['v0.48.0', 'v0.47.0', 'v0.46.1']
            
        except Exception:
            return ['v0.48.0', 'v0.47.0', 'v0.46.1']
    
    def analyze_error(self, build_log: str) -> Tuple[ErrorType, str]:
        """Analyze build errors"""
        for pattern in self.UPSTREAM_PATTERNS:
            if re.search(pattern, build_log, re.IGNORECASE | re.MULTILINE):
                return ErrorType.UPSTREAM_COMPILE, f"Upstream: {pattern[:30]}..."
        
        if re.search(r"dependency resolution|failed to select", build_log, re.IGNORECASE):
            return ErrorType.DEPENDENCY_FAILURE, "Dependency conflict"
            
        return ErrorType.OUR_CODE_FAILURE, "Code issue"
    
    def _download_vector_tarball(self, version: str) -> bool:
        """Download Vector source as tar.gz (cleaner, no git metadata)"""
        try:
            import requests
            
            # GitHub releases API for tar.gz
            tarball_url = f"https://github.com/vectordotdev/vector/archive/refs/tags/{version}.tar.gz"
            self.log(f"📥 Downloading Vector {version} tar.gz...")
            
            response = requests.get(tarball_url, timeout=60)
            if response.status_code != 200:
                self.log(f"❌ Tar.gz download failed: HTTP {response.status_code}")
                return False
            
            # Extract tar.gz
            import tarfile
            import io
            
            with tarfile.open(fileobj=io.BytesIO(response.content), mode='r:gz') as tar:
                # Extract to temporary location first
                temp_extract = self.tmp_dir / f"vector-extract-{version}"
                tar.extractall(temp_extract)
                
                # Find the extracted directory (usually vector-X.Y.Z format)
                extracted_dirs = list(temp_extract.glob('vector-*'))
                if not extracted_dirs:
                    self.log(f"❌ No vector directory found in tarball")
                    return False
                
                # Move to final location
                shutil.move(str(extracted_dirs[0]), str(self.vector_dir))
                shutil.rmtree(temp_extract)
            
            self.log(f"✅ Vector {version} extracted from tar.gz (no git metadata)")
            return True
            
        except Exception as e:
            self.log(f"❌ Tar.gz download failed: {e}")
            return False
    
    def monitor_intelligent_build(self, process, name: str, log_file: Path) -> bool:
        """Intelligent build monitoring with pattern-based progress and error detection"""
        self.log(f"📊 Monitoring {name} with intelligent detection...")
        
        last_activity = time.time()
        last_size = 0
        last_meaningful_output = time.time()
        
        # Track build phases with configurable durations
        build_phases = {
            'downloading': {
                'pattern': r'Downloading|Updating', 
                'max_duration': self.settings.get('build_system.downloading_timeout', 15) * 60
            },
            'compiling': {
                'pattern': r'Compiling', 
                'max_duration': self.settings.get('build_system.compiling_timeout', 30) * 60
            },
            'linking': {
                'pattern': r'Linking|Finished', 
                'max_duration': self.settings.get('build_system.linking_timeout', 10) * 60
            },
            'error': {'pattern': r'error:|ERROR:|failed|panic', 'immediate': True}
        }
        
        current_phase = None
        phase_start_time = time.time()
        error_indicators = []
        
        while process.poll() is None:
            try:
                if log_file.exists():
                    current_size = log_file.stat().st_size
                    
                    if current_size > last_size:
                        last_activity = time.time()
                        
                        # Read new content and analyze
                        with open(log_file, 'r') as f:
                            f.seek(last_size)
                            new_content = f.read()
                            last_size = current_size
                        
                        # Analyze new content for phases and errors
                        for line in new_content.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            
                            # Check for meaningful progress
                            if any(keyword in line for keyword in ['Compiling', 'Downloading', 'Building', 'Finished']):
                                last_meaningful_output = time.time()
                                
                                if self.verbose:
                                    self.log(f"  → {line[:60]}")
                            
                            # Detect build phases
                            for phase_name, phase_info in build_phases.items():
                                if re.search(phase_info['pattern'], line, re.IGNORECASE):
                                    if current_phase != phase_name:
                                        if current_phase:
                                            elapsed = time.time() - phase_start_time
                                            self.log(f"  ✓ {current_phase} completed in {elapsed:.1f}s")
                                        
                                        current_phase = phase_name
                                        phase_start_time = time.time()
                                        self.log(f"  📋 Entering {phase_name} phase...")
                            
                            # Check for error patterns
                            for pattern in self.UPSTREAM_PATTERNS:
                                if re.search(pattern, line, re.IGNORECASE):
                                    error_indicators.append(line[:100])
                                    self.log(f"  ⚠️ Detected upstream issue: {line[:80]}")
                                    
                                    # Immediate termination on certain errors
                                    if any(fatal in pattern for fatal in ['make failed', 'panic']):
                                        self.log(f"  💥 Fatal upstream error detected - terminating build")
                                        process.terminate()
                                        return False
                    
                    # Intelligent stall detection
                    time_since_activity = time.time() - last_activity
                    time_since_meaningful = time.time() - last_meaningful_output
                    
                    # Phase-specific timeout
                    if current_phase and current_phase in build_phases:
                        phase_duration = time.time() - phase_start_time
                        max_phase_duration = build_phases[current_phase].get('max_duration', 300)
                        
                        if phase_duration > max_phase_duration:
                            self.log(f"  ⏰ {current_phase} phase exceeded {max_phase_duration}s - likely hung")
                            process.terminate()
                            return False
                    
                    # No meaningful progress timeout (more generous for Vector builds)
                    if time_since_meaningful > 900:  # 15 minutes no meaningful progress
                        self.log(f"  😴 No meaningful progress for {time_since_meaningful:.0f}s - likely hung")
                        process.terminate()
                        return False
                    
                    # Basic heartbeat fallback
                    if time_since_activity > self.stall_timeout:
                        self.log(f"  💤 Complete stall for {time_since_activity:.0f}s - terminating")
                        process.terminate()
                        return False
                
            except Exception as e:
                if self.verbose:
                    self.log(f"  ⚠️ Monitor error: {e}")
            
            time.sleep(2)  # Check every 2 seconds
        
        # Process finished - check result
        return_code = process.wait()
        
        if current_phase:
            elapsed = time.time() - phase_start_time
            self.log(f"  ✓ {current_phase} completed in {elapsed:.1f}s")
        
        # Check if we collected any error indicators
        if return_code != 0 and error_indicators:
            self.log(f"  📋 Error patterns detected: {len(error_indicators)} issues")
            for error in error_indicators[:3]:  # Show first 3 errors
                self.log(f"    • {error}")
        
        return return_code == 0
    
    def clone_vector(self, version: str) -> bool:
        """Download Vector source - tries tar.gz first, fallback to git clone"""
        try:
            self.log(f"📥 Completely removing existing /vector...")
            if self.vector_dir.exists():
                shutil.rmtree(self.vector_dir)
            
            # Try tar.gz download first (faster, no git metadata)
            if self._download_vector_tarball(version):
                return True
            
            self.log(f"📦 Tar.gz failed, trying git clone for Vector {version}...")
            result = subprocess.run([
                'git', 'clone', '--depth', '1', '--branch', version,
                'https://github.com/vectordotdev/vector.git',
                str(self.vector_dir)
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.log(f"❌ Git clone failed: {result.stderr}")
                return False
            
            # Remove ALL git-related files and GitHub metadata
            self.log(f"🧹 Removing git and GitHub metadata...")
            git_items = [
                '.git',           # Git repository data
                '.github',        # GitHub workflows and settings  
                '.gitignore',     # Git ignore rules
                '.gitattributes', # Git attributes
                '.gitmodules',    # Git submodules
                '.git*'           # Any other git files
            ]
            
            for item_pattern in git_items:
                if '*' in item_pattern:
                    # Handle glob patterns
                    import glob
                    for match in glob.glob(str(self.vector_dir / item_pattern)):
                        match_path = Path(match)
                        if match_path.exists():
                            if match_path.is_dir():
                                shutil.rmtree(match_path)
                            else:
                                match_path.unlink()
                            self.log(f"  🗑️ Removed {match_path.name}")
                else:
                    path = self.vector_dir / item_pattern
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        self.log(f"  🗑️ Removed {item_pattern}")
            
            # Verify we have a valid Vector source
            if not (self.vector_dir / "Cargo.toml").exists():
                self.log(f"❌ Invalid Vector source - no Cargo.toml found")
                return False
            
            self.log(f"✅ Vector {version} ready in /vector")
            return True
            
        except Exception as e:
            self.log(f"❌ Clone failed: {e}")
            return False
    
    def build_vector_core(self, version: str) -> StageResult:
        """Build Vector core"""
        self.log(f"🚀 Building Vector core {version}")
        
        start_time = time.time()
        log_file = self.tmp_dir / f"vector_{version}.log"
        
        if not (self.vector_dir / "Cargo.toml").exists():
            return StageResult(
                BuildStage.VECTOR_CORE, False, 0,
                ErrorType.VECTOR_CORE_FAILURE, "No Vector source"
            )
        
        env = os.environ.copy()
        env['RUSTFLAGS'] = '-C linker=gcc'
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen([
                'cargo', 'build', '--release', '--lib',
                '--features', 'sources-file,sinks-file,sinks-console,transforms-remap'
            ], stdout=f, stderr=subprocess.STDOUT, 
               env=env, cwd=self.vector_dir)
        
        success = self.monitor_intelligent_build(process, "Vector Core", log_file)
        build_time = time.time() - start_time
        
        if success:
            self.log(f"✅ Vector core: {build_time:.1f}s")
            return StageResult(BuildStage.VECTOR_CORE, True, build_time)
        else:
            with open(log_file, 'r') as f:
                build_log = f.read()
            error_type, error_msg = self.analyze_error(build_log)
            return StageResult(BuildStage.VECTOR_CORE, False, build_time, error_type, error_msg)
    
    def build_python_layer(self, vector_result: StageResult) -> StageResult:
        """Build Python bindings"""
        self.log("🐍 Building Python layer")
        
        if not vector_result.success:
            return StageResult(
                BuildStage.PYTHON_BINDINGS, False, 0,
                ErrorType.DEPENDENCY_FAILURE, "Vector core failed"
            )
        
        start_time = time.time()
        log_file = self.tmp_dir / f"python_{int(time.time())}.log"
        
        env = os.environ.copy()
        env.update({
            'RUSTFLAGS': f'-C linker=gcc -L {self.vector_dir}/target/release',
            'PYO3_USE_ABI3_FORWARD_COMPATIBILITY': '1',
            'SKIP_VECTOR_UPDATE': '1'
        })
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen([
                'uv', 'run', 'maturin', 'develop'
            ], stdout=f, stderr=subprocess.STDOUT,
               env=env, cwd=self.vectordotdev_dir)
        
        success = self.monitor_intelligent_build(process, "Python Layer", log_file)
        build_time = time.time() - start_time
        
        if success:
            # Quick verification
            try:
                result = subprocess.run([
                    '.venv/bin/python', '-c', 'import vector; print("OK")'
                ], capture_output=True, cwd=self.vectordotdev_dir, timeout=10)
                
                if result.returncode == 0:
                    self.log(f"✅ Python layer: {build_time:.1f}s")
                    return StageResult(BuildStage.PYTHON_BINDINGS, True, build_time)
            except Exception:
                pass
        
        with open(log_file, 'r') as f:
            build_log = f.read()
        error_type, error_msg = self.analyze_error(build_log)
        return StageResult(BuildStage.PYTHON_BINDINGS, False, build_time, error_type, error_msg)
    
    def robust_build(self) -> BuildResult:
        """Main build with version fallback"""
        self.log("🚀 3-Stage Build: Vector → Bindings → Python")
        
        versions = self.get_vector_versions()
        self.log(f"📋 Versions: {versions[:4]}")
        
        for attempt, version in enumerate(versions[:2]):
            self.log(f"\n🔄 Attempt {attempt + 1}: {version}")
            
            start_time = time.time()
            
            # Clone Vector
            if not self.clone_vector(version):
                continue
            
            # Build stages
            vector_result = self.build_vector_core(version)
            if not vector_result.success:
                if vector_result.error_type == ErrorType.UPSTREAM_COMPILE:
                    continue  # Try older version
                else:
                    break  # Code issue
            
            python_result = self.build_python_layer(vector_result)
            
            total_time = time.time() - start_time
            stage_results = {
                BuildStage.VECTOR_CORE: vector_result,
                BuildStage.PYTHON_BINDINGS: python_result
            }
            
            if python_result.success:
                self.log(f"🎉 Success with {version} in {total_time:.1f}s!")
                return BuildResult(True, version, total_time, stage_results)
            elif python_result.error_type == ErrorType.UPSTREAM_COMPILE:
                continue  # Try older version
            else:
                break  # Code issue
        
        return BuildResult(False, "failed", 0, {})

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='3-stage build for vectordotdev')
    parser.add_argument('--clean', action='store_true', help='Clean artifacts')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        os.environ['VERBOSE'] = 'true'
    
    build_system = RobustBuildSystem()
    
    if args.clean:
        build_system.log("🧹 Cleaning...")
        for cleanup in ['target', '.tmp', 'vector', 'vector-bindings']:
            path = build_system.project_root / cleanup
            if path.exists():
                shutil.rmtree(path)
    
    result = build_system.robust_build()
    
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()