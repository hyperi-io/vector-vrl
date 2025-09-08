#!/usr/bin/env python3
"""
Main 3-Stage Build System for vectordotdev
Modular design with intelligent monitoring and auto-detection
"""

import os
import sys
import time
import shutil
from pathlib import Path

from common import BuildStage, StageResult, BuildResult, ErrorType, log_message
from vector_detection import VectorDetector
from dependency_sync import DependencyManager  
from monitoring import BuildMonitor
from core_build import CoreBuildSystem
from jfrog_deploy import JFrogPyPIDeployer

class RobustBuildSystem:
    """Main entry point for vectordotdev 3-stage build system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.core_builder = CoreBuildSystem(self.project_root)
        self.jfrog_deployer = JFrogPyPIDeployer(self.project_root)
        
        # Configure from environment
        self.max_fallbacks = 2
        self.verbose = os.environ.get('VECTORDOTDEV_VERBOSE', '').lower() == 'true'
    
    def robust_build(self) -> BuildResult:
        """Main build with version fallback and auto-detection"""
        log_message("🚀 3-Stage Build: Vector → Bindings → Python")
        
        versions = self.core_builder.detector.get_vector_versions()
        log_message(f"📋 Versions: {versions[:4]}")
        
        for attempt, version in enumerate(versions[:2]):
            log_message(f"\n🔄 Attempt {attempt + 1}: {version}")
            
            start_time = time.time()
            
            # Auto-detect existing Vector build
            existing_build = self.core_builder.detector.detect_vector_build_info()
            
            if existing_build and not self.core_builder.detector.should_rebuild_vector(existing_build, version):
                # Use existing build
                vector_result = StageResult(
                    BuildStage.VECTOR_CORE, True, 0.0,
                    error_message=f"Using existing Vector {existing_build['version']} build"
                )
                log_message(f"⚡ Skipping Vector build - using existing {existing_build['version']}")
            else:
                # Download and build Vector
                if not self.core_builder.download_vector(version):
                    continue
                
                vector_result = self.core_builder.build_vector_core(version)
            
            if not vector_result.success:
                if vector_result.error_type == ErrorType.UPSTREAM_COMPILE:
                    continue  # Try older version
                else:
                    break  # Code issue
            
            # Stage 1.5: Sync dependencies with Vector
            self.core_builder.dep_manager.sync_vector_dependencies(version)
            self.core_builder.dep_manager.auto_fix_vector_bindings()
            
            # Stage 2: Vector bindings 
            bindings_result = self.core_builder.build_vector_bindings(vector_result)
            
            # Stage 3: Python bindings  
            python_result = self.core_builder.build_python_layer(vector_result, bindings_result)
            
            total_time = time.time() - start_time
            stage_results = {
                BuildStage.VECTOR_CORE: vector_result,
                BuildStage.VECTOR_BINDINGS: bindings_result,
                BuildStage.PYTHON_BINDINGS: python_result
            }
            
            if python_result.success:
                log_message(f"🎉 Success with {version} in {total_time:.1f}s!")
                
                # Optional: Deploy to JFrog if enabled
                if os.environ.get('ENABLE_JFROG_DEPLOYMENT', 'OFF').upper() == 'ON':
                    log_message("\n📦 Deploying to JFrog PyPI...")
                    deploy_success = self.jfrog_deployer.full_build_and_deploy()
                    if deploy_success:
                        log_message("✅ JFrog deployment successful")
                    else:
                        log_message("⚠️ JFrog deployment failed (build still successful)")
                
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
    parser.add_argument('--test-flow', action='store_true', help='Test build flow without heavy compilation')
    parser.add_argument('--skip-vector', action='store_true', help='Skip Vector build (test stages 2-3 only)')
    parser.add_argument('--deploy', action='store_true', help='Deploy to JFrog PyPI after successful build')
    parser.add_argument('--deploy-only', action='store_true', help='Only deploy (skip build - requires existing wheel)')
    
    args = parser.parse_args()
    
    if args.verbose:
        os.environ['VECTORDOTDEV_VERBOSE'] = 'true'
    
    if args.deploy or args.deploy_only:
        os.environ['ENABLE_JFROG_DEPLOYMENT'] = 'ON'
    
    build_system = RobustBuildSystem()
    
    # Deploy-only mode
    if args.deploy_only:
        log_message("📦 JFrog PyPI deployment only...")
        success = build_system.jfrog_deployer.deploy_to_jfrog()
        sys.exit(0 if success else 1)
    
    # Test mode - just test the build flow logic
    if args.test_flow:
        log_message("🧪 Testing build flow without heavy compilation...")
        
        # Test auto-detection
        existing_build = build_system.core_builder.detector.detect_vector_build_info()
        if existing_build:
            log_message(f"✅ Auto-detection works: Found Vector {existing_build['version']}")
        else:
            log_message("ℹ️ No existing Vector build detected")
        
        # Test version checking
        versions = build_system.core_builder.detector.get_vector_versions()[:2]
        log_message(f"✅ Version discovery works: {versions}")
        
        # Test dependency sync
        if existing_build:
            sync_success = build_system.core_builder.dep_manager.sync_vector_dependencies(f"v{existing_build['version']}")
            log_message(f"✅ Dependency sync works: {sync_success}")
        
        log_message("🎉 Build flow test completed successfully!")
        return
    
    # Skip Vector mode - test stages 2-3 only
    if args.skip_vector:
        log_message("⚡ Skip Vector mode - testing stages 2-3 only...")
        
        # Check if Vector artifacts exist for stages 2-3
        existing_build = build_system.core_builder.detector.detect_vector_build_info()
        if not existing_build:
            log_message("❌ No Vector build found - cannot skip Vector stage")
            log_message("💡 Run without --skip-vector to build Vector first")
            sys.exit(1)
        
        # Create mock vector result for stages 2-3
        vector_result = StageResult(
            BuildStage.VECTOR_CORE, True, 0.0,
            error_message=f"Using existing Vector {existing_build['version']} build"
        )
        
        # Test Stage 2: Vector bindings
        build_system.core_builder.dep_manager.sync_vector_dependencies(f"v{existing_build['version']}")
        build_system.core_builder.dep_manager.auto_fix_vector_bindings()
        bindings_result = build_system.core_builder.build_vector_bindings(vector_result)
        
        # Test Stage 3: Python bindings
        python_result = build_system.core_builder.build_python_layer(vector_result, bindings_result)
        
        if bindings_result.success and python_result.success:
            log_message("🎉 Stages 2-3 completed successfully!")
            sys.exit(0)
        else:
            log_message("❌ Stages 2-3 failed")
            sys.exit(1)
    
    if args.clean:
        log_message("🧹 Cleaning...")
        for cleanup in ['target', '.tmp', 'vector']:
            path = build_system.project_root / cleanup
            if path.exists():
                shutil.rmtree(path)
    
    result = build_system.robust_build()
    
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()