#!/usr/bin/env python3
"""
Deployment mode configuration for JFrog PyPI.
Automatically disables GitHub Actions if local ENV credentials are configured.
"""

import os
import subprocess
import sys
from pathlib import Path


class DeploymentModeManager:
    """Manage local vs GitHub Actions deployment modes"""
    
    def __init__(self):
        self.build_dir = Path(__file__).parent
        self.project_root = self.build_dir.parent
        
        # Load .env configuration
        self._load_env_config()
    
    def _load_env_config(self):
        """Load configuration from build/.env"""
        env_file = self.build_dir / ".env"
        
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line and not line.startswith('# '):
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    
    def check_local_credentials(self) -> tuple:
        """Check if local JFrog credentials are configured"""
        
        # Check all possible credential sources
        username = (os.getenv("ARTIFACTORY_TENANT_USERNAME") or 
                   os.getenv("ARTIFACTORY_USERNAME") or
                   os.getenv("TWINE_USERNAME"))
        password = (os.getenv("ARTIFACTORY_TENANT_PASSWORD") or 
                   os.getenv("ARTIFACTORY_PASSWORD") or
                   os.getenv("TWINE_PASSWORD"))
        token = os.getenv("JFROG_ACCESS_TOKEN")
        
        has_local_creds = (username and password) or token
        
        return has_local_creds, {
            "username": username,
            "has_password": bool(password),
            "has_token": bool(token)
        }
    
    def configure_deployment_mode(self) -> str:
        """Configure deployment mode and return recommendation"""
        
        print("🔍 JFrog Deployment Mode Configuration")
        print("=" * 45)
        
        has_local_creds, cred_info = self.check_local_credentials()
        
        if has_local_creds:
            print("✅ Local JFrog credentials detected")
            print(f"   Username: {cred_info['username']}")
            print(f"   Password: {'✅' if cred_info['has_password'] else '❌'}")
            print(f"   Token: {'✅' if cred_info['has_token'] else '❌'}")
            print("")
            print("🔧 RECOMMENDATION: Use local deployment")
            print("   Command: ./build/build --deploy")
            print("")
            print("🚫 GitHub Actions should be DISABLED for this project")
            print("   Add DISABLE_GITHUB_JFROG=true to repository secrets")
            
            return "local"
        else:
            print("ℹ️ No local JFrog credentials found")
            print("")
            print("🌐 RECOMMENDATION: Use GitHub Actions deployment")
            print("   Credentials: GitHub organization secrets")
            print("   Trigger: git push (for tags) or manual workflow dispatch")
            print("")
            print("To switch to local deployment:")
            print("1. Add credentials to build/.env:")
            print("   ARTIFACTORY_TENANT_USERNAME=your_username")
            print("   ARTIFACTORY_TENANT_PASSWORD=your_password")
            print("2. Set: ENABLE_JFROG_DEPLOYMENT=ON")
            
            return "github"
    
    def update_github_secret(self, secret_name: str, value: str) -> bool:
        """Update GitHub repository secret"""
        try:
            result = subprocess.run([
                "gh", "secret", "set", secret_name, "--body", value
            ], check=True, capture_output=True, text=True)
            
            print(f"✅ Updated GitHub secret: {secret_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update GitHub secret {secret_name}: {e}")
            return False
        except FileNotFoundError:
            print("❌ gh CLI not available")
            return False
    
    def disable_github_actions_deployment(self) -> bool:
        """Disable GitHub Actions JFrog deployment when local creds are used"""
        
        print("🔧 Disabling GitHub Actions JFrog deployment...")
        
        # Set repository secret to disable GitHub workflow
        success = self.update_github_secret("DISABLE_GITHUB_JFROG", "true")
        
        if success:
            print("✅ GitHub Actions JFrog deployment disabled")
            print("   Local deployment mode activated")
        else:
            print("⚠️ Could not disable GitHub Actions - manual configuration needed")
            print("   Add DISABLE_GITHUB_JFROG=true to repository secrets")
        
        return success


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Configure JFrog deployment mode')
    parser.add_argument('--check', action='store_true', help='Check current deployment mode')
    parser.add_argument('--disable-github', action='store_true', help='Disable GitHub Actions deployment')
    parser.add_argument('--configure', action='store_true', help='Auto-configure deployment mode')
    
    args = parser.parse_args()
    
    manager = DeploymentModeManager()
    
    if args.check:
        mode = manager.configure_deployment_mode()
        print(f"\n🎯 Current mode: {mode}")
        
    elif args.disable_github:
        manager.disable_github_actions_deployment()
        
    elif args.configure:
        mode = manager.configure_deployment_mode()
        if mode == "local":
            manager.disable_github_actions_deployment()
        print(f"\n🎯 Configured for {mode} deployment")
        
    else:
        # Default: just show current status
        mode = manager.configure_deployment_mode()


if __name__ == '__main__':
    main()