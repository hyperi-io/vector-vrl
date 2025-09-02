#!/usr/bin/env python3
"""
Auto-Fix System for Vector Build Issues
Applies learned fixes automatically based on detected error patterns
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum

class AutoFixType(Enum):
    VRL_VERSION_ALIGNMENT = "vrl_version_alignment"
    TOML_VERSION_CONFLICT = "toml_version_conflict"
    DEPENDENCY_DOWNGRADE = "dependency_downgrade"
    FEATURE_EXCLUSION = "feature_exclusion"
    SYSTEM_LIBRARY_FIX = "system_library_fix"

class AutoFixSystem:
    """Automatically applies fixes based on detected build errors"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.cargo_toml = project_dir / "Cargo.toml"
        
    def analyze_and_fix(self, build_log: str, vector_version: str) -> List[AutoFixType]:
        """Analyze build errors and apply automatic fixes"""
        fixes_applied = []
        
        # Fix 1: VRL protobuf API incompatibility  
        if re.search(r"cannot find function.*proto_to_value.*vrl.*protobuf", build_log, re.IGNORECASE | re.DOTALL):
            if self.fix_vrl_protobuf_incompatibility(vector_version):
                fixes_applied.append(AutoFixType.VRL_VERSION_ALIGNMENT)
        
        # Fix 2: TOML version conflicts
        if re.search(r"two different versions of crate.*toml.*are being used", build_log, re.IGNORECASE):
            if self.fix_toml_version_conflicts():
                fixes_applied.append(AutoFixType.TOML_VERSION_CONFLICT)
        
        # Fix 3: System library conflicts (krb5, gssrpc)
        if re.search(r"krb5.*make failed|gssrpc.*error", build_log, re.IGNORECASE):
            if self.fix_system_library_conflicts():
                fixes_applied.append(AutoFixType.SYSTEM_LIBRARY_FIX)
        
        # Fix 4: Dependency version conflicts (indexmap, etc)
        if re.search(r"failed to select a version.*indexmap", build_log, re.IGNORECASE):
            if self.fix_dependency_conflicts():
                fixes_applied.append(AutoFixType.DEPENDENCY_DOWNGRADE)
        
        return fixes_applied
    
    def fix_vrl_protobuf_incompatibility(self, vector_version: str) -> bool:
        """Fix VRL protobuf API incompatibility by aligning VRL version"""
        try:
            # Map Vector versions to compatible VRL configurations
            vrl_config_map = {
                "v0.49.0": 'vrl = { git = "https://github.com/vectordotdev/vrl.git", rev = "40d3f6dfa395ef5dd306432e6cfd03af9966da00" }',
                "v0.48.0": 'vrl = { git = "https://github.com/vectordotdev/vrl.git", tag = "v0.25.0" }',
                "v0.47.0": 'vrl = { git = "https://github.com/vectordotdev/vrl.git", tag = "v0.24.0" }',
                "v0.46.1": 'vrl = { git = "https://github.com/vectordotdev/vrl.git", tag = "v0.23.0" }',
                "v0.46.0": 'vrl = { git = "https://github.com/vectordotdev/vrl.git", tag = "v0.23.0" }'
            }
            
            if vector_version in vrl_config_map:
                with open(self.cargo_toml, 'r') as f:
                    content = f.read()
                
                # Replace VRL dependency with compatible version
                new_content = re.sub(
                    r'vrl = \{[^}]+\}',
                    vrl_config_map[vector_version],
                    content
                )
                
                with open(self.cargo_toml, 'w') as f:
                    f.write(new_content)
                    
                print(f"[FIX] Applied VRL version alignment for Vector {vector_version}")
                return True
                
        except Exception as e:
            print(f"[WARN] Failed to apply VRL fix: {e}")
        
        return False
    
    def fix_toml_version_conflicts(self) -> bool:
        """Fix TOML version conflicts by pinning to compatible version"""
        try:
            with open(self.cargo_toml, 'r') as f:
                content = f.read()
            
            # Pin TOML version to avoid conflicts
            new_content = re.sub(
                r'toml = \{ version = "[^"]*"([^}]*)\}',
                r'toml = { version = "=0.8.12"\1}',
                content
            )
            
            if new_content != content:
                with open(self.cargo_toml, 'w') as f:
                    f.write(new_content)
                    
                print("[FIX] Applied TOML version pinning to resolve conflicts")
                return True
                
        except Exception as e:
            print(f"[WARN] Failed to apply TOML fix: {e}")
        
        return False
    
    def fix_system_library_conflicts(self) -> bool:
        """Fix system library conflicts by excluding problematic features"""
        try:
            with open(self.cargo_toml, 'r') as f:
                content = f.read()
            
            # Remove features that cause krb5/gssrpc issues
            problematic_features = [
                '"default"',
                '"rdkafka.*gssapi"',
                '"sources-dnstap"'
            ]
            
            new_content = content
            for feature in problematic_features:
                # Remove the feature from feature lists
                new_content = re.sub(f',?\\s*{feature},?', '', new_content)
            
            # If we removed default, add back essential features
            if '"default"' in content and '"default"' not in new_content:
                # Replace with essential features without problematic ones
                essential_features = [
                    '"api"', '"api-client"', '"enrichment-tables"', 
                    '"sinks"', '"sources"', '"transforms"', '"unix"', '"secrets"'
                ]
                
                feature_pattern = r'(features = \[)[^\]]*(\])'
                replacement = r'\1\n    ' + ',\n    '.join(essential_features) + r'\n\2'
                new_content = re.sub(feature_pattern, replacement, new_content)
            
            if new_content != content:
                with open(self.cargo_toml, 'w') as f:
                    f.write(new_content)
                    
                print("[FIX] Applied system library conflict resolution")
                return True
                
        except Exception as e:
            print(f"[WARN] Failed to apply system library fix: {e}")
        
        return False
    
    def fix_dependency_conflicts(self) -> bool:
        """Fix dependency version conflicts by adjusting version constraints"""
        try:
            with open(self.cargo_toml, 'r') as f:
                content = f.read()
            
            # Common dependency fixes based on our experience
            fixes = {
                r'serde_with = ">=3\.0\.0"': 'serde_with = ">=3.0.0,<3.15.0"',  # Avoid latest problematic versions
                r'indexmap = "[^"]*"': 'indexmap = ">=2.0.0,<2.5.0"',  # Pin to compatible range
            }
            
            new_content = content
            for pattern, replacement in fixes.items():
                new_content = re.sub(pattern, replacement, new_content)
            
            if new_content != content:
                with open(self.cargo_toml, 'w') as f:
                    f.write(new_content)
                    
                print("[FIX] Applied dependency conflict resolution")
                return True
                
        except Exception as e:
            print(f"[WARN] Failed to apply dependency fix: {e}")
        
        return False

class SmartFixRecommendations:
    """Provides recommendations for Vector feature configurations based on build results"""
    
    @staticmethod
    def get_feature_recommendations(failed_versions: List[str], error_patterns: List[str]) -> Dict:
        """Generate feature set recommendations based on failure patterns"""
        
        recommendations = {
            "minimal_stable": {
                "features": ["transforms-logs", "transforms-metrics", "sinks-logs", "sinks-metrics"],
                "description": "Minimal feature set - most likely to build successfully",
                "risk": "low"
            },
            
            "comprehensive_safe": {
                "features": ["api", "api-client", "sinks", "sources", "transforms", "unix", "secrets"],
                "description": "Comprehensive features excluding problematic system dependencies",
                "risk": "medium"
            },
            
            "full_with_workarounds": {
                "features": ["default"],
                "workarounds": [
                    "Set OPENSSL_NO_VENDOR=1",
                    "Install system krb5-devel packages",
                    "Use cmake build variant"
                ],
                "description": "Full Vector features with system library workarounds",
                "risk": "high"
            }
        }
        
        # Adjust recommendations based on detected error patterns
        if any("protobuf" in pattern for pattern in error_patterns):
            recommendations["minimal_stable"]["note"] = "VRL protobuf issues detected - minimal features recommended"
            
        if any("krb5" in pattern or "gssrpc" in pattern for pattern in error_patterns):
            recommendations["comprehensive_safe"]["note"] = "System library issues detected - avoiding rdkafka features"
            
        if any("toml" in pattern for pattern in error_patterns):
            recommendations["minimal_stable"]["extra_config"] = 'toml = { version = "=0.8.12", default-features = false }'
        
        return recommendations

# Integration function for use in smart_build_system.py
def apply_smart_fixes(project_dir: Path, build_log: str, vector_version: str) -> List[AutoFixType]:
    """Apply smart fixes and return list of fixes applied"""
    auto_fix = AutoFixSystem(project_dir)
    return auto_fix.analyze_and_fix(build_log, vector_version)

def get_build_recommendations(failed_versions: List[str], error_patterns: List[str]) -> Dict:
    """Get feature configuration recommendations"""
    return SmartFixRecommendations.get_feature_recommendations(failed_versions, error_patterns)