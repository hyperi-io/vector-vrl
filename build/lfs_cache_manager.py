#!/usr/bin/env python3
"""
LFS Cache Manager for Vector Build System
Manages build caches using Git LFS for efficient CI/CD
"""

import os
import shutil
import hashlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, List

import click
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="PYVECTOR",
    settings_files=['build/config/*.yaml'],
    load_dotenv=True
)

class LFSCacheManager:
    """Manages build caches using Git LFS"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.cache_dir = project_dir / ".tmp" / "lfs-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def get_cargo_cache_key(self) -> str:
        """Generate cache key based on Cargo.toml and lock file"""
        cargo_toml = self.project_dir / "Cargo.toml"
        cargo_lock = self.project_dir / "Cargo.lock"
        
        hasher = hashlib.sha256()
        
        if cargo_toml.exists():
            hasher.update(cargo_toml.read_bytes())
        if cargo_lock.exists():
            hasher.update(cargo_lock.read_bytes())
            
        return hasher.hexdigest()[:16]
    
    def get_vector_version_from_config(self) -> Optional[str]:
        """Extract Vector version from current Cargo.toml"""
        cargo_toml = self.project_dir / "Cargo.toml"
        if not cargo_toml.exists():
            return None
            
        content = cargo_toml.read_text()
        import re
        match = re.search(r'tag = "(v[0-9]+\.[0-9]+\.[0-9]+)"', content)
        return match.group(1) if match else None
    
    def create_cache_archive(self, cache_key: str, vector_version: str) -> bool:
        """Create LFS cache archive from successful build"""
        try:
            archive_name = f"build-cache-{vector_version}-{cache_key}.tar.gz"
            archive_path = self.cache_dir / archive_name
            
            # Directories to cache
            cache_targets = [
                "target/release/deps",
                "target/release/build", 
                ".cargo/registry/cache",
                ".cargo/git/checkouts"
            ]
            
            existing_targets = [
                target for target in cache_targets 
                if (self.project_dir / target).exists()
            ]
            
            if not existing_targets:
                print("[WARN] No build artifacts found to cache")
                return False
            
            # Create tar archive
            cmd = ["tar", "-czf", str(archive_path)] + [
                "-C", str(self.project_dir)
            ] + existing_targets
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"[INFO] Created build cache: {archive_name} ({archive_path.stat().st_size // 1024}KB)")
                
                # Add to LFS tracking
                subprocess.run([
                    "git", "lfs", "track", str(archive_path.relative_to(self.project_dir))
                ], cwd=self.project_dir)
                
                return True
            else:
                print(f"[WARN] Failed to create cache archive: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Cache creation failed: {e}")
            return False
    
    def restore_cache_archive(self, cache_key: str, vector_version: str) -> bool:
        """Restore build cache from LFS"""
        try:
            archive_name = f"build-cache-{vector_version}-{cache_key}.tar.gz"
            archive_path = self.cache_dir / archive_name
            
            if not archive_path.exists():
                print(f"[INFO] No cache found for Vector {vector_version} (key: {cache_key})")
                return False
            
            print(f"[INFO] Restoring build cache: {archive_name}")
            
            # Extract cache archive
            cmd = ["tar", "-xzf", str(archive_path), "-C", str(self.project_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"[INFO] Cache restored successfully")
                return True
            else:
                print(f"[WARN] Failed to restore cache: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Cache restoration failed: {e}")
            return False
    
    def find_compatible_cache(self, vector_version: str) -> Optional[str]:
        """Find compatible cache for given Vector version"""
        # Look for exact version match first
        pattern = f"build-cache-{vector_version}-*.tar.gz"
        matches = list(self.cache_dir.glob(pattern))
        
        if matches:
            # Return most recent cache
            latest = max(matches, key=lambda f: f.stat().st_mtime)
            cache_key = latest.name.split('-')[-1].replace('.tar.gz', '')
            return cache_key
        
        # Look for compatible minor version caches
        major_minor = '.'.join(vector_version.split('.')[:2])  # e.g., "v0.49"
        pattern = f"build-cache-{major_minor}.*-*.tar.gz"
        matches = list(self.cache_dir.glob(pattern))
        
        if matches:
            latest = max(matches, key=lambda f: f.stat().st_mtime)
            cache_key = latest.name.split('-')[-1].replace('.tar.gz', '')
            print(f"[INFO] Found compatible cache from similar version")
            return cache_key
            
        return None
    
    def cleanup_old_caches(self, retention_days: int = 7):
        """Clean up old cache files"""
        import time
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        
        for cache_file in self.cache_dir.glob("build-cache-*.tar.gz"):
            if cache_file.stat().st_mtime < cutoff_time:
                print(f"[INFO] Removing old cache: {cache_file.name}")
                cache_file.unlink()

def should_use_cache(project_dir: Path) -> bool:
    """Determine if we should use build caching"""
    # Enable caching in CI environments or when explicitly requested
    return (
        os.environ.get('CI') or 
        os.environ.get('PYVECTOR_USE_CACHE', '').lower() in ['1', 'true', 'yes'] or
        settings.get('caching.enabled', False)
    )

@click.command()
@click.option('--create-cache', is_flag=True, help='Create cache from current build artifacts')
@click.option('--restore-cache', help='Restore cache for specific Vector version')
@click.option('--cleanup', is_flag=True, help='Clean up old cache files')
@click.option('--list-caches', is_flag=True, help='List available caches')
def main(create_cache: bool, restore_cache: Optional[str], cleanup: bool, list_caches: bool):
    """LFS Cache Manager for Vector builds"""
    project_dir = Path(__file__).parent.parent
    cache_manager = LFSCacheManager(project_dir)
    
    if create_cache:
        vector_version = cache_manager.get_vector_version_from_config()
        if vector_version:
            cache_key = cache_manager.get_cargo_cache_key()
            if cache_manager.create_cache_archive(cache_key, vector_version):
                print(f"✓ Cache created for Vector {vector_version}")
            else:
                print("✗ Failed to create cache")
                sys.exit(1)
        else:
            print("✗ Could not determine Vector version")
            sys.exit(1)
    
    elif restore_cache:
        cache_key = cache_manager.find_compatible_cache(restore_cache)
        if cache_key and cache_manager.restore_cache_archive(cache_key, restore_cache):
            print(f"✓ Cache restored for Vector {restore_cache}")
        else:
            print(f"✗ No compatible cache found for Vector {restore_cache}")
            sys.exit(1)
    
    elif cleanup:
        retention_days = settings.get('caching.retention_days', 7)
        cache_manager.cleanup_old_caches(retention_days)
        print("✓ Cache cleanup completed")
    
    elif list_caches:
        caches = list(cache_manager.cache_dir.glob("build-cache-*.tar.gz"))
        if caches:
            print("Available caches:")
            for cache in sorted(caches, key=lambda f: f.stat().st_mtime, reverse=True):
                size_kb = cache.stat().st_size // 1024
                mtime = cache.stat().st_mtime
                print(f"  {cache.name} ({size_kb}KB, {time.ctime(mtime)})")
        else:
            print("No caches found")
    
    else:
        print("Use --help for available options")

if __name__ == "__main__":
    main()