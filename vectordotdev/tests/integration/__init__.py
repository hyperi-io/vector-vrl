"""
Integration tests - testing interaction between components.

Tests in this directory:
- bindings.py: Tests using vectordotdev Python bindings directly (in-process,
  no subprocess or vector binary needed)
- test_yaml_bindings.py, test_subprocess_first.py, test_regex2vrl_dual_mode.py,
  test_auto_stop_feature.py, test_vrl_harness.py, test_output_validation.py:
  pytest suites exercising the compiled `vector`/`vector_bindings` PyO3
  modules and/or a real Vector subprocess via the shared vector_runner
  fixture (tests/conftest.py)
"""