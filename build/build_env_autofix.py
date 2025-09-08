#!/usr/bin/env python3
"""
Build Environment Auto-Fix System for vectordotdev
Automatically detects and fixes build dependency issues
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from common import log_message

class BuildEnvironmentAutoFix:
    """Automatically detect and fix build environment compatibility issues"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.vector_dir = project_root / "vector"
        
        # Compiler compatibility fixes
        self.gcc_compat_fixes = {
            'CFLAGS': [
                '-Wno-error=excess-args',  # Correct flag name
                '-Wno-error=old-style-definition', 
                '-Wno-error=implicit-function-declaration',
                '-Wno-error=incompatible-pointer-types',
                '-Wno-error=deprecated-declarations',
                '-std=gnu11',  # More permissive C standard
            ],
            'CXXFLAGS': [
                '-Wno-error=excess-args',
                '-Wno-error=old-style-definition',
                '-Wno-error=deprecated-declarations',
                '-fpermissive',  # More permissive C++
            ]
        }
    
    def detect_build_environment_issues(self, build_log: str) -> List[str]:
        """Detect specific build environment compatibility issues"""
        issues = []
        
        # GCC 15+ compatibility issues
        if re.search(r"too many arguments to function.*xfunc.*expected 0, have 2", build_log):
            issues.append("gcc_15_krb5_compat")
        
        if re.search(r"old-style function definition.*krb5-src", build_log):
            issues.append("gcc_strict_c_compat")
            
        if re.search(r"implicit-function-declaration", build_log):
            issues.append("gcc_implicit_declarations")
            
        if re.search(r"incompatible-pointer-types", build_log):
            issues.append("gcc_pointer_compat")
        
        # Linker issues
        if re.search(r"could not find.*mold|ld.*failed", build_log):
            issues.append("linker_compatibility")
            
        # OpenSSL issues
        if re.search(r"openssl.*not found|SSL_VERIFY_PEER.*undefined", build_log):
            issues.append("openssl_compatibility")
        
        # System library issues  
        if re.search(r"could not find.*libz|zlib.*not found", build_log):
            issues.append("system_zlib")
            
        if re.search(r"could not find.*libssl|openssl-sys.*failed", build_log):
            issues.append("system_openssl")
        
        return issues
    
    def auto_fix_build_environment(self, issues: List[str], env: Dict[str, str]) -> Dict[str, str]:
        """Automatically apply fixes for detected build environment issues"""
        fixed_env = env.copy()
        
        for issue in issues:
            if issue == "gcc_15_krb5_compat":
                log_message("  🔧 Applying GCC 15+ Kerberos compatibility fix...")
                # Add permissive C compilation flags
                cflags = fixed_env.get('CFLAGS', '')
                cflags += ' ' + ' '.join(self.gcc_compat_fixes['CFLAGS'])
                fixed_env['CFLAGS'] = cflags.strip()
                
                cxxflags = fixed_env.get('CXXFLAGS', '')
                cxxflags += ' ' + ' '.join(self.gcc_compat_fixes['CXXFLAGS'])
                fixed_env['CXXFLAGS'] = cxxflags.strip()
            
            elif issue == "gcc_strict_c_compat":
                log_message("  🔧 Applying strict C compatibility fix...")
                fixed_env['CC_ENABLE_DEBUG_OUTPUT'] = '1'
                
            elif issue == "linker_compatibility":
                log_message("  🔧 Applying linker compatibility fix...")
                rustflags = fixed_env.get('RUSTFLAGS', '')
                if 'linker=gcc' not in rustflags:
                    rustflags += ' -C linker=gcc'
                    fixed_env['RUSTFLAGS'] = rustflags.strip()
                    
            elif issue == "openssl_compatibility":
                log_message("  🔧 Applying OpenSSL compatibility fix...")
                fixed_env['OPENSSL_NO_VENDOR'] = '1'
                fixed_env['PKG_CONFIG_ALLOW_CROSS'] = '1'
                
            elif issue == "system_zlib":
                log_message("  🔧 Applying system zlib fix...")
                fixed_env['LIBZ_SYS_STATIC'] = '0'  # Use system zlib
                
            elif issue == "system_openssl":
                log_message("  🔧 Applying system OpenSSL fix...")
                fixed_env['OPENSSL_STATIC'] = '0'  # Use system OpenSSL
        
        return fixed_env
    
    def check_system_dependencies(self) -> List[str]:
        """Check for missing system dependencies and provide guidance"""
        missing_deps = []
        
        # Check essential build tools
        tools = {
            'gcc': 'gcc compiler',
            'make': 'make build tool', 
            'cmake': 'cmake build system',
            'pkg-config': 'pkg-config tool',
            'cargo': 'Rust toolchain'
        }
        
        for tool, description in tools.items():
            if not shutil.which(tool):
                missing_deps.append(f"{tool} ({description})")
        
        # Check system libraries
        libs = {
            'openssl-devel': ['openssl/ssl.h', '/usr/include/openssl/ssl.h'],
            'zlib-devel': ['zlib.h', '/usr/include/zlib.h'],
            'protobuf-devel': ['google/protobuf/', '/usr/include/google/protobuf/']
        }
        
        for lib, headers in libs.items():
            found = any(Path(header).exists() for header in headers[1:])
            if not found:
                missing_deps.append(f"{lib} (system library)")
        
        return missing_deps
    
    def provide_system_dependency_guidance(self, missing_deps: List[str]):
        """Provide user guidance for installing missing system dependencies"""
        if not missing_deps:
            return
            
        log_message("❌ Missing system dependencies detected:")
        for dep in missing_deps:
            log_message(f"  • {dep}")
        
        log_message("")
        log_message("🔧 To install missing dependencies:")
        log_message("  Fedora/RHEL: sudo dnf install gcc make cmake pkg-config openssl-devel zlib-devel protobuf-devel")
        log_message("  Ubuntu/Debian: sudo apt install build-essential cmake pkg-config libssl-dev zlib1g-dev libprotobuf-dev")
        log_message("  macOS: brew install cmake pkg-config openssl zlib protobuf")
        log_message("")
        log_message("Or run the bootstrap script: ./build/bootstrap.sh")
    
    def analyze_and_fix_build_failure(self, build_log: str, current_env: Dict[str, str]) -> Tuple[bool, Dict[str, str], str]:
        """Analyze build failure and return auto-fix recommendations"""
        
        # Detect issues
        issues = self.detect_build_environment_issues(build_log)
        
        if not issues:
            # Check for system dependency issues
            missing_deps = self.check_system_dependencies()
            if missing_deps:
                self.provide_system_dependency_guidance(missing_deps)
                return False, current_env, "Missing system dependencies - install with bootstrap script"
            
            # No auto-fixable issues detected
            return False, current_env, "No auto-fixable build environment issues detected"
        
        log_message(f"🔧 Detected {len(issues)} build environment issues:")
        for issue in issues:
            log_message(f"  • {issue}")
        
        # Apply fixes
        fixed_env = self.auto_fix_build_environment(issues, current_env)
        
        # Verify fixes were applied
        if fixed_env != current_env:
            log_message("✅ Applied build environment compatibility fixes")
            log_message(f"  CFLAGS: {fixed_env.get('CFLAGS', 'unchanged')}")
            log_message(f"  CXXFLAGS: {fixed_env.get('CXXFLAGS', 'unchanged')}")
            log_message(f"  RUSTFLAGS: {fixed_env.get('RUSTFLAGS', 'unchanged')}")
            return True, fixed_env, "Applied compatibility fixes"
        
        return False, current_env, "No fixes applicable"


def main():
    """Test the build environment auto-fix system"""
    project_root = Path(__file__).parent.parent
    autofix = BuildEnvironmentAutoFix(project_root)
    
    # Test system dependency check
    missing = autofix.check_system_dependencies()
    if missing:
        autofix.provide_system_dependency_guidance(missing)
    else:
        log_message("✅ All system dependencies available")
    
    # Test with sample krb5 error
    sample_error = """
    /home/derek/.cargo/registry/src/krb5-src-0.3.2+1.19.2/krb5/src/lib/rpc/auth_none.c:146:18: error: too many arguments to function 'xfunc'; expected 0, have 2
        146 |         return ((*xfunc)(xdrs, xwhere));
    make failed in lib
    thread 'main' panicked at /home/derek/.cargo/registry/src/krb5-src-0.3.2+1.19.2/build.rs:138:41:
    """
    
    can_fix, fixed_env, message = autofix.analyze_and_fix_build_failure(sample_error, os.environ.copy())
    log_message(f"Test result: {can_fix} - {message}")

if __name__ == '__main__':
    main()