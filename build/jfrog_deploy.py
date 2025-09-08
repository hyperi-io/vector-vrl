#!/usr/bin/env python3
"""
JFrog PyPI deployment for vectordotdev.
Extracted from template-python-package - only PyPI deployment to JFrog.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class JFrogPyPIDeployer:
    """Deploy vectordotdev package to JFrog Artifactory PyPI repository"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.vectordotdev_dir = project_root / "vectordotdev"
        self.build_dir = project_root / "build"
        
        # Load .env configuration
        self.load_env_config()
    
    def load_env_config(self):
        """Load configuration from build/.env"""
        env_file = self.build_dir / ".env"
        
        if env_file.exists():
            # Simple .env parser (no external dependencies)
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        
        # Configuration from environment
        self.jfrog_base_url = os.getenv("JFROG_BASE_URL", "https://hypersec.jfrog.io/artifactory")
        self.jfrog_repo = os.getenv("JFROG_PYPI_REPO", "hypersec-pypi-local")
        self.jfrog_api_url = os.getenv("JFROG_API_URL", f"{self.jfrog_base_url}/api/pypi/{self.jfrog_repo}/")
        
        self.enable_deployment = os.getenv("ENABLE_JFROG_DEPLOYMENT", "OFF").upper() == "ON"
        self.verbose_twine = os.getenv("VERBOSE_TWINE", "ON").upper() == "ON"
    
    def check_credentials(self) -> tuple:
        """Check if JFrog credentials are available and determine deployment mode"""
        
        # Check local credentials first
        local_username = (os.getenv("ARTIFACTORY_TENANT_USERNAME") or 
                         os.getenv("ARTIFACTORY_USERNAME") or
                         os.getenv("TWINE_USERNAME"))
        local_password = (os.getenv("ARTIFACTORY_TENANT_PASSWORD") or 
                         os.getenv("ARTIFACTORY_PASSWORD") or
                         os.getenv("TWINE_PASSWORD"))
        local_token = os.getenv("JFROG_ACCESS_TOKEN")
        
        has_local_creds = (local_username and local_password) or local_token
        
        if has_local_creds:
            print("✅ Local JFrog credentials configured")
            print("🔧 GitHub Actions deployment will be DISABLED for this project")
            print("   Use local deployment: ./build/build --deploy")
            
            # Set flag to disable GitHub Actions
            os.environ["DISABLE_GITHUB_JFROG_DEPLOYMENT"] = "ON"
            
            return True, "local"
        
        # No local credentials - expect GitHub Actions deployment
        print("ℹ️ No local JFrog credentials found")
        print("🌐 Deployment will use GitHub Actions with organization secrets")
        print("")
        print("To use local deployment instead:")
        print("1. Add credentials to build/.env:")
        print("   ARTIFACTORY_TENANT_USERNAME=<your_username>")
        print("   ARTIFACTORY_TENANT_PASSWORD=<your_password>")
        print("2. Run: ./build/build --deploy")
        
        return False, "github"
    
    def get_package_version(self) -> str:
        """Get current package version from pyproject.toml"""
        
        pyproject_file = self.vectordotdev_dir / "pyproject.toml"
        
        if not pyproject_file.exists():
            raise RuntimeError(f"pyproject.toml not found: {pyproject_file}")
        
        # Simple TOML parser for version (no external dependencies)
        with open(pyproject_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith('version = '):
                    # Extract version from: version = "0.2.0"
                    version = line.split('=')[1].strip().strip('"\'')
                    return version
        
        raise RuntimeError("Version not found in pyproject.toml")
    
    def build_wheel(self) -> bool:
        """Build vectordotdev wheel with bundled dependencies"""
        print("🏗️ Building vectordotdev PyPI wheel...")
        
        # Use the build wheel script we created
        wheel_builder = self.vectordotdev_dir / "build_wheel.py"
        
        if wheel_builder.exists():
            # Use our custom wheel builder
            result = subprocess.run([
                sys.executable, str(wheel_builder)
            ], cwd=self.vectordotdev_dir)
            
            return result.returncode == 0
        else:
            # Fallback to standard build
            print("⚠️ Custom wheel builder not found, using standard build")
            
            # Check if dist directory exists and has wheels
            dist_dir = self.vectordotdev_dir / "dist"
            wheels = list(dist_dir.glob("*.whl")) if dist_dir.exists() else []
            
            if wheels:
                print(f"✅ Using existing wheel: {wheels[0].name}")
                return True
            else:
                print("❌ No wheel found and custom builder not available")
                return False
    
    def deploy_to_jfrog(self, version: Optional[str] = None) -> bool:
        """Deploy wheel to JFrog Artifactory PyPI repository"""
        
        if not self.enable_deployment:
            print("⏭️ JFrog deployment disabled (ENABLE_JFROG_DEPLOYMENT=OFF)")
            return True
        
        has_creds, deploy_mode = self.check_credentials()
        
        if not has_creds and deploy_mode == "github":
            print("ℹ️ Local deployment skipped - will use GitHub Actions")
            return True
        elif not has_creds and deploy_mode == "local":
            print("❌ Local deployment enabled but credentials missing")
            return False
        
        # Get version
        deploy_version = version or self.get_package_version()
        print(f"📦 Deploying vectordotdev v{deploy_version} to JFrog...")
        
        # Check wheel exists
        dist_dir = self.vectordotdev_dir / "dist"
        wheels = list(dist_dir.glob("*.whl"))
        
        if not wheels:
            print("❌ No wheel files found in dist/")
            return False
        
        print(f"Repository: {self.jfrog_api_url}")
        print(f"Wheel files: {[w.name for w in wheels]}")
        
        # Deploy using twine
        env = os.environ.copy()
        env.update({
            "TWINE_USERNAME": os.getenv("ARTIFACTORY_TENANT_USERNAME") or os.getenv("TWINE_USERNAME"),
            "TWINE_PASSWORD": os.getenv("ARTIFACTORY_TENANT_PASSWORD") or os.getenv("TWINE_PASSWORD"),
            "TWINE_REPOSITORY_URL": self.jfrog_api_url
        })
        
        twine_cmd = ["twine", "upload"]
        if self.verbose_twine:
            twine_cmd.append("--verbose")
        twine_cmd.append("dist/*")
        
        try:
            result = subprocess.run(
                twine_cmd,
                cwd=self.vectordotdev_dir,
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            
            print("✅ SUCCESS: vectordotdev deployed to JFrog Artifactory!")
            print("")
            print("To install:")
            print(f"  pip install vectordotdev=={deploy_version} \\")
            print(f"    --index-url {self.jfrog_api_url}simple")
            print("")
            print(f"View in JFrog: {self.jfrog_base_url}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ JFrog deployment failed:")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return False
        except FileNotFoundError:
            print("❌ twine not found. Install with: pip install twine")
            return False
    
    def full_build_and_deploy(self, version: Optional[str] = None) -> bool:
        """Complete build and deployment process"""
        print("🚀 vectordotdev JFrog PyPI Deployment")
        print("=" * 45)
        
        # Step 1: Build wheel
        if not self.build_wheel():
            print("❌ Wheel build failed")
            return False
        
        # Step 2: Deploy to JFrog
        if not self.deploy_to_jfrog(version):
            print("❌ JFrog deployment failed")
            return False
        
        print("🎉 Complete build and deployment successful!")
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy vectordotdev to JFrog PyPI')
    parser.add_argument('--version', help='Override version to deploy')
    parser.add_argument('--build-only', action='store_true', help='Only build wheel, skip deployment')
    parser.add_argument('--deploy-only', action='store_true', help='Only deploy (skip build)')
    parser.add_argument('--enable', action='store_true', help='Enable deployment (override ENABLE_JFROG_DEPLOYMENT)')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    deployer = JFrogPyPIDeployer(project_root)
    
    # Enable deployment if requested
    if args.enable:
        deployer.enable_deployment = True
    
    if args.build_only:
        success = deployer.build_wheel()
    elif args.deploy_only:
        success = deployer.deploy_to_jfrog(args.version)
    else:
        success = deployer.full_build_and_deploy(args.version)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()