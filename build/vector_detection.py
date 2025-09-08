"""
Vector build detection and version management
"""

import os
import re
import time
import subprocess
from pathlib import Path
from typing import List, Optional, Dict

from common import log_message

class VectorDetector:
    """Handles Vector version discovery and build detection"""
    
    def __init__(self, project_root: Path, vector_dir: Path):
        self.project_root = project_root
        self.vector_dir = vector_dir
    
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
    
    def detect_vector_build_info(self) -> Optional[Dict]:
        """Auto-detect if Vector is already successfully built and get version info"""
        try:
            # Check if Vector source exists
            if not (self.vector_dir / "Cargo.toml").exists():
                return None
            
            # Read Vector's Cargo.toml to get version
            with open(self.vector_dir / "Cargo.toml", 'r') as f:
                vector_content = f.read()
            
            # Extract version from Cargo.toml
            version_match = re.search(r'version\s*=\s*"([^"]+)"', vector_content)
            if not version_match:
                return None
            
            detected_version = version_match.group(1)
            
            # Check if build artifacts exist
            release_dir = self.vector_dir / "target" / "release"
            deps_dir = release_dir / "deps"
            
            if not release_dir.exists() or not deps_dir.exists():
                log_message(f"📋 Vector {detected_version} source found but not built")
                return None
            
            # Check for key Vector artifacts
            vector_artifacts = list(deps_dir.glob("*vector*")) + list(release_dir.glob("*vector*"))
            if not vector_artifacts:
                log_message(f"📋 Vector {detected_version} partially built - missing key artifacts")
                return None
            
            # Check build freshness (optional)
            build_time = max(artifact.stat().st_mtime for artifact in vector_artifacts)
            build_age_hours = (time.time() - build_time) / 3600
            
            build_info = {
                'version': detected_version,
                'build_time': build_time,
                'build_age_hours': build_age_hours,
                'artifacts_count': len(vector_artifacts),
                'release_dir': str(release_dir),
                'deps_dir': str(deps_dir)
            }
            
            log_message(f"✅ Found existing Vector {detected_version} build ({build_age_hours:.1f}h old, {len(vector_artifacts)} artifacts)")
            return build_info
            
        except Exception as e:
            log_message(f"⚠️ Build detection failed: {e}")
            return None
    
    def should_rebuild_vector(self, build_info: Dict, requested_version: str) -> bool:
        """Determine if Vector should be rebuilt based on existing build info"""
        if not build_info:
            return True
        
        existing_version = build_info['version']
        
        # Check if versions match
        if f"v{existing_version}" == requested_version or existing_version == requested_version.lstrip('v'):
            log_message(f"📋 Vector {existing_version} already built and matches requested {requested_version}")
            
            # Check if build is recent (optional freshness check)
            if build_info['build_age_hours'] < 24:  # Less than 24 hours old
                log_message(f"✅ Using existing Vector {existing_version} build (fresh)")
                return False
            else:
                log_message(f"⚠️ Vector {existing_version} build is {build_info['build_age_hours']:.1f}h old - rebuilding")
                return True
        else:
            log_message(f"🔄 Version mismatch: existing {existing_version} != requested {requested_version}")
            return True