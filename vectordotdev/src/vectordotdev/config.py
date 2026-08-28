"""
Configuration system for vectordotdev
Backed by scalo's config cascade: CLI -> ENV -> .env -> settings.{env}.yaml
-> settings.yaml -> defaults.yaml -> hardcoded default (DEFAULT_CONFIG below).

Previously this wrapped Dynaconf directly with a hand-rolled ENV fallback.
scalo.config.get_config() gives the same envvar_prefix behaviour
(VECTORDOTDEV_<KEY>) via a real Dynaconf instance, plus scalo's own
multi-location YAML file discovery (./, ./config/, /config/,
~/.config/{app_name}/) for free -- vectordotdev never shipped a
default.yaml under the old config_dir, so no file-based config is lost
in this swap, only gained.
"""

from scalo.config import get_config

# scalo Dynaconf instance with the VECTORDOTDEV_ envvar prefix preserved
# (matches the old Dynaconf(envvar_prefix="VECTORDOTDEV", ...) behaviour).
settings = get_config(env_prefix="VECTORDOTDEV")

# Default configuration values (final hardcoded fallback layer)
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


def get(key: str, default=None):
    """Get configuration value with full precedence chain (scalo cascade, then DEFAULT_CONFIG)"""
    fallback = DEFAULT_CONFIG.get(key, default)
    return settings.get(key, fallback)


def get_bool(key: str, default: bool = False) -> bool:
    """Get boolean configuration value"""
    value = get(key, default)
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on']
    return bool(value)


def get_int(key: str, default: int = 0) -> int:
    """Get integer configuration value"""
    value = get(key, default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_str(key: str, default: str = "") -> str:
    """Get string configuration value"""
    value = get(key, default)
    return str(value) if value is not None else default


# Convenience functions for common patterns
def get_vector_config():
    """Get Vector-specific configuration"""
    return {
        'validation': get_bool('vector.default_config_validation', True),
        'auto_start': get_bool('vector.auto_start', False),
        'max_concurrent': get_int('vector.max_concurrent_sends', 1000),
        'send_timeout': get_int('vector.send_timeout_seconds', 30),
        'vrl_cache_size': get_int('vector.vrl_cache_size', 1000),
        'vrl_timeout': get_int('vector.vrl_validation_timeout', 5),
    }

def get_logging_config():
    """Get logging configuration"""
    return {
        'level': get_str('logging.level', 'INFO'),
        'format': get_str('logging.format', 'structured'),
        'rust_logs': get_bool('logging.enable_rust_logs', False),
    }

def get_runtime_config():
    """Get runtime configuration"""
    return {
        'max_memory_mb': get_int('runtime.max_memory_mb', 1024),
        'thread_pool_size': get_int('runtime.thread_pool_size', 0),
        'multithread': get_bool('async.enable_multithread', True),
        'worker_threads': get_int('async.worker_threads', 0),
    }
