"""Core 3-stage build system for vector-vrl."""

import os
import shutil
import subprocess
import time
from pathlib import Path

from common import BuildStage, ErrorType, StageResult, log_message
from dependency_sync import DependencyManager
from monitoring import BuildMonitor
from vector_detection import VectorDetector


class CoreBuildSystem:
    """Main orchestrator for 3-stage build process."""

    def __init__(self, project_root: Path):
        """Set up build directories and the detector, dependency, and monitor components."""
        self.project_root = project_root
        self.vector_dir = project_root / "vector"
        self.vector_vrl_dir = project_root / "vector-vrl"
        self.tmp_dir = project_root / ".tmp"
        self.tmp_dir.mkdir(exist_ok=True, parents=True)

        # Initialize components
        self.detector = VectorDetector(project_root, self.vector_dir)
        self.dep_manager = DependencyManager(project_root, self.vector_dir)
        self.monitor = BuildMonitor(
            stall_timeout=600,  # 10 minutes
            verbose=os.environ.get("VECTOR_VRL_VERBOSE", "").lower() == "true",
        )

    def download_vector(self, version: str) -> bool:
        """Download Vector source - tries tar.gz first, fallback to git clone."""
        try:
            log_message("Completely removing existing /vector...")
            if self.vector_dir.exists():
                shutil.rmtree(self.vector_dir)

            # Try tar.gz download first (faster, no git metadata)
            if self._download_vector_tarball(version):
                return True

            log_message(f"Tar.gz failed, trying git clone for Vector {version}...")
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    version,
                    "https://github.com/vectordotdev/vector.git",
                    str(self.vector_dir),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log_message(f"Git clone failed: {result.stderr}")
                return False

            # Remove ALL git-related files and GitHub metadata
            self._clean_git_metadata()

            # Verify we have valid Vector source
            if not (self.vector_dir / "Cargo.toml").exists():
                log_message("Invalid Vector source - no Cargo.toml found")
                return False

            log_message(f"Vector {version} ready in /vector")
            return True

        except Exception as e:
            log_message(f"Vector download failed: {e}")
            return False

    def _download_vector_tarball(self, version: str) -> bool:
        """Download Vector source as tar.gz (cleaner, no git metadata)."""
        try:
            from scalo.http import HttpClient

            # GitHub releases API for tar.gz
            tarball_url = f"https://github.com/vectordotdev/vector/archive/refs/tags/{version}.tar.gz"
            log_message(f"Downloading Vector {version} tar.gz...")

            with HttpClient(timeout=60.0) as client:
                response = client.get(tarball_url)
            if response.status_code != 200:
                log_message(f"Tar.gz download failed: HTTP {response.status_code}")
                return False

            # Extract tar.gz
            import io
            import tarfile

            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                # Extract to temporary location first
                temp_extract = self.tmp_dir / f"vector-extract-{version}"
                # Use filter for Python 3.14 compatibility
                tar.extractall(temp_extract, filter="data")

                # Find the extracted directory (usually vector-X.Y.Z format)
                extracted_dirs = list(temp_extract.glob("vector-*"))
                if not extracted_dirs:
                    log_message("No vector directory found in tarball")
                    return False

                # Move to final location
                shutil.move(str(extracted_dirs[0]), str(self.vector_dir))
                shutil.rmtree(temp_extract)

            log_message(f"Vector {version} extracted from tar.gz (no git metadata)")
            return True

        except Exception as e:
            log_message(f"Tar.gz download failed: {e}")
            return False

    def _clean_git_metadata(self):
        """Remove all git and GitHub metadata from Vector directory."""
        log_message("Removing git and GitHub metadata...")
        git_items = [
            ".git",  # Git repository data
            ".github",  # GitHub workflows and settings
            ".gitignore",  # Git ignore rules
            ".gitattributes",  # Git attributes
            ".gitmodules",  # Git submodules
            ".git*",  # Any other git files
        ]

        for item_pattern in git_items:
            if "*" in item_pattern:
                # Handle glob patterns
                import glob

                for match in glob.glob(str(self.vector_dir / item_pattern)):
                    match_path = Path(match)
                    if match_path.exists():
                        if match_path.is_dir():
                            shutil.rmtree(match_path)
                        else:
                            match_path.unlink()
                        log_message(f"  Removed {match_path.name}")
            else:
                path = self.vector_dir / item_pattern
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    log_message(f"  Removed {item_pattern}")

    def build_vector_core(self, version: str) -> StageResult:
        """Stage 1: Build Vector core."""
        log_message(f"Building Vector core {version}")

        start_time = time.time()
        log_file = self.tmp_dir / f"vector_{version}.log"

        if not (self.vector_dir / "Cargo.toml").exists():
            return StageResult(
                BuildStage.VECTOR_CORE,
                False,
                0,
                ErrorType.VECTOR_CORE_FAILURE,
                "No Vector source",
            )

        env = os.environ.copy()
        env["RUSTFLAGS"] = "-C linker=gcc"
        # Use system libraries instead of building from source (fixes GCC 15+ compatibility)
        env["OPENSSL_NO_VENDOR"] = "1"
        env["OPENSSL_STATIC"] = "0"
        # Disable Kerberos to avoid krb5-src GCC 15+ compatibility issues
        env["CARGO_FEATURE_GSSAPI"] = "0"
        env["LIBZ_SYS_STATIC"] = "0"

        with open(log_file, "w") as f:
            process = subprocess.Popen(
                [
                    "cargo",
                    "build",
                    "--release",
                    "--lib",
                    "--features",
                    "sources-file,sinks-file,sinks-console,transforms-remap",
                    "--no-default-features",  # Disable default features that include Kerberos
                ],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=self.vector_dir,
            )

        success = self.monitor.monitor_intelligent_build(
            process, "Vector Core", log_file
        )
        build_time = time.time() - start_time

        if success:
            log_message(f"Vector core: {build_time:.1f}s")
            return StageResult(BuildStage.VECTOR_CORE, True, build_time)
        else:
            with open(log_file) as f:
                build_log = f.read()
            error_type, error_msg = self.monitor.analyze_stage_error(build_log)
            return StageResult(
                BuildStage.VECTOR_CORE, False, build_time, error_type, error_msg
            )

    def build_vector_bindings(self, vector_result: StageResult) -> StageResult:
        """Stage 2: Build Vector bindings using Vector core artifacts (READ ONLY)."""
        log_message("Building Vector bindings layer")

        if not vector_result.success:
            return StageResult(
                BuildStage.VECTOR_BINDINGS,
                False,
                0,
                ErrorType.DEPENDENCY_FAILURE,
                "Vector core failed",
            )

        # Check if vector-bindings directory exists
        bindings_dir = self.project_root / "vector-bindings"
        if not bindings_dir.exists() or not (bindings_dir / "Cargo.toml").exists():
            log_message("Vector-bindings not configured - skipping stage")
            return StageResult(
                BuildStage.VECTOR_BINDINGS, True, 0
            )  # Success (not required)

        start_time = time.time()
        log_file = self.tmp_dir / f"bindings_{int(time.time())}.log"

        # Setup environment to link against read-only Vector artifacts
        env = os.environ.copy()
        env.update(
            {
                "RUSTFLAGS": f"-C linker=gcc -L {self.vector_dir}/target/release -L {self.vector_dir}/target/release/deps",
                "VECTOR_LIB_DIR": str(self.vector_dir / "target" / "release"),
                "VECTOR_DEPS_DIR": str(self.vector_dir / "target" / "release" / "deps"),
                # Ensure Vector artifacts are available for linking
                "LD_LIBRARY_PATH": f"{self.vector_dir}/target/release:{os.environ.get('LD_LIBRARY_PATH', '')}",
            }
        )

        log_message(
            f"Linking against Vector artifacts in {self.vector_dir}/target/release"
        )

        with open(log_file, "w") as f:
            process = subprocess.Popen(
                ["cargo", "build", "--lib", "--jobs", str(os.cpu_count() or 4)],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=bindings_dir,
            )

        success = self.monitor.monitor_intelligent_build(
            process, "Vector Bindings", log_file
        )
        build_time = time.time() - start_time

        if success:
            log_message(f"Vector bindings: {build_time:.1f}s")
            return StageResult(BuildStage.VECTOR_BINDINGS, True, build_time)
        else:
            with open(log_file) as f:
                build_log = f.read()
            error_type, error_msg = self.monitor.analyze_stage_error(build_log)
            log_message(f"Vector bindings failed: {error_type.value}")
            return StageResult(
                BuildStage.VECTOR_BINDINGS, False, build_time, error_type, error_msg
            )

    def build_python_layer(
        self, vector_result: StageResult, bindings_result: StageResult | None = None
    ) -> StageResult:
        """Stage 3: Build Python bindings using Vector core and optional bindings artifacts."""
        log_message("Building Python layer")

        if not vector_result.success:
            return StageResult(
                BuildStage.PYTHON_BINDINGS,
                False,
                0,
                ErrorType.DEPENDENCY_FAILURE,
                "Vector core failed",
            )

        start_time = time.time()
        log_file = self.tmp_dir / f"python_{int(time.time())}.log"

        env = os.environ.copy()
        env.update(
            {
                "RUSTFLAGS": f"-C linker=gcc -L {self.vector_dir}/target/release",
                "PYO3_USE_ABI3_FORWARD_COMPATIBILITY": "1",
                "SKIP_VECTOR_UPDATE": "1",
            }
        )

        # Add bindings artifacts to environment if available
        if bindings_result and bindings_result.success:
            bindings_lib_dir = (
                self.project_root / "vector-bindings" / "target" / "debug"
            )
            if bindings_lib_dir.exists():
                env["RUSTFLAGS"] += f" -L {bindings_lib_dir}"

        with open(log_file, "w") as f:
            process = subprocess.Popen(
                ["uv", "run", "maturin", "develop"],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=self.vector_vrl_dir,
            )

        success = self.monitor.monitor_intelligent_build(
            process, "Python Layer", log_file
        )
        build_time = time.time() - start_time

        if success:
            # Quick verification
            try:
                result = subprocess.run(
                    [".venv/bin/python", "-c", 'import vector; print("OK")'],
                    capture_output=True,
                    cwd=self.vector_vrl_dir,
                    timeout=10,
                )

                if result.returncode == 0:
                    log_message(f"Python layer: {build_time:.1f}s")
                    return StageResult(BuildStage.PYTHON_BINDINGS, True, build_time)
            except Exception:
                pass

        with open(log_file) as f:
            build_log = f.read()
        error_type, error_msg = self.monitor.analyze_stage_error(build_log)
        return StageResult(
            BuildStage.PYTHON_BINDINGS, False, build_time, error_type, error_msg
        )
