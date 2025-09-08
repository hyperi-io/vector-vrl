"""
Dependency synchronization and auto-fixing for vector-bindings
"""

import re
from pathlib import Path
from typing import Dict

from common import log_message

class DependencyManager:
    """Manages dependency synchronization between Vector and vector-bindings"""
    
    def __init__(self, project_root: Path, vector_dir: Path):
        self.project_root = project_root
        self.vector_dir = vector_dir
    
    def sync_vector_dependencies(self, version: str) -> bool:
        """Sync vector-bindings dependencies to match Vector's workspace.dependencies"""
        try:
            log_message(f"🔄 Syncing vector-bindings deps with Vector {version}...")
            
            # Read Vector's Cargo.toml workspace dependencies
            vector_cargo = self.vector_dir / "Cargo.toml"
            if not vector_cargo.exists():
                log_message("⚠️ Vector Cargo.toml not found - skipping dependency sync")
                return True
            
            with open(vector_cargo, 'r') as f:
                vector_toml_content = f.read()
            
            # Parse Vector's workspace dependencies
            import toml
            vector_toml = toml.loads(vector_toml_content)
            workspace_deps = vector_toml.get('workspace', {}).get('dependencies', {})
            
            if not workspace_deps:
                log_message("⚠️ No workspace dependencies found in Vector")
                return True
            
            # Read vector-bindings Cargo.toml
            bindings_cargo = self.project_root / "vector-bindings" / "Cargo.toml"
            if not bindings_cargo.exists():
                log_message("ℹ️ vector-bindings/Cargo.toml not found - skipping sync")
                return True
            
            with open(bindings_cargo, 'r') as f:
                bindings_content = f.read()
            
            # Update key dependencies to match Vector versions
            key_deps = ['tokio', 'serde', 'serde_json', 'toml', 'uuid', 'anyhow', 'futures', 'indexmap']
            
            updated_content = bindings_content
            for dep in key_deps:
                if dep in workspace_deps:
                    vector_dep = workspace_deps[dep]
                    if isinstance(vector_dep, str):
                        version_str = vector_dep
                    elif isinstance(vector_dep, dict) and 'version' in vector_dep:
                        version_str = vector_dep['version']
                    else:
                        continue
                    
                    # Update in bindings Cargo.toml with required features
                    pattern = rf'^{dep}\s*=.*$'
                    
                    # Add necessary features for std library dependencies
                    if dep == 'serde_json':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["std"] }}'
                    elif dep == 'serde':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["derive", "std"] }}'
                    elif dep == 'indexmap':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["std"] }}'
                    elif dep == 'futures':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["std"] }}'
                    elif dep == 'tokio':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["full"] }}'
                    elif dep == 'toml':
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false, features = ["parse", "serde"] }}'
                    else:
                        replacement = f'{dep} = {{ version = "{version_str}", default-features = false }}'
                    
                    updated_content = re.sub(pattern, replacement, updated_content, flags=re.MULTILINE)
            
            # Write updated Cargo.toml
            with open(bindings_cargo, 'w') as f:
                f.write(updated_content)
            
            log_message(f"✅ Synced {len(key_deps)} dependencies with Vector {version}")
            return True
            
        except Exception as e:
            log_message(f"⚠️ Dependency sync failed: {e}")
            return True  # Don't fail build on sync issues
    
    def auto_fix_vector_bindings(self) -> bool:
        """Auto-fix common vector-bindings compilation issues"""
        try:
            log_message("🔧 Auto-fixing vector-bindings issues...")
            
            bindings_toml = self.project_root / "vector-bindings" / "Cargo.toml"
            if not bindings_toml.exists():
                return True
            
            with open(bindings_toml, 'r') as f:
                content = f.read()
            
            # Fix common feature issues
            fixes_applied = []
            
            # Ensure toml has required features (fallback fix)
            if 'toml = {' in content and 'features = [' not in content.split('toml = {')[1].split('}')[0]:
                content = re.sub(
                    r'toml = { version = "([^"]+)", default-features = false }',
                    r'toml = { version = "\1", default-features = false, features = ["parse", "serde"] }',
                    content
                )
                fixes_applied.append("toml features")
            
            # Write fixes if any applied
            if fixes_applied:
                with open(bindings_toml, 'w') as f:
                    f.write(content)
                log_message(f"✅ Applied auto-fixes: {', '.join(fixes_applied)}")
            
            return True
            
        except Exception as e:
            log_message(f"⚠️ Auto-fix failed: {e}")
            return True