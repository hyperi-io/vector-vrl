"""
Configuration system for vectordotdev
Implements config policy: CLI → ENV → .env → config file → code default
"""

import os
from pathlib import Path

try:
    from dynaconf import Dynaconf
    HAS_DYNACONF = True
except ImportError:
    HAS_DYNACONF = False

# Default configuration values (fallback when dynaconf not available)
DEFAULT_CONFIG = {
    'vector.default_config_validation': True,
    'vector.auto_start': False,
    'vector.max_concurrent_sends': 1000,
    'vector.send_timeout_seconds': 30,
    'vector.vrl_cache_size': 1000,
    'vector.vrl_validation_timeout': 5,
    'logging.level': 'INFO',
    'logging.format': 'structured',
    'logging.enable_rust_logs': False,
    'paths.temp_dir': '.tmp',
    'paths.config_dir': 'config',
    'runtime.max_memory_mb': 1024,
    'runtime.thread_pool_size': 0,
    'async.enable_multithread': True,
    'async.worker_threads': 0,
}

class Config:
    """Configuration manager following corporate config policy"""
    
    def __init__(self, config_dir: str = None):
        """Initialize configuration with policy: CLI → ENV → .env → config → default"""
        
        if config_dir is None:
            config_dir = Path(__file__).parent / "config"
        
        if HAS_DYNACONF:
            self._settings = Dynaconf(
                envvar_prefix="VECTORDOTDEV",
                settings_files=[f'{config_dir}/default.yaml'],
                load_dotenv=True,
                environments=True
            )
        else:
            # Fallback configuration
            self._settings = None
    
    def get(self, key: str, default=None):
        """Get configuration value with full precedence chain"""
        
        if self._settings:
            return self._settings.get(key, default)
        else:
            # Manual ENV → default fallback
            env_key = f"VECTORDOTDEV_{key.replace('.', '_').upper()}"
            env_value = os.environ.get(env_key)
            
            if env_value is not None:
                # Try to convert to appropriate type
                if env_value.lower() in ['true', 'false']:
                    return env_value.lower() == 'true'
                try:
                    return int(env_value)
                except ValueError:
                    try:
                        return float(env_value)
                    except ValueError:
                        return env_value
            
            # Use default from DEFAULT_CONFIG or provided default
            return DEFAULT_CONFIG.get(key, default)
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(key, default)
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on']
        return bool(value)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_str(self, key: str, default: str = "") -> str:
        """Get string configuration value"""
        value = self.get(key, default)
        return str(value) if value is not None else default

# Global configuration instance
config = Config()

# Convenience functions for common patterns
def get_vector_config():
    """Get Vector-specific configuration"""
    return {
        'validation': config.get_bool('vector.default_config_validation', True),
        'auto_start': config.get_bool('vector.auto_start', False),
        'max_concurrent': config.get_int('vector.max_concurrent_sends', 1000),
        'send_timeout': config.get_int('vector.send_timeout_seconds', 30),
        'vrl_cache_size': config.get_int('vector.vrl_cache_size', 1000),
        'vrl_timeout': config.get_int('vector.vrl_validation_timeout', 5),
    }

def get_logging_config():
    """Get logging configuration"""
    return {
        'level': config.get_str('logging.level', 'INFO'),
        'format': config.get_str('logging.format', 'structured'),
        'rust_logs': config.get_bool('logging.enable_rust_logs', False),
    }

def get_runtime_config():
    """Get runtime configuration"""
    return {
        'max_memory_mb': config.get_int('runtime.max_memory_mb', 1024),
        'thread_pool_size': config.get_int('runtime.thread_pool_size', 0),
        'multithread': config.get_bool('async.enable_multithread', True),
        'worker_threads': config.get_int('async.worker_threads', 0),
    }